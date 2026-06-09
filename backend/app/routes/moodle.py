from fastapi import APIRouter, HTTPException, BackgroundTasks
from bson import ObjectId
from datetime import datetime
from typing import Dict, Any

import base64

from app.config.database import raw_moodle_payload_collection, feature_vectors_collection
from app.schema.schemas import list_raw_moodle_payload_serial
from app.services.preprocessing import compute_features
from app.services.moodle_ingest import normalize_payload, slim_payload
from app.services.user_provisioning import extract_identity, resolve_or_create_user
from app.repositories import material_repository
from app.services import quiz_gen

router = APIRouter()


@router.post("/materials/content")
async def upload_material_content(payload: Dict[str, Any]):
    """
    Open endpoint (same trust model as /raw-moodle-payloads): the extension —
    which holds the Moodle session — fetches a material's PDF and uploads its
    bytes here. We extract the text (PyPDF2) and store it so quizzes can be
    generated from it later.

    Body: { course_id, material_id, content_base64 }
    """
    course_id = str(payload.get("course_id") or "").strip()
    material_id = str(payload.get("material_id") or "").strip()
    b64 = payload.get("content_base64")
    if not course_id or not material_id or not b64:
        raise HTTPException(status_code=400, detail="course_id, material_id, content_base64 required")
    try:
        data = base64.b64decode(b64)
        text = quiz_gen.extract_pdf_text(data)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not read PDF: {exc}")

    material_repository.set_content(course_id, material_id, text)
    return {"status": "stored", "material_id": material_id, "chars": len(text)}


# GET all raw moodle payloads
@router.get("/raw-moodle-payloads")
async def get_raw_moodle_payloads():
    try:
        payloads = list_raw_moodle_payload_serial(raw_moodle_payload_collection.find())
        return payloads
    except Exception as e:
        import traceback
        error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


# POST: ingest raw payload, compute features, store both
@router.post("/raw-moodle-payloads")
async def post_raw_moodle_payload(payload: Dict[str, Any], background_tasks: BackgroundTasks):
    """
    Accepts the exact JSON from the Chrome extension.
    Stores raw payload, computes feature vector, stores it,
    and optionally triggers ML pipeline in background.
    """
    try:
        # 1. Map this payload to an AcademIQ account (creating one if needed)
        #    BEFORE storing anything, so every record is linked to a real user.
        #    Matching is by Moodle User ID, then Student ID — never by name.
        identity = extract_identity(payload)
        academiq_user, was_created = resolve_or_create_user(identity)
        academiq_user_id = str(academiq_user["_id"])
        # Prefer the account's canonical student id for downstream keying.
        student_id = academiq_user.get("student_id") or identity.get("student_id")

        # 2. Compute the feature vector (reads materials from the payload).
        features = compute_features(payload)

        # 3. Normalize the payload into the deduplicated collections:
        #    materials are stored ONCE in course_materials (upsert by
        #    course_id+material_id); metrics and events go to their own
        #    collections. Materials are never duplicated across structures.
        norm = normalize_payload(payload, academiq_user_id)

        now = datetime.utcnow()

        # 4. Upsert ONE slim audit record per student — a re-sync UPDATES the
        #    same document instead of inserting a new one each time.
        slim = slim_payload(payload)
        raw_moodle_payload_collection.update_one(
            {"academiq_user_id": academiq_user_id},
            {
                "$set": {**slim, "academiq_user_id": academiq_user_id, "updated_at": now},
                "$setOnInsert": {"created_at": now},
                "$inc": {"sync_count": 1},
            },
            upsert=True,
        )
        raw_doc = raw_moodle_payload_collection.find_one(
            {"academiq_user_id": academiq_user_id}, {"_id": 1}
        )
        raw_id = str(raw_doc["_id"])

        # 5. Upsert ONE feature vector per student (the current snapshot).
        feature_vectors_collection.update_one(
            {"academiq_user_id": academiq_user_id},
            {
                "$set": {
                    "raw_payload_id": raw_id,
                    "student_id": student_id or features.get("student_id"),
                    "features": features,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

        return {
            "inserted_id": raw_id,
            "status": "features_computed",
            "academiq_user_id": academiq_user_id,
            "account_created": was_created,
            "login_email": academiq_user.get("email"),
            "student_id": student_id or features.get("student_id"),
            "normalized": norm,
            "message": (
                "New AcademIQ account created. Check the backend console for the "
                "temporary password (or your email if SMTP is configured)."
                if was_created else
                "Data synced to your existing AcademIQ account."
            ),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


# Alias for clients that call /api/raw-moodle-payloads (same handler, no logic change).
router.add_api_route(
    "/api/raw-moodle-payloads",
    post_raw_moodle_payload,
    methods=["POST"],
    name="post_raw_moodle_payload_api_alias",
)


# PUT: update raw payload by id (accepts any JSON, no validation)
@router.put("/raw-moodle-payloads/{id}")
async def put_raw_moodle_payload(id: str, payload: Dict[str, Any]):
    try:
        oid = ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id format")

    try:
        result = raw_moodle_payload_collection.update_one(
            {"_id": oid},
            {"$set": payload}
        )
        return {"matched_count": result.matched_count, "modified_count": result.modified_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {str(e)}")


# DELETE raw moodle payload
@router.delete("/raw-moodle-payloads/{id}")
async def delete_raw_moodle_payload(id: str):
    try:
        oid = ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id format")

    try:
        result = raw_moodle_payload_collection.delete_one({"_id": oid})
        # Also consider deleting associated feature vector
        return {"deleted_count": result.deleted_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {str(e)}")
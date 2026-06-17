from fastapi import APIRouter, HTTPException, BackgroundTasks
from bson import ObjectId
from datetime import datetime
from typing import Dict, Any

from app.config.database import raw_moodle_payload_collection, feature_vectors_collection
from app.schema.schemas import list_raw_moodle_payload_serial
from app.services.material_quiz_upload import (
    process_material_upload_for_quiz,
    preflight_materials,
    reassess_course_material_readiness,
    save_detected_materials,
)
from app.services.preprocessing import compute_features
from app.services.moodle_ingest import normalize_payload, slim_payload
from app.services.user_provisioning import (
    extract_identity,
    issue_demo_sync_temporary_password,
    resolve_or_create_user,
)
from app.services.synced_features import build_synced_course_features

router = APIRouter()

# Sign-in URL returned to the Chrome extension sync alert (deployed frontend).
EXTENSION_SIGNIN_URL = "https://academiq-frontend.vercel.app/signin"


@router.post("/materials/upload-for-quiz")
async def upload_material_for_quiz(payload: Dict[str, Any]):
    """
    Extension upload: Moodle file bytes or pre-extracted text → course_materials.

    Body (JSON):
      course_id, material_id, title, course_name, material_type, file_type,
      source_url, content_base64 OR content_text,
      user_email / academiq_user_id (optional, for audit only)
    """
    try:
        return process_material_upload_for_quiz(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}")


@router.post("/materials/save-detected")
async def save_detected_material_metadata(payload: Dict[str, Any]):
    """
    Save metadata for every material detected on a Moodle course page.

    Does not require file bytes. Call before preflight/upload so url/html/link
    lectures appear in MongoDB even when no downloadable file exists yet.
    """
    try:
        return save_detected_materials(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Save detected failed: {exc}")


@router.post("/materials/reassess-readiness")
async def reassess_material_readiness(payload: Dict[str, Any]):
    """
    Re-run slide/PDF probe on stored content for educational materials in a course.
    Does not download Moodle files or bypass upload caching for empty rows.
    """
    course_id = str(payload.get("course_id") or "").strip()
    if not course_id:
        raise HTTPException(status_code=400, detail="course_id required")
    try:
        return reassess_course_material_readiness(course_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Reassess readiness failed: {exc}")


@router.post("/materials/preflight")
async def preflight_material_upload(payload: Dict[str, Any]):
    """
    Check which materials need uploading without downloading any file bytes.

    The Chrome extension calls this BEFORE fetching files from Moodle.
    Only materials where ``should_upload: true`` in the response need to be
    downloaded and sent to /materials/upload-for-quiz.

    Body:
      {
        course_id,
        user_email?,            # optional, for future per-user filtering
        force_reupload?: bool,  # re-check even extraction_failed materials
        materials: [
          { material_id, title, source_url?, file_type }
        ]
      }

    Returns per material:
      should_upload, status, reason, content_text_length
    """
    try:
        return preflight_materials(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Preflight failed: {exc}")


@router.post("/materials/content")
async def upload_material_content(payload: Dict[str, Any]):
    """
    Legacy alias — forwards to /materials/upload-for-quiz.
    """
    try:
        return process_material_upload_for_quiz(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}")


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
        provision = resolve_or_create_user(identity, payload=payload)
        academiq_user = provision["user"]
        user_created = provision["created"]
        user_updated = provision["updated"]
        academiq_user_id = str(academiq_user["_id"])

        # Demo only: always return a fresh AcademIQ temporary password in the sync
        # response (new account or re-sync). Never use the university Moodle password.
        # Production should email a password-reset link instead.
        password_reset_for_demo = False
        if user_created:
            temporary_password = provision["temporary_password"]
        else:
            temporary_password = issue_demo_sync_temporary_password(academiq_user_id)
            password_reset_for_demo = True
            user_updated = True

        # Prefer the account's canonical student id for downstream keying.
        student_id = academiq_user.get("student_id") or identity.get("student_id")

        # 2. Compute the feature vector (reads materials from the payload).
        features = compute_features(payload)

        # 3. Normalize the payload into the deduplicated collections:
        #    materials are stored ONCE in course_materials (upsert by
        #    course_id+material_id); metrics and events go to their own
        #    collections. Materials are never duplicated across structures.
        norm = normalize_payload(payload, academiq_user_id)
        metrics_saved = bool(
            norm.get("metrics_courses", 0) > 0
            or payload.get("behavior")
            or payload.get("metricsByCourse")
            or payload.get("courses")
        )

        now = datetime.utcnow()

        # 4. Upsert ONE slim audit record per student — a re-sync UPDATES the
        #    same document instead of inserting a new one each time.
        slim = slim_payload(payload)
        grades = payload.get("grades") or []
        raw_result = raw_moodle_payload_collection.update_one(
            {"academiq_user_id": academiq_user_id},
            {
                "$set": {
                    **slim,
                    "academiq_user_id": academiq_user_id,
                    "grades": grades,
                    "updated_at": now,
                },
                "$unset": {"grades_source": ""},
                "$setOnInsert": {"created_at": now},
                "$inc": {"sync_count": 1},
            },
            upsert=True,
        )
        raw_payload_saved = bool(raw_result.acknowledged)
        raw_doc = raw_moodle_payload_collection.find_one(
            {"academiq_user_id": academiq_user_id}, {"_id": 1}
        )
        raw_id = str(raw_doc["_id"])

        # 5. Upsert ONE feature vector per student (the current snapshot).
        course_features = build_synced_course_features(payload, features)
        fv_result = feature_vectors_collection.update_one(
            {"academiq_user_id": academiq_user_id},
            {
                "$set": {
                    "raw_payload_id": raw_id,
                    "student_id": student_id or features.get("student_id"),
                    "features": features,
                    "course_features": course_features,
                    "feature_source": "synced",
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        feature_vector_updated = bool(
            fv_result.modified_count > 0 or fv_result.upserted_id is not None
        )

        return {
            "inserted_id": raw_id,
            "status": "features_computed",
            "academiq_user_id": academiq_user_id,
            "account_created": user_created,
            "password_reset_for_demo": password_reset_for_demo,
            "login_email": academiq_user.get("email"),
            "temporary_password": temporary_password,
            "signin_url": EXTENSION_SIGNIN_URL,
            "student_id": student_id or features.get("student_id"),
            "normalized": norm,
            "raw_payload_saved": raw_payload_saved,
            "user_created": user_created,
            "user_updated": user_updated,
            "metrics_saved": metrics_saved,
            "feature_vector_updated": feature_vector_updated,
            "message": (
                "New AcademIQ account created. Save the temporary password below to sign in."
                if user_created
                else "AcademIQ account already exists. A new temporary password was generated for demo sign-in."
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
"""
MongoDB connection for AcademIQ.

Uses lazy initialization so Vercel serverless builds and cold starts do not
call sys.exit() when the database is temporarily unreachable or env vars are
absent at build time.
"""

from __future__ import annotations

import certifi
from pymongo import ASCENDING, MongoClient
from pymongo.server_api import ServerApi

from app.config.settings import MONGODB_DB_NAME, MONGODB_URI

client: MongoClient | None = None
db = None

collection_name = None
assignments_collection = None
sessions_collection = None
quizzes_collection = None
courses_collection = None
raw_moodle_payload_collection = None
feature_vectors_collection = None
ml_results_collection = None
auth_sessions_collection = None
users_collection = None
user = None
course_materials_collection = None
student_metrics_collection = None
student_events_collection = None
uploaded_grade_records_collection = None
uploaded_transcript_records_collection = None

_initialized = False


def connect_database() -> bool:
    """Connect to MongoDB and bind collection handles. Safe to call repeatedly."""
    global client, db, _initialized
    global collection_name, assignments_collection, sessions_collection
    global quizzes_collection, courses_collection, raw_moodle_payload_collection
    global feature_vectors_collection, ml_results_collection, auth_sessions_collection
    global users_collection, user, course_materials_collection
    global student_metrics_collection, student_events_collection
    global uploaded_grade_records_collection
    global uploaded_transcript_records_collection

    if _initialized and client is not None:
        return True

    if not MONGODB_URI:
        print("[WARN] MONGODB_URI is not set — database calls will fail until configured.")
        return False

    try:
        client = MongoClient(
            MONGODB_URI,
            server_api=ServerApi("1"),
            tlsCAFile=certifi.where(),
        )
        client.admin.command("ping")
        db = client[MONGODB_DB_NAME]

        collection_name = db["AcademIQ"]
        assignments_collection = db["assignments_collection"]
        sessions_collection = db["sessions_collection"]
        quizzes_collection = db["quizzes_collection"]
        courses_collection = db["courses_collection"]
        raw_moodle_payload_collection = db["raw_moodle_payload_collection"]
        feature_vectors_collection = db["feature_vectors"]
        ml_results_collection = db["ml_results"]
        auth_sessions_collection = db["sessions"]
        users_collection = db["users"]
        user = users_collection
        course_materials_collection = db["course_materials"]
        student_metrics_collection = db["student_metrics"]
        student_events_collection = db["student_events"]
        uploaded_grade_records_collection = db["uploaded_grade_records"]
        uploaded_transcript_records_collection = db["uploaded_transcript_records"]

        _initialized = True
        print("[OK] Connected to MongoDB Atlas!")
        return True
    except Exception as exc:
        print(f"[ERROR] MongoDB connection failed: {exc}")
        client = None
        db = None
        _initialized = False
        return False


def ensure_database() -> None:
    """Raise RuntimeError if the database is not connected."""
    if not connect_database() or users_collection is None:
        raise RuntimeError(
            "Database unavailable. Set MONGODB_URI and ensure MongoDB Atlas is reachable."
        )


# Best-effort connect at import for local uvicorn; never exits the process.
connect_database()


def _ensure_unique_partial(field: str, name: str) -> None:
    spec = dict(
        unique=True,
        partialFilterExpression={field: {"$type": "string"}},
        name=name,
    )
    try:
        users_collection.create_index([(field, ASCENDING)], **spec)
    except Exception:
        try:
            users_collection.drop_index(name)
        except Exception:
            pass
        users_collection.create_index([(field, ASCENDING)], **spec)


def ensure_indexes() -> None:
    """Create auth/identity indexes. Idempotent — safe on every cold start."""
    if not connect_database():
        raise RuntimeError("Cannot ensure indexes — database not connected")

    users_collection.create_index([("email", ASCENDING)], unique=True, name="uniq_email")
    _ensure_unique_partial("moodle_user_id", "uniq_moodle_user_id")
    _ensure_unique_partial("student_id", "uniq_student_id")
    auth_sessions_collection.create_index(
        [("token_hash", ASCENDING)], unique=True, name="uniq_token_hash"
    )
    auth_sessions_collection.create_index([("expires_at", ASCENDING)], name="session_expiry")

    course_materials_collection.create_index(
        [("course_id", ASCENDING), ("material_id", ASCENDING)],
        unique=True,
        name="uniq_course_material",
    )
    student_metrics_collection.create_index(
        [("academiq_user_id", ASCENDING), ("course_id", ASCENDING)],
        unique=True,
        name="uniq_user_course_metrics",
    )
    student_events_collection.create_index(
        [("academiq_user_id", ASCENDING), ("event_id", ASCENDING)],
        unique=True,
        name="uniq_user_event",
    )
    uploaded_grade_records_collection.create_index(
        [("academiq_user_id", ASCENDING), ("course_id", ASCENDING)],
        unique=True,
        name="uniq_user_course_uploaded_grade",
    )
    uploaded_transcript_records_collection.create_index(
        [("academiq_user_id", ASCENDING)],
        unique=True,
        name="uniq_user_official_transcript",
    )

    for coll, name in (
        (raw_moodle_payload_collection, "uniq_raw_user"),
        (feature_vectors_collection, "uniq_feature_user"),
    ):
        try:
            coll.create_index(
                [("academiq_user_id", ASCENDING)],
                unique=True,
                partialFilterExpression={"academiq_user_id": {"$type": "string"}},
                name=name,
            )
        except Exception as exc:
            print(f"[WARN] could not create {name} (resolve duplicates first): {exc}")

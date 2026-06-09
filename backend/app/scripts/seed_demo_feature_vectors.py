"""
Seed demo behavioral feature vectors for Performance Model v4 (ML service).

One MongoDB document per student (unique on academiq_user_id). Course-specific
vectors live under course_features["101"] etc. — string keys, same 9 ML fields.

Idempotent: skips course entries already marked feature_source=synced; refreshes seeded demo rows.
Heals academiq_user_id drift when demo accounts were recreated in production.

Run from backend/:

    python -m app.scripts.seed_demo_feature_vectors

Uses MONGODB_URI from backend/.env (same Atlas DB as production when URI matches).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from app.config.database import connect_database, ensure_indexes, feature_vectors_collection
from app.config.settings import DATABASE_NAME
from app.repositories import user_repository

logger = logging.getLogger(__name__)

FEATURE_VECTORS_COLLECTION = "feature_vectors"

# Performance Model v4 — must match ml-service/app/performance_model.py REQUIRED_FEATURES
PERFORMANCE_V4_FEATURES = (
    "all_clicks",
    "active_days",
    "access_frequency",
    "material_clicks",
    "quiz_attempts",
    "assignment_submissions",
    "total_time_spent",
    "procrastination_index",
    "late_submission_count",
)

# student_id -> course_id (string) -> behavioural features (demo-only, not Moodle sync)
DEMO_COURSE_FEATURE_VECTORS: Dict[str, Dict[str, Dict[str, float | int]]] = {
    "student1": {
        "101": {
            "all_clicks": 185,
            "active_days": 28,
            "access_frequency": 4.5,
            "material_clicks": 72,
            "quiz_attempts": 12,
            "assignment_submissions": 8,
            "total_time_spent": 54_000,
            "procrastination_index": 1.2,
            "late_submission_count": 0,
        },
        "102": {
            "all_clicks": 120,
            "active_days": 18,
            "access_frequency": 2.8,
            "material_clicks": 48,
            "quiz_attempts": 7,
            "assignment_submissions": 5,
            "total_time_spent": 36_000,
            "procrastination_index": 3.5,
            "late_submission_count": 1,
        },
    },
    "student2": {
        "101": {
            "all_clicks": 42,
            "active_days": 7,
            "access_frequency": 0.9,
            "material_clicks": 14,
            "quiz_attempts": 2,
            "assignment_submissions": 1,
            "total_time_spent": 7_200,
            "procrastination_index": 7.8,
            "late_submission_count": 3,
        },
        "102": {
            "all_clicks": 95,
            "active_days": 15,
            "access_frequency": 2.2,
            "material_clicks": 38,
            "quiz_attempts": 6,
            "assignment_submissions": 4,
            "total_time_spent": 28_800,
            "procrastination_index": 4.0,
            "late_submission_count": 1,
        },
    },
}


def _course_feature_payload(
    course_id: str, features: Dict[str, Any]
) -> Dict[str, Any]:
    payload = {key: features[key] for key in PERFORMANCE_V4_FEATURES}
    payload["course_id"] = str(course_id)
    payload["feature_source"] = "seeded"
    payload["seeded_demo"] = True
    return payload


def _should_seed_course(existing: Dict[str, Any] | None) -> bool:
    if not existing:
        return True
    if existing.get("feature_source") == "synced":
        return False
    return True


def _merge_course_features(
    existing: Dict[str, Any], course_id: str, payload: Dict[str, Any]
) -> Dict[str, Any]:
    """Ensure all course_features keys are strings."""
    merged: Dict[str, Any] = {}
    for key, value in (existing or {}).items():
        merged[str(key)] = value
    merged[str(course_id)] = payload
    return merged


def seed_demo_feature_vectors() -> None:
    if not connect_database():
        raise RuntimeError("Cannot seed feature vectors — database connection failed")

    ensure_indexes()
    now = datetime.now(timezone.utc)
    seeded_count = 0
    skipped_count = 0

    logger.info(
        "Seeding demo feature vectors into collection=%s database=%s",
        FEATURE_VECTORS_COLLECTION,
        DATABASE_NAME,
    )
    print(
        f"Seeding demo feature vectors into collection={FEATURE_VECTORS_COLLECTION} "
        f"database={DATABASE_NAME}"
    )

    for student_id, courses in DEMO_COURSE_FEATURE_VECTORS.items():
        user = user_repository.find_by_student_id(student_id)
        if not user:
            msg = f"[skip] Student not found: {student_id}"
            print(msg)
            logger.warning(msg)
            continue

        user_id = str(user["_id"])
        doc = feature_vectors_collection.find_one(
            {"$or": [{"academiq_user_id": user_id}, {"student_id": student_id}]}
        ) or {}
        course_features = doc.get("course_features") or {}

        for course_id, raw_features in courses.items():
            course_key = str(course_id)
            existing = course_features.get(course_key)
            if not _should_seed_course(existing):
                msg = f"[skip] {student_id} course {course_key}: synced features present"
                print(msg)
                logger.info(msg)
                skipped_count += 1
                continue

            payload = _course_feature_payload(course_key, raw_features)
            course_features = _merge_course_features(course_features, course_key, payload)

            feature_vectors_collection.update_one(
                {"_id": doc["_id"]} if doc.get("_id") else {"academiq_user_id": user_id},
                {
                    "$set": {
                        "academiq_user_id": user_id,
                        "student_id": student_id,
                        "course_features": course_features,
                        "feature_source": "seeded",
                        "seeded_demo": True,
                        "updated_at": now,
                    },
                    "$setOnInsert": {
                        "created_at": now,
                    },
                },
                upsert=True,
            )
            msg = f"Seeded feature vector for {student_id} course {course_key} (academiq_user_id={user_id})"
            print(msg)
            logger.info(msg)
            seeded_count += 1
            doc = feature_vectors_collection.find_one({"academiq_user_id": user_id}) or doc

    summary = (
        f"Demo feature vectors: {seeded_count} course row(s) seeded, "
        f"{skipped_count} skipped (synced)."
    )
    print(summary)
    logger.info(summary)


if __name__ == "__main__":
    seed_demo_feature_vectors()

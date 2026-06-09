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
#
# Coverage must match every visible demo course in seed_students.DEMO_COURSE_METRICS:
#   student1: 101 Programming, 102 Database
#   student2: 101 Programming, 102 Database, 103 Web Dev
#
# Tuned for varied, realistic ML outputs (~38–58 predicted grade); student2/101 is
# intentionally the weakest visible course (At Risk band, not single-digit scores).
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
            "all_clicks": 130,
            "active_days": 20,
            "access_frequency": 3.1,
            "material_clicks": 52,
            "quiz_attempts": 8,
            "assignment_submissions": 5,
            "total_time_spent": 38_400,
            "procrastination_index": 2.8,
            "late_submission_count": 1,
        },
    },
    "student2": {
        "101": {
            "all_clicks": 88,
            "active_days": 13,
            "access_frequency": 1.7,
            "material_clicks": 30,
            "quiz_attempts": 4,
            "assignment_submissions": 3,
            "total_time_spent": 15_000,
            "procrastination_index": 4.8,
            "late_submission_count": 2,
        },
        "102": {
            "all_clicks": 98,
            "active_days": 16,
            "access_frequency": 2.4,
            "material_clicks": 40,
            "quiz_attempts": 6,
            "assignment_submissions": 4,
            "total_time_spent": 30_600,
            "procrastination_index": 3.8,
            "late_submission_count": 1,
        },
        "103": {
            "all_clicks": 148,
            "active_days": 24,
            "access_frequency": 3.8,
            "material_clicks": 58,
            "quiz_attempts": 10,
            "assignment_submissions": 7,
            "total_time_spent": 46_800,
            "procrastination_index": 1.8,
            "late_submission_count": 0,
        },
    },
}

# Visible demo courses without a seeded vector (intentionally empty — document here if any).
DEMO_COURSES_WITHOUT_FEATURE_VECTORS: Dict[str, list[str]] = {}


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


def _validate_demo_course_coverage() -> None:
    """Ensure every visible demo course has a seeded feature vector definition."""
    from app.scripts.seed_students import DEMO_COURSE_METRICS

    missing: list[str] = []
    for student_id, courses in DEMO_COURSE_METRICS.items():
        for course in courses:
            course_id = str(course["course_id"])
            course_name = course.get("course_name", course_id)
            if course_id in (DEMO_COURSES_WITHOUT_FEATURE_VECTORS.get(student_id) or []):
                continue
            if course_id not in (DEMO_COURSE_FEATURE_VECTORS.get(student_id) or {}):
                missing.append(f"{student_id} course {course_id} ({course_name})")
    if missing:
        raise RuntimeError(
            "Missing demo feature vector definitions for visible courses: "
            + ", ".join(missing)
        )


def seed_demo_feature_vectors() -> None:
    if not connect_database():
        raise RuntimeError("Cannot seed feature vectors — database connection failed")

    _validate_demo_course_coverage()
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

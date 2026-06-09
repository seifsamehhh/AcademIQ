"""
Seed demo behavioral feature vectors for Performance Model v4 (ML service).

One MongoDB document per student (unique on academiq_user_id). Course-specific
vectors live under course_features.{course_id} — same 9 fields the ML service expects.

Idempotent: skips course entries already marked feature_source=synced; refreshes seeded demo rows.

Run from backend/:

    python -m app.scripts.seed_demo_feature_vectors

Uses MONGODB_URI from backend/.env (same Atlas DB as production when URI matches).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from app.config.database import ensure_indexes, feature_vectors_collection
from app.repositories import user_repository

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

# student_id -> course_id -> behavioural features (demo-only, not Moodle sync)
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


def seed_demo_feature_vectors() -> None:
    ensure_indexes()
    now = datetime.now(timezone.utc)
    seeded_count = 0
    skipped_count = 0

    for student_id, courses in DEMO_COURSE_FEATURE_VECTORS.items():
        user = user_repository.find_by_student_id(student_id)
        if not user:
            print(f"[skip] Student not found: {student_id}")
            continue

        user_id = str(user["_id"])
        doc = feature_vectors_collection.find_one({"academiq_user_id": user_id}) or {}
        course_features = doc.get("course_features") or {}

        for course_id, raw_features in courses.items():
            existing = course_features.get(str(course_id))
            if not _should_seed_course(existing):
                print(
                    f"[skip] {student_id} course {course_id}: synced features present"
                )
                skipped_count += 1
                continue

            feature_vectors_collection.update_one(
                {"academiq_user_id": user_id},
                {
                    "$set": {
                        f"course_features.{course_id}": _course_feature_payload(
                            course_id, raw_features
                        ),
                        "student_id": student_id,
                        "feature_source": "seeded",
                        "seeded_demo": True,
                        "updated_at": now,
                    },
                    "$setOnInsert": {
                        "academiq_user_id": user_id,
                        "created_at": now,
                    },
                },
                upsert=True,
            )
            print(f"[ok] Seeded feature vector: {student_id} course {course_id}")
            seeded_count += 1

    print(
        f"Demo feature vectors: {seeded_count} course row(s) seeded, "
        f"{skipped_count} skipped (synced)."
    )


if __name__ == "__main__":
    seed_demo_feature_vectors()

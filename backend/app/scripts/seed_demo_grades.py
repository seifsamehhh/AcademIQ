"""
Seed demo course grades for Performance Analysis and dashboard consistency.

Grades are stored on the student's raw_moodle_payload document (grades array).
Idempotent: always refreshes demo grade rows for student1/student2 unless a
real Moodle sync payload is present (metricsByCourse without grades_source=seeded).

Run from backend/:

    python -m app.scripts.seed_demo_grades

Also invoked by seed_students() / BOOTSTRAP_STUDENTS.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.config.database import ensure_indexes, raw_moodle_payload_collection
from app.repositories import user_repository
from app.scripts.seed_students import DEMO_COURSE_METRICS

# course_id -> target course average (percentage) per student
DEMO_COURSE_GRADES: dict[str, dict[str, int]] = {
    "student1": {
        "101": 85,
        "102": 78,
        "103": 82,
        "104": 88,
        "105": 80,
    },
    "student2": {
        "101": 74,
        "102": 69,
        "103": 84,
        "104": 76,
        "105": 72,
    },
}


def _grade_entries(course_id: str, course_name: str, target_pct: int) -> list[dict]:
    """Quiz + assignment rows that average near the dashboard course grade."""
    quiz_pct = target_pct
    assign_pct = max(0, min(100, target_pct - 4))
    return [
        {
            "course_id": str(course_id),
            "item_type": "quiz",
            "item_name": f"{course_name} Quiz",
            "percentage": quiz_pct,
            "grade": quiz_pct,
            "max_grade": 100,
        },
        {
            "course_id": str(course_id),
            "item_type": "assignment",
            "item_name": f"{course_name} Assignment",
            "percentage": assign_pct,
            "grade": assign_pct,
            "max_grade": 100,
        },
    ]


def _has_live_sync_payload(doc: dict | None) -> bool:
    if not doc:
        return False
    if doc.get("grades_source") == "seeded":
        return False
    return bool(doc.get("metricsByCourse") or doc.get("behavior"))


def seed_demo_grades() -> None:
    ensure_indexes()
    now = datetime.now(timezone.utc)

    for student_id, courses in DEMO_COURSE_METRICS.items():
        user = user_repository.find_by_student_id(student_id)
        if not user:
            print(f"[skip] Student not found for grades: {student_id}")
            continue

        user_id = str(user["_id"])
        existing = raw_moodle_payload_collection.find_one({"academiq_user_id": user_id})
        if _has_live_sync_payload(existing):
            print(f"[skip] {student_id} has live Moodle payload — grades not overwritten")
            continue

        grade_map = DEMO_COURSE_GRADES.get(student_id) or {}
        grades: list[dict] = []
        for course in courses:
            course_id = str(course["course_id"])
            course_name = course["course_name"]
            target = grade_map.get(course_id)
            if target is None:
                continue
            grades.extend(_grade_entries(course_id, course_name, int(target)))

        raw_moodle_payload_collection.update_one(
            {"academiq_user_id": user_id},
            {
                "$set": {
                    "academiq_user_id": user_id,
                    "student_id": student_id,
                    "grades": grades,
                    "grades_source": "seeded",
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        print(
            f"Seeded demo grades for {student_id}: "
            f"{len(grades)} grade row(s) across {len(grade_map)} course(s)."
        )


if __name__ == "__main__":
    seed_demo_grades()

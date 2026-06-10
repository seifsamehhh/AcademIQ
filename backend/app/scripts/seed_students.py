"""
Seed demo student accounts into MongoDB with bcrypt-hashed passwords.

Idempotent: skips any student_id that already exists.

Run from the backend/ directory:

    python -m app.scripts.seed_students
"""

from datetime import datetime, timezone

from app.config.database import ensure_indexes
from app.models.user import ROLE_STUDENT
from app.repositories import metrics_repository, user_repository
from app.services.auth_service import hash_password

STUDENTS = [
    {
        "student_id": "student1",
        "name": "Seif Sameh",
        "password": "password123",
        "role": ROLE_STUDENT,
    },
    {
        "student_id": "student2",
        "name": "Aly Ehab",
        "password": "pass456",
        "role": ROLE_STUDENT,
    },
]

# Demo course metrics keyed by student_id (stored in student_metrics collection).
DEMO_COURSE_METRICS = {
    "student1": [
        {"course_id": "101", "course_name": "Programming"},
        {"course_id": "102", "course_name": "Database"},
        {"course_id": "103", "course_name": "Computer Vision"},
        {"course_id": "104", "course_name": "Artificial Intelligence"},
        {"course_id": "105", "course_name": "Software Engineering"},
    ],
    "student2": [
        {"course_id": "101", "course_name": "Programming"},
        {"course_id": "102", "course_name": "Database"},
        {"course_id": "103", "course_name": "Web Development"},
        {"course_id": "104", "course_name": "Data Structures"},
        {"course_id": "105", "course_name": "Machine Learning"},
    ],
}


def _default_course_metrics(course_name: str) -> dict:
    return {
        "course_name": course_name,
        "activity_source": "seeded",
        "quiz_attempts": 3,
        "assignment_submissions": 2,
        "number_of_quizzes_viewed": 4,
        "number_of_assignments_viewed": 3,
        "total_time_spent_seconds": 5400,
    }


def _seed_course_metrics() -> None:
    """Ensure seeded demo students have course rows in student_metrics (idempotent upsert)."""
    for student_id, courses in DEMO_COURSE_METRICS.items():
        user = user_repository.find_by_student_id(student_id)
        if not user:
            continue
        user_id = str(user["_id"])
        for course in courses:
            existing = metrics_repository.get(user_id, course["course_id"]) or {}
            existing_metrics = existing.get("metrics") or {}
            merged = {
                **_default_course_metrics(course["course_name"]),
                **{k: v for k, v in existing_metrics.items() if k not in ("course_name", "activity_source")},
                "course_name": course["course_name"],
                "activity_source": "seeded",
            }
            metrics_repository.upsert(user_id, course["course_id"], merged)
        overall = metrics_repository.get(user_id, metrics_repository.OVERALL)
        if not overall:
            metrics_repository.upsert(
                user_id,
                metrics_repository.OVERALL,
                {
                    "activity_source": "seeded",
                    "all_clicks": 120,
                    "active_days": 18,
                    "total_time_spent": 14_400,
                    "access_frequency": 2.4,
                },
            )


def seed_students() -> None:
    ensure_indexes()
    now = datetime.now(timezone.utc)

    for spec in STUDENTS:
        display_name = spec["name"]
        existing = user_repository.find_by_student_id(spec["student_id"])
        if existing:
            updates: dict = {}
            if existing.get("full_name") != display_name:
                updates["full_name"] = display_name
            if existing.get("name") != display_name:
                updates["name"] = display_name
            if updates:
                user_repository.update(str(existing["_id"]), updates)
                print(
                    f"Updated demo student name: {spec['student_id']} -> {display_name}"
                )
            else:
                print(f"Student already exists: {spec['student_id']} (name up to date).")
            continue

        document = {
            "student_id": spec["student_id"],
            "full_name": display_name,
            "name": display_name,
            "email": f"{spec['student_id']}@students.academiq.local",
            "password_hash": hash_password(spec["password"]),
            "role": spec["role"],
            "created_at": now,
        }
        user_repository.create(document)
        print(f"Created student: {spec['student_id']} ({display_name})")

    _seed_course_metrics()

    from app.scripts.seed_demo_materials import seed_demo_materials
    from app.scripts.seed_demo_feature_vectors import seed_demo_feature_vectors
    from app.scripts.seed_demo_grades import seed_demo_grades

    seed_demo_materials()
    seed_demo_grades()
    print("Running seed_demo_feature_vectors from seed_students...")
    seed_demo_feature_vectors()


if __name__ == "__main__":
    seed_students()

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
        "name": "Ahmed Ali",
        "password": "password123",
        "role": ROLE_STUDENT,
    },
    {
        "student_id": "student2",
        "name": "Fatima Mohamed",
        "password": "pass456",
        "role": ROLE_STUDENT,
    },
]

# Demo course metrics keyed by student_id (stored in student_metrics collection).
DEMO_COURSE_METRICS = {
    "student1": [
        {"course_id": "101", "course_name": "Programming"},
        {"course_id": "102", "course_name": "Database"},
    ],
    "student2": [
        {"course_id": "101", "course_name": "Programming"},
        {"course_id": "103", "course_name": "Web Dev"},
    ],
}


def _seed_course_metrics() -> None:
    """Ensure seeded demo students have course rows in student_metrics."""
    for student_id, courses in DEMO_COURSE_METRICS.items():
        user = user_repository.find_by_student_id(student_id)
        if not user:
            continue
        user_id = str(user["_id"])
        for course in courses:
            if metrics_repository.get(user_id, course["course_id"]):
                continue
            metrics_repository.upsert(
                user_id,
                course["course_id"],
                {
                    "course_name": course["course_name"],
                    "quiz_attempts": 2,
                    "assignment_submissions": 1,
                    "number_of_quizzes_viewed": 3,
                    "number_of_assignments_viewed": 2,
                    "total_time_spent_seconds": 3600,
                },
            )
        if not metrics_repository.get(user_id, metrics_repository.OVERALL):
            metrics_repository.upsert(
                user_id,
                metrics_repository.OVERALL,
                {
                    "all_clicks": 40,
                    "active_days": 10,
                    "total_time_spent": 7200,
                    "access_frequency": 1.2,
                },
            )


def seed_students() -> None:
    ensure_indexes()
    now = datetime.now(timezone.utc)

    for spec in STUDENTS:
        existing = user_repository.find_by_student_id(spec["student_id"])
        if existing:
            print(f"Student already exists: {spec['student_id']} (no changes made).")
            continue

        # Synthetic email satisfies the unique email index without exposing login via email.
        document = {
            "student_id": spec["student_id"],
            "name": spec["name"],
            "email": f"{spec['student_id']}@students.academiq.local",
            "password_hash": hash_password(spec["password"]),
            "role": spec["role"],
            "created_at": now,
        }
        user_repository.create(document)
        print(f"Created student: {spec['student_id']} ({spec['name']})")

    _seed_course_metrics()


if __name__ == "__main__":
    seed_students()

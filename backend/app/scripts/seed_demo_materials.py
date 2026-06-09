"""
Seed demo learning materials for test student courses (Quiz Generation).

Materials are stored in course_materials — course-scoped, not Moodle sync.
Idempotent: skips rows that already have non-empty content_text.

Run from backend/:

    python -m app.scripts.seed_demo_materials

Also invoked automatically by seed_students() / BOOTSTRAP_STUDENTS.
"""

from pathlib import Path

from app.config.database import ensure_indexes
from app.repositories import material_repository

_REPO = Path(__file__).resolve().parents[3]
_SAMPLE_TEXT = _REPO / "ai" / "quiz_generator-main" / "assessment.txt"

# Seeded test materials for demo course IDs (see seed_students.DEMO_COURSE_METRICS).
DEMO_MATERIALS = [
    {
        "course_id": "101",
        "material_id": "prog_lec1",
        "title": "Programming Lecture 1",
        "file_type": "pdf",
        "course_name": "Programming",
    },
    {
        "course_id": "102",
        "material_id": "db_lec1",
        "title": "Database Lecture 1",
        "file_type": "pdf",
        "course_name": "Database",
    },
]

_FALLBACK_TEXT = """
Programming and Database Fundamentals — Seeded Demo Material

A variable is a named storage location in a program. Data types include integers,
floating-point numbers, strings, and booleans. Control structures such as if-else
statements and loops determine execution order.

A relational database stores data in tables with rows and columns. Primary keys
uniquely identify rows. Foreign keys link tables together. SQL is used to query and
update data. Normalization reduces redundancy. Indexes improve lookup performance.

Object-oriented programming uses classes, objects, inheritance, and encapsulation.
Functions modularize code. Arrays and lists store collections. Hash tables provide
fast key-based access. Transactions in databases follow ACID properties: atomicity,
consistency, isolation, and durability.

Software testing includes unit tests, integration tests, and regression tests.
Version control systems track changes to source code. APIs expose functionality
between services. REST uses HTTP verbs such as GET, POST, PUT, and DELETE.
""".strip()


def _load_sample_text() -> str:
    if _SAMPLE_TEXT.is_file():
        return _SAMPLE_TEXT.read_text(encoding="utf-8")
    return _FALLBACK_TEXT


def seed_demo_materials() -> None:
    """Upsert demo materials + content_text for courses 101 and 102."""
    ensure_indexes()
    text = _load_sample_text()

    for spec in DEMO_MATERIALS:
        course_id = spec["course_id"]
        material_id = spec["material_id"]
        existing = material_repository.get(course_id, material_id)
        if existing and (existing.get("content_text") or "").strip():
            print(
                f"Demo material already seeded: course {course_id} / {material_id} "
                f"({existing.get('content_chars', 0)} chars, skipped)."
            )
            continue

        material_repository.upsert(
            {
                "course_id": course_id,
                "material_id": material_id,
                "title": spec["title"],
                "course_name": spec["course_name"],
                "file_type": spec["file_type"],
                "material_type": "lecture",
                "semantic_tags": ["lecture", "seeded_demo"],
                "category": "lecture",
                "seed_source": "demo_test",
            }
        )
        material_repository.set_content(course_id, material_id, text)
        print(
            f"Seeded demo material: course {course_id} / {material_id} "
            f"({spec['title']}, {len(text)} chars, ready for quiz)."
        )


if __name__ == "__main__":
    seed_demo_materials()

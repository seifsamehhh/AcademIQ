"""
Seed demo learning materials for test student courses (Quiz Generation).

Materials are stored in course_materials — course-scoped, not Moodle sync.
Re-running always refreshes metadata and content_text (no skip on existing content).

Run from backend/:

    python -m app.scripts.seed_demo_materials

Also invoked automatically by seed_students() / BOOTSTRAP_STUDENTS.
"""

from app.config.database import course_materials_collection, ensure_indexes
from app.repositories import material_repository
from app.scripts.seed_demo_materials_data import (
    DEPRECATED_DEMO_MATERIAL_IDS,
    all_demo_materials,
)


def _remove_deprecated_materials() -> None:
    """Drop legacy single-lecture demo rows superseded by multi-material seeds."""
    for course_id, material_id in DEPRECATED_DEMO_MATERIAL_IDS:
        result = course_materials_collection.delete_one(
            {"course_id": str(course_id), "material_id": str(material_id)}
        )
        if result.deleted_count:
            print(f"Removed deprecated demo material: course {course_id} / {material_id}")


def seed_demo_materials() -> None:
    """Upsert demo materials and refresh content_text for courses 101–105."""
    ensure_indexes()
    _remove_deprecated_materials()

    for spec in all_demo_materials():
        course_id = spec["course_id"]
        material_id = spec["material_id"]
        text = spec["content"]

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
        word_count = len(text.split())
        print(
            f"Seeded demo material: course {course_id} / {material_id} "
            f"({spec['title']}, {len(text)} chars, ~{word_count} words, ready for quiz)."
        )


if __name__ == "__main__":
    seed_demo_materials()

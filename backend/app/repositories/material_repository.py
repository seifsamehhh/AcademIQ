"""
Data access for canonical course materials.

Materials are stored once per `(course_id, material_id)`. `upsert` guarantees a
re-synced material updates the existing record instead of inserting a duplicate.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.config.database import course_materials_collection


def upsert(material_doc: Dict[str, Any]) -> bool:
    """
    Insert or update a material by its (course_id, material_id) key.

    Returns True if a new material was inserted, False if an existing one was
    updated. `first_seen` is set only on insert; `last_seen` always refreshed.
    """
    now = datetime.utcnow()
    key = {
        "course_id": material_doc.get("course_id"),
        "material_id": material_doc.get("material_id"),
    }
    update = {
        "$set": {**material_doc, "last_seen": now},
        "$setOnInsert": {"first_seen": now},
    }
    result = course_materials_collection.update_one(key, update, upsert=True)
    return result.upserted_id is not None


def list_by_course(course_id: str) -> List[Dict[str, Any]]:
    return list(course_materials_collection.find({"course_id": str(course_id)}))


def list_by_category(course_id: str, category: str) -> List[Dict[str, Any]]:
    """Materials in a course filtered by category — derived, not duplicated.

    Matches either the derived `category` or membership in `semantic_tags`.
    """
    return list(
        course_materials_collection.find(
            {
                "course_id": str(course_id),
                "$or": [{"category": category}, {"semantic_tags": category}],
            }
        )
    )


def get(course_id: str, material_id: str) -> Optional[Dict[str, Any]]:
    return course_materials_collection.find_one(
        {"course_id": str(course_id), "material_id": str(material_id)}
    )


def find_by_course_and_url(course_id: str, url: str) -> Optional[Dict[str, Any]]:
    """Find an existing material row by Moodle activity or file URL."""
    if not url:
        return None
    cid = str(course_id)
    normalized = url.strip()
    doc = course_materials_collection.find_one({"course_id": cid, "url": normalized})
    if doc:
        return doc
    return course_materials_collection.find_one(
        {"course_id": cid, "resolved_url": normalized}
    )


def set_content(course_id: str, material_id: str, text: str) -> bool:
    """Store extracted text for a material (used for quiz generation)."""
    result = course_materials_collection.update_one(
        {"course_id": str(course_id), "material_id": str(material_id)},
        {"$set": {"content_text": text, "content_chars": len(text or "")}},
        upsert=True,
    )
    return result.matched_count > 0 or result.upserted_id is not None


def get_content(course_id: str, material_ids: List[str]) -> str:
    """Concatenate stored text for the given materials in a course."""
    ids = [str(m) for m in material_ids]
    cursor = course_materials_collection.find(
        {"course_id": str(course_id), "material_id": {"$in": ids}, "content_text": {"$exists": True}},
        {"content_text": 1},
    )
    return "\n\n".join(d.get("content_text", "") for d in cursor)


def count() -> int:
    return course_materials_collection.count_documents({})

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


def get_content_with_meta(
    course_id: str, material_ids: List[str]
) -> tuple[str, List[Dict[str, Any]]]:
    """
    Return (combined_text, per_material_meta_list).

    per_material_meta_list contains one dict per found material with:
      material_id, title, raw_chars (original content_text length).
    Combined text uses the order of material_ids as requested.
    """
    ids = [str(m) for m in material_ids]
    rows = {
        str(d["material_id"]): d
        for d in course_materials_collection.find(
            {"course_id": str(course_id), "material_id": {"$in": ids}},
            {"content_text": 1, "material_id": 1, "title": 1},
        )
    }
    texts: List[str] = []
    meta: List[Dict[str, Any]] = []
    for mid in ids:
        doc = rows.get(mid)
        if not doc:
            meta.append({"material_id": mid, "title": None, "raw_chars": 0, "found": False})
            continue
        raw = (doc.get("content_text") or "").strip()
        texts.append(raw)
        meta.append({
            "material_id": mid,
            "title": doc.get("title"),
            "raw_chars": len(raw),
            "found": bool(raw),
        })
    return "\n\n".join(texts), meta


def get_ready_context_materials(
    course_id: str,
    exclude_ids: List[str],
    min_chars: int = 600,
    max_results: int = 8,
) -> List[Dict[str, Any]]:
    """
    Return educational materials in a course that have sufficient extracted text,
    excluding the materials already selected by the user.

    Used by the course-context fallback in quiz generation when the selected
    material alone does not have enough content to produce questions.

    Results are sorted by descending content length (richest context first)
    and capped at max_results.  Only materials with usable extracted text are
    returned; non-quiz materials (no content_text or failed extraction) are
    excluded server-side and then re-filtered in Python using content length.
    """
    exclude = [str(i) for i in (exclude_ids or [])]
    # Exclude materials with known non-quiz / failed extraction statuses
    bad_statuses = {
        "not_quiz_material", "extraction_failed", "no_content",
        "insufficient_text", "not_educational", "folder", "assign",
        "forum",
    }
    query: Dict[str, Any] = {
        "course_id": str(course_id),
        "content_text": {"$exists": True, "$nin": [None, ""]},
    }
    if exclude:
        query["material_id"] = {"$nin": exclude}

    docs = list(
        course_materials_collection.find(
            query,
            {"content_text": 1, "material_id": 1, "title": 1,
             "file_type": 1, "extraction_status": 1},
        )
    )

    # Python-side filtering: text length + bad status
    ready: List[Dict[str, Any]] = []
    for doc in docs:
        if (doc.get("extraction_status") or "") in bad_statuses:
            continue
        text = (doc.get("content_text") or "").strip()
        if len(text) >= min_chars:
            doc["_ctx_text_len"] = len(text)
            ready.append(doc)

    # Richest content first
    ready.sort(key=lambda d: d["_ctx_text_len"], reverse=True)
    return ready[:max_results]


def count() -> int:
    return course_materials_collection.count_documents({})

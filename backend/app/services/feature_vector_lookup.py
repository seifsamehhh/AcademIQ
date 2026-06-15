"""
Feature vector lookup helpers — shared by performance endpoint and debug route.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from app.config.database import connect_database, feature_vectors_collection

logger = logging.getLogger(__name__)

FEATURE_VECTORS_COLLECTION = "feature_vectors"


def _normalize_course_id(course_id: str | int | None) -> str:
    return str(course_id).strip() if course_id is not None else ""


def _course_vector(by_course: Dict[str, Any], course_id: str) -> Dict[str, Any]:
    """Return course features, matching string or int MongoDB keys."""
    if not by_course or not course_id:
        return {}
    direct = by_course.get(course_id)
    if direct:
        return direct
    try:
        as_int = by_course.get(int(course_id))
        if as_int:
            return as_int
    except (TypeError, ValueError):
        pass
    return {}


def find_feature_vector_doc(
    user_id: str, student_id: str | None = None
) -> Tuple[Optional[Dict[str, Any]], str]:
    """
    Find a feature_vectors document by academiq_user_id, then student_id fallback.
    Returns (document, matched_by) where matched_by is academiq_user_id|student_id|none.
    """
    connect_database()
    if feature_vectors_collection is None:
        return None, "none"

    doc = feature_vectors_collection.find_one({"academiq_user_id": user_id})
    if doc:
        return doc, "academiq_user_id"

    if student_id:
        doc = feature_vectors_collection.find_one({"student_id": student_id})
        if doc:
            return doc, "student_id"

    return None, "none"


def resolve_course_features(
    user_id: str,
    course_id: str | int | None,
    student_id: str | None = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Resolve behavioural features for a course.

    Returns (features_dict, debug_info).
    """
    course_key = _normalize_course_id(course_id)
    doc, matched_by = find_feature_vector_doc(user_id, student_id)

    debug: Dict[str, Any] = {
        "collection": FEATURE_VECTORS_COLLECTION,
        "academiq_user_id": user_id,
        "student_id": student_id,
        "course_id": course_key,
        "course_id_type": type(course_id).__name__ if course_id is not None else "NoneType",
        "document_found": doc is not None,
        "matched_by": matched_by,
        "course_features_keys": [],
        "course_vector_found": False,
    }

    if not doc:
        return {}, debug

    by_course = doc.get("course_features") or {}
    debug["course_features_keys"] = [
        {"key": str(k), "type": type(k).__name__} for k in by_course.keys()
    ]

    course_feats = _course_vector(by_course, course_key)

    # Moodle-synced snapshot: per-course vectors, else overall synced features.
    if doc.get("feature_source") == "synced":
        if course_feats and course_feats.get("feature_source") == "synced":
            debug["course_vector_found"] = True
            debug["feature_source"] = "synced"
            return course_feats, debug
        overall = doc.get("features") or {}
        if overall:
            debug["course_vector_found"] = True
            debug["feature_source"] = "synced"
            debug["used_overall_synced"] = True
            return overall, debug
        return {}, debug

    # Seeded demo vectors: per-course only (ignore legacy top-level features).
    if course_feats and course_feats.get("feature_source") == "seeded":
        debug["course_vector_found"] = True
        debug["feature_source"] = "seeded"
        return course_feats, debug

    return {}, debug


def log_missing_feature_vector(
    *,
    student_id: str | None,
    course_id: str | int | None,
    debug: Dict[str, Any],
) -> None:
    logger.warning(
        "Performance: no feature vector — collection=%s student_id=%s course_id=%s "
        "(type=%s) academiq_user_id=%s document_found=%s matched_by=%s "
        "course_features_keys=%s course_vector_found=%s",
        debug.get("collection"),
        student_id,
        debug.get("course_id"),
        debug.get("course_id_type"),
        debug.get("academiq_user_id"),
        debug.get("document_found"),
        debug.get("matched_by"),
        debug.get("course_features_keys"),
        debug.get("course_vector_found"),
    )

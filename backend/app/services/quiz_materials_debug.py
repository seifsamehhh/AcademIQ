"""
Safe diagnostics for quiz material readiness (no secrets or full document bodies).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.repositories import material_repository, user_repository
from app.services.moodle_course_display import get_visible_synced_courses_for_user
from app.services.student_data import (
    MIN_QUIZ_CONTENT_CHARS,
    MIN_EDUCATIONAL_REPROCESS_CHARS,
    _classify_non_quiz_material,
    _is_educational_material,
    get_materials,
)


def _content_length(doc: Dict[str, Any]) -> int:
    text = (doc.get("content_text") or "").strip()
    if text:
        return len(text)
    chars = doc.get("content_chars")
    if isinstance(chars, int) and chars > 0:
        return chars
    return 0


def _material_quiz_status(doc: Dict[str, Any]) -> tuple[str, str | None]:
    """
    Return (quiz_status, quiz_status_reason) for a raw MongoDB material doc.

    Status values:
      ready                 — has enough extracted text, selectable for quiz
      not_uploaded          — no content_text stored yet
      extraction_failed     — extraction attempted but failed
      extraction_too_short  — educational material with < MIN_QUIZ_CONTENT_CHARS chars
      too_short             — non-educational material with < MIN_QUIZ_CONTENT_CHARS chars
      not_quiz_material     — activity type / title / extension is non-educational
    """
    title = doc.get("title") or ""
    file_type = (doc.get("file_type") or doc.get("category") or "")
    is_non_quiz, reason = _classify_non_quiz_material(title, file_type)
    if is_non_quiz:
        return "not_quiz_material", reason

    extraction_status = doc.get("extraction_status") or ""
    content = (doc.get("content_text") or "").strip()
    length = len(content) if content else _content_length(doc)

    if extraction_status == "extraction_failed":
        return "extraction_failed", (
            doc.get("extraction_error") or "Extraction failed"
        )
    if not content and length == 0:
        return "not_uploaded", "No content_text stored yet"
    if length < MIN_QUIZ_CONTENT_CHARS:
        is_educ = _is_educational_material(title, file_type)
        if is_educ:
            return "extraction_too_short", (
                f"Only {length} chars — educational material needs re-extraction "
                f"(min: {MIN_QUIZ_CONTENT_CHARS})"
            )
        return "too_short", f"Only {length} chars (need ≥ {MIN_QUIZ_CONTENT_CHARS})"

    return "ready", None


# ── Per-course + per-material debug ─────────────────────────────────────────

def debug_quiz_materials_for_email(email: str, course_id: str) -> Dict[str, Any]:
    """
    Return quiz-material readiness for a user + course.
    Includes quiz_status, quiz_status_reason, file_type per material.
    Never returns content_text, passwords, tokens, or connection strings.
    """
    normalized_email = (email or "").strip().lower()
    course_id = str(course_id or "").strip()

    user = user_repository.find_by_email(normalized_email) if normalized_email else None
    user_exists = user is not None
    user_id = str(user["_id"]) if user else None

    course_name: Optional[str] = None
    visible_course_ids: List[str] = []
    if user_id:
        visible = get_visible_synced_courses_for_user(user_id)
        visible_course_ids = [str(c.get("id") or c.get("course_id") or "") for c in visible]
        for course in visible:
            cid = str(course.get("id") or course.get("course_id") or "")
            if cid == course_id:
                course_name = course.get("name") or course.get("course_name")
                break

    docs = material_repository.list_by_course(course_id) if course_id else []

    materials_out: List[Dict[str, Any]] = []
    status_counts: Dict[str, int] = {
        "ready": 0,
        "not_uploaded": 0,
        "extraction_failed": 0,
        "extraction_too_short": 0,
        "too_short": 0,
        "not_quiz_material": 0,
    }

    for doc in docs:
        mid = str(doc.get("material_id") or "")
        length = _content_length(doc)
        file_type = (doc.get("file_type") or "unknown").lower()
        title = doc.get("title") or "Untitled"
        quiz_status, quiz_status_reason = _material_quiz_status(doc)
        status_counts[quiz_status] = status_counts.get(quiz_status, 0) + 1

        is_non_quiz, _ = _classify_non_quiz_material(title, file_type)
        is_educ = _is_educational_material(title, file_type)
        # Can reprocess: educational with insufficient chars that are not confirmed-failed
        can_reprocess = (
            is_educ
            and quiz_status in ("extraction_too_short", "too_short", "not_uploaded")
            and doc.get("extraction_status") not in ("extraction_failed", "insufficient_text")
        )

        materials_out.append(
            {
                "material_id": mid,
                "title": title,
                "file_type": file_type,
                "source": doc.get("source") or doc.get("seed_source") or "unknown",
                "content_text_length": length,
                "extraction_status": (doc.get("extraction_status") or None),
                "is_educational_material": is_educ,
                "is_non_quiz_material": is_non_quiz,
                "can_reprocess": can_reprocess,
                "quiz_generation_eligible": quiz_status == "ready",
                "ready_for_quiz": quiz_status == "ready",
                "quiz_status": quiz_status,
                "quiz_status_reason": quiz_status_reason,
            }
        )

    materials_out.sort(
        key=lambda row: (
            row["quiz_status"] != "ready",
            row["quiz_status"] == "not_quiz_material",
            row["title"].lower(),
        )
    )

    return {
        "user_exists": user_exists,
        "user_email": normalized_email or None,
        "academiq_user_id": user_id,
        "course_id": course_id,
        "course_name": course_name,
        "course_in_visible_synced_list": course_id in visible_course_ids if course_id else False,
        "visible_synced_course_ids": visible_course_ids,
        "total_materials": len(materials_out),
        "detected_materials_count": len(materials_out),
        "ready_count": status_counts.get("ready", 0),
        "not_uploaded_count": status_counts.get("not_uploaded", 0),
        "not_quiz_material_count": status_counts.get("not_quiz_material", 0),
        "extraction_failed_count": status_counts.get("extraction_failed", 0),
        "extraction_too_short_count": status_counts.get("extraction_too_short", 0),
        "too_short_count": status_counts.get("too_short", 0),
        "status_counts": status_counts,
        "min_quiz_content_chars": MIN_QUIZ_CONTENT_CHARS,
        "min_educational_reprocess_chars": MIN_EDUCATIONAL_REPROCESS_CHARS,
        "materials": materials_out,
        "hint": (
            "quiz_status='ready' = selectable for quiz. "
            "'extraction_too_short' = educational file with too little extracted text — "
            "re-upload via Chrome extension to re-extract with improved extractor. "
            "'not_quiz_material' = grades/admin/forum type (never selectable). "
            "'not_uploaded' = listed from Moodle but not processed yet. "
            f"min_quiz_content_chars={MIN_QUIZ_CONTENT_CHARS}, "
            f"min_educational_reprocess_chars={MIN_EDUCATIONAL_REPROCESS_CHARS}."
        ),
    }


# ── Account-level coverage across all synced courses ────────────────────────

def debug_course_material_coverage(email: str) -> Dict[str, Any]:
    """
    Return per-course material coverage summary for a user's synced Moodle courses.
    Shows status counts and per-material details for every detected course.
    Never returns content_text, passwords, tokens, or connection strings.
    """
    normalized_email = (email or "").strip().lower()

    user = user_repository.find_by_email(normalized_email) if normalized_email else None
    user_exists = user is not None
    user_id = str(user["_id"]) if user else None

    if not user_id:
        return {
            "user_exists": False,
            "user_email": normalized_email or None,
            "message": "No user found with this email.",
            "courses": [],
        }

    visible = get_visible_synced_courses_for_user(user_id)
    courses_out: List[Dict[str, Any]] = []

    for course in visible:
        course_id = str(course.get("id") or course.get("course_id") or "")
        course_name = course.get("name") or course.get("course_name") or "Unknown"

        if not course_id:
            continue

        docs = material_repository.list_by_course(course_id)

        status_counts: Dict[str, int] = {
            "ready": 0,
            "not_uploaded": 0,
            "extraction_failed": 0,
            "extraction_too_short": 0,
            "too_short": 0,
            "not_quiz_material": 0,
        }
        materials_list: List[Dict[str, Any]] = []

        for doc in docs:
            mid = str(doc.get("material_id") or "")
            length = _content_length(doc)
            _ft = (doc.get("file_type") or "unknown").lower()
            _title = doc.get("title") or "Untitled"
            quiz_status, quiz_status_reason = _material_quiz_status(doc)
            status_counts[quiz_status] = status_counts.get(quiz_status, 0) + 1
            is_educ = _is_educational_material(_title, _ft)
            can_reprocess = (
                is_educ
                and quiz_status in ("extraction_too_short", "too_short", "not_uploaded")
                and doc.get("extraction_status") not in ("extraction_failed", "insufficient_text")
            )

            materials_list.append({
                "material_id": mid,
                "title": _title,
                "file_type": _ft,
                "content_text_length": length,
                "extraction_status": (doc.get("extraction_status") or None),
                "is_educational_material": is_educ,
                "can_reprocess": can_reprocess,
                "quiz_status": quiz_status,
                "quiz_status_reason": quiz_status_reason,
            })

        materials_list.sort(
            key=lambda row: (
                row["quiz_status"] != "ready",
                row["quiz_status"] == "not_quiz_material",
                row["title"].lower(),
            )
        )

        courses_out.append({
            "course_id": course_id,
            "course_name": course_name,
            "detected_materials_count": len(materials_list),
            "ready_count": status_counts.get("ready", 0),
            "not_uploaded_count": status_counts.get("not_uploaded", 0),
            "not_quiz_material_count": status_counts.get("not_quiz_material", 0),
            "extraction_failed_count": status_counts.get("extraction_failed", 0),
            "too_short_count": status_counts.get("too_short", 0),
            "status_counts": status_counts,
            "materials": materials_list,
        })

    total_ready = sum(c["status_counts"].get("ready", 0) for c in courses_out)
    total_not_uploaded = sum(c["status_counts"].get("not_uploaded", 0) for c in courses_out)
    total_non_quiz = sum(c["status_counts"].get("not_quiz_material", 0) for c in courses_out)
    total_failed = sum(c["status_counts"].get("extraction_failed", 0) for c in courses_out)

    return {
        "user_exists": user_exists,
        "user_email": normalized_email,
        "academiq_user_id": user_id,
        "synced_courses_count": len(courses_out),
        "summary": {
            "total_ready": total_ready,
            "total_not_uploaded": total_not_uploaded,
            "total_not_quiz_material": total_non_quiz,
            "total_extraction_failed": total_failed,
        },
        "courses": courses_out,
    }


# ── Single-material debug ─────────────────────────────────────────────────────

def debug_single_material(material_id: str) -> Dict[str, Any]:
    """
    Return quiz eligibility for a specific material_id across all courses.
    Never returns content_text, passwords, tokens, or connection strings.
    """
    from app.config.database import course_materials_collection

    docs = list(course_materials_collection.find({"material_id": str(material_id)}))
    if not docs:
        return {
            "material_exists": False,
            "material_id": material_id,
            "message": "No material found with this ID in any course.",
        }

    results = []
    for doc in docs:
        length = _content_length(doc)
        quiz_status, quiz_status_reason = _material_quiz_status(doc)
        results.append(
            {
                "course_id": str(doc.get("course_id") or ""),
                "material_id": str(doc.get("material_id") or ""),
                "title": doc.get("title") or "Untitled",
                "file_type": (doc.get("file_type") or "unknown").lower(),
                "source": doc.get("source") or doc.get("seed_source") or "unknown",
                "content_text_length": length,
                "ready_for_quiz": bool(doc.get("ready_for_quiz")),
                "extraction_status": doc.get("extraction_status"),
                "quiz_status": quiz_status,
                "quiz_status_reason": quiz_status_reason,
            }
        )

    return {
        "material_exists": True,
        "material_id": material_id,
        "matches": results,
    }

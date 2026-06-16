"""
Safe diagnostics for quiz material readiness (no secrets or full document bodies).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.repositories import material_repository, user_repository
from app.services.moodle_course_display import get_visible_synced_courses_for_user
from app.services.quiz_material_eligibility import (
    assess_material_doc,
    reason_message,
)
from app.services.student_data import MIN_QUIZ_CONTENT_CHARS, get_materials


def _content_length(doc: Dict[str, Any]) -> int:
    text = (doc.get("content_text") or "").strip()
    if text:
        return len(text)
    chars = doc.get("content_chars")
    if isinstance(chars, int) and chars > 0:
        return chars
    return 0


def debug_quiz_materials_for_email(email: str, course_id: str) -> Dict[str, Any]:
    """
    Return quiz-material readiness for a user + course.
    Includes quiz_generation_eligible, failure_reason, file_type per material.
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
    api_materials = get_materials(course_id, user_id) if course_id and user_id else []
    api_ready_by_id = {
        str(m.get("id")): bool(m.get("hasContent")) for m in api_materials
    }

    materials_out: List[Dict[str, Any]] = []
    ready_count = 0
    quiz_eligible_count = 0

    for doc in docs:
        mid = str(doc.get("material_id") or "")
        length = _content_length(doc)
        has_content_text = length > 0
        ready_flag = doc.get("ready_for_quiz")
        api_ready = api_ready_by_id.get(mid, False)
        if api_ready:
            ready_count += 1

        # Quick eligibility check (no heavy generator — Vercel safe)
        eligible, reason_code, _meta = assess_material_doc(doc, probe=False)
        if eligible:
            quiz_eligible_count += 1

        failure_reason = reason_message(reason_code) if not eligible else None

        materials_out.append(
            {
                "material_id": mid,
                "title": doc.get("title") or "Untitled",
                "file_type": (doc.get("file_type") or "unknown").lower(),
                "source": doc.get("source") or doc.get("seed_source") or "unknown",
                "has_content_text": has_content_text,
                "content_text_length": length,
                "ready_for_quiz": bool(ready_flag) if ready_flag is not None else api_ready,
                "api_has_content": api_ready,
                "quiz_generation_eligible": eligible,
                "extraction_status": doc.get("extraction_status"),
                "failure_reason": failure_reason,
            }
        )

    materials_out.sort(
        key=lambda row: (not row["api_has_content"], not row["quiz_generation_eligible"], row["title"].lower())
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
        "ready_materials_count": ready_count,
        "quiz_eligible_count": quiz_eligible_count,
        "min_quiz_content_chars": MIN_QUIZ_CONTENT_CHARS,
        "materials": materials_out,
        "hint": (
            "quiz_generation_eligible=true means the text structure is sufficient for "
            "quiz generation. api_has_content=true means the UI shows 'Ready for quiz'."
        ),
    }


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
        eligible, reason_code, meta = assess_material_doc(doc, probe=False)
        results.append(
            {
                "course_id": str(doc.get("course_id") or ""),
                "material_id": str(doc.get("material_id") or ""),
                "title": doc.get("title") or "Untitled",
                "file_type": (doc.get("file_type") or "unknown").lower(),
                "source": doc.get("source") or doc.get("seed_source") or "unknown",
                "content_text_length": meta.get("content_text_length", 0),
                "ready_for_quiz": bool(doc.get("ready_for_quiz")),
                "extraction_status": doc.get("extraction_status"),
                "quiz_generation_eligible": eligible,
                "failure_reason": reason_message(reason_code) if not eligible else None,
                "definition_pair_count": meta.get("definition_pair_count"),
            }
        )

    return {
        "material_exists": True,
        "material_id": material_id,
        "matches": results,
    }

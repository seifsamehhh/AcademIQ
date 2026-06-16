# backend/app/routes/student_data.py
"""
Student-facing data endpoints consumed by the Next.js frontend
(front-end/src/lib/api.ts). All are scoped to the authenticated student via
JWT Bearer tokens or legacy session cookies (get_current_user), and read the
real normalized MongoDB collections.

Paths intentionally have NO /api prefix to match the frontend's api.ts calls
(/courses, /dashboard, /courses/{id}/performance, ...).
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.models.user import ROLE_ADMIN
from app.repositories import material_repository
from app.services import quiz_gen, student_data

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Student data"])


def _student_id_from_user(user: Dict[str, Any]) -> str | None:
    sid = user.get("student_id")
    return str(sid).strip() if sid else None


@router.get("/courses")
def list_courses(user: Dict[str, Any] = Depends(get_current_user)):
    return student_data.get_courses(str(user["_id"]), user.get("student_id"))


@router.get("/dashboard")
def dashboard(user: Dict[str, Any] = Depends(get_current_user)):
    return student_data.get_dashboard(user)


@router.get("/courses/{course_id}/performance")
def performance(course_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    return student_data.get_performance(
        str(user["_id"]),
        course_id,
        _student_id_from_user(user),
    )


@router.get("/courses/{course_id}/insights")
def insights(course_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    return student_data.get_insights(
        str(user["_id"]),
        course_id,
        _student_id_from_user(user),
    )


@router.get("/debug/feature-vectors/{student_id}/{course_id}")
def debug_feature_vectors(
    student_id: str,
    course_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Demo-safe debug: inspect whether a feature vector exists for student/course.
    Students may only query their own student_id; admins may query any demo student.
    """
    caller_student_id = _student_id_from_user(user)
    is_admin = user.get("role") == ROLE_ADMIN
    if not is_admin and caller_student_id != student_id:
        raise HTTPException(status_code=403, detail="Cannot inspect another student's features")

    from app.repositories import user_repository

    target_user = user_repository.find_by_student_id(student_id)
    if not target_user:
        raise HTTPException(status_code=404, detail=f"Student not found: {student_id}")

    return student_data.debug_feature_vector(
        str(target_user["_id"]),
        student_id,
        course_id,
    )


@router.get("/courses/{course_id}/materials")
def materials(course_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    # Materials are course-scoped (shared), filtered by enrolled course name when needed.
    return student_data.get_materials(course_id, str(user["_id"]))


@router.post("/courses/{course_id}/quiz")
def generate_quiz(
    course_id: str,
    body: Dict[str, Any],
    _user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Generate a quiz from selected materials' stored content_text (no PDF required).
    Uses the heavy local generator when available, otherwise a lightweight
    Vercel-safe rule-based generator.
    """
    material_ids: List[str] = body.get("materialIds", []) or []
    if not material_ids:
        raise HTTPException(status_code=400, detail="materialIds required")

    # Fetch text + per-material metadata in one query
    text, mat_meta = material_repository.get_content_with_meta(course_id, material_ids)
    content_chars = len((text or "").strip())

    logger.info(
        "Quiz request course=%s materials=%s content_chars=%d",
        course_id, material_ids, content_chars,
    )

    if not content_chars:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "missing_content_text",
                "message": (
                    "Selected materials have no extracted text. "
                    "Use the Chrome extension → 'Upload materials for quiz' on "
                    "the Moodle course page first."
                ),
                "material_ids": material_ids,
            },
        )

    if content_chars < student_data.MIN_QUIZ_CONTENT_CHARS:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "content_too_short",
                "message": (
                    f"The selected material(s) only have {content_chars} characters of text "
                    f"(need at least {student_data.MIN_QUIZ_CONTENT_CHARS}). "
                    "Re-upload a more content-rich PDF via the Chrome extension."
                ),
                "content_chars": content_chars,
                "min_required": student_data.MIN_QUIZ_CONTENT_CHARS,
            },
        )

    questions, engine = quiz_gen.generate_questions(text, num_questions=5)

    if not questions:
        detail = {
            "error": "quiz_generation_failed",
            "message": (
                f"Could not generate quiz questions from the selected material "
                f"({content_chars} characters of text). "
                "The content may be too short, contain only images, or have no "
                "readable sentences. Try selecting a different material or "
                "re-uploading with a text-based PDF."
            ),
            "content_chars": content_chars,
            "engine": engine,
            "material_ids": material_ids,
        }
        logger.error("Quiz gen failed: %s", detail)
        raise HTTPException(status_code=422, detail=detail)

    # Build safe debug metadata (no content_text in response)
    debug = {
        "selected_material_ids": material_ids,
        "selected_material_titles": [m.get("title") for m in mat_meta],
        "content_text_length_per_material": {
            m["material_id"]: m["raw_chars"] for m in mat_meta
        },
        "total_content_chars": content_chars,
        "generator_mode": engine,
        "question_count": len(questions),
    }

    return {
        "courseId": course_id,
        "materialIds": material_ids,
        "questions": questions,
        "engine": engine,
        "debug": debug,
    }

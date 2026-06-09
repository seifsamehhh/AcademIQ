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
from app.repositories import material_repository
from app.services import quiz_gen, student_data

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Student data"])


@router.get("/courses")
def list_courses(user: Dict[str, Any] = Depends(get_current_user)):
    return student_data.get_courses(str(user["_id"]))


@router.get("/dashboard")
def dashboard(user: Dict[str, Any] = Depends(get_current_user)):
    return student_data.get_dashboard(user)


@router.get("/courses/{course_id}/performance")
def performance(course_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    return student_data.get_performance(str(user["_id"]), course_id)


@router.get("/courses/{course_id}/insights")
def insights(course_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    return student_data.get_insights(str(user["_id"]), course_id)


@router.get("/courses/{course_id}/materials")
def materials(course_id: str, _user: Dict[str, Any] = Depends(get_current_user)):
    # Materials are course-scoped (shared), but still gated behind auth.
    return student_data.get_materials(course_id)


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

    text = material_repository.get_content(course_id, material_ids)
    logger.info(
        "Quiz request course=%s materials=%s content_chars=%d",
        course_id,
        material_ids,
        len(text or ""),
    )

    questions, engine = quiz_gen.generate_questions(text, num_questions=8)

    if not questions:
        detail = (
            "Selected materials have no uploaded text. Upload PDFs via the extension "
            "or seed demo content before generating a quiz."
            if not (text or "").strip()
            else
            f"Quiz generation failed for course {course_id} (engine={engine}). "
            "Content may lack definition-style sentences."
        )
        logger.error(detail)
        raise HTTPException(status_code=422, detail=detail)

    return {
        "courseId": course_id,
        "materialIds": material_ids,
        "questions": questions,
        "engine": engine,
    }

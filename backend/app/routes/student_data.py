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
from app.services.student_data import (
    MIN_QUIZ_CONTENT_CHARS,
    _classify_non_quiz_material,
    _is_educational_material,
    _is_quiz_generation_eligible,
)

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
    Generate a quiz from selected materials' stored content_text only.

    Course-context fallback is disabled — each quiz uses the selected material alone.
    """
    material_ids: List[str] = body.get("materialIds", []) or []
    if not material_ids:
        raise HTTPException(status_code=400, detail="materialIds required")

    # ── Validate every selected material before generation ─────────────────────
    for mid in material_ids:
        doc = material_repository.get(course_id, str(mid))
        if not doc:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "material_not_found",
                    "message": f"Material not found: {mid}",
                    "material_ids": material_ids,
                },
            )

        title = doc.get("title") or ""
        file_type = (doc.get("file_type") or doc.get("category") or "file")
        content = (doc.get("content_text") or "").strip()

        is_non_quiz, non_quiz_reason = _classify_non_quiz_material(title, file_type)
        if is_non_quiz or doc.get("extraction_status") == "not_quiz_material":
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "not_quiz_material",
                    "message": non_quiz_reason or "This material is not quiz learning content.",
                    "material_ids": material_ids,
                    "material_title": title,
                },
            )

        if not _is_educational_material(title, file_type):
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "not_quiz_material",
                    "message": (
                        "Only lectures, labs, revisions, notes, and similar "
                        "learning materials can generate quizzes."
                    ),
                    "material_ids": material_ids,
                    "material_title": title,
                },
            )

        if not _is_quiz_generation_eligible(title, file_type, content):
            from app.services.material_quiz_display import resolve_material_display

            display = resolve_material_display(doc)
            reason = (
                display.get("why_not_ready")
                or display["quiz_status_reason"]
                or "insufficient content"
            )
            raise HTTPException(
                status_code=422,
                detail={
                    "error": display["quiz_status"],
                    "message": f"This material is not eligible for quiz generation: {reason}",
                    "content_chars": len(content),
                    "min_required": MIN_QUIZ_CONTENT_CHARS,
                    "material_ids": material_ids,
                    "material_title": title,
                },
            )

    # ── Fetch combined text from selected materials only ──────────────────────
    text, mat_meta = material_repository.get_content_with_meta(course_id, material_ids)
    selected_text = (text or "").strip()
    content_chars = len(selected_text)
    primary_title: str = (mat_meta[0].get("title") or "") if mat_meta else ""
    selected_titles = [m.get("title") for m in mat_meta]

    logger.info(
        "Quiz request course=%s materials=%s content_chars=%d mode=selected_material_only",
        course_id, material_ids, content_chars,
    )

    if content_chars < MIN_QUIZ_CONTENT_CHARS:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "content_too_short",
                "message": (
                    f"Not enough readable educational text in the selected material "
                    f"({content_chars} characters; need at least {MIN_QUIZ_CONTENT_CHARS})."
                ),
                "content_chars": content_chars,
                "min_required": MIN_QUIZ_CONTENT_CHARS,
                "material_ids": material_ids,
            },
        )

    questions, engine = quiz_gen.generate_questions(selected_text, num_questions=5)

    if not questions:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "quiz_generation_failed",
                "message": (
                    f"Could not generate quiz questions from '{primary_title or 'selected material'}' "
                    f"({content_chars} characters). The content may be image-only, too fragmented, "
                    "or have no teachable concepts. Try re-uploading a text-based PDF or selecting "
                    "a different material."
                ),
                "content_chars": content_chars,
                "engine": engine,
                "generator_mode": "selected_material_only",
                "material_ids": material_ids,
            },
        )

    generator_mode = "selected_material_only"
    debug: Dict[str, Any] = {
        "generator_mode": generator_mode,
        "selected_material_id": material_ids[0] if len(material_ids) == 1 else material_ids,
        "selected_material_title": primary_title,
        "selected_material_ids": material_ids,
        "selected_material_titles": selected_titles,
        "selected_material_content_length": content_chars,
        "content_text_length_per_material": {
            m["material_id"]: m["raw_chars"] for m in mat_meta
        },
        "question_count": len(questions),
        "engine": engine,
    }

    return {
        "courseId": course_id,
        "materialIds": material_ids,
        "questions": questions,
        "engine": engine,
        "generatorMode": generator_mode,
        "debug": debug,
    }

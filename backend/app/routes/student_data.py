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
    MIN_EDUCATIONAL_REPROCESS_CHARS,
    _classify_non_quiz_material,
    _is_educational_material,
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
    Generate a quiz from selected materials' stored content_text.

    Two modes:
      selected_material_only   — selected material has enough content on its own.
      course_context_fallback  — selected material is educational but too sparse;
                                 supplemented with other ready educational materials
                                 from the same course.  Never uses content from a
                                 different course or non-educational files.
    """
    material_ids: List[str] = body.get("materialIds", []) or []
    if not material_ids:
        raise HTTPException(status_code=400, detail="materialIds required")

    # ── 1. Fetch selected-material text ───────────────────────────────────────
    text, mat_meta = material_repository.get_content_with_meta(course_id, material_ids)
    selected_text = (text or "").strip()
    content_chars = len(selected_text)

    selected_titles = [m.get("title") for m in mat_meta]
    selected_is_educational = all(
        _is_educational_material(m.get("title") or "", "")
        or not _classify_non_quiz_material(m.get("title") or "", "")[0]
        for m in mat_meta
    )

    logger.info(
        "Quiz request course=%s materials=%s content_chars=%d",
        course_id, material_ids, content_chars,
    )

    # ── 2. First attempt: generate from selected material alone ───────────────
    questions: List[Dict[str, Any]] = []
    engine = "no_text"
    generator_mode = "selected_material_only"
    context_material_ids: List[str] = []
    context_material_titles: List[str] = []
    context_reason: str | None = None

    if content_chars >= MIN_QUIZ_CONTENT_CHARS:
        questions, engine = quiz_gen.generate_questions(selected_text, num_questions=5)

    # ── 3. Course-context fallback ────────────────────────────────────────────
    # Triggered when:
    #   a) Selected material has no/insufficient text, OR
    #   b) Generator produced 0 questions from the selected text.
    # Only applies when the selected material is educational.
    # Context is drawn ONLY from the same course and ONLY from ready educational
    # materials (grades/admin/forum files are excluded both by classification
    # and by requiring a minimum extracted text length).
    if not questions and selected_is_educational:
        context_docs = material_repository.get_ready_context_materials(
            course_id,
            exclude_ids=material_ids,
            min_chars=MIN_QUIZ_CONTENT_CHARS,
        )

        # Keep only genuinely educational context documents
        edu_context: List[Dict[str, Any]] = []
        for doc in context_docs:
            title = doc.get("title") or ""
            ft = (doc.get("file_type") or "").lower()
            is_non_quiz, _ = _classify_non_quiz_material(title, ft)
            if not is_non_quiz:
                edu_context.append(doc)

        if edu_context:
            # Build combined text: selected first (even if short), then context
            combined_parts: List[str] = []

            # Selected material (may be short — keep for topic grounding)
            if selected_text:
                header = selected_titles[0] if selected_titles else "Selected material"
                combined_parts.append(f"[{header}]\n{selected_text}")

            # Context materials (up to 5; cap total context chars at 15 000)
            ctx_chars = 0
            ctx_cap = 15_000
            for doc in edu_context[:5]:
                ctx_text = (doc.get("content_text") or "").strip()
                if not ctx_text:
                    continue
                if ctx_chars + len(ctx_text) > ctx_cap:
                    ctx_text = ctx_text[: ctx_cap - ctx_chars]
                ctx_title = doc.get("title") or "Course material"
                combined_parts.append(f"[{ctx_title}]\n{ctx_text}")
                context_material_ids.append(str(doc.get("material_id") or ""))
                context_material_titles.append(ctx_title)
                ctx_chars += len(ctx_text)
                if ctx_chars >= ctx_cap:
                    break

            combined_text = "\n\n".join(combined_parts)

            if combined_text.strip():
                ctx_questions, ctx_engine = quiz_gen.generate_questions(
                    combined_text, num_questions=5
                )
                if ctx_questions:
                    questions = ctx_questions
                    engine = ctx_engine
                    generator_mode = "course_context_fallback"
                    context_reason = (
                        f"Selected material had only {content_chars} chars of extracted text; "
                        f"supplemented with {len(context_material_ids)} other educational "
                        f"material(s) from course {course_id}."
                    )
                    logger.info(
                        "Course-context fallback succeeded: course=%s selected=%s "
                        "context=%s questions=%d",
                        course_id, material_ids, context_material_ids, len(questions),
                    )

    # ── 4. Final error gates ──────────────────────────────────────────────────
    if not questions:
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

        if not context_material_ids and content_chars < MIN_QUIZ_CONTENT_CHARS:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "content_too_short_no_context",
                    "message": (
                        f"The selected material has only {content_chars} characters of "
                        f"extracted text (need at least {MIN_QUIZ_CONTENT_CHARS}), and no "
                        "other ready educational materials exist in this course to provide "
                        "context. Re-upload a text-based PDF or PPTX via the Chrome extension."
                    ),
                    "content_chars": content_chars,
                    "min_required": MIN_QUIZ_CONTENT_CHARS,
                    "material_ids": material_ids,
                },
            )

        raise HTTPException(
            status_code=422,
            detail={
                "error": "quiz_generation_failed",
                "message": (
                    f"Could not generate quiz questions from the selected material "
                    f"({content_chars} chars) even with course-context support. "
                    "The content may be image-only, too fragmented, or have no teachable "
                    "concepts. Try re-uploading a text-based PDF or selecting a "
                    "different material."
                ),
                "content_chars": content_chars,
                "engine": engine,
                "generator_mode": generator_mode,
                "context_materials_tried": len(context_material_ids),
                "material_ids": material_ids,
            },
        )

    # ── 5. Success response ───────────────────────────────────────────────────
    debug: Dict[str, Any] = {
        "generator_mode": generator_mode,
        "selected_material_ids": material_ids,
        "selected_material_titles": selected_titles,
        "content_text_length_per_material": {
            m["material_id"]: m["raw_chars"] for m in mat_meta
        },
        "total_content_chars": content_chars,
        "question_count": len(questions),
        "engine": engine,
    }
    if generator_mode == "course_context_fallback":
        debug["context_material_ids_used"] = context_material_ids
        debug["context_material_titles_used"] = context_material_titles
        debug["reason"] = context_reason

    return {
        "courseId": course_id,
        "materialIds": material_ids,
        "questions": questions,
        "engine": engine,
        "generatorMode": generator_mode,
        "debug": debug,
    }

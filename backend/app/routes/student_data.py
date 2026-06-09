# backend/app/routes/student_data.py
"""
Student-facing data endpoints consumed by the Next.js frontend
(front-end/src/lib/api.ts). All are scoped to the authenticated student via
JWT Bearer tokens or legacy session cookies (get_current_user), and read the
real normalized MongoDB collections.

Paths intentionally have NO /api prefix to match the frontend's api.ts calls
(/courses, /dashboard, /courses/{id}/performance, ...).
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.repositories import material_repository
from app.services import quiz_gen, student_data

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
    Generate a quiz from the selected materials' stored text (uploaded by the
    extension via POST /materials/content). Falls back to a clear placeholder
    question when no content/generator is available, so the UI never breaks.
    """
    material_ids: List[str] = body.get("materialIds", []) or []
    text = material_repository.get_content(course_id, material_ids)

    questions: List[Dict[str, Any]] = []
    if text and quiz_gen.available():
        try:
            questions = quiz_gen.generate_from_text(text, num_questions=8)
        except Exception:
            questions = []

    if not questions:
        reason = (
            "No question could be generated — the selected materials have no "
            "uploaded text yet. In the extension, run the materials upload so "
            "the PDFs' text reaches the backend, then try again."
            if not text else
            "The selected materials' text didn't yield enough structured "
            "concepts for question generation. Try different/〈more〉 materials."
        )
        questions = [{
            "id": "placeholder",
            "question": reason,
            "options": ["Understood", "OK", "Got it", "Retry later"],
            "correctIndex": 0,
        }]

    return {"courseId": course_id, "materialIds": material_ids, "questions": questions}

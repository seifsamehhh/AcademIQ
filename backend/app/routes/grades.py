"""Grade manual upload API."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.repositories.uploaded_grade_repository import LABEL_UPLOADED, upsert_record

router = APIRouter(tags=["Grades"])


class ManualGradePayload(BaseModel):
    course_id: str
    course_name: str = ""
    grade_percentage: float = Field(..., ge=0, le=100)


class BulkGradePayload(BaseModel):
    grades: List[ManualGradePayload]


@router.post("/grades/manual-upsert")
def manual_grade_upsert(
    payload: ManualGradePayload,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Store an uploaded grade transcript row for the authenticated user."""
    email = (user.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="User email is required.")
    user_id = str(user["_id"])
    doc = upsert_record(
        academiq_user_id=user_id,
        user_email=email,
        course_id=payload.course_id,
        course_name=payload.course_name,
        grade_percentage=payload.grade_percentage,
        created_by=email,
    )
    return {
        "ok": True,
        "courseId": doc["course_id"],
        "gradePercentage": doc["grade_percentage"],
        "gradeLabel": LABEL_UPLOADED,
        "source": doc["source"],
    }


@router.post("/grades/bulk-upsert")
def bulk_grade_upsert(
    payload: BulkGradePayload,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Bulk uploaded grade transcript rows for the authenticated user."""
    email = (user.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="User email is required.")
    user_id = str(user["_id"])
    saved: List[Dict[str, Any]] = []
    for row in payload.grades:
        doc = upsert_record(
            academiq_user_id=user_id,
            user_email=email,
            course_id=row.course_id,
            course_name=row.course_name,
            grade_percentage=row.grade_percentage,
            created_by=email,
        )
        saved.append(
            {
                "courseId": doc["course_id"],
                "gradePercentage": doc["grade_percentage"],
            }
        )
    return {"ok": True, "count": len(saved), "grades": saved}

"""Grade manual upload API."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.repositories.uploaded_grade_repository import LABEL_MIDTERM, upsert_record
from app.repositories.uploaded_transcript_repository import (
    LABEL_OFFICIAL,
    upsert_official_transcript,
)

router = APIRouter(tags=["Grades"])


class OfficialTranscriptPayload(BaseModel):
    official_cumulative_gpa: float = Field(..., ge=0, le=4)
    qualified_hours: float = Field(..., ge=0)
    qualified_points: float = Field(..., ge=0)
    transcript_label: str = LABEL_OFFICIAL


class ManualGradePayload(BaseModel):
    course_id: str
    course_name: str = ""
    grade_percentage: float = Field(..., ge=0, le=100)
    grade_label: str = LABEL_MIDTERM


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
        grade_label=payload.grade_label,
    )
    return {
        "ok": True,
        "courseId": doc["course_id"],
        "gradePercentage": doc["grade_percentage"],
        "gradeLabel": doc.get("grade_label") or LABEL_MIDTERM,
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
            grade_label=row.grade_label,
        )
        saved.append(
            {
                "courseId": doc["course_id"],
                "gradePercentage": doc["grade_percentage"],
            }
        )
    return {"ok": True, "count": len(saved), "grades": saved}


@router.post("/transcript/official-upsert")
def official_transcript_upsert(
    payload: OfficialTranscriptPayload,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Store official cumulative transcript summary for the authenticated user.

    Future: replace manual entry with parsed transcript upload (Cum GPA, Qul. Hrs, Qul.Points).
    """
    email = (user.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="User email is required.")
    user_id = str(user["_id"])
    doc = upsert_official_transcript(
        academiq_user_id=user_id,
        user_email=email,
        official_cumulative_gpa=payload.official_cumulative_gpa,
        qualified_hours=payload.qualified_hours,
        qualified_points=payload.qualified_points,
        created_by=email,
        transcript_label=payload.transcript_label,
    )
    return {
        "ok": True,
        "officialCumulativeGpa": doc["official_cumulative_gpa"],
        "qualifiedHours": doc["qualified_hours"],
        "qualifiedPoints": doc["qualified_points"],
        "transcriptLabel": doc.get("transcript_label") or LABEL_OFFICIAL,
        "source": doc["source"],
    }

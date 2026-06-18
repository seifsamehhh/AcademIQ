"""Uploaded / manual grade transcript records (when Moodle does not publish grades)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.config.database import connect_database, uploaded_grade_records_collection

SOURCE_UPLOADED = "uploaded_transcript"
LABEL_UPLOADED = "Uploaded grade transcript"
LABEL_MIDTERM = "Midterm scoring"


def _ensure():
    connect_database()
    if uploaded_grade_records_collection is None:
        raise RuntimeError("Database unavailable")


def upsert_record(
    *,
    academiq_user_id: str,
    user_email: str,
    course_id: str,
    course_name: str,
    grade_percentage: float,
    created_by: str,
    grade_label: Optional[str] = None,
) -> Dict[str, Any]:
    _ensure()
    now = datetime.utcnow()
    pct = round(float(grade_percentage), 2)
    if pct < 0 or pct > 100:
        raise ValueError("grade_percentage must be between 0 and 100")

    label = (grade_label or "").strip() or LABEL_UPLOADED

    doc = {
        "academiq_user_id": academiq_user_id,
        "user_email": user_email.strip().lower(),
        "course_id": str(course_id).strip(),
        "course_name": (course_name or "").strip(),
        "grade_percentage": pct,
        "grade_label": label,
        "source": SOURCE_UPLOADED,
        "uploaded_at": now,
        "created_by": created_by,
        "updated_at": now,
    }
    uploaded_grade_records_collection.update_one(
        {"academiq_user_id": academiq_user_id, "course_id": doc["course_id"]},
        {"$set": doc, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    return doc


def list_for_user(academiq_user_id: str) -> List[Dict[str, Any]]:
    _ensure()
    return list(
        uploaded_grade_records_collection.find({"academiq_user_id": academiq_user_id})
    )


def map_by_course_id(academiq_user_id: str) -> Dict[str, Dict[str, Any]]:
    rows = list_for_user(academiq_user_id)
    out: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        cid = str(row.get("course_id") or "").strip()
        if cid:
            out[cid] = row
    return out


def get_for_course(academiq_user_id: str, course_id: str) -> Optional[Dict[str, Any]]:
    _ensure()
    return uploaded_grade_records_collection.find_one(
        {
            "academiq_user_id": academiq_user_id,
            "course_id": str(course_id).strip(),
        }
    )

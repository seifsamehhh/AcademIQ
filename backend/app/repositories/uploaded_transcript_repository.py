"""Official cumulative transcript summary (separate from per-course midterm records)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from app.config.database import connect_database, uploaded_transcript_records_collection

SOURCE_OFFICIAL = "uploaded_official_transcript"
LABEL_OFFICIAL = "Uploaded official transcript"

# Demo account — known official transcript values for presentation.
_DEMO_TRANSCRIPT_EMAIL = "seif2200957@miuegypt.edu.eg"
_DEMO_OFFICIAL_GPA = 2.35
_DEMO_QUALIFIED_HOURS = 112.0
_DEMO_QUALIFIED_POINTS = 263.2


def _ensure():
    connect_database()
    if uploaded_transcript_records_collection is None:
        raise RuntimeError("Database unavailable")


def upsert_official_transcript(
    *,
    academiq_user_id: str,
    user_email: str,
    official_cumulative_gpa: float,
    qualified_hours: float,
    qualified_points: float,
    created_by: str,
    transcript_label: Optional[str] = None,
) -> Dict[str, Any]:
    _ensure()
    now = datetime.utcnow()
    gpa = round(float(official_cumulative_gpa), 2)
    hours = round(float(qualified_hours), 2)
    points = round(float(qualified_points), 2)
    if gpa < 0 or gpa > 4.0:
        raise ValueError("official_cumulative_gpa must be between 0 and 4.0")

    label = (transcript_label or "").strip() or LABEL_OFFICIAL
    doc = {
        "academiq_user_id": academiq_user_id,
        "user_email": user_email.strip().lower(),
        "official_cumulative_gpa": gpa,
        "qualified_hours": hours,
        "qualified_points": points,
        "source": SOURCE_OFFICIAL,
        "transcript_label": label,
        "uploaded_at": now,
        "created_by": created_by,
        "updated_at": now,
        # Future file-upload parse fields (Cum GPA, Qul. Hrs, Qul.Points).
        "parse_ready": False,
    }
    uploaded_transcript_records_collection.update_one(
        {"academiq_user_id": academiq_user_id},
        {"$set": doc, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    return doc


def get_for_user(academiq_user_id: str) -> Optional[Dict[str, Any]]:
    _ensure()
    return uploaded_transcript_records_collection.find_one(
        {"academiq_user_id": academiq_user_id}
    )


def ensure_demo_official_transcript(
    academiq_user_id: str,
    user_email: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Seed known demo transcript once when missing."""
    email = (user_email or "").strip().lower()
    if email != _DEMO_TRANSCRIPT_EMAIL:
        return get_for_user(academiq_user_id)
    existing = get_for_user(academiq_user_id)
    if existing:
        return existing
    return upsert_official_transcript(
        academiq_user_id=academiq_user_id,
        user_email=email,
        official_cumulative_gpa=_DEMO_OFFICIAL_GPA,
        qualified_hours=_DEMO_QUALIFIED_HOURS,
        qualified_points=_DEMO_QUALIFIED_POINTS,
        created_by=email,
        transcript_label=LABEL_OFFICIAL,
    )

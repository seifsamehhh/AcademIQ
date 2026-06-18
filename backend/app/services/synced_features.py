"""
Build per-course behavioural feature vectors from a Moodle sync payload.

Used during ingestion so Performance Analysis can call the ML service per course
without changing the external ML service API.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Tuple

from app.services.moodle_ingest import is_real_course, materials_from_payload

PERFORMANCE_V4_KEYS = (
    "all_clicks",
    "active_days",
    "access_frequency",
    "material_clicks",
    "quiz_attempts",
    "assignment_submissions",
    "total_time_spent",
    "procrastination_index",
    "late_submission_count",
)


def _parse_moodle_date(value: Any) -> datetime | None:
    from app.services.preprocessing import parse_moodle_date

    return parse_moodle_date(value)


def compute_course_late_procrastination(
    payload: Dict[str, Any], course_id: str
) -> Tuple[int, float]:
    """Late assignments and procrastination index scoped to one course."""
    cid = str(course_id)
    late = 0
    total_assignments = 0
    now = datetime.now()

    for material in materials_from_payload(payload):
        mat_cid = str(material.get("course_id") or material.get("courseId") or "")
        if mat_cid != cid:
            continue
        tags = {str(t).lower() for t in (material.get("semantic_tags") or [])}
        mtype = str(material.get("material_type") or material.get("type") or "").lower()
        if "assignment" not in tags and mtype != "assignment":
            continue
        total_assignments += 1
        due_date_str = material.get("due_date")
        if due_date_str:
            due = _parse_moodle_date(due_date_str)
            if due and due < now:
                late += 1

    procrastination = (late / total_assignments * 10.0) if total_assignments else 0.0
    return late, round(procrastination, 2)


def build_synced_course_features(
    payload: Dict[str, Any], overall_features: Dict[str, Any]
) -> Dict[str, Dict[str, Any]]:
    """Map metricsByCourse (+ behaviour fallbacks) to ML v4 course_features keys."""
    behavior = payload.get("behavior") or {}
    metrics_by_course = dict(payload.get("metricsByCourse") or {})

    if not metrics_by_course:
        for course in payload.get("courses") or []:
            cid = course.get("course_id")
            if cid:
                metrics_by_course[str(cid)] = course

    overall_active = int(behavior.get("active_days_count") or overall_features.get("active_days") or 0)

    result: Dict[str, Dict[str, Any]] = {}
    for course_id, metrics in metrics_by_course.items():
        if not is_real_course(course_id, (metrics or {}).get("course_name")):
            continue
        m = metrics or {}
        active_days = int(m.get("active_days_count") or overall_active or 0)
        visits = int(m.get("total_visits") or 0)
        clicks = int(m.get("click_count") or 0)
        access_frequency = float(visits / active_days) if active_days > 0 else 0.0
        late, procrastination = compute_course_late_procrastination(payload, str(course_id))

        vector = {
            "all_clicks": clicks,
            "active_days": active_days,
            "access_frequency": access_frequency,
            "material_clicks": int(m.get("number_of_resources_clicked") or 0),
            "quiz_attempts": int(m.get("quiz_attempts") or 0),
            "assignment_submissions": int(m.get("assignment_submissions") or 0),
            "total_time_spent": int(m.get("total_time_spent_seconds") or 0),
            "procrastination_index": procrastination,
            "late_submission_count": late,
            "course_id": str(course_id),
            "feature_source": "synced",
        }
        result[str(course_id)] = {k: vector[k] for k in PERFORMANCE_V4_KEYS if k in vector}
        result[str(course_id)]["course_id"] = str(course_id)
        result[str(course_id)]["feature_source"] = "synced"

    return result

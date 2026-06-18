"""
Per-course data foundation audit — grades, uploaded transcripts, features, ML modes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.repositories import user_repository
from app.repositories.uploaded_grade_repository import map_by_course_id
from app.services.moodle_course_display import get_visible_synced_courses_for_user
from app.services.student_data import (
    _apply_course_scoped_behavioral_features,
    _derive_performance_mode,
    _grades,
    _has_ml_feature_data,
    _is_feature_vector_complete,
    _resolve_display_grade_for_course,
    _run_ml_prediction,
    _task_breakdown,
)
from app.repositories import metrics_repository


def audit_data_foundation_for_email(email: str) -> Dict[str, Any]:
    user = user_repository.find_by_email(email.strip().lower())
    if not user:
        return {"email": email, "found": False, "courses": []}

    user_id = str(user["_id"])
    student_id = user.get("student_id")
    grade_rows = _grades(user_id)
    uploaded_by_course = map_by_course_id(user_id)

    courses_out: List[Dict[str, Any]] = []
    for course in get_visible_synced_courses_for_user(user_id):
        cid = str(course["id"])
        cname = course.get("name")
        uploaded = uploaded_by_course.get(cid)
        resolved = _resolve_display_grade_for_course(
            user_id, cid, cname, grade_rows, uploaded
        )
        metrics = (metrics_repository.get(user_id, cid) or {}).get("metrics", {}) or {}
        feats, feat_debug = resolve_course_features(user_id, cid, student_id)
        feats = _apply_course_scoped_behavioral_features(user_id, cid, feats, feat_debug)
        fv_complete = _is_feature_vector_complete(feats, feat_debug, metrics, resolved)
        ml_bundle = _run_ml_prediction(
            user_id,
            cid,
            student_id,
            feats,
            feat_debug,
            metrics,
            resolved,
            include_debug=True,
        )
        mode = _derive_performance_mode(ml_bundle, resolved, feats, feat_debug, metrics)

        moodle_grade = resolved.get("moodleGrade")
        uploaded_grade = resolved.get("uploadedGrade")
        if uploaded_grade is None and uploaded:
            raw = uploaded.get("grade_percentage")
            if isinstance(raw, (int, float)):
                uploaded_grade = round(float(raw), 1)

        courses_out.append(
            {
                "course_id": cid,
                "course_name": cname,
                "moodle_grade": moodle_grade,
                "uploaded_grade": uploaded_grade,
                "resolved_display_grade": resolved.get("displayGrade"),
                "grade_source": resolved.get("gradeSource"),
                "grade_label": resolved.get("gradeLabel"),
                "feature_vector_exists": bool(feats) and feat_debug.get("document_found"),
                "feature_vector_complete": fv_complete,
                "feature_vector_source": feat_debug.get("feature_source"),
                "used_overall_synced_fallback": bool(feat_debug.get("used_overall_synced")),
                "ml_prediction_available": ml_bundle.get("predictionVerified"),
                "ml_prediction_value": ml_bundle.get("predictedGrade"),
                "performance_mode": mode,
                "reason": ml_bundle.get("reason") or resolved.get("gradeNote"),
                "feature_fields": {
                    k: feats.get(k)
                    for k in (
                        "quiz_attempts",
                        "assignment_submissions",
                        "active_days",
                        "late_submission_count",
                        "procrastination_index",
                        "total_time_spent",
                    )
                },
            }
        )

    graded = [
        c["resolved_display_grade"]
        for c in courses_out
        if c.get("resolved_display_grade") is not None
    ]
    gpa_available = len(graded) >= 2

    return {
        "email": email,
        "found": True,
        "academiq_user_id": user_id,
        "student_id": student_id,
        "uploaded_grade_count": len(uploaded_by_course),
        "gpa_available": gpa_available,
        "courses": courses_out,
    }

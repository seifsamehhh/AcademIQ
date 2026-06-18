"""
Performance feature audit — per-course ML inputs, sources, and trust eligibility.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from app.repositories import metrics_repository, user_repository
from app.repositories.uploaded_grade_repository import get_for_course
from app.services.feature_vector_lookup import find_feature_vector_doc, resolve_course_features
from app.services.grade_resolution import resolve_course_grade
from app.services.ml_service_client import PERFORMANCE_FEATURE_KEYS, build_performance_payload
from app.services.moodle_course_display import get_visible_synced_courses_for_user
from app.services.performance_feature_schema import (
    ML_BEHAVIORAL_FEATURES,
    ML_FEATURE_NAMES,
    RULE_ONLY_FEATURES,
)
from app.services.performance_feature_trust import (
    build_feature_trust_context,
    derive_performance_mode_from_trust,
)
from app.services.student_data import (
    _apply_course_scoped_behavioral_features,
    _data_backed_heuristic_factors,
    _grades,
    _resolve_display_grade_for_course,
    _run_ml_prediction,
)

_AUDIT_COURSE_IDS_DEFAULT = ("666", "808", "478", "670", "462", "669")


def _global_late_proc_fingerprint(doc: Optional[Dict[str, Any]]) -> Tuple[Optional[int], Optional[float]]:
    if not doc:
        return None, None
    overall = doc.get("features") or {}
    return (
        overall.get("late_submission_count"),
        overall.get("procrastination_index"),
    )


def _stored_late_proc_same_across_courses(doc: Optional[Dict[str, Any]]) -> bool:
    if not doc:
        return False
    by_course = doc.get("course_features") or {}
    late_vals: Set[Any] = set()
    proc_vals: Set[Any] = set()
    for _cid, vec in by_course.items():
        if not vec:
            continue
        late_vals.add(vec.get("late_submission_count"))
        proc_vals.add(vec.get("procrastination_index"))
    return len(late_vals) == 1 and len(proc_vals) == 1 and len(by_course) > 1


def audit_performance_features_for_email(
    email: str,
    course_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    user = user_repository.find_by_email(email.strip().lower())
    if not user:
        return {"email": email, "found": False, "courses": [], "schema": _schema_export()}

    user_id = str(user["_id"])
    student_id = user.get("student_id")
    grade_rows = _grades(user_id)
    fv_doc, _matched = find_feature_vector_doc(user_id, student_id)
    global_late_proc_copied = _stored_late_proc_same_across_courses(fv_doc)
    global_late, global_proc = _global_late_proc_fingerprint(fv_doc)

    target_ids = set(course_ids or _AUDIT_COURSE_IDS_DEFAULT)
    courses_out: List[Dict[str, Any]] = []
    all_feature_rows: List[Dict[str, Any]] = []

    visible = get_visible_synced_courses_for_user(user_id)
    visible_by_id = {str(c["id"]): c for c in visible}

    for cid in sorted(target_ids, key=lambda x: int(x) if x.isdigit() else x):
        course_meta = visible_by_id.get(cid, {})
        cname = course_meta.get("name") or f"Course {cid}"
        uploaded = get_for_course(user_id, cid)
        resolved = resolve_course_grade(grade_rows, cid, cname, uploaded)

        metrics = (metrics_repository.get(user_id, cid) or {}).get("metrics", {}) or {}
        raw_feats, feat_debug = resolve_course_features(user_id, cid, student_id)
        overlay_feats = _apply_course_scoped_behavioral_features(
            user_id, cid, dict(raw_feats), feat_debug
        )

        trust_context = build_feature_trust_context(
            user_id,
            cid,
            student_id,
            overlay_feats,
            raw_feats,
            feat_debug,
            metrics,
            resolved,
        )
        stored_course_feats = trust_context["stored_course_feats"]
        feature_rows: List[Dict[str, Any]] = []
        for spec in ML_BEHAVIORAL_FEATURES:
            base = next(
                f
                for f in trust_context["feature_rows"]
                if f["feature_name"] == spec["feature_name"]
            )
            row = dict(base)
            row.update(
                {
                    "expected_type": spec["expected_type"],
                    "required_for_ml": spec["required_for_ml"],
                    "used_by_model": spec["used_by_model"],
                    "used_by_rule_based_insights": spec["used_by_rule_based_insights"],
                    "course_id": cid,
                    "course_name": cname,
                }
            )
            feature_rows.append(row)

        resolved_display = _resolve_display_grade_for_course(
            user_id, cid, cname, grade_rows=grade_rows, uploaded=uploaded
        )
        ml_bundle = _run_ml_prediction(
            user_id,
            cid,
            student_id,
            overlay_feats,
            feat_debug,
            metrics,
            resolved_display,
            include_debug=True,
            raw_feats=raw_feats,
        )
        factors = _data_backed_heuristic_factors(overlay_feats, metrics, feat_debug)
        performance_mode = derive_performance_mode_from_trust(
            ml_bundle.get("predictionVerified"),
            resolved_display,
            feat_debug,
            trust_context,
            overlay_feats,
            metrics,
            bool(factors),
        )
        eligible = bool(ml_bundle.get("predictionVerified"))
        eligibility_reason = (
            ml_bundle.get("reason")
            or (
                "ML prediction verified with trusted per-course inputs."
                if eligible
                else "Numeric ML prediction withheld by trust rules."
            )
        )

        trusted_count = sum(1 for f in feature_rows if f.get("is_trusted_for_ml"))
        missing_count = sum(1 for f in feature_rows if f.get("is_missing"))
        global_fb_count = sum(1 for f in feature_rows if f.get("is_global_fallback"))
        default_zero_count = sum(1 for f in feature_rows if f.get("is_default_zero"))

        ml_payload = build_performance_payload(overlay_feats)

        courses_out.append(
            {
                "course_id": cid,
                "course_name": cname,
                "resolved_grade": resolved_display.get("displayGrade"),
                "grade_source": resolved_display.get("gradeSource"),
                "grade_label": resolved_display.get("gradeLabel"),
                "feature_vector_exists": bool(overlay_feats) and feat_debug.get("document_found"),
                "feature_vector_source": feat_debug.get("feature_source"),
                "used_overall_synced_fallback": bool(feat_debug.get("used_overall_synced")),
                "trusted_feature_count": trusted_count,
                "missing_feature_count": missing_count,
                "global_fallback_count": global_fb_count,
                "default_zero_count": default_zero_count,
                "eligible_for_ml_prediction": eligible,
                "ml_prediction_verified": ml_bundle.get("predictionVerified"),
                "ml_prediction_value": ml_bundle.get("predictedGrade"),
                "performance_mode": performance_mode,
                "reason": eligibility_reason if not eligible else ml_bundle.get("reason"),
                "eligibility_reason": eligibility_reason,
                "ml_service_payload_features": ml_payload.get("features"),
                "stored_course_vector": {
                    k: stored_course_feats.get(k)
                    for k in ML_FEATURE_NAMES
                    if k in stored_course_feats
                },
                "features": feature_rows,
            }
        )
        all_feature_rows.extend(feature_rows)

    summary = {
        "courses_count": len(courses_out),
        "courses_with_trusted_features": sum(
            1 for c in courses_out if c["trusted_feature_count"] > 0
        ),
        "courses_with_missing_features": sum(
            1 for c in courses_out if c["missing_feature_count"] > 0
        ),
        "courses_using_global_fallbacks": sum(
            1 for c in courses_out if c["global_fallback_count"] > 0
        ),
        "courses_with_default_zero_features": sum(
            1 for c in courses_out if c["default_zero_count"] > 0
        ),
        "courses_eligible_for_ml_prediction": sum(
            1 for c in courses_out if c["eligible_for_ml_prediction"]
        ),
        "courses_not_eligible_for_ml_prediction": sum(
            1 for c in courses_out if not c["eligible_for_ml_prediction"]
        ),
        "courses_ml_prediction_verified": sum(
            1 for c in courses_out if c["ml_prediction_verified"]
        ),
        "global_stored_late_submission_count": global_late,
        "global_stored_procrastination_index": global_proc,
        "global_late_proc_copied_to_all_stored_courses": global_late_proc_copied,
    }

    return {
        "email": email,
        "found": True,
        "academiq_user_id": user_id,
        "student_id": student_id,
        "schema": _schema_export(),
        "ml_service_feature_keys": list(PERFORMANCE_FEATURE_KEYS),
        "summary": summary,
        "courses": courses_out,
    }


def _schema_export() -> Dict[str, Any]:
    return {
        "ml_behavioral_features": ML_BEHAVIORAL_FEATURES,
        "rule_only_features": RULE_ONLY_FEATURES,
        "feature_vector_generation": {
            "source": "synced_features.build_synced_course_features",
            "keys": list(ML_FEATURE_NAMES),
        },
        "backend_performance_endpoint": {
            "path": "GET /courses/{course_id}/performance",
            "uses": list(ML_FEATURE_NAMES),
            "grade_resolution": "resolve_course_grade / midterm priority",
        },
        "ml_service_request": {
            "path": "POST {ML_SERVICE_URL}/predict/performance",
            "payload_shape": "features: {9 behavioural keys}",
            "keys": list(PERFORMANCE_FEATURE_KEYS),
            "default_on_missing": 0,
        },
        "frontend_performance_display": {
            "path": "GET /courses/{course_id}/performance",
            "fields": [
                "predictedGrade",
                "status",
                "courseAverage",
                "gradeLabel",
                "performanceMode",
                "classificationSource",
                "featureVectorSource",
                "featureVectorComplete",
                "statistics",
            ],
        },
    }

"""
Per-course ML feature trust assessment — shared by get_performance() and audits.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from app.services.feature_vector_lookup import find_feature_vector_doc
from app.services.performance_feature_schema import (
    ML_BEHAVIORAL_FEATURES,
    ML_FEATURE_NAMES,
    ML_MIN_TRUSTED_BEHAVIORAL,
)

LIMITED_INSIGHT_MESSAGE = (
    "Based on current grade records and available activity signals."
)
NOT_ENOUGH_DATA_MESSAGE = (
    "Not enough synced Moodle activity data is available for a reliable prediction yet."
)


def _course_vector_from_doc(doc: Optional[Dict[str, Any]], course_id: str) -> Dict[str, Any]:
    if not doc:
        return {}
    by_course = doc.get("course_features") or {}
    direct = by_course.get(course_id) or by_course.get(str(course_id))
    if direct:
        return dict(direct)
    try:
        as_int = by_course.get(int(course_id))
        if as_int:
            return dict(as_int)
    except (TypeError, ValueError):
        pass
    return {}


def _stored_value_same_across_courses(
    doc: Optional[Dict[str, Any]], field: str
) -> bool:
    if not doc:
        return False
    by_course = doc.get("course_features") or {}
    vals: Set[Any] = set()
    for vec in by_course.values():
        if not vec:
            continue
        vals.add(vec.get(field))
    return len(vals) == 1 and len(by_course) > 1


def _stored_late_proc_same_across_courses(doc: Optional[Dict[str, Any]]) -> bool:
    return (
        _stored_value_same_across_courses(doc, "late_submission_count")
        and _stored_value_same_across_courses(doc, "procrastination_index")
    )


def _stored_active_days_same_across_courses(doc: Optional[Dict[str, Any]]) -> bool:
    return _stored_value_same_across_courses(doc, "active_days")


def _metric_value(metrics: Dict[str, Any], metrics_key: Optional[str]) -> Optional[Any]:
    if not metrics_key:
        return None
    val = metrics.get(metrics_key)
    if val is None:
        return None
    return val


def assess_feature_trust(
    spec: Dict[str, Any],
    *,
    overlay_feats: Dict[str, Any],
    raw_feats: Dict[str, Any],
    stored_course_feats: Dict[str, Any],
    overall_feats: Dict[str, Any],
    metrics: Dict[str, Any],
    feat_debug: Dict[str, Any],
    resolved_grade: Dict[str, Any],
    global_late_proc_copied: bool,
    active_days_copied_across_courses: bool,
) -> Dict[str, Any]:
    name = spec["feature_name"]
    value = overlay_feats.get(name)
    if value is None and name in overlay_feats:
        value = overlay_feats[name]
    if value is None:
        raw_val = None
        is_missing = True
    else:
        raw_val = value
        is_missing = False

    feature_source = "unknown"
    is_per_course = False
    is_global_fallback = False
    is_default_zero = False
    is_trusted = False
    reason = ""

    if feat_debug.get("feature_source") == "seeded":
        feature_source = "seeded_demo"
        reason = "Seeded demo feature vector — not live Moodle sync."
    elif feat_debug.get("used_overall_synced"):
        feature_source = "global_overall_fallback"
        is_global_fallback = True
        reason = "Per-course vector missing; overall account features used."
    elif not feat_debug.get("course_vector_found"):
        feature_source = "missing_vector"
        is_missing = True
        reason = "No per-course feature vector in MongoDB."
    elif name == "active_days":
        metrics_active = metrics.get("active_days_count")
        stored_active = stored_course_feats.get("active_days")
        vector_active = raw_val
        if active_days_copied_across_courses and stored_active is not None:
            feature_source = "global_copied_stored_vector"
            is_global_fallback = True
            reason = "Stored active_days is identical across all courses."
        elif metrics_active is not None:
            mcmp = int(metrics_active or 0)
            vcmp = int(vector_active or 0)
            if vcmp == mcmp:
                feature_source = "per_course_metrics"
                is_per_course = True
                is_trusted = True
                reason = "Matches synced student_metrics active_days_count."
            else:
                feature_source = "per_course_vector_mismatch_metrics"
                is_per_course = True
                reason = f"Feature vector ({vcmp}) differs from metrics ({mcmp})."
        elif raw_val is not None and int(raw_val or 0) > 0:
            if active_days_copied_across_courses:
                feature_source = "global_copied_stored_vector"
                is_global_fallback = True
                reason = "Stored active_days is identical across all courses."
            else:
                feature_source = "per_course_stored_vector"
                is_per_course = True
                is_trusted = True
                reason = "Non-zero per-course stored active_days."
        else:
            feature_source = "per_course_metrics_zero"
            is_per_course = True
            is_default_zero = True
            is_trusted = True
            reason = "Zero active_days confirmed."
    elif name in ("late_submission_count", "procrastination_index"):
        raw_stored = stored_course_feats.get(name)
        overlay_val = overlay_feats.get(name)
        if overlay_val != raw_feats.get(name) or overlay_val != raw_stored:
            feature_source = "per_course_materials_read_time"
            is_per_course = True
            assign = int(
                overlay_feats.get("assignment_submissions")
                or metrics.get("assignment_submissions")
                or 0
            )
            if assign > 0 or (overlay_val or 0) > 0:
                is_trusted = True
                reason = "Recomputed per course from synced assignment due dates."
            else:
                is_trusted = overlay_val == 0
                reason = "Zero late/procrastination — no assignment activity in course."
        elif global_late_proc_copied and raw_stored == overall_feats.get(name):
            feature_source = "global_copied_stored_vector"
            is_global_fallback = True
            reason = "Stored vector copied account-wide late/procrastination to all courses."
        else:
            feature_source = "per_course_stored_vector"
            is_per_course = True
            assign = int(metrics.get("assignment_submissions") or 0)
            if (overlay_val or 0) == 0 and assign == 0:
                is_trusted = True
                reason = "Zero value confirmed — no assignment submissions."
            elif assign > 0:
                is_trusted = True
                reason = "Per-course stored vector with assignment activity."
            else:
                reason = "Stored per-course value without assignment activity confirmation."
    else:
        metrics_key = spec.get("metrics_key")
        mval = _metric_value(metrics, metrics_key)
        feat_int = int(raw_val or 0) if spec["expected_type"] == "int" else raw_val
        if mval is not None:
            mcmp = int(mval) if spec["expected_type"] == "int" else float(mval)
            if feat_int == mcmp or (
                spec["expected_type"] == "float" and float(raw_val or 0) == float(mval)
            ):
                feature_source = "per_course_metrics"
                is_per_course = True
                is_trusted = True
                reason = "Matches synced student_metrics for this course."
            elif (raw_val or 0) == 0 and (mval or 0) == 0:
                feature_source = "per_course_metrics_zero"
                is_per_course = True
                is_default_zero = True
                is_trusted = True
                reason = "Zero confirmed in metrics and feature vector."
            else:
                feature_source = "per_course_vector_mismatch_metrics"
                is_per_course = True
                reason = f"Feature vector ({raw_val}) differs from metrics ({mval})."
        elif name == "access_frequency":
            feature_source = "per_course_derived"
            is_per_course = True
            active_trusted = assess_feature_trust(
                next(s for s in ML_BEHAVIORAL_FEATURES if s["feature_name"] == "active_days"),
                overlay_feats=overlay_feats,
                raw_feats=raw_feats,
                stored_course_feats=stored_course_feats,
                overall_feats=overall_feats,
                metrics=metrics,
                feat_debug=feat_debug,
                resolved_grade=resolved_grade,
                global_late_proc_copied=global_late_proc_copied,
                active_days_copied_across_courses=active_days_copied_across_courses,
            )
            if active_trusted.get("is_trusted_for_ml") and int(overlay_feats.get("active_days") or 0) > 0:
                is_trusted = True
                reason = "Derived from per-course visits / trusted active_days."
            else:
                is_default_zero = (raw_val or 0) == 0
                reason = "Derived access_frequency without trusted active_days."
        elif raw_val is not None:
            feature_source = "per_course_stored_vector"
            is_per_course = True
            if (raw_val or 0) == 0:
                is_default_zero = True
                if resolved_grade.get("gradeAvailable"):
                    is_trusted = True
                    reason = "Zero activity feature; course has resolved grade signal."
                else:
                    reason = "Zero in stored vector without metrics confirmation."
            else:
                is_trusted = True
                reason = "Non-zero per-course stored vector value."

    if is_missing:
        raw_val = None
        is_trusted = False
        if not reason:
            reason = "Feature not present in resolved overlay vector."

    return {
        "feature_name": name,
        "feature_value": raw_val,
        "feature_source": feature_source,
        "is_per_course": is_per_course,
        "is_global_fallback": is_global_fallback,
        "is_default_zero": is_default_zero,
        "is_missing": is_missing,
        "is_trusted_for_ml": is_trusted,
        "reason_if_untrusted": reason if not is_trusted else None,
    }


def build_feature_trust_context(
    user_id: str,
    course_id: str,
    student_id: Optional[str],
    overlay_feats: Dict[str, Any],
    raw_feats: Dict[str, Any],
    feat_debug: Dict[str, Any],
    metrics: Dict[str, Any],
    resolved_grade: Dict[str, Any],
) -> Dict[str, Any]:
    fv_doc, _ = find_feature_vector_doc(user_id, student_id)
    overall_feats = (fv_doc or {}).get("features") or {}
    stored_course_feats = _course_vector_from_doc(fv_doc, course_id)
    global_late_proc_copied = _stored_late_proc_same_across_courses(fv_doc)
    active_days_copied = _stored_active_days_same_across_courses(fv_doc)

    rows: List[Dict[str, Any]] = []
    for spec in ML_BEHAVIORAL_FEATURES:
        rows.append(
            assess_feature_trust(
                spec,
                overlay_feats=overlay_feats,
                raw_feats=raw_feats,
                stored_course_feats=stored_course_feats,
                overall_feats=overall_feats,
                metrics=metrics,
                feat_debug=feat_debug,
                resolved_grade=resolved_grade,
                global_late_proc_copied=global_late_proc_copied,
                active_days_copied_across_courses=active_days_copied,
            )
        )

    trusted_nonzero_behavioral = [
        f
        for f in rows
        if f.get("is_trusted_for_ml")
        and f["feature_name"] != "access_frequency"
        and (f.get("feature_value") or 0) != 0
    ]
    active_days_row = next((f for f in rows if f["feature_name"] == "active_days"), None)
    active_days_untrusted = bool(
        active_days_row and not active_days_row.get("is_trusted_for_ml")
    )
    global_fallback_critical = any(
        f.get("is_global_fallback") and f.get("feature_name") in ML_FEATURE_NAMES
        for f in rows
    )

    return {
        "feature_rows": rows,
        "trusted_nonzero_behavioral_count": len(trusted_nonzero_behavioral),
        "active_days_untrusted": active_days_untrusted,
        "global_fallback_critical": global_fallback_critical,
        "fv_doc": fv_doc,
        "stored_course_feats": stored_course_feats,
        "global_late_proc_copied": global_late_proc_copied,
        "active_days_copied": active_days_copied,
    }


def _behavioral_zeros_dominant(overlay_feats: Dict[str, Any], trust_rows: List[Dict[str, Any]]) -> bool:
    """True when behavioural signal is mostly missing/zero defaults."""
    activity_keys = (
        "all_clicks",
        "active_days",
        "quiz_attempts",
        "assignment_submissions",
        "total_time_spent",
        "material_clicks",
    )
    trusted_nonzero = sum(
        1
        for f in trust_rows
        if f.get("is_trusted_for_ml")
        and f["feature_name"] in activity_keys
        and (f.get("feature_value") or 0) != 0
    )
    if trusted_nonzero >= ML_MIN_TRUSTED_BEHAVIORAL:
        return False
    raw_nonzero = sum(1 for k in activity_keys if (overlay_feats.get(k) or 0) != 0)
    return raw_nonzero <= 1


def is_numeric_ml_prediction_trustworthy(
    predicted: Optional[int],
    resolved_grade: Dict[str, Any],
    feat_debug: Dict[str, Any],
    trust_context: Dict[str, Any],
    overlay_feats: Dict[str, Any],
) -> Tuple[bool, Optional[str]]:
    if predicted is None:
        return False, "No model output."

    if feat_debug.get("used_overall_synced"):
        return False, "Overall account feature fallback — not per-course."

    if feat_debug.get("feature_source") != "synced":
        return False, "Feature source is not synced Moodle data."

    if not feat_debug.get("course_vector_found"):
        return False, "No per-course feature vector."

    if feat_debug.get("feature_source") == "seeded":
        return False, "Seeded demo features."

    if trust_context.get("global_fallback_critical"):
        return False, "Critical feature uses global/account fallback."

    if trust_context.get("active_days_untrusted"):
        return False, "active_days is untrusted (global copy or metrics mismatch)."

    trust_rows = trust_context.get("feature_rows") or []
    trusted_count = trust_context.get("trusted_nonzero_behavioral_count") or 0
    if trusted_count < ML_MIN_TRUSTED_BEHAVIORAL:
        return False, (
            f"Need at least {ML_MIN_TRUSTED_BEHAVIORAL} trusted non-zero behavioural features."
        )

    display = resolved_grade.get("displayGrade")
    has_grade = bool(resolved_grade.get("gradeAvailable"))

    if predicted <= 0 and has_grade:
        return False, "Prediction is zero while a resolved course grade exists."

    if display is not None and predicted <= 10 and float(display) >= 40:
        return False, "Prediction is inconsistent with resolved course grade."

    if predicted <= 0 and _behavioral_zeros_dominant(overlay_feats, trust_rows):
        return False, "Prediction is zero from mostly missing/default behavioural features."

    return True, None


def derive_performance_mode_from_trust(
    prediction_verified: bool,
    resolved_grade: Dict[str, Any],
    feat_debug: Dict[str, Any],
    trust_context: Dict[str, Any],
    overlay_feats: Dict[str, Any],
    metrics: Dict[str, Any],
    has_heuristic_factors: bool,
) -> str:
    if prediction_verified:
        return "ml_prediction"

    has_grade = bool(resolved_grade.get("gradeAvailable"))
    quiz = int(overlay_feats.get("quiz_attempts") or metrics.get("quiz_attempts") or 0)
    assign = int(
        overlay_feats.get("assignment_submissions") or metrics.get("assignment_submissions") or 0
    )
    time_spent = int(
        overlay_feats.get("total_time_spent") or metrics.get("total_time_spent_seconds") or 0
    )
    trusted_nonzero = trust_context.get("trusted_nonzero_behavioral_count") or 0

    if (
        has_grade
        or trusted_nonzero > 0
        or quiz > 0
        or assign > 0
        or time_spent > 0
        or has_heuristic_factors
    ):
        return "limited_insight"

    if feat_debug.get("feature_source") == "synced" and feat_debug.get("course_vector_found"):
        if has_grade or quiz > 0 or assign > 0:
            return "limited_insight"

    return "not_enough_data"

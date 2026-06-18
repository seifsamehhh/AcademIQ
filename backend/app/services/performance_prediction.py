"""
Course performance prediction — ML + rule-adjusted fallback with confidence tiers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.services.ml_service_client import ml_service_configured, predict_performance_remote
from app.services.performance_feature_schema import ML_MIN_TRUSTED_BEHAVIORAL
from app.services.performance_feature_trust import (
    LIMITED_INSIGHT_MESSAGE,
    NOT_ENOUGH_DATA_MESSAGE,
    build_feature_trust_context,
    is_numeric_ml_prediction_trustworthy,
)

ML_SOURCE_LABEL = "ML prediction based on synced Moodle activity features"
RULE_ADJUSTED_LABEL = (
    "Prediction based on current grade records and limited synced activity features"
)
LIMITED_CONFIDENCE_NOTE = (
    "Prediction uses available grade records and limited synced activity features."
)

HIGH_ACTIVITY_SIGNAL_THRESHOLD = 3
LIMITED_ACTIVITY_SIGNAL_THRESHOLD = 1


def _effective_active_days(
    overlay_feats: Dict[str, Any],
    metrics: Dict[str, Any],
    trust_context: Dict[str, Any],
) -> int:
    if trust_context.get("active_days_untrusted"):
        return int(metrics.get("active_days_count") or 0)
    return int(overlay_feats.get("active_days") or 0)


def _activity_signal_count(
    overlay_feats: Dict[str, Any],
    metrics: Dict[str, Any],
    trust_context: Dict[str, Any],
) -> int:
    active = _effective_active_days(overlay_feats, metrics, trust_context)
    signals = 0
    if int(overlay_feats.get("all_clicks") or 0) > 0:
        signals += 1
    if int(overlay_feats.get("material_clicks") or metrics.get("number_of_resources_clicked") or 0) > 0:
        signals += 1
    if int(overlay_feats.get("quiz_attempts") or metrics.get("quiz_attempts") or 0) > 0:
        signals += 1
    if int(overlay_feats.get("assignment_submissions") or metrics.get("assignment_submissions") or 0) > 0:
        signals += 1
    if int(overlay_feats.get("total_time_spent") or metrics.get("total_time_spent_seconds") or 0) > 0:
        signals += 1
    if active > 0:
        signals += 1
    return signals


def assess_prediction_confidence(
    resolved_grade: Dict[str, Any],
    feat_debug: Dict[str, Any],
    trust_context: Dict[str, Any],
    overlay_feats: Dict[str, Any],
    metrics: Dict[str, Any],
) -> str:
    """Return high | limited | not_enough_data."""
    has_grade = bool(resolved_grade.get("gradeAvailable"))
    activity_signals = _activity_signal_count(overlay_feats, metrics, trust_context)
    is_seeded = feat_debug.get("feature_source") == "seeded"

    if is_seeded and _has_ml_feature_data(overlay_feats):
        if has_grade and activity_signals >= LIMITED_ACTIVITY_SIGNAL_THRESHOLD:
            return "high"
        if has_grade or activity_signals >= HIGH_ACTIVITY_SIGNAL_THRESHOLD:
            return "limited"
        return "not_enough_data" if activity_signals == 0 and not has_grade else "limited"

    if not has_grade and activity_signals < LIMITED_ACTIVITY_SIGNAL_THRESHOLD:
        return "not_enough_data"

    trusted_nonzero = trust_context.get("trusted_nonzero_behavioral_count") or 0
    if has_grade and (
        activity_signals >= HIGH_ACTIVITY_SIGNAL_THRESHOLD
        or trusted_nonzero >= ML_MIN_TRUSTED_BEHAVIORAL + 1
    ):
        return "high"

    if has_grade and activity_signals >= LIMITED_ACTIVITY_SIGNAL_THRESHOLD:
        return "limited"

    if has_grade:
        return "limited"

    if activity_signals >= HIGH_ACTIVITY_SIGNAL_THRESHOLD:
        return "limited"

    return "not_enough_data"


def _has_ml_feature_data(features: Dict[str, Any]) -> bool:
    if not features:
        return False
    keys = (
        "all_clicks",
        "active_days",
        "quiz_attempts",
        "assignment_submissions",
        "total_time_spent",
        "material_clicks",
    )
    return any((features.get(k) or 0) > 0 for k in keys)


def is_ml_output_usable(
    predicted: Optional[int],
    resolved_grade: Dict[str, Any],
) -> bool:
    if predicted is None or predicted <= 0:
        return False
    display = resolved_grade.get("displayGrade")
    if display is not None and predicted <= 10 and float(display) >= 30:
        return False
    return True


def status_from_predicted_grade(predicted: int, confidence: str) -> str:
    if predicted < 50:
        label = "At Risk"
    elif predicted < 70:
        label = "Room to improve"
    else:
        label = "On Track"
    if confidence == "limited":
        return label
    return label


def status_note_for_confidence(confidence: str) -> Optional[str]:
    if confidence == "limited":
        return "Status based on limited available data."
    return None


def compute_rule_adjusted_prediction(
    resolved_grade: Dict[str, Any],
    overlay_feats: Dict[str, Any],
    metrics: Dict[str, Any],
    trust_context: Dict[str, Any],
) -> Optional[int]:
    if not resolved_grade.get("gradeAvailable"):
        return None
    display = resolved_grade.get("displayGrade")
    if display is None:
        return None

    base = float(display)
    adj = base

    active = _effective_active_days(overlay_feats, metrics, trust_context)
    material = int(
        overlay_feats.get("material_clicks")
        or metrics.get("number_of_resources_clicked")
        or 0
    )
    clicks = int(overlay_feats.get("all_clicks") or 0)
    time_spent = int(
        overlay_feats.get("total_time_spent") or metrics.get("total_time_spent_seconds") or 0
    )
    quiz = int(overlay_feats.get("quiz_attempts") or metrics.get("quiz_attempts") or 0)
    assign = int(
        overlay_feats.get("assignment_submissions") or metrics.get("assignment_submissions") or 0
    )
    late = int(overlay_feats.get("late_submission_count") or 0)
    proc = float(overlay_feats.get("procrastination_index") or 0)
    access_freq = float(overlay_feats.get("access_frequency") or 0)

    if active < 5:
        adj -= 8
    elif active < 10:
        adj -= 4
    if material == 0 and clicks < 3:
        adj -= 5
    if time_spent < 60:
        adj -= 6
    elif time_spent < 600:
        adj -= 3
    if quiz == 0:
        adj -= 4
    if assign == 0:
        adj -= 3
    if late > 0:
        adj -= min(12, late * 4)
    if proc >= 5:
        adj -= 8
    elif proc >= 3:
        adj -= 4

    if active >= 10:
        adj += 3
    if quiz >= 2:
        adj += 4
    if assign >= 1:
        adj += 3
    if access_freq >= 1.0:
        adj += 2
    if material >= 5:
        adj += 2

    return max(0, min(100, round(adj)))


def _invoke_ml_model(
    feats: Dict[str, Any],
    stack_predict_fn,
    stack_predict_grade_fn,
    stack_available_fn,
) -> Dict[str, Any]:
    predicted: Optional[int] = None
    status: Optional[str] = None
    probability: Optional[float] = None
    confidence: Optional[float] = None
    prediction_source: Optional[str] = None
    ml_service_called = False
    ml_service_response: Optional[Dict[str, Any]] = None
    used_model = False

    if ml_service_configured():
        ml_service_called = True
        remote = predict_performance_remote(feats)
        if remote:
            ml_service_response = {
                "predictedGrade": remote.get("predictedGrade"),
                "status": remote.get("status"),
                "probability": remote.get("probability"),
                "engine": remote.get("engine"),
            }
            used_model = True
            prediction_source = "ml_service"
            raw_pred = remote.get("predictedGrade")
            if raw_pred is not None:
                predicted = int(round(float(raw_pred)))
            status = remote.get("status")
            probability = remote.get("probability")
            confidence = remote.get("confidence")
    elif stack_available_fn():
        perf = stack_predict_fn(feats)
        grade_pred = stack_predict_grade_fn(feats)
        if perf or grade_pred:
            used_model = True
            prediction_source = "local_ml"
            if grade_pred and grade_pred.get("predicted_grade") is not None:
                predicted = round(grade_pred["predicted_grade"])
            elif perf:
                predicted = round((perf.get("probability", 0) or 0) * 100)
            if perf:
                prob = perf.get("probability", 0) or 0
                probability = prob
                confidence = round(prob * 100, 1)
            elif predicted is not None:
                status = status_from_predicted_grade(predicted, "high")

    return {
        "predictedGrade": predicted,
        "status": status,
        "probability": probability,
        "confidence": confidence,
        "predictionSource": prediction_source,
        "mlServiceCalled": ml_service_called,
        "mlServiceResponse": ml_service_response,
        "usedModel": used_model,
    }


def resolve_course_performance(
    user_id: str,
    course_id: str,
    student_id: Optional[str],
    overlay_feats: Dict[str, Any],
    raw_feats: Dict[str, Any],
    feat_debug: Dict[str, Any],
    metrics: Dict[str, Any],
    resolved_grade: Dict[str, Any],
    *,
    stack_predict_fn,
    stack_predict_grade_fn,
    stack_available_fn,
    can_attempt_fn,
    include_debug: bool = False,
) -> Dict[str, Any]:
    trust_context = build_feature_trust_context(
        user_id,
        course_id,
        student_id,
        overlay_feats,
        raw_feats,
        feat_debug,
        metrics,
        resolved_grade,
    )

    confidence_level = assess_prediction_confidence(
        resolved_grade, feat_debug, trust_context, overlay_feats, metrics
    )

    empty: Dict[str, Any] = {
        "predictedGrade": None,
        "status": None,
        "probability": None,
        "confidence": None,
        "predictionVerified": False,
        "predictionSource": None,
        "predictionConfidence": None,
        "performanceMode": "not_enough_data",
        "classificationSource": None,
        "message": NOT_ENOUGH_DATA_MESSAGE,
        "mlServiceCalled": False,
        "mlServiceResponse": None,
        "reason": None,
        "usedModel": False,
        "trustContext": trust_context,
    }

    if confidence_level == "not_enough_data":
        return empty

    raw_ml: Dict[str, Any] = {
        "predictedGrade": None,
        "usedModel": False,
        "predictionSource": None,
        "mlServiceCalled": False,
        "mlServiceResponse": None,
    }
    if can_attempt_fn(overlay_feats, feat_debug, metrics, resolved_grade) and _has_ml_feature_data(
        overlay_feats
    ):
        raw_ml = _invoke_ml_model(
            overlay_feats, stack_predict_fn, stack_predict_grade_fn, stack_available_fn
        )

    is_seeded = feat_debug.get("feature_source") == "seeded"
    raw_predicted = raw_ml.get("predictedGrade")
    prediction_source: Optional[str] = None
    predicted: Optional[int] = None
    probability = raw_ml.get("probability")
    ml_confidence = raw_ml.get("confidence")
    used_model = bool(raw_ml.get("usedModel"))

    ml_usable = is_ml_output_usable(raw_predicted, resolved_grade)
    ml_strict_ok = False
    if ml_usable and used_model:
        if is_seeded:
            ml_strict_ok = True
        else:
            ml_strict_ok, _ = is_numeric_ml_prediction_trustworthy(
                raw_predicted,
                resolved_grade,
                feat_debug,
                trust_context,
                overlay_feats,
            )

    if ml_usable and ml_strict_ok and confidence_level == "high":
        predicted = int(raw_predicted)
        prediction_source = raw_ml.get("predictionSource")
        final_confidence = "high"
    elif ml_usable and used_model and confidence_level in ("high", "limited"):
        predicted = int(raw_predicted)
        prediction_source = raw_ml.get("predictionSource")
        final_confidence = "limited" if confidence_level == "limited" or not ml_strict_ok else "high"
    else:
        adjusted = compute_rule_adjusted_prediction(
            resolved_grade, overlay_feats, metrics, trust_context
        )
        if adjusted is not None and adjusted > 0:
            predicted = adjusted
            prediction_source = "rule_adjusted_prediction"
            final_confidence = "limited"
            used_model = False
            probability = None
            ml_confidence = None

    if predicted is None or predicted <= 0:
        empty["reason"] = "No usable prediction from ML or rule-adjusted model."
        empty["performanceMode"] = (
            "limited_insight" if confidence_level == "limited" else "not_enough_data"
        )
        empty["message"] = (
            LIMITED_INSIGHT_MESSAGE if confidence_level == "limited" else NOT_ENOUGH_DATA_MESSAGE
        )
        empty["predictionConfidence"] = confidence_level if confidence_level != "not_enough_data" else None
        return empty

    status = status_from_predicted_grade(predicted, final_confidence)
    if prediction_source == "rule_adjusted_prediction":
        classification_source = RULE_ADJUSTED_LABEL
        performance_mode = "limited_insight"
        message = LIMITED_CONFIDENCE_NOTE if final_confidence == "limited" else LIMITED_INSIGHT_MESSAGE
    elif final_confidence == "high":
        classification_source = ML_SOURCE_LABEL
        performance_mode = "ml_prediction"
        message = None
    else:
        classification_source = RULE_ADJUSTED_LABEL
        performance_mode = "limited_insight"
        message = LIMITED_CONFIDENCE_NOTE

    verified = prediction_source in ("ml_service", "local_ml") and ml_strict_ok

    return {
        "predictedGrade": predicted,
        "status": status,
        "probability": probability,
        "confidence": ml_confidence,
        "predictionVerified": verified,
        "predictionSource": prediction_source,
        "predictionConfidence": final_confidence,
        "performanceMode": performance_mode,
        "classificationSource": classification_source,
        "message": message,
        "mlServiceCalled": raw_ml.get("mlServiceCalled"),
        "mlServiceResponse": raw_ml.get("mlServiceResponse") if include_debug else None,
        "reason": None,
        "usedModel": used_model and prediction_source != "rule_adjusted_prediction",
        "trustContext": trust_context,
        "statusNote": status_note_for_confidence(final_confidence),
    }


GUIDANCE_WEAKNESS_SPECS: List[Dict[str, Any]] = [
    {
        "key": "active_days",
        "title": "Low weekly engagement",
        "description": "Active days on the platform are low; consistent access predicts performance better than total time.",
        "recommendation": "Log in for a short focused session most days rather than occasional long ones.",
        "severity": "High",
        "test": lambda f, m, a: a < 8,
        "impact": lambda f, m, a: 75 if a < 5 else 55,
    },
    {
        "key": "material_engagement",
        "title": "Low material engagement",
        "description": "Few course materials have been opened compared to available clicks.",
        "recommendation": "Review lecture slides and readings before each assignment deadline.",
        "severity": "Medium",
        "test": lambda f, m, a: int(f.get("material_clicks") or m.get("number_of_resources_clicked") or 0) < 2
        and int(f.get("all_clicks") or 0) < 5,
        "impact": lambda f, m, a: 50,
    },
    {
        "key": "total_time_spent",
        "title": "Low study time",
        "description": "Total time spent in the course is low relative to what strong performers typically log.",
        "recommendation": "Schedule two 45-minute study blocks per week for this course.",
        "severity": "Medium",
        "test": lambda f, m, a: int(f.get("total_time_spent") or m.get("total_time_spent_seconds") or 0) < 600,
        "impact": lambda f, m, a: 45,
    },
    {
        "key": "quiz_attempts",
        "title": "No quiz practice recorded",
        "description": "No quiz attempts are synced for this course yet.",
        "recommendation": "Attempt available quizzes and review incorrect answers before the next assessment.",
        "severity": "Medium",
        "test": lambda f, m, a: int(f.get("quiz_attempts") or m.get("quiz_attempts") or 0) == 0,
        "impact": lambda f, m, a: 48,
    },
    {
        "key": "assignment_submissions",
        "title": "No assignment activity recorded",
        "description": "No assignment submissions are synced for this course.",
        "recommendation": "Submit drafts early and use feedback before the final due date.",
        "severity": "Medium",
        "test": lambda f, m, a: int(f.get("assignment_submissions") or m.get("assignment_submissions") or 0) == 0,
        "impact": lambda f, m, a: 46,
    },
    {
        "key": "late_submission_count",
        "title": "Late submissions",
        "description": "One or more assignments were submitted past their due date.",
        "recommendation": "Enable calendar reminders and aim to submit a day early.",
        "severity": "High",
        "test": lambda f, m, a: int(f.get("late_submission_count") or 0) > 0,
        "impact": lambda f, m, a: min(85, 40 + int(f.get("late_submission_count") or 0) * 15),
    },
    {
        "key": "procrastination_index",
        "title": "High procrastination",
        "description": "Tasks are being started close to deadlines, which the data links to lower performance.",
        "recommendation": "Break work into daily micro-tasks and set personal deadlines 48 hours early.",
        "severity": "High",
        "test": lambda f, m, a: float(f.get("procrastination_index") or 0) >= 3,
        "impact": lambda f, m, a: min(90, int(float(f.get("procrastination_index") or 0) * 10)),
    },
]

GUIDANCE_STRENGTH_SPECS: List[Dict[str, Any]] = [
    {
        "title": "Consistent engagement",
        "description": "You are accessing the course regularly across multiple active days.",
        "recommendation": "Keep your current weekly rhythm — consistency is a strong predictor.",
        "severity": "Low",
        "test": lambda f, m, a, g: a >= 8,
        "impact": lambda f, m, a, g: 35,
        "feature": "active_days",
    },
    {
        "title": "Good grade position",
        "description": "Your current course grade is in a solid range.",
        "recommendation": "Protect your position by maintaining submissions before deadlines.",
        "severity": "Low",
        "test": lambda f, m, a, g: g is not None and g >= 70,
        "impact": lambda f, m, a, g: 40,
        "feature": "grade",
    },
    {
        "title": "Keep current rhythm",
        "description": "Study time and material engagement are supporting your progress.",
        "recommendation": "Continue reviewing materials before each new topic week.",
        "severity": "Low",
        "test": lambda f, m, a, g: int(f.get("total_time_spent") or m.get("total_time_spent_seconds") or 0) >= 600
        and int(f.get("material_clicks") or m.get("number_of_resources_clicked") or 0) >= 2,
        "impact": lambda f, m, a, g: 32,
        "feature": "total_time_spent",
    },
    {
        "title": "Continue early submissions",
        "description": "No late submissions are recorded for this course.",
        "recommendation": "Maintain early submission habits to avoid end-of-term pressure.",
        "severity": "Low",
        "test": lambda f, m, a, g: int(f.get("late_submission_count") or 0) == 0
        and int(f.get("assignment_submissions") or m.get("assignment_submissions") or 0) > 0,
        "impact": lambda f, m, a, g: 30,
        "feature": "late_submission_count",
    },
    {
        "title": "Maintain weekly access",
        "description": "Regular platform access is logged for this course.",
        "recommendation": "Keep logging short sessions even during lighter weeks.",
        "severity": "Low",
        "test": lambda f, m, a, g: float(f.get("access_frequency") or 0) >= 0.5 or a >= 5,
        "impact": lambda f, m, a, g: 28,
        "feature": "access_frequency",
    },
]


def _metrics_has(metrics: Dict[str, Any], key: str) -> bool:
    return bool(metrics) and key in metrics and metrics.get(key) is not None


def _build_engagement_weakness(
    overlay_feats: Dict[str, Any],
    metrics: Dict[str, Any],
    trust_context: Dict[str, Any],
    active: int,
) -> Optional[Dict[str, Any]]:
    active_untrusted = trust_context.get("active_days_untrusted")
    metrics_active = metrics.get("active_days_count")
    if active_untrusted and metrics_active is None:
        return {
            "title": "Weekly engagement not synced",
            "description": "Weekly engagement data is not synced for this course yet.",
            "impact": 45,
            "recommendation": "Sync Moodle activity or log in regularly so engagement can be tracked.",
            "feature": "active_days",
            "severity": "Medium",
        }
    if active < 8:
        return {
            "title": "Low weekly engagement",
            "description": "Active days on the platform are low; consistent access predicts performance better than total time.",
            "impact": 75 if active < 5 else 55,
            "recommendation": "Log in for a short focused session most days rather than occasional long ones.",
            "feature": "active_days",
            "severity": "High",
        }
    return None


def _build_quiz_weakness(
    overlay_feats: Dict[str, Any],
    metrics: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if _metrics_has(metrics, "quiz_attempts"):
        if int(metrics.get("quiz_attempts") or 0) == 0:
            return {
                "title": "No quiz practice recorded",
                "description": "No quiz attempts are synced for this course.",
                "impact": 48,
                "recommendation": "Attempt available quizzes and review incorrect answers before the next assessment.",
                "feature": "quiz_attempts",
                "severity": "Medium",
            }
        return None
    if overlay_feats.get("quiz_attempts") is not None and int(overlay_feats.get("quiz_attempts") or 0) == 0:
        return {
            "title": "No quiz practice recorded",
            "description": "Feature records show no quiz attempts for this course.",
            "impact": 48,
            "recommendation": "Attempt available quizzes and review incorrect answers before the next assessment.",
            "feature": "quiz_attempts",
            "severity": "Medium",
        }
    return {
        "title": "Quiz practice not synced",
        "description": "No synced quiz practice is available for this course yet.",
        "impact": 42,
        "recommendation": "Complete Moodle quizzes so attempt data can support guidance.",
        "feature": "quiz_attempts",
        "severity": "Medium",
    }


def _build_assignment_weakness(
    overlay_feats: Dict[str, Any],
    metrics: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if _metrics_has(metrics, "assignment_submissions"):
        if int(metrics.get("assignment_submissions") or 0) == 0:
            return {
                "title": "No assignment activity recorded",
                "description": "No assignment submissions are synced for this course.",
                "impact": 46,
                "recommendation": "Submit drafts early and use feedback before the final due date.",
                "feature": "assignment_submissions",
                "severity": "Medium",
            }
        return None
    if overlay_feats.get("assignment_submissions") is not None and int(
        overlay_feats.get("assignment_submissions") or 0
    ) == 0:
        return {
            "title": "No assignment activity recorded",
            "description": "Feature records show no assignment submissions for this course.",
            "impact": 46,
            "recommendation": "Submit drafts early and use feedback before the final due date.",
            "feature": "assignment_submissions",
            "severity": "Medium",
        }
    return {
        "title": "Assignment activity not synced",
        "description": "No synced assignment activity is available for this course yet.",
        "impact": 40,
        "recommendation": "Submit assignments in Moodle so activity can inform guidance.",
        "feature": "assignment_submissions",
        "severity": "Medium",
    }


def build_guidance_factors(
    overlay_feats: Dict[str, Any],
    metrics: Dict[str, Any],
    trust_context: Dict[str, Any],
    resolved_grade: Dict[str, Any],
    predicted: Optional[int],
) -> List[Dict[str, Any]]:
    active = _effective_active_days(overlay_feats, metrics, trust_context)
    display = resolved_grade.get("displayGrade")
    grade_val = float(display) if display is not None else None

    weaknesses: List[Dict[str, Any]] = []

    engagement = _build_engagement_weakness(overlay_feats, metrics, trust_context, active)
    if engagement:
        weaknesses.append(engagement)

    material = int(
        overlay_feats.get("material_clicks") or metrics.get("number_of_resources_clicked") or 0
    )
    clicks = int(overlay_feats.get("all_clicks") or 0)
    if material < 2 and clicks < 5:
        weaknesses.append(
            {
                "title": "Low material engagement",
                "description": "Few course materials have been opened compared to typical engagement.",
                "impact": 50,
                "recommendation": "Review lecture slides and readings before each assignment deadline.",
                "feature": "material_clicks",
                "severity": "Medium",
            }
        )

    time_spent = int(
        overlay_feats.get("total_time_spent") or metrics.get("total_time_spent_seconds") or 0
    )
    if _metrics_has(metrics, "total_time_spent_seconds") or overlay_feats.get("total_time_spent") is not None:
        if time_spent < 600:
            weaknesses.append(
                {
                    "title": "Low study time",
                    "description": "Total time spent in the course is low relative to what strong performers typically log.",
                    "impact": 45,
                    "recommendation": "Schedule two 45-minute study blocks per week for this course.",
                    "feature": "total_time_spent",
                    "severity": "Medium",
                }
            )

    quiz_weakness = _build_quiz_weakness(overlay_feats, metrics)
    if quiz_weakness:
        weaknesses.append(quiz_weakness)

    assign_weakness = _build_assignment_weakness(overlay_feats, metrics)
    if assign_weakness:
        weaknesses.append(assign_weakness)

    assign = int(
        overlay_feats.get("assignment_submissions") or metrics.get("assignment_submissions") or 0
    )
    late = int(overlay_feats.get("late_submission_count") or 0)
    proc = float(overlay_feats.get("procrastination_index") or 0)
    if assign > 0 and late > 0:
        weaknesses.append(
            {
                "title": "Late submissions",
                "description": "One or more assignments were submitted past their due date.",
                "impact": min(85, 40 + late * 15),
                "recommendation": "Enable calendar reminders and aim to submit a day early.",
                "feature": "late_submission_count",
                "severity": "High",
            }
        )
    if assign > 0 and proc >= 3:
        weaknesses.append(
            {
                "title": "High procrastination",
                "description": "Tasks are being started close to deadlines, which the data links to lower performance.",
                "impact": min(90, int(proc * 10)),
                "recommendation": "Break work into daily micro-tasks and set personal deadlines 48 hours early.",
                "feature": "procrastination_index",
                "severity": "High",
            }
        )

    if weaknesses:
        weaknesses.sort(key=lambda x: x["impact"], reverse=True)
        return weaknesses[:3]

    strengths: List[Dict[str, Any]] = []
    for spec in GUIDANCE_STRENGTH_SPECS:
        if not spec["test"](overlay_feats, metrics, active, grade_val):
            continue
        strengths.append(
            {
                "title": spec["title"],
                "description": spec["description"],
                "impact": spec["impact"](overlay_feats, metrics, active, grade_val),
                "recommendation": spec["recommendation"],
                "feature": spec.get("feature"),
                "severity": spec["severity"],
            }
        )
    strengths.sort(key=lambda x: x["impact"], reverse=True)
    return strengths[:3]

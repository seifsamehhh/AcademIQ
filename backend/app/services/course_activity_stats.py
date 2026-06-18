"""
Per-course activity statistics with explicit value sources for the Performance UI.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from app.repositories import metrics_repository

_OVERALL = metrics_repository.OVERALL


def _metrics_has(metrics: Dict[str, Any], key: str) -> bool:
    if not metrics:
        return False
    return key in metrics and metrics.get(key) is not None


def _task_field(
    metrics: Dict[str, Any],
    feats: Dict[str, Any],
    feat_debug: Dict[str, Any],
    attempted_key: str,
    viewed_key: str,
    feat_key: str,
    average_score: Optional[float],
    activity_source: str,
    force_unavailable: bool,
) -> Dict[str, Any]:
    if force_unavailable:
        return {
            "attempted": None,
            "total": None,
            "averageScore": average_score if average_score is not None else None,
            "valueSource": "unavailable",
            "available": False,
        }

    if _metrics_has(metrics, attempted_key) or _metrics_has(metrics, viewed_key):
        attempted = int(metrics.get(attempted_key) or 0)
        viewed = metrics.get(viewed_key)
        if viewed is None:
            total: Optional[int] = None if attempted == 0 else attempted
        else:
            viewed_int = int(viewed or 0)
            if viewed_int == 0 and attempted == 0:
                total = None
            else:
                total = max(viewed_int, attempted)
        return {
            "attempted": attempted,
            "total": total,
            "averageScore": average_score,
            "valueSource": "synced_moodle",
            "available": True,
        }

    if (
        feat_debug.get("document_found")
        and feat_debug.get("feature_source") in ("synced", "seeded")
        and feat_key in feats
    ):
        attempted = int(feats.get(feat_key) or 0)
        return {
            "attempted": attempted,
            "total": None,
            "averageScore": average_score,
            "valueSource": "feature_vector",
            "available": True,
        }

    return {
        "attempted": None,
        "total": None,
        "averageScore": average_score if average_score is not None else None,
        "valueSource": "unavailable",
        "available": False,
    }


def _total_time_field(
    metrics: Dict[str, Any],
    feats: Dict[str, Any],
    feat_debug: Dict[str, Any],
    force_unavailable: bool,
) -> Tuple[Optional[float], str, bool]:
    if force_unavailable:
        return None, "unavailable", False

    if _metrics_has(metrics, "total_time_spent_seconds"):
        seconds = int(metrics.get("total_time_spent_seconds") or 0)
        return round(seconds / 3600, 1), "synced_moodle", True

    if (
        feat_debug.get("document_found")
        and feat_debug.get("feature_source") in ("synced", "seeded")
        and feats.get("total_time_spent") is not None
    ):
        seconds = int(feats.get("total_time_spent") or 0)
        return round(seconds / 3600, 1), "feature_vector", True

    return None, "unavailable", False


def _weekly_average_field(
    user_id: str,
    total_hours: Optional[float],
    activity_source: str,
    force_unavailable: bool,
) -> Tuple[Optional[float], str, bool, bool]:
    """Returns (hours, value_source, available, is_estimated)."""
    if force_unavailable or total_hours is None:
        return None, "unavailable", False, False

    if activity_source == "synced":
        overall_metrics = (metrics_repository.get(user_id, _OVERALL) or {}).get("metrics", {}) or {}
        weekly_history = overall_metrics.get("weekly_hours") or []
        if weekly_history:
            values = [float(entry.get("hours") or 0) for entry in weekly_history]
            if values:
                return round(sum(values) / len(values), 1), "synced_moodle", True, False

    if total_hours > 0:
        return round(total_hours / 3, 1), "estimated_from_synced_activity", True, True

    return None, "unavailable", False, False


def build_course_activity_statistics(
    user_id: str,
    metrics: Dict[str, Any],
    feats: Dict[str, Any],
    feat_debug: Dict[str, Any],
    quiz_avg: Optional[float],
    assign_avg: Optional[float],
    activity_source: str,
    performance_mode: str,
) -> Dict[str, Any]:
    force_unavailable = performance_mode == "not_enough_data" and activity_source == "none"

    quizzes = _task_field(
        metrics,
        feats,
        feat_debug,
        "quiz_attempts",
        "number_of_quizzes_viewed",
        "quiz_attempts",
        quiz_avg,
        activity_source,
        force_unavailable,
    )
    assignments = _task_field(
        metrics,
        feats,
        feat_debug,
        "assignment_submissions",
        "number_of_assignments_viewed",
        "assignment_submissions",
        assign_avg,
        activity_source,
        force_unavailable,
    )
    total_hours, total_source, total_available = _total_time_field(
        metrics, feats, feat_debug, force_unavailable
    )
    weekly_hours, weekly_source, weekly_available, weekly_estimated = _weekly_average_field(
        user_id,
        total_hours,
        activity_source,
        force_unavailable,
    )

    has_missing = (
        not quizzes.get("available")
        or not assignments.get("available")
        or not total_available
        or not weekly_available
    )

    return {
        "quizzes": quizzes,
        "assignments": assignments,
        "totalTimeHours": total_hours,
        "totalTimeValueSource": total_source,
        "totalTimeAvailable": total_available,
        "weeklyAverageHours": weekly_hours,
        "weeklyAverageValueSource": weekly_source,
        "weeklyAverageAvailable": weekly_available,
        "weeklyAverageEstimated": weekly_estimated,
        "hasMissingFields": has_missing,
    }

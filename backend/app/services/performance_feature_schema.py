"""
Canonical performance / ML behavioural feature schema.

Single source of truth for audits, debug endpoints, and documentation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

# Model + ML service + feature vector ingest (synced_features.PERFORMANCE_V4_KEYS).
ML_BEHAVIORAL_FEATURES: List[Dict[str, Any]] = [
    {
        "feature_name": "all_clicks",
        "expected_type": "int",
        "required_for_ml": True,
        "used_by_model": True,
        "used_by_rule_based_insights": False,
        "metrics_key": None,
        "per_course_metric": True,
    },
    {
        "feature_name": "active_days",
        "expected_type": "int",
        "required_for_ml": True,
        "used_by_model": True,
        "used_by_rule_based_insights": True,
        "metrics_key": "active_days_count",
        "per_course_metric": True,
    },
    {
        "feature_name": "access_frequency",
        "expected_type": "float",
        "required_for_ml": True,
        "used_by_model": True,
        "used_by_rule_based_insights": False,
        "metrics_key": None,
        "per_course_metric": True,
        "derived": "total_visits / active_days",
    },
    {
        "feature_name": "material_clicks",
        "expected_type": "int",
        "required_for_ml": True,
        "used_by_model": True,
        "used_by_rule_based_insights": False,
        "metrics_key": "number_of_resources_clicked",
        "per_course_metric": True,
    },
    {
        "feature_name": "quiz_attempts",
        "expected_type": "int",
        "required_for_ml": True,
        "used_by_model": True,
        "used_by_rule_based_insights": False,
        "metrics_key": "quiz_attempts",
        "per_course_metric": True,
    },
    {
        "feature_name": "assignment_submissions",
        "expected_type": "int",
        "required_for_ml": True,
        "used_by_model": True,
        "used_by_rule_based_insights": True,
        "metrics_key": "assignment_submissions",
        "per_course_metric": True,
    },
    {
        "feature_name": "total_time_spent",
        "expected_type": "int",
        "required_for_ml": True,
        "used_by_model": True,
        "used_by_rule_based_insights": False,
        "metrics_key": "total_time_spent_seconds",
        "per_course_metric": True,
    },
    {
        "feature_name": "procrastination_index",
        "expected_type": "float",
        "required_for_ml": True,
        "used_by_model": True,
        "used_by_rule_based_insights": True,
        "metrics_key": None,
        "per_course_metric": True,
        "derived": "late / assignment materials with due dates",
    },
    {
        "feature_name": "late_submission_count",
        "expected_type": "int",
        "required_for_ml": True,
        "used_by_model": True,
        "used_by_rule_based_insights": True,
        "metrics_key": None,
        "per_course_metric": True,
        "derived": "assignment due dates vs now",
    },
]

RULE_ONLY_FEATURES: List[Dict[str, Any]] = [
    {
        "feature_name": "avg_quiz_score",
        "expected_type": "float",
        "required_for_ml": False,
        "used_by_model": False,
        "used_by_rule_based_insights": True,
    },
    {
        "feature_name": "low_engagement",
        "expected_type": "derived",
        "required_for_ml": False,
        "used_by_model": False,
        "used_by_rule_based_insights": True,
        "derived": "active_days < 10",
    },
]

ML_FEATURE_NAMES: Tuple[str, ...] = tuple(
    f["feature_name"] for f in ML_BEHAVIORAL_FEATURES
)

ML_MIN_TRUSTED_BEHAVIORAL = 2

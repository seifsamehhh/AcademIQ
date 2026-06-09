"""
Maps the normalized MongoDB collections to the shapes the Next.js frontend
expects (see front-end/src/lib/types.ts), scoped to one student.

Real data is used wherever it exists (courses, materials, per-course averages
from grades, time/engagement from metrics). Fields that genuinely require the ML
models — predictedGrade, performance status, burnout, ranked risk factors — are
computed as transparent HEURISTICS from the student's latest feature vector and
flagged with `heuristic: True`. Once the ML routes are mounted (Python 3.11/3.12
venv), these can be swapped for real model output / `ml_results`.
"""

from typing import Any, Dict, List, Optional

from app.config.database import (
    feature_vectors_collection,
    raw_moodle_payload_collection,
)
from app.repositories import material_repository, metrics_repository
from app.services.moodle_ingest import is_real_course

_OVERALL = metrics_repository.OVERALL

# Minimal recommendation text per heuristic risk factor (mirrors the v4 map).
_RISK_LIBRARY = [
    {
        "key": "procrastination_index",
        "test": lambda f: f.get("procrastination_index", 0) >= 5,
        "title": "High procrastination",
        "description": "Tasks are being started close to their deadlines, which the data links to lower performance.",
        "recommendation": "Break work into daily micro-tasks and set personal deadlines 48 hours early.",
        "impact": lambda f: min(100, int(f.get("procrastination_index", 0) * 10)),
    },
    {
        "key": "late_submission_count",
        "test": lambda f: f.get("late_submission_count", 0) > 0,
        "title": "Late submissions",
        "description": "One or more assignments were submitted (or remain) past their due date.",
        "recommendation": "Enable calendar reminders and aim to submit a day early, even if imperfect.",
        "impact": lambda f: min(100, 40 + int(f.get("late_submission_count", 0)) * 15),
    },
    {
        "key": "low_engagement",
        "test": lambda f: f.get("active_days", 0) < 10,
        "title": "Low weekly engagement",
        "description": "Active days on the platform are low; consistent access predicts performance better than total time.",
        "recommendation": "Log in for a short focused session most days rather than occasional long ones.",
        "impact": lambda f: 60 if f.get("active_days", 0) < 5 else 40,
    },
    {
        "key": "low_quiz",
        "test": lambda f: 0 < f.get("avg_quiz_score", 0) < 0.6,
        "title": "Quiz scores below target",
        "description": "Average quiz performance is under 60%, suggesting topics aren't being consolidated.",
        "recommendation": "Re-attempt quizzes (first without notes), focusing on the questions you got wrong.",
        "impact": lambda f: 50,
    },
]


def _clean_course_name(name: Optional[str]) -> str:
    name = (name or "").strip()
    # Moodle often prefixes the breadcrumb link with "Course ".
    if name.lower().startswith("course "):
        name = name[len("course "):].strip()
    return name or "Untitled Course"


def _course_code(name: str, course_id: str) -> str:
    """Derive a short code from the course name (e.g. 'Machine Learning' -> 'ML')."""
    words = [w for w in name.replace("-", " ").split() if w[:1].isalpha()]
    initials = "".join(w[0].upper() for w in words[:3])
    return initials or f"C{course_id}"


def _latest_features(user_id: str) -> Dict[str, Any]:
    doc = feature_vectors_collection.find_one({"academiq_user_id": user_id})
    return (doc or {}).get("features", {}) or {}


def _resolve_activity_source(user_id: str, metrics: Dict[str, Any]) -> str:
    """Classify whether course activity stats are seeded demo data or Moodle sync."""
    explicit = (metrics or {}).get("activity_source")
    if explicit in ("seeded", "synced"):
        return explicit

    doc = raw_moodle_payload_collection.find_one({"academiq_user_id": user_id})
    if doc and (
        doc.get("metricsByCourse")
        or doc.get("behavior")
        or doc.get("courses")
    ):
        return "synced"

    if metrics and any(
        (metrics.get(k) or 0) > 0
        for k in (
            "quiz_attempts",
            "assignment_submissions",
            "total_time_spent_seconds",
            "number_of_quizzes_viewed",
            "number_of_assignments_viewed",
        )
    ):
        return "seeded"

    return "none"


def _activity_stats_note(source: str) -> str:
    if source == "synced":
        return _ACTIVITY_NOTE_SYNCED
    if source == "seeded":
        return _ACTIVITY_NOTE_SEEDED
    return _ACTIVITY_NOTE_NONE


def _weekly_average_hours(
    user_id: str,
    total_course_hours: float,
    activity_source: str,
) -> tuple[float | None, bool]:
    """
    Return (weekly_hours, is_estimated).

    Uses rolling ISO-week history only for Moodle-synced overall metrics.
    Seeded or unknown sources get an approximate value from total course time.
    """
    if activity_source == "synced":
        overall_metrics = (
            (metrics_repository.get(user_id, _OVERALL) or {}).get("metrics", {}) or {}
        )
        weekly_history = overall_metrics.get("weekly_hours") or []
        if weekly_history:
            values = [float(entry.get("hours") or 0) for entry in weekly_history]
            if values:
                return round(sum(values) / len(values), 1), False

    if total_course_hours > 0:
        return round(total_course_hours / 3, 1), True

    return None, False


def _has_ml_feature_data(features: Dict[str, Any]) -> bool:
    """True when synced feature vectors contain enough signal for a real inference."""
    if not features:
        return False
    activity_keys = (
        "all_clicks",
        "active_days",
        "quiz_attempts",
        "assignment_submissions",
        "total_time_spent",
        "material_clicks",
    )
    return any((features.get(k) or 0) > 0 for k in activity_keys)


def _grades(user_id: str) -> List[Dict[str, Any]]:
    doc = raw_moodle_payload_collection.find_one({"academiq_user_id": user_id})
    return (doc or {}).get("grades", []) or []


def _avg_percentage(grades: List[Dict[str, Any]], course_id: str = None, item_type: str = None) -> Optional[float]:
    vals = []
    for g in grades:
        if course_id is not None and str(g.get("course_id")) != str(course_id):
            continue
        if item_type is not None and (g.get("item_type") or "").lower() != item_type:
            continue
        pct = g.get("percentage")
        if isinstance(pct, (int, float)):
            vals.append(float(pct))
    return round(sum(vals) / len(vals), 1) if vals else None


# Raw behavioural features the performance model expects.
_PERF_FEATURES = [
    "all_clicks", "active_days", "access_frequency", "material_clicks",
    "quiz_attempts", "assignment_submissions", "total_time_spent",
    "procrastination_index", "late_submission_count",
]

_ML_UNAVAILABLE_MESSAGE = (
    "ML prediction is not available yet because model dependencies are not deployed."
)
_ML_NO_FEATURES_MESSAGE = (
    "ML prediction is not available yet because synced behavioral data is missing. "
    "Use the Chrome extension to sync Moodle activity."
)

_ACTIVITY_NOTE_SEEDED = (
    "Activity stats below come from seeded demo records for presentation. "
    "They are not live Moodle analytics. Sync the Chrome extension to replace "
    "them with real activity data."
)
_ACTIVITY_NOTE_SYNCED = (
    "Activity stats below are based on your latest synced Moodle activity records."
)
_ACTIVITY_NOTE_NONE = (
    "Activity stats are based on available synced records. Live Moodle analytics "
    "will appear after the extension syncs real activity data."
)

_ml_stack_available_cache: bool | None = None


def _ml_stack_available() -> bool:
    """True when performance model artifacts can be loaded (not true on Vercel slim deploy)."""
    global _ml_stack_available_cache
    if _ml_stack_available_cache is not None:
        return _ml_stack_available_cache
    try:
        from app.services.performance_predict import load_artifacts

        load_artifacts()
        _ml_stack_available_cache = True
    except Exception:
        _ml_stack_available_cache = False
    return _ml_stack_available_cache


def _predict(features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Run the real performance model if its deps are installed; else None.

    Lazy import so the API still boots (on heuristics) when the ML stack isn't
    available (e.g. Python 3.14 without scikit-learn/shap wheels).
    """
    try:
        from app.services.performance_predict import predict_performance
        raw = {k: features.get(k, 0) for k in _PERF_FEATURES}
        return predict_performance(raw)
    except Exception:
        return None


def _predict_grade(features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Run the real grade/risk model (TensorFlow) if available; else None.

    Scores are stored 0-1 by the feature pipeline; the grade model trained on
    0-100, so we rescale the score inputs.
    """
    try:
        from app.services.grade_risk_predict import predict_grade_and_risk
        req = {
            "all_clicks": features.get("all_clicks", 0),
            "active_days": features.get("active_days", 0),
            "access_frequency": features.get("access_frequency", 0.0),
            "material_clicks": features.get("material_clicks", 0),
            "avg_quiz_score": (features.get("avg_quiz_score", 0) or 0) * 100,
            "quiz_attempts": features.get("quiz_attempts", 0),
            "avg_assignment_score": (features.get("avg_assignment_score", 0) or 0) * 100,
            "assignment_submissions": features.get("assignment_submissions", 0),
            "total_time_spent": features.get("total_time_spent", 0),
        }
        return predict_grade_and_risk(req)
    except Exception:
        return None


def _store_prediction(user_id: str, result: Dict[str, Any]) -> None:
    """Persist the latest model output to ml_results (one per user+model)."""
    try:
        from datetime import datetime
        from app.config.database import ml_results_collection
        now = datetime.utcnow()
        ml_results_collection.update_one(
            {"academiq_user_id": user_id, "model_name": "performance_model_v4"},
            {
                "$set": {
                    "academiq_user_id": user_id,
                    "model_name": "performance_model_v4",
                    "prediction": result,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
    except Exception:
        pass


def get_courses(user_id: str) -> List[Dict[str, Any]]:
    """The student's courses (derived from their per-course metrics)."""
    courses = []
    for m in metrics_repository.list_for_user(user_id):
        cid = m.get("course_id")
        if cid == _OVERALL:
            continue
        raw_name = (m.get("metrics") or {}).get("course_name")
        if not is_real_course(cid, raw_name):  # skip stale 'My courses' (id 1) etc.
            continue
        name = _clean_course_name(raw_name)
        courses.append({"id": cid, "name": name, "code": _course_code(name, cid)})
    courses.sort(key=lambda c: c["name"])
    return courses


def _course_obj(user_id: str, course_id: str) -> Dict[str, Any]:
    m = metrics_repository.get(user_id, course_id) or {}
    name = _clean_course_name((m.get("metrics") or {}).get("course_name"))
    return {"id": course_id, "name": name, "code": _course_code(name, course_id)}


def get_materials(course_id: str) -> List[Dict[str, Any]]:
    """Real learning materials for a course (LearningMaterial shape)."""
    out = []
    for doc in material_repository.list_by_course(course_id):
        out.append({
            "id": doc.get("material_id"),
            "title": doc.get("title", "Untitled"),
            "kind": (doc.get("file_type") or doc.get("category") or "file").upper(),
            "hasContent": bool((doc.get("content_text") or "").strip()),
        })
    return out


def get_performance(user_id: str, course_id: str) -> Dict[str, Any]:
    metrics = (metrics_repository.get(user_id, course_id) or {}).get("metrics", {}) or {}
    grades = _grades(user_id)

    course_avg = _avg_percentage(grades, course_id)
    quiz_avg = _avg_percentage(grades, course_id, "quiz")
    assign_avg = _avg_percentage(grades, course_id, "assignment")
    has_grade_data = course_avg is not None

    feats = _latest_features(user_id)
    stack_ready = _ml_stack_available()
    has_feature_data = _has_ml_feature_data(feats)
    perf = None
    grade = None
    if stack_ready and has_feature_data:
        perf = _predict(feats)
        grade = _predict_grade(feats)

    used_model = bool(perf or grade)
    predicted: int | None = None
    status: str | None = None

    if used_model:
        if grade and grade.get("predicted_grade") is not None:
            predicted = round(grade["predicted_grade"])
        elif course_avg is not None:
            predicted = round(course_avg)
        elif perf:
            predicted = round((perf.get("probability", 0) or 0) * 100)

        if perf:
            prob = perf.get("probability", 0) or 0
            status = "Good" if prob >= 0.5 else "Average" if prob >= 0.4 else "At Risk"
        elif predicted is not None:
            status = (
                "Good" if predicted >= 75 else "Average" if predicted >= 60 else "At Risk"
            )

    total_seconds = metrics.get("total_time_spent_seconds", 0) or 0
    total_hours = round(total_seconds / 3600, 1)
    activity_source = _resolve_activity_source(user_id, metrics)
    weekly_avg, weekly_estimated = _weekly_average_hours(
        user_id, total_hours, activity_source
    )

    return {
        "course": _course_obj(user_id, course_id),
        "predictedGrade": predicted,
        "status": status,
        "courseAverage": course_avg,
        "hasGradeData": has_grade_data,
        "activityDataSource": activity_source,
        "activityStatsNote": _activity_stats_note(activity_source),
        "statistics": {
            "quizzes": {
                "attempted": metrics.get("quiz_attempts", 0) or 0,
                "total": max(
                    metrics.get("number_of_quizzes_viewed", 0) or 0,
                    metrics.get("quiz_attempts", 0) or 0,
                ),
                "averageScore": quiz_avg,
            },
            "assignments": {
                "attempted": metrics.get("assignment_submissions", 0) or 0,
                "total": max(
                    metrics.get("number_of_assignments_viewed", 0) or 0,
                    metrics.get("assignment_submissions", 0) or 0,
                ),
                "averageScore": assign_avg,
            },
            "totalTimeHours": total_hours,
            "weeklyAverageHours": weekly_avg,
            "weeklyAverageEstimated": weekly_estimated,
        },
        "engine": "ml" if used_model else "fallback",
        "mlAvailable": used_model,
        "message": (
            None
            if used_model
            else (
                _ML_UNAVAILABLE_MESSAGE
                if not stack_ready
                else _ML_NO_FEATURES_MESSAGE
            )
        ),
        "heuristic": not used_model,
    }


def get_insights(user_id: str, course_id: str) -> Dict[str, Any]:
    feats = _latest_features(user_id)

    # --- Real model path: SHAP-driven risk factors + recommendations --------
    result = _predict(feats)
    if result:
        _store_prediction(user_id, result)
        recs = result.get("recommendations", []) or []
        shaps = [abs(r.get("shap_impact") or 0) for r in recs] or [0]
        mx = max(shaps) or 1
        model_factors = []
        for r in recs:
            impact = round(min(95, (abs(r.get("shap_impact") or 0) / mx) * 80 + 15))
            model_factors.append({
                "title": r.get("short") or "Recommendation",
                "description": r.get("why") or "",
                "impact": impact,
                "recommendation": r.get("action") or "",
                "feature": r.get("feature"),
            })
        prob = result.get("probability", 0) or 0
        note = result.get("confidence_note")
        summary = f"Model classification: {result.get('classification', '')} ({round(prob * 100)}% confidence)."
        if note:
            summary += f" {note}"
        return {
            "course": _course_obj(user_id, course_id),
            "isHighPerformer": prob >= 0.5,
            "classificationSummary": summary.strip(),
            "riskFactors": model_factors,
            "heuristic": False,
        }

    # --- Heuristic fallback (no ML stack installed) -------------------------
    course_avg = _avg_percentage(_grades(user_id), course_id) or 0.0
    is_high = course_avg >= 75

    factors = []
    for spec in _RISK_LIBRARY:
        if spec["test"](feats):
            factors.append({
                "title": spec["title"],
                "description": spec["description"],
                "impact": spec["impact"](feats),
                "recommendation": spec["recommendation"],
            })
    factors.sort(key=lambda f: f["impact"], reverse=True)

    summary = (
        "You are tracking as a strong performer in this course based on your engagement and scores."
        if is_high else
        "Your engagement/score signals suggest room to improve in this course. The factors below have the most impact."
    )
    return {
        "course": _course_obj(user_id, course_id),
        "isHighPerformer": is_high,
        "classificationSummary": summary,
        "riskFactors": factors,
        "heuristic": True,  # heuristic until ML risk model is mounted
    }


def get_dashboard(user: Dict[str, Any]) -> Dict[str, Any]:
    user_id = str(user.get("_id") or user.get("id"))
    feats = _latest_features(user_id)
    grades = _grades(user_id)
    courses = get_courses(user_id)

    overall_avg = _avg_percentage(grades)
    if overall_avg is None:
        scores = [s * 100 for s in (feats.get("avg_quiz_score", 0), feats.get("avg_assignment_score", 0)) if s]
        overall_avg = round(sum(scores) / len(scores), 1) if scores else 0.0

    # Completion heuristic: attempted vs viewed across courses.
    attempted = viewed = 0
    for m in metrics_repository.list_for_user(user_id):
        if m.get("course_id") == _OVERALL:
            continue
        if not is_real_course(m.get("course_id"), (m.get("metrics") or {}).get("course_name")):
            continue
        mm = m.get("metrics", {}) or {}
        attempted += (mm.get("quiz_attempts", 0) or 0) + (mm.get("assignment_submissions", 0) or 0)
        viewed += (mm.get("number_of_quizzes_viewed", 0) or 0) + (mm.get("number_of_assignments_viewed", 0) or 0)
    completion = round(min(100, (attempted / viewed * 100) if viewed else 0), 1)

    total_hours = round((feats.get("total_time_spent", 0) or 0) / 3600, 1)

    # Study-time trend: real rolling weekly history when available.
    overall_metrics = (metrics_repository.get(user_id, _OVERALL) or {}).get("metrics", {}) or {}
    weekly_history = overall_metrics.get("weekly_hours") or []
    if weekly_history:
        study_time = [
            {"label": entry.get("label") or f"Week {entry.get('week', '')}", "hours": entry.get("hours", 0)}
            for entry in weekly_history
        ]
        study_time_heuristic = False
    else:
        weekly = round(total_hours / 3, 1) if total_hours else 0
        study_time = [
            {"label": "3 weeks ago", "hours": round(weekly * 0.8, 1)},
            {"label": "2 weeks ago", "hours": round(weekly, 1)},
            {"label": "Last week", "hours": round(weekly * 1.2, 1)},
        ]
        study_time_heuristic = True

    # Burnout: prefer the trained Random Forest; fall back to simple rules.
    burnout_result = None
    try:
        from app.services.burnout_predict import predict_burnout
        burnout_result = predict_burnout(feats)
    except Exception:
        burnout_result = None

    if burnout_result:
        burnout = {
            "level": burnout_result["level"],
            "message": burnout_result["message"],
        }
        burnout_heuristic = False
    else:
        active_days = feats.get("active_days", 0) or 0
        if total_hours > 20 and active_days < 8:
            level, msg = "High Risk", "High study time concentrated into few active days — pace yourself and rest."
        elif total_hours > 10 and active_days < 10:
            level, msg = "Medium Risk", "Workload is climbing relative to your active days. Keep an eye on rest."
        elif total_hours > 0:
            level, msg = "Low Risk", "Your workload looks manageable. Maintain a steady pace."
        else:
            level, msg = "Safe", "No signs of overload from the current data."
        burnout = {"level": level, "message": msg}
        burnout_heuristic = True

    return {
        "student": {
            "id": user_id,
            "username": user.get("email") or user.get("student_id") or "",
            "fullName": user.get("full_name") or user.get("name") or "Student",
        },
        "stats": {
            "averageScore": overall_avg,
            "averageCompletion": completion,
            "enrolledCourses": len(courses),
        },
        "studyTime": study_time,
        "burnout": burnout,
        "heuristic": burnout_heuristic or study_time_heuristic,
    }

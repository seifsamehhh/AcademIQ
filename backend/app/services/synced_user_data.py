"""
Resolve dashboard / identity data for Moodle-synced students vs seeded demo accounts.

Synced users are detected from student_metrics (activity_source=synced) or a
non-demo raw_moodle_payload audit record. Demo accounts student1/student2 keep
DEMO_RESULTS when no Moodle sync is present.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.config.database import (
    course_materials_collection,
    feature_vectors_collection,
    raw_moodle_payload_collection,
    student_metrics_collection,
)
from app.repositories import metrics_repository, user_repository
from app.demo_data import DEMO_RESULTS, DEMO_STUDENT_IDS
from app.services.moodle_course_display import (
    get_visible_synced_courses_for_user,
    resolve_display_name,
    resolve_login_email,
    should_use_visible_moodle_courses,
)
from app.services.moodle_sync_status import has_synced_moodle_data
from app.services.moodle_ingest import is_real_course
from app.services.grade_resolution import resolve_course_grade
from app.repositories.uploaded_grade_repository import map_by_course_id
from app.repositories.uploaded_transcript_repository import (
    LABEL_OFFICIAL,
    ensure_demo_official_transcript,
    get_for_user as get_official_transcript,
)
from app.services.student_data import (
    _clean_course_name,
    _course_code,
    _grades,
)


def _normalize_identifier(value: Any) -> str:
    return str(value or "").strip().lower()


def can_access_student_param(user: Dict[str, Any], student_id_param: str) -> bool:
    """True when the JWT user may read results for the path identifier."""
    if user.get("role") == "admin":
        return True
    param = _normalize_identifier(student_id_param)
    allowed = {
        _normalize_identifier(user.get("student_id")),
        _normalize_identifier(user.get("email")),
        str(user.get("_id")),
    }
    return param in allowed


def _last_sync_iso(user_id: str) -> Optional[str]:
    raw = raw_moodle_payload_collection.find_one({"academiq_user_id": user_id})
    if not raw:
        return None
    ts = raw.get("updated_at") or raw.get("created_at")
    if isinstance(ts, datetime):
        return ts.isoformat()
    return str(ts) if ts else None


def _course_activity_summary(user_id: str, course_id: str) -> Dict[str, Any]:
    doc = metrics_repository.get(user_id, str(course_id)) or {}
    metrics = doc.get("metrics") or {}
    return {
        "quizAttempts": metrics.get("quiz_attempts", 0) or 0,
        "assignmentSubmissions": metrics.get("assignment_submissions", 0) or 0,
        "timeSpentSeconds": metrics.get("total_time_spent_seconds", 0) or 0,
        "activitySource": metrics.get("activity_source") or "none",
    }


def _derive_demo_risk(avg_grade: Optional[float]) -> str:
    if avg_grade is None:
        return "Pending"
    if avg_grade >= 80:
        return "Low"
    if avg_grade >= 65:
        return "Medium"
    return "High"


def _derive_synced_risk(
    user_id: str,
    student_id: Optional[str],
    overall_avg: Optional[float],
) -> Dict[str, Any]:
    """Risk label aligned with per-course performance modes — no global ML fallback."""
    from app.services.moodle_course_display import get_visible_synced_courses_for_user
    from app.services.performance_feature_trust import (
        LIMITED_INSIGHT_MESSAGE,
        NOT_ENOUGH_DATA_MESSAGE,
    )
    from app.services.student_data import get_course_performance_mode

    course_ids = [
        str(c["id"]) for c in get_visible_synced_courses_for_user(user_id)
    ]
    if not course_ids:
        return {
            "risk": "Not enough data",
            "riskAvailable": False,
            "riskSource": None,
            "riskNote": NOT_ENOUGH_DATA_MESSAGE,
        }

    modes: List[str] = []
    verified_statuses: List[str] = []
    for cid in course_ids:
        snap = get_course_performance_mode(user_id, cid, student_id)
        modes.append(snap.get("performanceMode") or "not_enough_data")
        if snap.get("predictionVerified") and snap.get("status"):
            verified_statuses.append(str(snap["status"]))

    if verified_statuses:
        if any(s == "At Risk" for s in verified_statuses):
            label = "At risk"
        elif any(s == "Average" for s in verified_statuses):
            label = "Medium risk"
        else:
            label = "Low risk"
        return {
            "risk": label,
            "riskAvailable": True,
            "riskSource": "Based on verified ML performance prediction",
            "riskNote": None,
        }

    if all(m == "not_enough_data" for m in modes):
        return {
            "risk": "Not enough data",
            "riskAvailable": False,
            "riskSource": None,
            "riskNote": NOT_ENOUGH_DATA_MESSAGE,
        }

    if all(m in ("limited_insight", "not_enough_data") for m in modes):
        return {
            "risk": "Medium risk",
            "riskAvailable": True,
            "riskSource": "Based on current grade records and limited activity signals",
            "riskNote": LIMITED_INSIGHT_MESSAGE,
        }

    return {
        "risk": "Not enough data",
        "riskAvailable": False,
        "riskSource": None,
        "riskNote": NOT_ENOUGH_DATA_MESSAGE,
    }


def _course_grade_note(resolved: Dict[str, Any]) -> Optional[str]:
    if resolved.get("gradeAvailable"):
        return None
    return resolved.get("gradeNote")


def _gpa_from_percentages(grades: List[float]) -> Optional[float]:
    if not grades:
        return None
    avg_pct = sum(grades) / len(grades)
    return round(min(4.0, avg_pct / 25.0), 2)


def _midterm_average(courses_out: List[Dict[str, Any]]) -> Optional[float]:
    scores = [
        float(c["grade"])
        for c in courses_out
        if c.get("gradeSource") == "midterm_scoring" and c.get("grade") is not None
    ]
    if not scores:
        return None
    return round(sum(scores) / len(scores), 2)


def _official_transcript_payload(
    user_id: str,
    user: Dict[str, Any],
) -> Dict[str, Any]:
    record = ensure_demo_official_transcript(user_id, user.get("email"))
    if not record:
        record = get_official_transcript(user_id)
    if not record or record.get("official_cumulative_gpa") is None:
        return {
            "officialGpa": None,
            "officialGpaAvailable": False,
            "officialGpaSource": None,
            "officialGpaNote": "Upload your official transcript to show cumulative GPA.",
            "qualifiedHours": None,
            "qualifiedPoints": None,
            "transcriptLabel": None,
        }
    label = record.get("transcript_label") or LABEL_OFFICIAL
    return {
        "officialGpa": float(record["official_cumulative_gpa"]),
        "officialGpaAvailable": True,
        "officialGpaSource": "From uploaded official transcript",
        "officialGpaNote": None,
        "qualifiedHours": record.get("qualified_hours"),
        "qualifiedPoints": record.get("qualified_points"),
        "transcriptLabel": label,
    }


def build_synced_results(user: Dict[str, Any]) -> Dict[str, Any]:
    """Build dashboard results from synced MongoDB collections."""
    user_id = str(user["_id"])
    student_id = user.get("student_id")
    display_name = resolve_display_name(user)
    grade_rows = _grades(user_id)
    uploaded_by_course = map_by_course_id(user_id)
    courses_out: List[Dict[str, Any]] = []

    for course in get_visible_synced_courses_for_user(user_id):
        cid = str(course["id"])
        cname = course.get("name")
        uploaded = uploaded_by_course.get(cid)
        resolved = resolve_course_grade(grade_rows, cid, cname, uploaded)
        courses_out.append(
            {
                "name": cname,
                "grade": resolved["grade"],
                "gradeAvailable": resolved["gradeAvailable"],
                "gradeSource": resolved["gradeSource"],
                "gradeLabel": resolved["gradeLabel"],
                "gradeNote": _course_grade_note(resolved),
                "gpaEligible": resolved.get("gpaEligible", False),
                "excludeFromGpa": resolved.get("excludeFromGpa", True),
                "courseId": cid,
                "code": course.get("code") or _course_code(course["name"], cid),
                "source": course.get("source", "moodle_sync"),
                "lastSyncedAt": course.get("lastSyncedAt"),
                "titleSource": course.get("titleSource"),
                "activity": _course_activity_summary(user_id, cid),
            }
        )

    midterm_avg = _midterm_average(courses_out)
    midterm_available = midterm_avg is not None
    risk_payload = _derive_synced_risk(user_id, student_id, midterm_avg)
    official = _official_transcript_payload(user_id, user)

    return {
        "name": display_name,
        "loginEmail": resolve_login_email(user),
        # Official cumulative GPA (transcript) — not derived from midterm percentages.
        "gpa": official["officialGpa"],
        "gpaAvailable": official["officialGpaAvailable"],
        "gpaSource": official["officialGpaSource"],
        "gpaNote": official["officialGpaNote"],
        "officialGpa": official["officialGpa"],
        "officialGpaAvailable": official["officialGpaAvailable"],
        "officialGpaSource": official["officialGpaSource"],
        "officialGpaNote": official["officialGpaNote"],
        "qualifiedHours": official["qualifiedHours"],
        "qualifiedPoints": official["qualifiedPoints"],
        "transcriptLabel": official["transcriptLabel"],
        "midtermAverage": midterm_avg,
        "midtermAverageAvailable": midterm_available,
        "midtermAverageSource": (
            "Calculated from current midterm scoring records" if midterm_available else None
        ),
        "risk": risk_payload["risk"],
        "riskAvailable": risk_payload["riskAvailable"],
        "riskSource": risk_payload["riskSource"],
        "riskNote": risk_payload["riskNote"],
        "courses": courses_out,
        "dataSource": "synced",
        "lastSync": _last_sync_iso(user_id),
        "averageScore": midterm_avg,
    }


def build_student_results(user: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return dashboard results for the authenticated user.

    Synced Moodle data wins when present; demo accounts fall back to DEMO_RESULTS.
    """
    user_id = str(user["_id"])
    student_id = user.get("student_id")

    if should_use_visible_moodle_courses(user_id, student_id) or has_synced_moodle_data(user_id):
        return build_synced_results(user)

    if student_id in DEMO_STUDENT_IDS:
        demo = DEMO_RESULTS.get(student_id, {})
        if demo:
            return {
                **demo,
                "dataSource": "demo",
                "lastSync": None,
                "loginEmail": resolve_login_email(user),
                "gpaAvailable": demo.get("gpa") is not None,
                "gpaNote": None,
            }

    display_name = resolve_display_name(user)
    courses_out: List[Dict[str, Any]] = []
    grade_rows = _grades(user_id)

    for row in metrics_repository.list_for_user(user_id):
        cid = row.get("course_id")
        if cid == metrics_repository.OVERALL:
            continue
        metrics = row.get("metrics") or {}
        raw_name = metrics.get("course_name")
        if not is_real_course(cid, raw_name):
            continue
        name = _clean_course_name(raw_name)
        resolved = resolve_course_grade(grade_rows, str(cid), name)
        courses_out.append(
            {
                "name": name,
                "grade": resolved["grade"],
                "gradeAvailable": resolved["gradeAvailable"],
                "gradeSource": resolved["gradeSource"],
                "gradeLabel": resolved["gradeLabel"],
                "gradeNote": _course_grade_note(resolved),
                "gpaEligible": resolved.get("gpaEligible", False),
                "excludeFromGpa": resolved.get("excludeFromGpa", True),
                "courseId": str(cid),
                "code": _course_code(name, str(cid)),
                "activity": _course_activity_summary(user_id, str(cid)),
            }
        )
    courses_out.sort(key=lambda c: c["name"])

    graded = [
        c["grade"]
        for c in courses_out
        if c.get("gpaEligible") and c["grade"] is not None
    ]
    overall_avg = round(sum(graded) / len(graded), 1) if graded else None
    gpa_available = len(graded) >= 2

    return {
        "name": display_name,
        "loginEmail": resolve_login_email(user),
        "gpa": _gpa_from_percentages(graded) if gpa_available else None,
        "gpaAvailable": gpa_available,
        "gpaSource": (
            "Calculated from synced Moodle and uploaded grade records" if gpa_available else None
        ),
        "gpaNote": None if gpa_available else "GPA not available yet.",
        "risk": _derive_demo_risk(overall_avg),
        "riskAvailable": overall_avg is not None,
        "riskSource": "Based on synced course grades" if overall_avg is not None else None,
        "riskNote": (
            None
            if overall_avg is not None
            else "Risk analysis requires synced grades or activity data."
        ),
        "courses": courses_out,
        "dataSource": "metrics_only" if courses_out else "none",
        "lastSync": _last_sync_iso(user_id),
        "averageScore": overall_avg,
    }


def summarize_user_by_email(email: str) -> Dict[str, Any]:
    """Non-secret summary for GET /debug/user-data/{email}."""
    normalized = email.strip().lower()
    user = user_repository.find_by_email(normalized)
    if not user:
        return {
            "email": normalized,
            "userExists": False,
            "academiqUserId": None,
            "studentId": None,
            "coursesCount": 0,
            "materialsCount": 0,
            "metricsCount": 0,
            "featureVectorsCount": 0,
            "lastSyncedAt": None,
            "hasSyncedMoodleData": False,
            "dataSource": "none",
        }

    user_id = str(user["_id"])
    course_ids = {
        str(row.get("course_id"))
        for row in metrics_repository.list_for_user(user_id)
        if row.get("course_id") not in (None, metrics_repository.OVERALL)
        and is_real_course(
            row.get("course_id"),
            (row.get("metrics") or {}).get("course_name"),
        )
    }

    materials_count = 0
    if course_ids:
        materials_count = course_materials_collection.count_documents(
            {"course_id": {"$in": list(course_ids)}}
        )

    metrics_count = student_metrics_collection.count_documents(
        {"academiq_user_id": user_id}
    )
    fv_count = feature_vectors_collection.count_documents(
        {"$or": [{"academiq_user_id": user_id}, {"student_id": user.get("student_id")}]}
    )

    synced = has_synced_moodle_data(user_id)
    return {
        "email": user.get("email"),
        "userExists": True,
        "academiqUserId": user_id,
        "studentId": user.get("student_id"),
        "moodleUserId": user.get("moodle_user_id"),
        "coursesCount": len(course_ids),
        "materialsCount": materials_count,
        "metricsCount": metrics_count,
        "featureVectorsCount": fv_count,
        "lastSyncedAt": _last_sync_iso(user_id),
        "hasSyncedMoodleData": synced,
        "dataSource": "synced" if synced else "demo_or_none",
    }

"""
Grade data audit for dashboard diagnostics.
Safe output — no secrets, tokens, or full payload bodies.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.config.database import raw_moodle_payload_collection
from app.repositories import user_repository
from app.services.grade_resolution import resolve_course_grade, row_candidate_fields, grade_row_percentage
from app.services.moodle_course_display import get_visible_synced_courses_for_user
from app.services.student_data import _grades


def _grade_rows_doc(user_id: str) -> Optional[Dict[str, Any]]:
    return raw_moodle_payload_collection.find_one({"academiq_user_id": user_id})


def _why_not_available(resolved: Dict[str, Any]) -> str:
    case = resolved.get("missingCase")
    reason = resolved.get("missingGradeReason")
    if resolved.get("gradeAvailable"):
        return "grade_available"
    if case == "case_1_parse_failure":
        return "Grade rows exist but numeric parsing failed."
    if case == "case_3_non_numeric":
        return "Grade rows synced; all items are ungraded or non-numeric in Moodle."
    if case == "case_4_no_sync":
        return "No grade rows were synced for this course."
    if case == "case_5_senior_project":
        return "Senior project course with no synced numeric grade."
    if reason == "ungraded_in_moodle" or reason == "synced_grade_rows_have_no_numeric_scores":
        return "Grade rows synced; Moodle has no numeric scores yet (all '-' or pending)."
    if reason == "no_grade_rows_synced_for_course":
        return "Extension did not sync gradebook rows for this course."
    return resolved.get("gradeNote") or "No numeric grade available."


def _numeric_rows(rows: List[Dict[str, Any]], source: Optional[str] = None) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        src = row.get("grade_source") or "gradebook"
        if source == "gradebook" and src not in ("gradebook", None, ""):
            continue
        if source == "activity_page" and src != "activity_page":
            continue
        if grade_row_percentage(row) is not None:
            out.append(row)
    return out


def audit_missing_courses_deep(
    email: str,
    course_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Deep per-course grade source audit for troubleshooting missing grades."""
    normalized = email.strip().lower()
    user = user_repository.find_by_email(normalized)
    if not user:
        return {"user_email": normalized, "user_exists": False, "courses": []}

    user_id = str(user["_id"])
    raw_doc = _grade_rows_doc(user_id) or {}
    grade_rows = _grades(user_id)
    targets = course_ids or ["666", "808", "670"]

    reports: List[Dict[str, Any]] = []
    for cid in targets:
        cname = None
        for course in get_visible_synced_courses_for_user(user_id):
            if str(course["id"]) == str(cid):
                cname = course.get("name")
                break
        course_rows = [g for g in grade_rows if str(g.get("course_id")) == str(cid)]
        resolved = resolve_course_grade(grade_rows, str(cid), cname)
        gradebook_numeric = _numeric_rows(course_rows, "gradebook")
        activity_numeric = _numeric_rows(course_rows, "activity_page")
        activity_pages_checked = len(
            {
                str(r.get("source_url"))
                for r in course_rows
                if r.get("grade_source") == "activity_page" and r.get("source_url")
            }
        )
        numeric_candidates = [
            row_candidate_fields(r)
            for r in course_rows
            if row_candidate_fields(r).get("resolved_percentage") is not None
        ]
        dash_rows = [
            row_candidate_fields(r)
            for r in course_rows
            if row_candidate_fields(r).get("resolved_percentage") is None
        ]
        reports.append(
            {
                "course_id": str(cid),
                "course_name": cname,
                "grade_rows_found": len(course_rows),
                "gradebook_numeric_count": len(gradebook_numeric),
                "activity_numeric_count": len(activity_numeric),
                "activity_pages_checked": activity_pages_checked,
                "numeric_candidates_found": numeric_candidates,
                "numeric_course_total_found": resolved.get("hasCourseGrade"),
                "numeric_graded_items_found": resolved.get("gradedItemsUsed", 0),
                "all_numeric_candidates": numeric_candidates,
                "all_dash_or_pending_rows": dash_rows,
                "source_used": resolved.get("gradeSource"),
                "final_display_grade": resolved.get("displayGrade"),
                "source": resolved.get("displaySource"),
                "reason_if_not_available": resolved.get("gradeNote"),
                "reason_if_missing": resolved.get("gradeNote"),
                "gpa_eligible": resolved.get("gpaEligible"),
                "exclude_from_gpa": resolved.get("excludeFromGpa"),
            }
        )

    return {
        "user_email": user.get("email"),
        "user_exists": True,
        "courses": reports,
    }


def audit_grades_for_email(email: str) -> Dict[str, Any]:
    normalized = email.strip().lower()
    user = user_repository.find_by_email(normalized)
    if not user:
        return {
            "user_email": normalized,
            "user_exists": False,
            "summary": {
                "courses_count": 0,
                "courses_with_course_total": 0,
                "courses_with_computed_average": 0,
                "courses_without_grades": 0,
            },
            "grades_rows_total": 0,
            "grades_source": None,
            "courses": [],
        }

    user_id = str(user["_id"])
    raw_doc = _grade_rows_doc(user_id)
    grade_rows = _grades(user_id)
    courses = get_visible_synced_courses_for_user(user_id)

    course_reports: List[Dict[str, Any]] = []
    with_total = 0
    with_average = 0
    without_grades = 0

    for course in courses:
        cid = str(course["id"])
        cname = course.get("name")
        course_grade_rows = [
            g for g in grade_rows if str(g.get("course_id")) == cid
        ]
        resolved = resolve_course_grade(grade_rows, cid, cname)

        if resolved.get("gradeSource") == "course_total":
            with_total += 1
        elif resolved.get("gradeSource") == "graded_items_average":
            with_average += 1
        if not resolved.get("gradeAvailable"):
            without_grades += 1

        raw_examples = [
            row_candidate_fields(r)
            for r in course_grade_rows[:5]
        ]

        course_reports.append(
            {
                "course_id": cid,
                "course_name": cname,
                "grade_rows_found": len(course_grade_rows),
                "course_total_found": resolved.get("hasCourseGrade"),
                "course_total_value": resolved.get("courseGradeValue"),
                "course_total_source_field": (
                    "course_total" if resolved.get("hasCourseGrade") else None
                ),
                "graded_items_found": resolved.get("gradedItemsCount", 0),
                "graded_items_numeric_count": resolved.get("gradedItemsUsed", 0),
                "graded_items_average": resolved.get("computedAverage"),
                "all_candidate_grade_fields": resolved.get("allCandidateGradeFields"),
                "why_dashboard_currently_shows_not_available": _why_not_available(resolved),
                "missing_case": resolved.get("missingCase"),
                "display_grade": resolved.get("displayGrade"),
                "display_source": resolved.get("displaySource"),
                "grade_available": resolved.get("gradeAvailable"),
                "grade_reason": resolved.get("missingGradeReason"),
                "course_total_candidate": resolved.get("courseTotalCandidate"),
                "graded_items_count": resolved.get("gradedItemsCount"),
                "graded_items_used": resolved.get("gradedItemsUsed"),
                "computed_average": resolved.get("computedAverage"),
                "raw_grade_examples": raw_examples,
                # legacy fields kept for compatibility
                "has_course_grade": resolved.get("hasCourseGrade"),
                "course_grade_value": resolved.get("courseGradeValue"),
                "grade_source_collection": "raw_moodle_payload",
                "grade_source_field": resolved.get("gradeSource"),
                "has_graded_items": resolved.get("hasGradedItems"),
                "available_grade_items": resolved.get("availableGradeItems"),
                "missing_grade_reason": resolved.get("missingGradeReason"),
                "course_grade": resolved.get("grade"),
                "grade_source": resolved.get("gradeSource"),
                "computed_average_available": resolved.get("computedAverageAvailable"),
                "reason_if_missing": resolved.get("missingGradeReason"),
                "gpa_eligible": resolved.get("gpaEligible"),
                "exclude_from_gpa": resolved.get("excludeFromGpa"),
            }
        )

    return {
        "user_email": user.get("email"),
        "user_exists": True,
        "academiq_user_id": user_id,
        "summary": {
            "courses_count": len(course_reports),
            "courses_with_course_total": with_total,
            "courses_with_computed_average": with_average,
            "courses_without_grades": without_grades,
            "grades_rows_total": len(grade_rows),
            "gpa_eligible_courses": sum(1 for c in course_reports if c.get("gpa_eligible")),
        },
        "missing_courses_deep": audit_missing_courses_deep(email, ["666", "808", "670"]),
        "courses_count": len(course_reports),
        "grades_rows_total": len(grade_rows),
        "grades_source": (raw_doc or {}).get("grades_source"),
        "courses": course_reports,
    }

"""
Grade data audit for dashboard diagnostics.
Safe output — no secrets, tokens, or full payload bodies.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.config.database import raw_moodle_payload_collection
from app.repositories import user_repository
from app.services.grade_resolution import resolve_course_grade, row_candidate_fields
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
    if reason == "synced_grade_rows_have_no_numeric_scores":
        return "Grade rows synced; all items are ungraded or non-numeric in Moodle."
    if reason == "no_grade_rows_synced_for_course":
        return "Extension did not sync gradebook rows for this course."
    return resolved.get("gradeNote") or "No numeric grade available."


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
        },
        "courses_count": len(course_reports),
        "grades_rows_total": len(grade_rows),
        "grades_source": (raw_doc or {}).get("grades_source"),
        "courses": course_reports,
    }

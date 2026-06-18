"""
Resolve Moodle grade rows stored on raw_moodle_payload into dashboard-ready values.

Handles rows where `percentage` is missing but numeric values live in grade/max_grade,
and alternate field names (score, grade_percentage, etc.).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from app.repositories import user_repository
from app.services.student_data import _grades

_SOURCE_MOODLE_TOTAL = "moodle_course_total"
_SOURCE_UPLOADED = "uploaded_transcript"
_SOURCE_GRADED_AVG = "graded_items_average"

_LABEL_MOODLE_TOTAL = "Moodle course total"
_LABEL_UPLOADED = "Uploaded grade transcript"
_LABEL_GRADED_AVG = "Average from synced graded tasks"

_COURSE_TOTAL_RE = re.compile(
    r"(?:^|\b)(?:course\s+total|aggregation\s*course\s+total|total\s+for\s+course)(?:\b|$)",
    re.I,
)
_SENIOR_PROJECT_RE = re.compile(r"senior\s+project", re.I)
_NUMERIC_GRADE_RE = re.compile(r"^(\d+(?:\.\d+)?)")
_RANGE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[–\-]\s*(\d+(?:\.\d+)?)")
_GRADE_FIELD_NAMES = (
    "percentage",
    "grade_percentage",
    "grade",
    "raw_grade",
    "score",
    "final_grade",
    "course_total",
    "course_grade",
    "grade_value",
)
_MAX_FIELD_NAMES = (
    "max_grade",
    "max_score",
    "grade_max",
    "maximum_grade",
)
_NAME_FIELD_NAMES = (
    "item_name",
    "itemname",
    "title",
    "activity_name",
    "name",
)

# Maps missingGradeReason → audit case label
_REASON_CASE: Dict[str, str] = {
    "no_grade_rows_synced_for_course": "case_4_no_sync",
    "synced_grade_rows_have_no_numeric_scores": "case_3_non_numeric",
    "ungraded_in_moodle": "case_3_non_numeric",
    "senior_project_no_synced_grade": "case_5_senior_project",
    "parse_failure": "case_1_parse_failure",
}


def _normalize_course_id(value: Any) -> str:
    return str(value or "").strip()


def _row_item_name(row: Dict[str, Any]) -> str:
    for key in _NAME_FIELD_NAMES:
        val = row.get(key)
        if val:
            return str(val).strip()
    return ""


def _is_course_total_item(item_name: str) -> bool:
    name = (item_name or "").strip()
    if not name:
        return False
    return bool(_COURSE_TOTAL_RE.search(name))


def _is_senior_project_course(course_name: Optional[str], course_id: str) -> bool:
    if course_name and _SENIOR_PROJECT_RE.search(course_name):
        return True
    return False


def _gpa_flags(
    course_name: Optional[str],
    course_id: str,
    grade_available: bool,
    grade_source: Optional[str] = None,
) -> Dict[str, bool]:
    senior = _is_senior_project_course(course_name, course_id)
    if senior and grade_available and grade_source == _SOURCE_UPLOADED:
        return {"gpaEligible": True, "excludeFromGpa": False}
    return {
        "gpaEligible": grade_available and not senior,
        "excludeFromGpa": senior or not grade_available,
    }


def _base_resolve_fields(
    course_name: Optional[str],
    course_id: str,
    grade_available: bool,
    grade_source: Optional[str] = None,
) -> Dict[str, bool]:
    return _gpa_flags(course_name, course_id, grade_available, grade_source)


def _parse_max_points(max_grade: Any) -> Optional[float]:
    text = str(max_grade or "").strip()
    if not text:
        return None
    slash_parts = text.split("/")
    if len(slash_parts) >= 2:
        try:
            return float(slash_parts[-1].strip())
        except ValueError:
            pass
    match = _RANGE_RE.search(text)
    if match:
        low = float(match.group(1))
        high = float(match.group(2))
        if high > low:
            return high - low
        return high
    match = _NUMERIC_GRADE_RE.match(text)
    if match:
        return float(match.group(1))
    return None


def _parse_grade_points(grade: Any) -> Optional[float]:
    text = str(grade or "").strip()
    if not text or text == "-":
        return None
    if text.startswith("- "):
        return None
    if "/" in text:
        head = text.split("/", 1)[0].strip()
        try:
            return float(head)
        except ValueError:
            pass
    match = _NUMERIC_GRADE_RE.match(text)
    if match:
        return float(match.group(1))
    return None


def _direct_percentage(row: Dict[str, Any]) -> Optional[float]:
    for key in ("percentage", "grade_percentage"):
        val = row.get(key)
        if isinstance(val, (int, float)):
            pct = float(val)
            if 0 <= pct <= 1:
                return round(pct * 100.0, 1)
            if 0 <= pct <= 100:
                return round(pct, 1)
    return None


def _score_pair_percentage(row: Dict[str, Any]) -> Optional[float]:
    score = row.get("score")
    max_score = row.get("max_score")
    if isinstance(score, (int, float)) and isinstance(max_score, (int, float)):
        if max_score > 0:
            return round((float(score) / float(max_score)) * 100.0, 1)
    return None


def grade_row_percentage(row: Dict[str, Any]) -> Optional[float]:
    """Return 0–100 percentage for a single grade row, or None if not gradable."""
    direct = _direct_percentage(row)
    if direct is not None:
        return direct

    pair = _score_pair_percentage(row)
    if pair is not None:
        return pair

    for grade_key in ("grade", "raw_grade", "final_grade", "course_total", "course_grade", "grade_value"):
        points = _parse_grade_points(row.get(grade_key))
        if points is None:
            continue
        max_pts = None
        for max_key in _MAX_FIELD_NAMES:
            max_pts = _parse_max_points(row.get(max_key))
            if max_pts is not None:
                break
        if max_pts is not None and max_pts > 0:
            return round((points / max_pts) * 100.0, 1)

    return None


def row_candidate_fields(row: Dict[str, Any]) -> Dict[str, Any]:
    """Safe snapshot of grade-related fields on a row (for audit)."""
    keys = set(_GRADE_FIELD_NAMES) | set(_MAX_FIELD_NAMES) | set(_NAME_FIELD_NAMES) | {
        "course_id",
        "item_type",
        "submission_status",
    }
    out: Dict[str, Any] = {}
    for key in sorted(keys):
        if key in row and row[key] is not None:
            out[key] = row[key]
    out["resolved_percentage"] = grade_row_percentage(row)
    return out


def _rows_for_course(grades: List[Dict[str, Any]], course_id: str) -> List[Dict[str, Any]]:
    cid = _normalize_course_id(course_id)
    return [g for g in grades if _normalize_course_id(g.get("course_id")) == cid]


def graded_item_rows(grades: List[Dict[str, Any]], course_id: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in _rows_for_course(grades, course_id):
        if _is_course_total_item(_row_item_name(row)):
            continue
        pct = grade_row_percentage(row)
        if pct is None:
            continue
        out.append({**row, "_resolved_percentage": pct})
    return out


def course_total_row(grades: List[Dict[str, Any]], course_id: str) -> Optional[Dict[str, Any]]:
    for row in _rows_for_course(grades, course_id):
        if not _is_course_total_item(_row_item_name(row)):
            continue
        pct = grade_row_percentage(row)
        if pct is not None:
            return {**row, "_resolved_percentage": pct}
    return None


def _moodle_unavailable_payload(
    course_rows: List[Dict[str, Any]],
    total_row: Optional[Dict[str, Any]],
    course_name: Optional[str],
    course_id: str,
) -> Dict[str, Any]:
    if course_rows:
        if _is_senior_project_course(course_name, course_id):
            reason = "senior_project_no_synced_grade"
            note = "Project course grade is not available through synced Moodle grades."
        else:
            reason = "ungraded_in_moodle"
            note = "No numeric grade is currently published in Moodle for this course."
    else:
        reason = "no_grade_rows_synced_for_course"
        note = "Moodle grade data has not been synced yet."

    return {
        "grade": None,
        "gradeAvailable": False,
        "gradeSource": None,
        "gradeLabel": "Not available",
        "gradeNote": note,
        "displayGrade": None,
        "displaySource": "Not available",
        "moodleGrade": None,
        "moodleGradeSource": None,
        "uploadedGrade": None,
        "hasCourseGrade": False,
        "courseGradeValue": None,
        "courseTotalCandidate": (
            row_candidate_fields(total_row) if total_row else None
        ),
        "hasGradedItems": False,
        "gradedItemsCount": len(course_rows),
        "gradedItemsUsed": 0,
        "availableGradeItems": [],
        "missingGradeReason": reason,
        "missingCase": _REASON_CASE.get(reason, "case_3_non_numeric"),
        "computedAverage": None,
        "computedAverageAvailable": False,
        "allCandidateGradeFields": [row_candidate_fields(r) for r in course_rows[:8]],
        **_base_resolve_fields(course_name, course_id, False),
    }


def resolve_course_grade(
    grades: List[Dict[str, Any]],
    course_id: str,
    course_name: Optional[str] = None,
    uploaded_record: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Resolve the best display grade for dashboard / GPA / performance.

    Priority:
    1. Synced Moodle course total
    2. Uploaded grade transcript
    3. Average from synced graded Moodle tasks
    4. Not available
    """
    course_rows = _rows_for_course(grades, course_id)
    total_row = course_total_row(grades, course_id)
    graded_items = graded_item_rows(grades, course_id)

    available_items = [
        {
            "itemName": _row_item_name(r),
            "itemType": r.get("item_type"),
            "percentage": r["_resolved_percentage"],
        }
        for r in graded_items
    ]

    moodle_total_pct: Optional[float] = None
    if total_row is not None:
        moodle_total_pct = float(total_row["_resolved_percentage"])

    graded_avg: Optional[float] = None
    if graded_items:
        graded_avg = round(
            sum(r["_resolved_percentage"] for r in graded_items) / len(graded_items),
            1,
        )

    uploaded_pct: Optional[float] = None
    if uploaded_record is not None:
        raw = uploaded_record.get("grade_percentage")
        if isinstance(raw, (int, float)):
            uploaded_pct = round(float(raw), 1)

    # Priority 1 — Moodle course total
    if moodle_total_pct is not None:
        value = moodle_total_pct
        return {
            "grade": value,
            "gradeAvailable": True,
            "gradeSource": _SOURCE_MOODLE_TOTAL,
            "gradeLabel": _LABEL_MOODLE_TOTAL,
            "gradeNote": None,
            "displayGrade": value,
            "displaySource": _LABEL_MOODLE_TOTAL,
            "moodleGrade": value,
            "moodleGradeSource": _SOURCE_MOODLE_TOTAL,
            "uploadedGrade": uploaded_pct,
            "hasCourseGrade": True,
            "courseGradeValue": value,
            "courseTotalCandidate": row_candidate_fields(total_row),
            "hasGradedItems": bool(graded_items),
            "gradedItemsCount": len(graded_items),
            "gradedItemsUsed": len(graded_items),
            "availableGradeItems": available_items,
            "missingGradeReason": None,
            "missingCase": None,
            "computedAverage": graded_avg,
            "computedAverageAvailable": graded_avg is not None,
            "allCandidateGradeFields": [row_candidate_fields(r) for r in course_rows[:8]],
            **_base_resolve_fields(course_name, course_id, True, _SOURCE_MOODLE_TOTAL),
        }

    # Priority 2 — uploaded transcript
    if uploaded_pct is not None:
        return {
            "grade": uploaded_pct,
            "gradeAvailable": True,
            "gradeSource": _SOURCE_UPLOADED,
            "gradeLabel": _LABEL_UPLOADED,
            "gradeNote": None,
            "displayGrade": uploaded_pct,
            "displaySource": _LABEL_UPLOADED,
            "moodleGrade": None,
            "moodleGradeSource": None,
            "uploadedGrade": uploaded_pct,
            "hasCourseGrade": False,
            "courseGradeValue": None,
            "courseTotalCandidate": (
                row_candidate_fields(total_row) if total_row else None
            ),
            "hasGradedItems": bool(graded_items),
            "gradedItemsCount": len(graded_items),
            "gradedItemsUsed": len(graded_items),
            "availableGradeItems": available_items,
            "missingGradeReason": None,
            "missingCase": None,
            "computedAverage": graded_avg,
            "computedAverageAvailable": graded_avg is not None,
            "allCandidateGradeFields": [row_candidate_fields(r) for r in course_rows[:8]],
            **_base_resolve_fields(course_name, course_id, True, _SOURCE_UPLOADED),
        }

    # Priority 3 — graded tasks average
    if graded_avg is not None:
        return {
            "grade": graded_avg,
            "gradeAvailable": True,
            "gradeSource": _SOURCE_GRADED_AVG,
            "gradeLabel": _LABEL_GRADED_AVG,
            "gradeNote": None,
            "displayGrade": graded_avg,
            "displaySource": _LABEL_GRADED_AVG,
            "moodleGrade": graded_avg,
            "moodleGradeSource": _SOURCE_GRADED_AVG,
            "uploadedGrade": None,
            "hasCourseGrade": False,
            "courseGradeValue": None,
            "courseTotalCandidate": (
                row_candidate_fields(total_row) if total_row else None
            ),
            "hasGradedItems": True,
            "gradedItemsCount": len(graded_items),
            "gradedItemsUsed": len(graded_items),
            "availableGradeItems": available_items,
            "missingGradeReason": None,
            "missingCase": None,
            "computedAverage": graded_avg,
            "computedAverageAvailable": True,
            "allCandidateGradeFields": [row_candidate_fields(r) for r in course_rows[:8]],
            **_base_resolve_fields(course_name, course_id, True, _SOURCE_GRADED_AVG),
        }

    return _moodle_unavailable_payload(course_rows, total_row, course_name, course_id)


def resolve_course_grade_for_user(email: str, course_id: str) -> Dict[str, Any]:
    """Entry point: resolve grade for one course by user email."""
    from app.repositories.uploaded_grade_repository import get_for_course

    user = user_repository.find_by_email(email.strip().lower())
    if not user:
        return {
            "gradeAvailable": False,
            "missingGradeReason": "user_not_found",
            "gradeNote": "User not found.",
        }
    user_id = str(user["_id"])
    grades = _grades(user_id)
    uploaded = get_for_course(user_id, course_id)
    course_name = None
    from app.services.moodle_course_display import get_visible_synced_courses_for_user

    for course in get_visible_synced_courses_for_user(user_id):
        if str(course["id"]) == str(course_id):
            course_name = course.get("name")
            break
    return resolve_course_grade(grades, course_id, course_name, uploaded)


def average_percentage(
    grades: List[Dict[str, Any]],
    course_id: Optional[str] = None,
    item_type: Optional[str] = None,
) -> Optional[float]:
    rows = grades
    if course_id is not None:
        rows = _rows_for_course(grades, course_id)
    if item_type is not None:
        it = item_type.lower()
        rows = [g for g in rows if str(g.get("item_type") or "").lower() == it]

    vals: List[float] = []
    for row in rows:
        if _is_course_total_item(_row_item_name(row)):
            continue
        pct = grade_row_percentage(row)
        if pct is not None:
            vals.append(pct)
    return round(sum(vals) / len(vals), 1) if vals else None


def course_display_percentage(
    grades: List[Dict[str, Any]],
    course_id: str,
    course_name: Optional[str] = None,
    uploaded_record: Optional[Dict[str, Any]] = None,
) -> Optional[float]:
    resolved = resolve_course_grade(grades, course_id, course_name, uploaded_record)
    return resolved["grade"] if resolved.get("gradeAvailable") else None

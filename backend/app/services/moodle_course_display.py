"""
Display helpers for Moodle-synced courses and student identity on the Dashboard.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.config.database import raw_moodle_payload_collection
from app.demo_data import DEMO_STUDENT_IDS
from app.repositories import material_repository, metrics_repository
from app.services.moodle_ingest import is_real_course


def _clean_course_name(name: Optional[str]) -> str:
    name = (name or "").strip()
    if name.lower().startswith("course "):
        name = name[len("course ") :].strip()
    return name or "Untitled Course"


def _course_code(name: str, course_id: str) -> str:
    words = [w for w in name.replace("-", " ").split() if w[:1].isalpha()]
    initials = "".join(w[0].upper() for w in words[:3])
    return initials or f"C{course_id}"


def _iso_timestamp(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    text = str(value).strip()
    return text or None


def _normalize_person_name(name: Optional[str]) -> str:
    """Collapse whitespace and remove consecutive duplicate name tokens."""
    if not name:
        return ""
    text = re.sub(r"\s+", " ", str(name).strip())
    words = text.split()
    deduped: List[str] = []
    for word in words:
        if not deduped or word.lower() != deduped[-1].lower():
            deduped.append(word)
    return " ".join(deduped)


def _looks_like_internal_id(value: str) -> bool:
    lower = value.strip().lower()
    return lower.startswith("stu_") or lower.startswith("moodle+")


def resolve_display_name(user: Dict[str, Any]) -> str:
    """
    Prefer Moodle full name, then MongoDB name fields, then email local-part.
    """
    user_id = str(user["_id"])
    raw = raw_moodle_payload_collection.find_one({"academiq_user_id": user_id}) or {}
    student = raw.get("student") or {}

    for candidate in (
        student.get("full_name"),
        user.get("full_name"),
        user.get("name"),
    ):
        cleaned = _normalize_person_name(candidate)
        if cleaned and not _looks_like_internal_id(cleaned):
            return cleaned

    email = (user.get("email") or "").strip().lower()
    if email and "@" in email:
        local = email.split("@", 1)[0]
        local = re.sub(r"[._+-]+", " ", local)
        local = re.sub(r"\d+", " ", local).strip()
        if local:
            return " ".join(part.capitalize() for part in local.split())

    return "Student"


def resolve_login_email(user: Dict[str, Any]) -> str:
    """Email shown on Dashboard — never the internal stu_* provisioning id."""
    email = (user.get("email") or "").strip()
    if email and "@" in email:
        return email
    student_id = (user.get("student_id") or "").strip()
    if student_id and "@" in student_id:
        return student_id
    return email or student_id or ""


def _is_bare_course_id(name: Optional[str], course_id: str) -> bool:
    cid = str(course_id).strip()
    n = (name or "").strip()
    if not n:
        return True
    if n == cid or n == f"Course {cid}":
        return True
    cleaned = _clean_course_name(n)
    if cleaned == cid or (cleaned.isdigit() and cleaned == cid):
        return True
    return False


_SECTION_GROUP_RE = re.compile(
    r":\s*(General|Section|Topic|Group|Week\s*\d+)\s*$",
    re.IGNORECASE,
)


def _is_section_group_name(name: Optional[str]) -> bool:
    """Moodle subsection / group labels such as 'Course Name: General'."""
    text = (name or "").strip()
    if not text:
        return False
    return bool(_SECTION_GROUP_RE.search(text))


def _dashboard_hide_reason(
    display_name: str,
    course_id: str,
    title_source: Optional[str] = None,
) -> Optional[str]:
    """
    Return a hide reason for non-top-level Dashboard courses, or None if visible.
    """
    if _is_section_group_name(display_name):
        return "section_general_group"
    if title_source == "fallback_id" or _is_bare_course_id(display_name, course_id):
        return "numeric_orphan"
    return None


def _is_top_level_course_name(name: str, course_id: str) -> bool:
    return _dashboard_hide_reason(name, course_id) is None


def _course_name_map_from_raw(raw: Dict[str, Any], user_id: str = "") -> Dict[str, str]:
    """Best non-bare Moodle title per course_id from the latest payload + metrics."""
    resolved: Dict[str, str] = {}
    for cid, candidates in _course_name_candidates_from_raw(raw, user_id).items():
        name, _source = _pick_best_course_name(cid, candidates)
        if name:
            resolved[cid] = name
    return resolved


def _course_name_candidates_from_raw(
    raw: Dict[str, Any],
    user_id: str,
) -> Dict[str, List[Tuple[str, str]]]:
    """course_id -> [(name, source), ...] from every payload location."""
    out: Dict[str, List[Tuple[str, str]]] = {}

    def add(cid: Any, name: Any, source: str) -> None:
        cid_str = str(cid or "").strip()
        if not cid_str or not name:
            return
        cleaned = _clean_course_name(str(name))
        if not cleaned or cleaned == "Untitled Course":
            return
        bucket = out.setdefault(cid_str, [])
        if not any(existing == cleaned for existing, _ in bucket):
            bucket.append((cleaned, source))

    for course in raw.get("courses") or []:
        cid = course.get("course_id")
        add(cid, course.get("course_name"), course.get("course_name_source") or "raw_courses")

    for cid, metrics in (raw.get("metricsByCourse") or {}).items():
        if metrics:
            add(
                cid,
                metrics.get("course_name"),
                metrics.get("course_name_source") or "metrics_by_course",
            )

    if user_id:
        for row in metrics_repository.list_for_user(user_id):
            cid = row.get("course_id")
            if cid == metrics_repository.OVERALL:
                continue
            metrics = row.get("metrics") or {}
            add(
                cid,
                metrics.get("course_name"),
                metrics.get("course_name_source") or "student_metrics",
            )

        for cid in {str(c.get("course_id")) for c in (raw.get("courses") or []) if c.get("course_id")}:
            for doc in material_repository.list_by_course(cid):
                add(cid, doc.get("course_name") or doc.get("title"), "course_materials")

    return out


def _pick_best_course_name(
    course_id: str,
    candidates: List[Tuple[str, str]],
) -> Tuple[str, str]:
    """Return the best display name and the source that supplied it."""
    cid = str(course_id)
    for name, source in candidates:
        if name and not _is_bare_course_id(name, cid):
            return name, source
    return f"Course {cid}", "fallback_id"


def resolve_synced_course_display_name(
    course_id: str,
    raw_name: Optional[str],
    name_map: Dict[str, str],
) -> str:
    """Prefer Moodle title; fall back to Course <id> when only a numeric id exists."""
    cid = str(course_id)
    inline = [(_clean_course_name(raw_name), "inline_raw_name")] if raw_name else []
    mapped = [(name_map[cid], "name_map")] if name_map.get(cid) else []
    name, _source = _pick_best_course_name(cid, inline + mapped)
    return name


def resolve_synced_course_display_name_with_source(
    course_id: str,
    raw_name: Optional[str],
    candidates_map: Dict[str, List[Tuple[str, str]]],
) -> Tuple[str, str]:
    cid = str(course_id)
    candidates: List[Tuple[str, str]] = list(candidates_map.get(cid, []))
    if raw_name:
        candidates.insert(0, (_clean_course_name(raw_name), "inline_raw_name"))
    return _pick_best_course_name(cid, candidates)


def _course_entry(
    course_id: str,
    display_name: str,
    last_synced_at: Optional[str],
    title_source: Optional[str] = None,
) -> Dict[str, Any]:
    entry = {
        "id": course_id,
        "name": display_name,
        "code": _course_code(display_name, course_id),
        "source": "moodle_sync",
        "lastSyncedAt": last_synced_at,
    }
    if title_source:
        entry["titleSource"] = title_source
    return entry


def extract_synced_courses(
    user_id: str,
    *,
    collect_filter_reasons: bool = False,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Build the Moodle course list from the latest raw payload for this user.

    Returns (visible_top_level_courses, hidden_courses_with_reasons).
    """
    raw = raw_moodle_payload_collection.find_one({"academiq_user_id": user_id}) or {}
    candidates_map = _course_name_candidates_from_raw(raw, user_id)
    payload_synced_at = _iso_timestamp(raw.get("updated_at") or raw.get("created_at"))

    by_id: Dict[str, Dict[str, Any]] = {}
    hidden: List[Dict[str, Any]] = []
    hidden_keys: set[str] = set()

    def _record_hidden(entry: Dict[str, Any]) -> None:
        if not collect_filter_reasons:
            return
        key = f"{entry.get('courseId')}:{entry.get('hiddenReason')}"
        if key in hidden_keys:
            return
        hidden_keys.add(key)
        hidden.append(entry)

    def _register_course(
        course_id: str,
        raw_name: Optional[str],
        last_access: Any = None,
        origin: str = "raw_courses",
    ) -> None:
        cid = str(course_id).strip()
        if not cid:
            _record_hidden(
                {
                    "courseId": None,
                    "courseName": None,
                    "hiddenReason": "missing_course_id",
                    "origin": origin,
                }
            )
            return
        if cid in by_id:
            return
        if not is_real_course(cid, raw_name):
            _record_hidden(
                {
                    "courseId": cid,
                    "courseName": raw_name,
                    "hiddenReason": "excluded_nav_or_site_home",
                    "origin": origin,
                }
            )
            return

        display, title_source = resolve_synced_course_display_name_with_source(
            cid, raw_name, candidates_map
        )
        hide_reason = _dashboard_hide_reason(display, cid, title_source)
        if hide_reason:
            _record_hidden(
                {
                    "courseId": cid,
                    "courseName": display,
                    "hiddenReason": hide_reason,
                    "titleSource": title_source,
                    "origin": origin,
                }
            )
            return

        last_synced = _iso_timestamp(last_access) or payload_synced_at
        by_id[cid] = _course_entry(cid, display, last_synced, title_source)

    # Primary: My Courses / extension course cards (raw payload courses array).
    for course in raw.get("courses") or []:
        cid = course.get("course_id")
        _register_course(
            str(cid) if cid is not None else "",
            course.get("course_name"),
            course.get("last_access_time"),
            origin="raw_courses",
        )

    # Supplement only when a real top-level title exists outside the card list.
    for cid, metrics in (raw.get("metricsByCourse") or {}).items():
        if not metrics:
            continue
        _register_course(
            str(cid),
            metrics.get("course_name"),
            metrics.get("last_access_time"),
            origin="metrics_by_course",
        )

    for row in metrics_repository.list_for_user(user_id):
        cid = row.get("course_id")
        if cid == metrics_repository.OVERALL:
            continue
        metrics = row.get("metrics") or {}
        _register_course(
            str(cid),
            metrics.get("course_name"),
            metrics.get("last_access_time"),
            origin="student_metrics",
        )

    courses = sorted(by_id.values(), key=lambda c: c["name"].lower())
    return courses, hidden


def should_use_visible_moodle_courses(
    user_id: str,
    student_id: Optional[str] = None,
) -> bool:
    """
    True when this account should use the filtered Moodle My Courses list.

    Demo seeded accounts keep their hardcoded course lists even if a raw
    payload exists with grades_source=seeded.
    """
    if student_id in DEMO_STUDENT_IDS:
        return False
    raw = raw_moodle_payload_collection.find_one({"academiq_user_id": user_id})
    if not raw:
        return False
    if raw.get("grades_source") == "seeded":
        return False
    return bool(
        raw.get("courses")
        or raw.get("metricsByCourse")
        or raw.get("sync_count")
        or raw.get("behavior")
    )


def get_visible_synced_courses_for_user(user_id: str) -> List[Dict[str, Any]]:
    """
    Canonical filtered top-level Moodle course list for all student-facing APIs.

    Same logic as GET /debug/synced-courses visibleCourses.
    """
    courses, _hidden = extract_synced_courses(user_id)
    return courses


def get_synced_courses_for_user(user_id: str) -> List[Dict[str, Any]]:
    """Alias for backwards compatibility — always returns visible courses only."""
    return get_visible_synced_courses_for_user(user_id)


def debug_synced_courses_for_email(email: str) -> Dict[str, Any]:
    """Safe diagnostics for GET /debug/synced-courses/{email}."""
    from app.repositories import user_repository

    normalized = email.strip().lower()
    user = user_repository.find_by_email(normalized)
    if not user:
        return {
            "email": normalized,
            "userExists": False,
            "academiqUserId": None,
            "rawPayloadCount": 0,
            "extractedCourseCount": 0,
            "visibleCourses": [],
            "hiddenCourses": [],
            "visibleCourseCount": 0,
            "hiddenCourseCount": 0,
        }

    user_id = str(user["_id"])
    raw_payload_count = raw_moodle_payload_collection.count_documents(
        {"academiq_user_id": user_id}
    )
    raw = raw_moodle_payload_collection.find_one({"academiq_user_id": user_id}) or {}
    extracted_count = len(raw.get("courses") or [])

    visible, hidden = extract_synced_courses(user_id, collect_filter_reasons=True)

    return {
        "email": user.get("email"),
        "userExists": True,
        "academiqUserId": user_id,
        "rawPayloadCount": raw_payload_count,
        "extractedCourseCount": extracted_count,
        "visibleCourses": visible,
        "visibleCourseCount": len(visible),
        "hiddenCourses": hidden,
        "hiddenCourseCount": len(hidden),
        # Back-compat aliases — filtered visible list only (never unfiltered).
        "normalizedCourseList": visible,
        "displayedCourseCount": len(visible),
        "filteredCourses": hidden,
        "filteredCount": len(hidden),
        "usesVisibleCourseList": should_use_visible_moodle_courses(
            user_id, user.get("student_id")
        ),
    }

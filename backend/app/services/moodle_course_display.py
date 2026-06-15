"""
Display helpers for Moodle-synced courses and student identity on the Dashboard.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.config.database import raw_moodle_payload_collection
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


def _normalize_title_key(name: str) -> str:
    """Normalize course title for deduplication (strip suffix noise)."""
    key = _clean_course_name(name).lower()
    for suffix in (": general", " - general", " general"):
        if key.endswith(suffix):
            key = key[: -len(suffix)].strip()
    return re.sub(r"[^a-z0-9]+", "", key)


def _course_names_from_raw(user_id: str) -> Dict[str, str]:
    raw = raw_moodle_payload_collection.find_one({"academiq_user_id": user_id}) or {}
    names: Dict[str, str] = {}
    for course in raw.get("courses") or []:
        cid = str(course.get("course_id") or "").strip()
        if cid and course.get("course_name"):
            names[cid] = _clean_course_name(course["course_name"])
    for cid, metrics in (raw.get("metricsByCourse") or {}).items():
        if metrics and metrics.get("course_name"):
            names[str(cid)] = _clean_course_name(metrics["course_name"])
    return names


def _course_has_substance(metrics: Dict[str, Any], course_id: str) -> bool:
    if material_repository.list_by_course(str(course_id)):
        return True
    return any(
        (metrics.get(key) or 0) > 0
        for key in (
            "quiz_attempts",
            "assignment_submissions",
            "number_of_quizzes_viewed",
            "number_of_assignments_viewed",
            "number_of_resources_clicked",
        )
    )


def resolve_synced_course_name(
    course_id: str,
    metrics_name: Optional[str],
    raw_names: Dict[str, str],
) -> str:
    cid = str(course_id)
    for candidate in (_clean_course_name(metrics_name), raw_names.get(cid)):
        if candidate and candidate != "Untitled Course" and not _is_bare_course_id(candidate, cid):
            return candidate
    for doc in material_repository.list_by_course(cid):
        title = _clean_course_name(doc.get("course_name") or doc.get("title"))
        if title and not _is_bare_course_id(title, cid):
            return title
    return f"Course {cid}"


def get_synced_courses_for_user(user_id: str) -> List[Dict[str, Any]]:
    """Courses for synced Moodle users — filtered, deduped, with readable titles."""
    raw_names = _course_names_from_raw(user_id)
    by_id: Dict[str, Dict[str, Any]] = {}
    by_title: Dict[str, str] = {}

    def _prefer_name(current: str, candidate: str, course_id: str) -> str:
        if ": General" in current and ": General" not in candidate:
            return candidate
        if current.lower().startswith("course ") and not candidate.lower().startswith("course "):
            return candidate
        if _is_bare_course_id(current, course_id) and not _is_bare_course_id(candidate, course_id):
            return candidate
        return candidate if len(candidate) < len(current) else current

    for row in metrics_repository.list_for_user(user_id):
        cid = row.get("course_id")
        if cid == metrics_repository.OVERALL:
            continue
        cid_str = str(cid)
        metrics = row.get("metrics") or {}
        raw_name = metrics.get("course_name")
        if not is_real_course(cid, raw_name):
            continue

        display_name = resolve_synced_course_name(cid_str, raw_name, raw_names)
        if _is_bare_course_id(display_name, cid_str) and not _course_has_substance(metrics, cid_str):
            continue
        if _is_bare_course_id(display_name, cid_str):
            display_name = f"Course {cid_str}"

        title_key = _normalize_title_key(display_name)
        if title_key in by_title:
            existing_id = by_title[title_key]
            existing = by_id[existing_id]
            existing["name"] = _prefer_name(existing["name"], display_name, existing_id)
            existing["code"] = _course_code(existing["name"], existing_id)
            continue

        existing = by_id.get(cid_str)
        if existing:
            existing["name"] = _prefer_name(existing["name"], display_name, cid_str)
            existing["code"] = _course_code(existing["name"], cid_str)
            continue

        by_id[cid_str] = {
            "id": cid_str,
            "name": display_name,
            "code": _course_code(display_name, cid_str),
        }
        by_title[title_key] = cid_str

    courses = list(by_id.values())
    courses.sort(key=lambda c: c["name"].lower())
    return courses

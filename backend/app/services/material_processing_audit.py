"""
Full material processing audit across synced Moodle courses.
Safe diagnostics — no content_text bodies, secrets, or tokens.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.repositories import material_repository, user_repository
from app.services.material_quiz_display import (
    classify_material_kind,
    extract_material_number,
    is_educational_material,
    matches_educational_title,
    resolve_quiz_material_display,
)
from app.services.moodle_course_display import get_visible_synced_courses_for_user
from app.services.material_quiz_upload import _find_canonical_learning_row, _mongo_id_str as upload_mongo_id_str
from app.services.student_data import MIN_QUIZ_CONTENT_CHARS

_PLUGINFILE_RE = re.compile(r"pluginfile\.php", re.I)
_RESOURCE_VIEW_RE = re.compile(r"/mod/resource/view\.php", re.I)

_ISSUE_ROW_MISMATCH = "row_mismatch"
_ISSUE_NEVER_ATTEMPTED = "never_attempted"
_ISSUE_DOWNLOAD_URL = "download_url_problem"
_ISSUE_FETCH_FAILED = "fetch_failed"
_ISSUE_EXTRACTED_NOT_ENOUGH = "extracted_but_not_enough"
_ISSUE_MISCLASSIFIED = "misclassified"
_ISSUE_ACTUALLY_OK = "actually_ok"
_ISSUE_OTHER = "other"


def _mongo_id_str(doc: Dict[str, Any]) -> Optional[str]:
    oid = doc.get("_id")
    return str(oid) if oid is not None else None


def _content_length(doc: Dict[str, Any]) -> int:
    text = (doc.get("content_text") or "").strip()
    if text:
        return len(text)
    chars = doc.get("content_chars")
    if isinstance(chars, int) and chars > 0:
        return chars
    return 0


def _is_pdf_or_pptx(file_type: str) -> bool:
    return (file_type or "").lower() in ("pdf", "pptx", "ppt")


def _has_download_url_problem(source_url: str, resolved_url: str, file_type: str) -> bool:
    if not _is_pdf_or_pptx(file_type):
        return False
    urls = [u for u in (source_url, resolved_url) if u]
    if not urls:
        return False
    has_pluginfile = any(_PLUGINFILE_RE.search(u) for u in urls)
    if has_pluginfile:
        return False
    return any(_RESOURCE_VIEW_RE.search(u) for u in urls)


def _build_kind_index(docs: List[Dict[str, Any]]) -> Dict[str, Dict[int, List[Dict[str, Any]]]]:
    index: Dict[str, Dict[int, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for doc in docs:
        if doc.get("hidden_duplicate"):
            continue
        title = doc.get("title") or ""
        ft = str(doc.get("file_type") or "")
        is_non_quiz = not is_educational_material(title, ft) and not matches_educational_title(title)
        kind = classify_material_kind(title, ft, is_non_quiz)
        num = extract_material_number(title, kind)
        if num > 0 and kind in ("lecture", "lab", "revision"):
            index[kind][num].append(doc)
    return index


def _sibling_with_content(
    doc: Dict[str, Any],
    kind_index: Dict[str, Dict[int, List[Dict[str, Any]]]],
    min_chars: int = 100,
) -> Optional[Dict[str, Any]]:
    title = doc.get("title") or ""
    ft = str(doc.get("file_type") or "")
    is_non_quiz = not is_educational_material(title, ft) and not matches_educational_title(title)
    kind = classify_material_kind(title, ft, is_non_quiz)
    num = extract_material_number(title, kind)
    if num <= 0:
        return None
    siblings = kind_index.get(kind, {}).get(num, [])
    my_id = str(doc.get("material_id") or "")
    for sibling in siblings:
        sid = str(sibling.get("material_id") or "")
        if sid == my_id:
            continue
        if _content_length(sibling) >= min_chars:
            return sibling
    return None


def _compute_flags(
    doc: Dict[str, Any],
    display: Dict[str, Any],
    kind_index: Dict[str, Dict[int, List[Dict[str, Any]]]],
) -> Dict[str, bool]:
    title = doc.get("title") or ""
    ft = str(doc.get("file_type") or "").lower()
    source_url = str(doc.get("url") or doc.get("source_url") or "")
    resolved_url = str(doc.get("resolved_url") or "")
    content_len = display.get("content_text_length") or _content_length(doc)
    quiz_status = display.get("quiz_status") or ""
    probe = int(display.get("probe_question_count") or 0)
    last_attempted = doc.get("last_attempted_at")
    processed_at = doc.get("processed_at")
    extraction_status = str(doc.get("extraction_status") or "")
    extraction_error = str(doc.get("extraction_error") or "").lower()
    is_educ = display.get("is_educational_material", False)
    visible_main = display.get("visible_in_main_list", False)

    sibling = _sibling_with_content(doc, kind_index) if content_len == 0 else None
    duplicate_of = doc.get("duplicate_of")

    flags = {
        "needs_upload_attempt": bool(
            is_educ
            and visible_main
            and content_len == 0
            and quiz_status in (
                "not_uploaded",
                "extraction_failed",
                "not_enough_readable_text",
            )
        ),
        "uploaded_but_row_not_updated": bool(
            visible_main
            and content_len == 0
            and (last_attempted or processed_at)
        ),
        "has_source_url_but_no_content": bool(source_url and content_len == 0),
        "has_resolved_url_but_no_content": bool(resolved_url and content_len == 0),
        "pdf_or_pptx_but_not_uploaded": bool(
            _is_pdf_or_pptx(ft) and quiz_status == "not_uploaded" and content_len == 0
        ),
        "educational_but_marked_not_quiz": bool(
            matches_educational_title(title) and quiz_status == "not_quiz_material"
        ),
        "ready_but_would_not_generate": bool(
            quiz_status in ("ready", "limited_ready")
            and not display.get("will_generate_successfully", False)
        ),
        "not_uploaded_after_upload_attempt": bool(
            last_attempted
            and content_len == 0
            and quiz_status == "not_uploaded"
        ),
        "duplicate_content_on_other_row": bool(
            sibling is not None or duplicate_of and content_len == 0
        ),
        "download_url_problem": _has_download_url_problem(source_url, resolved_url, ft),
        "fetch_failed": bool(
            quiz_status == "extraction_failed"
            or extraction_status == "extraction_failed"
            or "download_failed" in extraction_error
            or extraction_error.startswith("http_")
        ),
        "extracted_but_not_enough": bool(
            content_len > 0 and probe < 3 and quiz_status not in ("ready", "limited_ready")
        ),
        "actually_ok": bool(
            quiz_status in ("ready", "limited_ready")
            and display.get("will_generate_successfully", False)
            and probe >= 3
        ),
    }
    return flags


def _primary_issue_type(flags: Dict[str, bool], display: Dict[str, Any]) -> str:
    if flags.get("actually_ok"):
        return _ISSUE_ACTUALLY_OK
    if flags.get("duplicate_content_on_other_row") or flags.get("uploaded_but_row_not_updated"):
        return _ISSUE_ROW_MISMATCH
    if flags.get("educational_but_marked_not_quiz"):
        return _ISSUE_MISCLASSIFIED
    if flags.get("fetch_failed"):
        return _ISSUE_FETCH_FAILED
    if flags.get("download_url_problem"):
        return _ISSUE_DOWNLOAD_URL
    if flags.get("extracted_but_not_enough"):
        return _ISSUE_EXTRACTED_NOT_ENOUGH
    if (
        flags.get("needs_upload_attempt")
        or flags.get("not_uploaded_after_upload_attempt")
        or flags.get("pdf_or_pptx_but_not_uploaded")
    ):
        return _ISSUE_NEVER_ATTEMPTED
    return _ISSUE_OTHER


def _upload_identity_section(doc: Dict[str, Any], display: Dict[str, Any]) -> Dict[str, Any]:
    audit = dict(doc.get("last_upload_audit") or {})
    last_attempted = doc.get("last_attempted_at")
    attempted = bool(last_attempted or doc.get("processed_at") or audit)

    section = {
        "was_in_preflight": audit.get("was_in_preflight"),
        "preflight_should_upload": audit.get("preflight_should_upload"),
        "was_in_extension_upload_queue": audit.get("was_in_extension_upload_queue"),
        "was_attempted_by_extension": audit.get("was_attempted_by_extension") or attempted,
        "download_url_used": audit.get("download_url_used"),
        "download_status": audit.get("download_status"),
        "backend_upload_called": audit.get("backend_upload_called"),
        "backend_response_status": audit.get("backend_response_status"),
        "matched_db_id_before_upload": audit.get("matched_db_id_before_upload"),
        "final_saved_db_id": audit.get("final_saved_db_id"),
        "final_content_text_length": audit.get("final_content_text_length"),
        "final_quiz_status": audit.get("final_quiz_status"),
        "failure_reason": audit.get("failure_reason") or doc.get("extraction_error"),
        "last_upload_audit_at": (
            doc.get("last_upload_audit_at").isoformat()
            if isinstance(doc.get("last_upload_audit_at"), datetime)
            else doc.get("last_upload_audit_at")
        ),
        "last_attempted_at": (
            last_attempted.isoformat() if isinstance(last_attempted, datetime) else last_attempted
        ),
    }

    if not attempted:
        section.update(
            {
                "was_attempted_by_extension": False,
                "note": "No last_attempted_at or last_upload_audit on this row",
            }
        )
    elif not audit:
        section["note"] = "Attempt inferred from timestamps; no stored last_upload_audit blob"

    return section


def _canonical_db_id_for_doc(doc: Dict[str, Any], course_id: str) -> Optional[str]:
    title = doc.get("title") or ""
    ft = str(doc.get("file_type") or "")
    canonical = _find_canonical_learning_row(course_id, title, ft)
    if not canonical:
        return _mongo_id_str(doc)
    return upload_mongo_id_str(canonical) or _mongo_id_str(doc)


def _audit_one_educational_material(
    doc: Dict[str, Any],
    display: Dict[str, Any],
    kind_index: Dict[str, Dict[int, List[Dict[str, Any]]]],
    course_id: str,
) -> Dict[str, Any]:
    flags = _compute_flags(doc, display, kind_index)
    issue_type = _primary_issue_type(flags, display)
    sibling = _sibling_with_content(doc, kind_index) if flags["duplicate_content_on_other_row"] else None
    upload_identity = _upload_identity_section(doc, display)
    canonical_db_id = _canonical_db_id_for_doc(doc, course_id)

    row = {
        "title": display.get("title") or doc.get("title"),
        "issue_type": issue_type,
        "material_id": str(doc.get("material_id") or ""),
        "db_id": _mongo_id_str(doc),
        "canonical_db_id": canonical_db_id,
        "file_type": display.get("file_type") or doc.get("file_type"),
        "source_url": doc.get("url") or doc.get("source_url"),
        "resolved_url": doc.get("resolved_url"),
        "download_url_used": upload_identity.get("download_url_used"),
        "download_status": upload_identity.get("download_status"),
        "quiz_status": display.get("quiz_status"),
        "extraction_status": doc.get("extraction_status"),
        "content_text_length": display.get("content_text_length") or _content_length(doc),
        "ready_for_quiz": display.get("ready_for_quiz", False),
        "quiz_generation_eligible": display.get("quiz_generation_eligible", False),
        "selectable": display.get("selectable", False),
        "visible_in_main_list": display.get("visible_in_main_list", False),
        "visible_in_other_items": display.get("visible_in_other_items", False),
        "probe_question_count": display.get("probe_question_count"),
        "reason": display.get("reason") or display.get("why_not_ready"),
        "last_attempted_at": (
            doc.get("last_attempted_at").isoformat()
            if isinstance(doc.get("last_attempted_at"), datetime)
            else doc.get("last_attempted_at")
        ),
        "processed_at": (
            doc.get("processed_at").isoformat()
            if isinstance(doc.get("processed_at"), datetime)
            else doc.get("processed_at")
        ),
        "is_metadata_only": bool(doc.get("metadata_only")),
        "is_duplicate": bool(doc.get("duplicate_of")),
        "hidden_duplicate": bool(doc.get("hidden_duplicate")),
        "duplicate_of": doc.get("duplicate_of"),
        "material_kind": display.get("material_kind"),
        "material_number": display.get("material_number"),
        "stable_material_key": doc.get("stable_material_key"),
        "flags": flags,
        "upload_identity": upload_identity,
    }
    if sibling:
        row["content_on_sibling_row"] = {
            "material_id": sibling.get("material_id"),
            "title": sibling.get("title"),
            "content_text_length": _content_length(sibling),
            "db_id": _mongo_id_str(sibling),
        }
    return row


def _audit_course(course_id: str, course_name: str) -> Dict[str, Any]:
    docs = material_repository.list_by_course(course_id)
    hidden_ids = {str(d.get("material_id")) for d in docs if d.get("hidden_duplicate")}
    displays, _ = resolve_quiz_material_display(docs)
    doc_by_id = {str(d.get("material_id") or ""): d for d in docs}
    kind_index = _build_kind_index(docs)

    educational_materials: List[Dict[str, Any]] = []
    status_counts: Dict[str, int] = defaultdict(int)

    for display in displays:
        mid = str(display.get("material_id") or "")
        doc = doc_by_id.get(mid)
        if not doc or mid in hidden_ids:
            continue
        if not display.get("is_educational_material"):
            continue

        row = _audit_one_educational_material(doc, display, kind_index, course_id)
        educational_materials.append(row)
        quiz_status = row.get("quiz_status") or "unknown"
        status_counts[quiz_status] += 1

    educational_materials.sort(
        key=lambda r: (
            r.get("material_kind") or "",
            r.get("material_number") or 0,
            (r.get("title") or "").lower(),
        )
    )

    ready_count = status_counts.get("ready", 0)
    limited_count = status_counts.get("limited_ready", 0)
    not_uploaded_count = status_counts.get("not_uploaded", 0)
    not_enough_count = (
        status_counts.get("not_enough_readable_text", 0)
        + status_counts.get("extraction_too_short", 0)
    )
    extraction_failed_count = status_counts.get("extraction_failed", 0)
    not_quiz_count = status_counts.get("not_quiz_material", 0)

    return {
        "course_id": course_id,
        "course_name": course_name,
        "total_materials": len(displays),
        "educational_count": len(educational_materials),
        "ready_count": ready_count,
        "limited_ready_count": limited_count,
        "not_uploaded_count": not_uploaded_count,
        "not_enough_count": not_enough_count,
        "extraction_failed_count": extraction_failed_count,
        "not_quiz_count": not_quiz_count,
        "status_counts": dict(status_counts),
        "educational_materials": educational_materials,
    }


def _build_problem_summary(courses: List[Dict[str, Any]]) -> Dict[str, Any]:
    buckets: Dict[str, List[Dict[str, Any]]] = {
        _ISSUE_ROW_MISMATCH: [],
        _ISSUE_NEVER_ATTEMPTED: [],
        _ISSUE_DOWNLOAD_URL: [],
        _ISSUE_FETCH_FAILED: [],
        _ISSUE_EXTRACTED_NOT_ENOUGH: [],
        _ISSUE_MISCLASSIFIED: [],
        _ISSUE_ACTUALLY_OK: [],
        _ISSUE_OTHER: [],
    }

    for course in courses:
        cid = course["course_id"]
        cname = course["course_name"]
        for mat in course.get("educational_materials") or []:
            entry = {
                "course_id": cid,
                "course_name": cname,
                "material_id": mat.get("material_id"),
                "title": mat.get("title"),
                "quiz_status": mat.get("quiz_status"),
                "content_text_length": mat.get("content_text_length"),
                "issue_type": mat.get("issue_type"),
                "flags": mat.get("flags"),
            }
            issue = mat.get("issue_type") or _ISSUE_OTHER
            buckets.setdefault(issue, []).append(entry)

    totals = {k: len(v) for k, v in buckets.items()}
    return {
        "by_issue_type": buckets,
        "counts_by_issue_type": totals,
        "labels": {
            _ISSUE_ROW_MISMATCH: "Row mismatch: content on another row",
            _ISSUE_NEVER_ATTEMPTED: "Never attempted / still not uploaded",
            _ISSUE_DOWNLOAD_URL: "Download URL problem (view.php vs pluginfile)",
            _ISSUE_FETCH_FAILED: "Fetch failed (HTTP/session/download)",
            _ISSUE_EXTRACTED_NOT_ENOUGH: "Extracted but probe < 3 questions",
            _ISSUE_MISCLASSIFIED: "Educational but marked not_quiz_material",
            _ISSUE_ACTUALLY_OK: "Ready / limited — Generate should work",
            _ISSUE_OTHER: "Other / unclassified",
        },
    }


def debug_material_processing_audit(email: str) -> Dict[str, Any]:
    """
    Full processing audit for all synced courses visible to the user.
    Never returns content_text, passwords, tokens, or connection strings.
    """
    normalized_email = (email or "").strip().lower()
    user = user_repository.find_by_email(normalized_email) if normalized_email else None
    if not user:
        return {
            "user_exists": False,
            "user_email": normalized_email or None,
            "message": "No user found with this email.",
            "courses": [],
            "problem_summary": {},
        }

    user_id = str(user["_id"])
    visible = get_visible_synced_courses_for_user(user_id)
    courses_out: List[Dict[str, Any]] = []

    for course in visible:
        course_id = str(course.get("id") or course.get("course_id") or "")
        course_name = course.get("name") or course.get("course_name") or "Unknown"
        if not course_id:
            continue
        courses_out.append(_audit_course(course_id, course_name))

    problem_summary = _build_problem_summary(courses_out)

    global_totals = defaultdict(int)
    for course in courses_out:
        for k, v in (course.get("status_counts") or {}).items():
            global_totals[k] += v

    return {
        "user_exists": True,
        "user_email": normalized_email,
        "academiq_user_id": user_id,
        "synced_courses_count": len(courses_out),
        "min_quiz_content_chars": MIN_QUIZ_CONTENT_CHARS,
        "global_status_counts": dict(global_totals),
        "problem_summary": problem_summary,
        "courses": courses_out,
    }

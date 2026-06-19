"""
Canonical material extraction cache — stable identity, content hash, terminal statuses,
and audit helpers for Quiz Generation.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.repositories import material_repository, user_repository
from app.services.material_quiz_display import (
    classify_material_kind,
    classify_non_quiz_material,
    extract_material_number,
    resolve_material_display,
)

# Terminal extraction/quiz states — skip re-extraction unless force_reprocess=true.
TERMINAL_EXTRACTION_STATUSES = frozenset(
    {
        "ready",
        "limited_ready",
        "not_enough_readable_text",
        "extraction_failed",
        "unsupported_file_type",
        "not_quiz_material",
        # Legacy aliases still stored on older rows
        "success",
        "insufficient_text",
        "too_short",
        "insufficient_quiz_structure",
        "unsupported",
        "failed",
        "no_text",
        "no_content",
        "not_educational",
    }
)

TERMINAL_QUIZ_STATUSES = frozenset(
    {
        "ready",
        "limited_ready",
        "not_enough_readable_text",
        "extraction_failed",
        "not_quiz_material",
        "extraction_too_short",
    }
)


def compute_content_hash(text: str) -> Optional[str]:
    stripped = (text or "").strip()
    if not stripped:
        return None
    return hashlib.sha256(stripped.encode("utf-8")).hexdigest()


def content_text_length(doc: Dict[str, Any]) -> int:
    text = (doc.get("content_text") or "").strip()
    if text:
        return len(text)
    chars = doc.get("content_text_length")
    if isinstance(chars, int) and chars > 0:
        return chars
    legacy = doc.get("content_chars")
    if isinstance(legacy, int) and legacy > 0:
        return legacy
    return 0


def is_extraction_cache_hit(doc: Optional[Dict[str, Any]], force: bool = False) -> bool:
    """True when extraction should be skipped (cached content or terminal status)."""
    if force or not doc:
        return False

    length = content_text_length(doc)
    if length > 0 and doc.get("content_hash"):
        return True

    extraction_status = str(doc.get("extraction_status") or "")
    quiz_status = str(doc.get("quiz_status") or "")

    if extraction_status == "not_uploaded" and length == 0:
        return False

    if extraction_status in TERMINAL_EXTRACTION_STATUSES:
        if extraction_status in ("success", "ready", "limited_ready") and length == 0:
            return bool(doc.get("processed_at"))
        return True

    if quiz_status in TERMINAL_QUIZ_STATUSES and quiz_status != "not_uploaded":
        return True

    if extraction_status == "success" and length > 0 and doc.get("processed_at"):
        return True

    display = resolve_material_display(doc)
    if display.get("quiz_status") in ("ready", "limited_ready") and length > 0:
        return True

    return False


def enrich_kind_fields(title: str, file_type: str) -> Dict[str, Any]:
    is_non_quiz, _ = classify_non_quiz_material(title, file_type)
    kind = classify_material_kind(title, file_type, is_non_quiz)
    number = extract_material_number(title, kind)
    out: Dict[str, Any] = {"material_kind": kind}
    if number is not None:
        out["material_number"] = number
    return out


def build_extracted_content_fields(
    text: str,
    probe_fields: Dict[str, Any],
    *,
    source_url: Optional[str] = None,
    resolved_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Canonical persisted fields after extraction + readiness probe."""
    stripped = (text or "").strip()
    chars = len(stripped)
    content_hash = compute_content_hash(stripped)
    quiz_status = probe_fields.get("quiz_probe_status") or probe_fields.get("quiz_status")
    extraction_status = probe_fields.get("extraction_status") or "not_uploaded"
    ready = bool(probe_fields.get("ready_for_quiz"))
    failure_reason = None
    if not ready:
        failure_reason = probe_fields.get("extraction_error") or probe_fields.get(
            "probe_failure_reason"
        )

    fields: Dict[str, Any] = {
        "content_text": stripped,
        "content_text_length": chars,
        "content_chars": chars,
        "content_hash": content_hash,
        "ready_for_quiz": ready,
        "quiz_generation_eligible": ready,
        "quiz_status": quiz_status,
        "extraction_status": extraction_status,
        "extraction_error": probe_fields.get("extraction_error"),
        "failure_reason": failure_reason,
        "probe_question_count": probe_fields.get("probe_question_count"),
        "probe_engine": probe_fields.get("probe_engine"),
        "probe_failure_reason": probe_fields.get("probe_failure_reason"),
        "processed_at": datetime.utcnow(),
        "last_attempted_at": datetime.utcnow(),
        "metadata_only": False,
    }
    if source_url:
        fields["url"] = source_url
        fields["original_moodle_url"] = source_url
    if resolved_url:
        fields["resolved_url"] = resolved_url
    return fields


def _normalize_url_key(url: str) -> str:
    return (url or "").strip().lower().split("#")[0].rstrip("/")


def _find_by_kind_number(
    course_id: str,
    title: str,
    file_type: str,
) -> Optional[Dict[str, Any]]:
    is_non_quiz, _ = classify_non_quiz_material(title, file_type)
    kind = classify_material_kind(title, file_type, is_non_quiz)
    number = extract_material_number(title, kind)
    if number is None:
        return None
    for doc in material_repository.list_by_course(course_id):
        doc_kind = doc.get("material_kind")
        if not doc_kind:
            dt = str(doc.get("title") or "")
            dft = str(doc.get("file_type") or "")
            d_non, _ = classify_non_quiz_material(dt, dft)
            doc_kind = classify_material_kind(dt, dft, d_non)
        doc_num = doc.get("material_number")
        if doc_num is None:
            doc_num = extract_material_number(str(doc.get("title") or ""), doc_kind)
        if doc_kind == kind and doc_num == number:
            return doc
    return None


def resolve_canonical_material(
    course_id: str,
    norm: Dict[str, Any],
    *,
    db_id: Optional[str] = None,
    stable_material_key: Optional[str] = None,
    matched_material_id: Optional[str] = None,
    batch_cmid_titles: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Shared identity resolver (save-detected, preflight, upload-for-quiz).

    Priority:
      1. existing db_id
      2. course_id + stable_material_key
      3. course_id + normalized resolved_url
      4. course_id + normalized source_url
      5. course_id + title + file_type
      6. course_id + material_kind + material_number
    """
    from app.services.material_quiz_upload import (
        _allocate_material_id,
        _compute_stable_material_key,
        _identity_result,
        _mongo_id_str,
        _normalize_title,
    )

    batch_cmid_titles = batch_cmid_titles or {}
    stable_key = stable_material_key or _compute_stable_material_key(course_id, norm)
    title = norm.get("title") or ""
    file_type = norm.get("file_type") or ""
    activity_url = norm.get("activity_url") or ""
    resolved_url = norm.get("resolved_url") or ""

    # 1. db_id
    if db_id:
        doc = material_repository.get_by_object_id(db_id)
        if doc and str(doc.get("course_id")) == str(course_id):
            return _identity_result(doc, "mongo_id", stable_key)

    # 2. stable_material_key
    doc = material_repository.get_by_stable_key(course_id, stable_key)
    if doc:
        return _identity_result(doc, "stable_material_key", stable_key)

    # 3. normalized resolved_url
    if resolved_url:
        doc = material_repository.find_by_course_and_url(course_id, resolved_url)
        if doc:
            return _identity_result(doc, "resolved_url", stable_key)

    # 4. normalized source_url
    if activity_url:
        doc = material_repository.find_by_course_and_url(course_id, activity_url)
        if doc:
            return _identity_result(doc, "source_url", stable_key)

    # 5. title + file_type (via allocate helper)
    allocated_id, existing, strategy = _allocate_material_id(course_id, norm, batch_cmid_titles)
    if existing:
        return _identity_result(existing, strategy, stable_key)

    # 6. material_kind + material_number
    kind_doc = _find_by_kind_number(course_id, title, file_type)
    if kind_doc:
        return _identity_result(kind_doc, "material_kind_number", stable_key)

    return _identity_result(None, strategy, stable_key, allocated_id)


def audit_material_cache(email: str, course_id: str) -> Dict[str, Any]:
    """Per-course material cache audit for demo/debug."""
    email = (email or "").strip().lower()
    course_id = str(course_id or "").strip()
    user = user_repository.find_by_email(email) if email else None

    docs = material_repository.list_by_course(course_id)
    visible_docs = [d for d in docs if not d.get("hidden_duplicate")]

    ready_count = 0
    limited_count = 0
    not_enough_count = 0
    failed_count = 0
    never_attempted_count = 0
    duplicates_count = sum(1 for d in docs if d.get("hidden_duplicate") or d.get("duplicate_of"))
    cache_hit_count = 0
    cache_miss_count = 0
    educational_count = 0

    rows: List[Dict[str, Any]] = []

    for doc in visible_docs:
        display = resolve_material_display(doc)
        title = str(doc.get("title") or "")
        file_type = str(doc.get("file_type") or "")
        is_non_quiz, _ = classify_non_quiz_material(title, file_type)
        if display.get("is_educational_material") or display.get("visible_in_main_list"):
            educational_count += 1

        quiz_status = str(display.get("quiz_status") or doc.get("quiz_status") or "")
        length = content_text_length(doc)
        cached = is_extraction_cache_hit(doc)

        if cached:
            cache_hit_count += 1
        else:
            cache_miss_count += 1

        if quiz_status == "ready":
            ready_count += 1
        elif quiz_status == "limited_ready":
            limited_count += 1
        elif quiz_status in ("not_enough_readable_text", "extraction_too_short"):
            not_enough_count += 1
        elif quiz_status == "extraction_failed":
            failed_count += 1
        elif quiz_status == "not_uploaded" and not doc.get("last_attempted_at"):
            never_attempted_count += 1

        rows.append(
            {
                "title": title,
                "db_id": str(doc.get("_id") or ""),
                "material_id": doc.get("material_id"),
                "stable_material_key": doc.get("stable_material_key"),
                "file_type": file_type,
                "source_url": doc.get("url") or doc.get("original_moodle_url"),
                "resolved_url": doc.get("resolved_url"),
                "content_text_length": length,
                "content_hash_exists": bool(doc.get("content_hash")),
                "processed_at": (
                    doc.get("processed_at").isoformat()
                    if doc.get("processed_at")
                    else None
                ),
                "extraction_status": doc.get("extraction_status"),
                "quiz_status": quiz_status,
                "ready_for_quiz": bool(doc.get("ready_for_quiz")),
                "content_source": doc.get("content_source"),
                "original_filename": doc.get("original_filename"),
                "material_kind": doc.get("material_kind"),
                "material_number": doc.get("material_number"),
                "reason": doc.get("failure_reason") or doc.get("extraction_error"),
                "duplicate_of": doc.get("duplicate_of"),
                "cache_hit": cached,
            }
        )

    rows.sort(key=lambda r: r.get("title") or "")

    imported_count = sum(
        1 for d in visible_docs if d.get("content_source") == "course_material_import"
    )
    imported_ready = sum(
        1
        for d in visible_docs
        if d.get("content_source") == "course_material_import"
        and str(d.get("quiz_status") or "") in ("ready", "limited_ready")
    )

    missing_expected: List[Dict[str, Any]] = []
    visibility_audit = _build_quiz_visibility_audit(visible_docs)

    for kind_label, kind_values in (
        ("lecture", ("lecture", "lecture_link")),
        ("lab", ("lab", "lab_link")),
        ("revision", ("revision",)),
    ):
        seen_numbers: Dict[int, Dict[str, Any]] = {}
        for doc in visible_docs:
            title = str(doc.get("title") or "")
            file_type = str(doc.get("file_type") or "")
            is_non, _ = classify_non_quiz_material(title, file_type)
            kind = doc.get("material_kind")
            if not kind:
                kind = classify_material_kind(title, file_type, is_non)
            if kind not in kind_values:
                continue
            num = doc.get("material_number")
            if num is None:
                num = extract_material_number(title, kind)
            if num is None or num >= 9999:
                continue
            display = resolve_material_display(doc)
            qs = str(display.get("quiz_status") or doc.get("quiz_status") or "")
            entry = seen_numbers.get(int(num))
            if not entry or qs in ("ready", "limited_ready"):
                seen_numbers[int(num)] = {
                    "kind": kind_label,
                    "number": int(num),
                    "title": title,
                    "quiz_status": qs,
                    "content_source": doc.get("content_source"),
                    "content_text_length": content_text_length(doc),
                }
        for num, info in sorted(seen_numbers.items()):
            if info["quiz_status"] not in ("ready", "limited_ready"):
                missing_expected.append(info)

    return {
        "email": email,
        "course_id": course_id,
        "user_exists": user is not None,
        "total_materials": len(visible_docs),
        "educational_materials": educational_count,
        "ready_count": ready_count,
        "limited_ready_count": limited_count,
        "not_enough_count": not_enough_count,
        "extraction_failed_count": failed_count,
        "never_attempted_count": never_attempted_count,
        "duplicates_count": duplicates_count,
        "cache_hit_count": cache_hit_count,
        "cache_miss_count": cache_miss_count,
        "imported_count": imported_count,
        "imported_ready_count": imported_ready,
        "missing_expected_materials": missing_expected,
        "quiz_visibility_audit": visibility_audit,
        "materials": rows,
    }


def _build_quiz_visibility_audit(docs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Per-course quiz UI visibility diagnostics for demo verification."""
    from app.services.material_quiz_display import (
        is_standalone_exercise_title,
        resolve_material_display,
    )

    displays = [resolve_material_display(d) for d in docs]
    imported = [d for d in docs if d.get("content_source") == "course_material_import"]

    def _count_kind(kind_values: tuple[str, ...], in_main: bool = True) -> int:
        n = 0
        for doc, disp in zip(docs, displays):
            kind = str(disp.get("material_kind") or doc.get("material_kind") or "")
            if kind not in kind_values:
                continue
            if in_main and not disp.get("visible_in_main_list"):
                continue
            if disp.get("is_non_quiz_material"):
                continue
            n += 1
        return n

    imported_with_content = [
        d for d in imported if content_text_length(d) > 0
    ]
    wrongly_not_uploaded = []
    wrongly_other = []
    standalone_exercises_visible = []
    for doc, disp in zip(docs, displays):
        title = str(doc.get("title") or "")
        if is_standalone_exercise_title(title) and disp.get("visible_in_main_list"):
            standalone_exercises_visible.append(
                {
                    "title": title,
                    "material_id": doc.get("material_id"),
                    "quiz_status": disp.get("quiz_status"),
                }
            )
        if doc.get("content_source") == "course_material_import" and content_text_length(doc) > 0:
            if disp.get("quiz_status") in ("not_uploaded", "extraction_failed"):
                wrongly_not_uploaded.append(
                    {
                        "title": title,
                        "quiz_status": disp.get("quiz_status"),
                        "content_text_length": content_text_length(doc),
                        "material_id": doc.get("material_id"),
                    }
                )
        if disp.get("visible_in_other_items") and disp.get("is_educational_material"):
            kind = str(disp.get("material_kind") or "")
            if kind in ("lecture", "lab", "revision", "notes", "other_educational"):
                wrongly_other.append(
                    {
                        "title": title,
                        "material_kind": kind,
                        "quiz_status": disp.get("quiz_status"),
                        "material_id": doc.get("material_id"),
                    }
                )

    # Bad sort: labs out of numeric order in main list
    bad_sort: List[Dict[str, Any]] = []
    lab_displays = [
        disp
        for disp in displays
        if disp.get("material_kind") in ("lab", "lab_link")
        and disp.get("visible_in_main_list")
    ]
    lab_displays.sort(key=lambda d: int(d.get("material_number") or 9999))
    lab_nums: List[int] = [
        int(d.get("material_number") or 9999)
        for d in lab_displays
        if isinstance(d.get("material_number"), int) and d.get("material_number") < 9999
    ]
    for i in range(len(lab_nums) - 1):
        if lab_nums[i] > lab_nums[i + 1]:
            bad_sort.append(
                {
                    "kind": "lab",
                    "sequence": lab_nums,
                    "issue": "non_numeric_order",
                }
            )
            break

    duplicates_hidden = sum(
        1 for disp in displays if disp.get("hidden_duplicate_display")
    )
    visible_educational_main = sum(
        1
        for disp in displays
        if disp.get("visible_in_main_list") and disp.get("is_educational_material")
    )
    hidden_skipped = sum(
        1
        for disp in displays
        if not disp.get("visible_in_main_list")
        and disp.get("is_educational_material")
        and not disp.get("is_non_quiz_material")
    )

    return {
        "imported_rows": len(imported),
        "imported_with_content": len(imported_with_content),
        "visible_educational_main": visible_educational_main,
        "hidden_skipped_educational": hidden_skipped,
        "duplicates_hidden_from_main": duplicates_hidden,
        "visible_lectures": _count_kind(("lecture", "lecture_link")),
        "visible_labs": _count_kind(("lab", "lab_link")),
        "visible_revisions": _count_kind(("revision",)),
        "standalone_exercises_still_visible": standalone_exercises_visible,
        "expected_imported_lectures": sum(
            1
            for d in imported_with_content
            if str(d.get("material_kind") or "") in ("lecture", "lecture_link")
            or "lecture" in str(d.get("title") or "").lower()
        ),
        "expected_imported_labs": sum(
            1
            for d in imported_with_content
            if str(d.get("material_kind") or "") in ("lab", "lab_link")
            or re.search(r"(?i)\blab\s*\d", str(d.get("title") or ""))
        ),
        "wrongly_not_uploaded_imported": wrongly_not_uploaded,
        "wrongly_classified_other_moodle": wrongly_other,
        "bad_sort_examples": bad_sort,
    }

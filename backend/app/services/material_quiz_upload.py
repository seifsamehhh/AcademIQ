"""
Handle Moodle material uploads from the Chrome extension for quiz generation.
"""

from __future__ import annotations

import base64
import hashlib
import re
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.models.material import build_material_doc, stable_material_id
from app.repositories import material_repository, user_repository
from app.services.material_text_extract import extract_text_from_bytes
from app.services.material_quiz_display import (
    classify_non_quiz_material,
    detect_link_wrapper,
    is_educational_material,
    matches_educational_title,
    resolve_material_display,
    resolve_quiz_material_display,
    was_upload_attempted,
    _LAB_NUM_RE,
    _LECTURE_NUM_RE,
)
from app.services.material_cache import (
    build_extracted_content_fields,
    content_text_length,
    enrich_kind_fields,
    is_extraction_cache_hit,
    resolve_canonical_material,
    TERMINAL_EXTRACTION_STATUSES,
)
from app.services.quiz_material_eligibility import assess_quiz_eligibility
from app.services.student_data import (
    MIN_QUIZ_CONTENT_CHARS,
    MIN_EDUCATIONAL_REPROCESS_CHARS,
)

_DOWNLOADABLE_FILE_TYPES = {"pdf", "pptx", "ppt", "docx", "doc", "txt", "text"}
_LINK_LIKE_FILE_TYPES = frozenset({"link", "url", "html", "page", "book"})
_TARGETED_RETRY_FILE_TYPES = frozenset(
    {"pdf", "pptx", "ppt", "html", "link", "url", "page", "book"}
)

# Bump when extraction logic changes materially — preflight may re-offer upload once.
CURRENT_EXTRACTOR_VERSION = "2"

_READY_EXTRACTION_STATUSES = frozenset(
    {"success", "ready", "ready_for_quiz", "extracted"}
)

# Terminal statuses — shared with material_cache (includes ready / limited_ready).
_TERMINAL_EXTRACTION_STATUSES = TERMINAL_EXTRACTION_STATUSES


_TITLE_STOP_WORDS = {"the", "a", "an", "and", "or", "for", "of", "to", "in", "is", "on", "at", "by"}


def _normalize_title(title: str) -> str:
    """
    Stable lowercase key for title-based deduplication.

    Strips, in order:
      1. Common file extensions (.pdf, .pptx, .docx, .txt …)
      2. Moodle "File" display suffix  ("Lab 4 File" → "Lab 4")
      3. One or more leading course-code prefixes ("SWE423 - Lab 4" → "Lab 4")
      4. All non-alphanumeric chars replaced with spaces
      5. Collapse and lowercase
    """
    s = (title or "").strip()
    # 1. Strip trailing file extension
    s = re.sub(r'\.[a-zA-Z0-9]{1,6}$', '', s)
    # 2. Strip Moodle "File" display suffix (Moodle appends " File" to resource names)
    s = re.sub(r'\s+[Ff]ile\s*$', '', s)
    # 3. Strip one or more leading course-code prefixes e.g. "SWE423 ", "CSC344: "
    s = re.sub(r'^([A-Z]{2,6}\d{3,4}\s*[-:_]?\s*)+', '', s)
    # 4. Replace non-alphanumeric with space
    s = "".join(c if c.isalnum() or c.isspace() else " " for c in s)
    return " ".join(s.lower().split())


def _title_word_overlap(t1: str, t2: str) -> float:
    """Jaccard similarity of meaningful word sets (stop-words removed)."""
    w1 = set(t1.split()) - _TITLE_STOP_WORDS
    w2 = set(t2.split()) - _TITLE_STOP_WORDS
    if not w1 or not w2:
        return 0.0
    return len(w1 & w2) / len(w1 | w2)


def _is_downloadable_material(
    file_type: str,
    activity_url: str = "",
    resolved_url: str = "",
) -> bool:
    """True when the extension can fetch file bytes (PDF/PPTX/DOCX/TXT)."""
    ft = (file_type or "").lower().strip()
    if ft in _DOWNLOADABLE_FILE_TYPES:
        return True
    for url in (activity_url, resolved_url):
        if url and re.search(r"\.(pdf|pptx?|docx?|txt)(\?|$)", url, re.I):
            return True
    return False


def _content_chars_from_doc(doc: Dict[str, Any]) -> int:
    text = (doc.get("content_text") or "").strip()
    if text:
        return len(text)
    chars = doc.get("content_chars")
    if isinstance(chars, int) and chars > 0:
        return chars
    return 0


def _is_force_reprocess(payload: Dict[str, Any]) -> bool:
    return bool(payload.get("force_reupload") or payload.get("force_reprocess"))


def _is_targeted_not_uploaded_learning_material(
    title: str,
    file_type: str,
    existing_doc: Optional[Dict[str, Any]],
) -> bool:
    """
    Educational rows that still need a first extraction attempt (not_ready admin).
    """
    if not existing_doc:
        return False
    ft = (file_type or "").lower().strip()
    if ft not in _TARGETED_RETRY_FILE_TYPES and ft not in _LINK_LIKE_FILE_TYPES:
        return False
    if not is_educational_material(title, file_type):
        return False
    is_non_quiz, _ = classify_non_quiz_material(title, file_type)
    if is_non_quiz:
        return False
    if not matches_educational_title(title):
        return False
    chars = _content_chars_from_doc(existing_doc)
    if chars >= MIN_QUIZ_CONTENT_CHARS and bool(existing_doc.get("ready_for_quiz")):
        return False
    status = str(existing_doc.get("extraction_status") or "")
    if status == "not_quiz_material":
        return False
    if status in ("not_uploaded", "no_content") and chars == 0:
        return True
    if bool(existing_doc.get("metadata_only")) and chars == 0 and status != "extraction_failed":
        return True
    return False


def _preflight_row_urls(
    existing_doc: Optional[Dict[str, Any]],
    activity_url: str,
    resolved_url: str,
) -> Dict[str, Any]:
    db_source = ""
    db_resolved = ""
    if existing_doc:
        db_source = str(
            existing_doc.get("url") or existing_doc.get("source_url") or activity_url or ""
        ).strip()
        db_resolved = str(existing_doc.get("resolved_url") or resolved_url or "").strip()
    return {
        "source_url_present": bool(activity_url or db_source),
        "resolved_url_present": bool(resolved_url or db_resolved),
        "db_source_url": db_source or activity_url or None,
        "db_resolved_url": db_resolved or resolved_url or None,
    }


def _preflight_upload_decision(
    existing_doc: Optional[Dict[str, Any]],
    title: str,
    raw_file_type: str,
    activity_url: str,
    resolved_url: str,
    force: bool,
) -> tuple[bool, str, str, int, bool]:
    """
    Decide whether the extension should download/upload this material.

    Ready materials with stored content are skipped (upload caching).
    Educational url/html/link/page rows without extracted content may upload
    once so the extension can resolve nested files or HTML page text.
    """
    downloadable = _is_downloadable_material(raw_file_type, activity_url, resolved_url)
    ft = (raw_file_type or "").lower().strip()
    url_like = ft in _LINK_LIKE_FILE_TYPES
    educational = is_educational_material(title, raw_file_type)
    resolvable_educational = educational and (downloadable or url_like)

    if not existing_doc:
        if downloadable:
            return (
                True,
                "not_uploaded",
                "No DB record found — file download needed",
                0,
                True,
            )
        if educational and url_like:
            return (
                True,
                "not_uploaded",
                "Educational Moodle page — content extraction needed",
                0,
                False,
            )
        return (
            False,
            "metadata_only",
            "Metadata-only Moodle resource — no downloadable file",
            0,
            False,
        )

    existing_chars = _content_chars_from_doc(existing_doc)
    existing_status = str(existing_doc.get("extraction_status") or "")

    if force and (downloadable or (educational and url_like)):
        return (
            True,
            "force_reprocess",
            "Force reprocess requested",
            existing_chars,
            downloadable or url_like,
        )

    if is_extraction_cache_hit(existing_doc, force):
        display = resolve_material_display(existing_doc)
        display_status = str(display.get("quiz_status") or "")
        if existing_chars > 0 or display_status in ("ready", "limited_ready"):
            return (
                False,
                "cache_hit",
                "Skipped — already processed (content cached)",
                existing_chars,
                downloadable,
            )
        return (
            False,
            "already_classified",
            existing_doc.get("failure_reason")
            or existing_doc.get("extraction_error")
            or f"Terminal status: {existing_doc.get('extraction_status')}",
            existing_chars,
            downloadable,
        )

    if existing_chars >= MIN_QUIZ_CONTENT_CHARS:
        return (
            False,
            "already_ready",
            "Already has enough extracted content",
            existing_chars,
            downloadable,
        )

    display = resolve_material_display(existing_doc)
    display_status = str(display.get("quiz_status") or "")
    if display_status in ("ready", "limited_ready"):
        return (
            False,
            "already_ready",
            f"Already {display_status.replace('_', ' ')}",
            existing_chars,
            downloadable,
        )

    if existing_status in _TERMINAL_EXTRACTION_STATUSES and not force:
        return (
            False,
            "already_classified",
            existing_doc.get("extraction_error") or f"Terminal status: {existing_status}",
            existing_chars,
            downloadable,
        )

    if was_upload_attempted(existing_doc) and existing_chars == 0:
        if existing_status == "extraction_failed":
            return (
                False,
                "extraction_failed",
                existing_doc.get("extraction_error") or "Extraction failed",
                existing_chars,
                downloadable,
            )
        return (
            False,
            "already_classified",
            existing_doc.get("extraction_error")
            or "Upload attempted — content could not be extracted",
            existing_chars,
            downloadable,
        )

    if resolvable_educational and existing_chars < MIN_QUIZ_CONTENT_CHARS:
        if _is_targeted_not_uploaded_learning_material(title, raw_file_type, existing_doc):
            return (
                True,
                "not_uploaded",
                "Educational material — targeted content extraction needed",
                existing_chars,
                downloadable or url_like,
            )
        if not existing_doc.get("processed_at"):
            return (
                True,
                "not_uploaded",
                "Educational material — content not extracted yet",
                existing_chars,
                downloadable or url_like,
            )
        if existing_status in ("not_uploaded", "no_content") and existing_chars == 0:
            return (
                True,
                "not_uploaded",
                "Educational material — retry content extraction",
                existing_chars,
                downloadable or url_like,
            )

    return (
        False,
        "already_saved",
        "Already exists in database",
        existing_chars,
        downloadable,
    )


def _normalize_incoming_material_item(item: Dict[str, Any]) -> Dict[str, Any]:
    title = (item.get("title") or "Untitled").strip()
    raw_file_type = str(item.get("file_type") or item.get("fileType") or "unknown").strip()
    activity_url = str(item.get("source_url") or item.get("url") or "").strip()
    resolved_url = str(item.get("resolved_url") or item.get("resolvedUrl") or "").strip()
    raw_material_id = str(
        item.get("material_id") or item.get("id") or stable_material_id(item) or ""
    ).strip()
    url_cmid = _material_id_from_url(activity_url) or _material_id_from_url(resolved_url)
    material_id = url_cmid or raw_material_id
    return {
        "title": title,
        "file_type": raw_file_type,
        "activity_url": activity_url,
        "resolved_url": resolved_url,
        "raw_material_id": raw_material_id,
        "material_id": material_id,
        "url_cmid": url_cmid,
    }


def _normalize_source_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    return u.split("#")[0].strip().lower()


def _stable_hash_material_id(prefix: str, key: str) -> str:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


def _compute_stable_material_key(course_id: str, norm: Dict[str, Any]) -> str:
    activity_url = norm.get("activity_url") or ""
    resolved_url = norm.get("resolved_url") or ""
    cmid = str(norm.get("url_cmid") or "").strip()
    norm_url = _normalize_source_url(activity_url)
    norm_resolved = _normalize_source_url(resolved_url)
    if norm_url:
        return f"url:{norm_url}"
    if norm_resolved:
        return f"resolved:{norm_resolved}"
    if cmid:
        return f"cmid:{course_id}:{cmid}"
    tft_key = f"{_normalize_title(norm.get('title') or '')}|{(norm.get('file_type') or '').lower()}"
    return f"tft:{course_id}:{tft_key}"


def _mongo_id_str(doc: Optional[Dict[str, Any]]) -> Optional[str]:
    if not doc or not doc.get("_id"):
        return None
    return str(doc["_id"])


def _canonical_learning_row_score(doc: Dict[str, Any]) -> int:
    """Higher = preferred main-list file row for quiz content."""
    title = str(doc.get("title") or "")
    ft = str(doc.get("file_type") or "").lower()
    score = 0
    if detect_link_wrapper(title, ft):
        score -= 50
    if str(doc.get("material_id") or "").startswith("url_"):
        score -= 40
    if ft in ("pdf", "pptx", "ppt"):
        score += 30
    if re.search(r"(?i)\blab\s*#?\d+\s*-?\s*file\s*$", title.strip()):
        score += 25
    if re.search(r"(?i)\blecture\s*#?\d+.*\bfile\s*$", title.strip()):
        score += 22
    if re.search(r"(?i)\b(code|notebook|building\s+cnn)\b", title):
        score -= 12
    if doc.get("metadata_only"):
        score -= 20
    chars = int(doc.get("content_chars") or len((doc.get("content_text") or "").strip()))
    if chars > 0:
        score += min(10, chars // 500)
    return score


def _find_canonical_learning_row(
    course_id: str,
    title: str,
    file_type: str,
) -> Optional[Dict[str, Any]]:
    """
    When several DB rows share a lecture/lab number, prefer the file row shown
    in Quiz Generation (PDF/PPTX File), not URL/page wrapper duplicates.
    """
    t = title or ""
    lecture_m = _LECTURE_NUM_RE.search(t)
    lab_m = _LAB_NUM_RE.search(t)
    if not lecture_m and not lab_m:
        return None
    num = lecture_m.group(1) if lecture_m else lab_m.group(1)
    kind = "lecture" if lecture_m else "lab"

    candidates: List[Dict[str, Any]] = []
    for doc in material_repository.list_by_course(course_id):
        dt = doc.get("title") or ""
        if kind == "lecture":
            m = _LECTURE_NUM_RE.search(dt)
            if not m or m.group(1) != num:
                continue
        else:
            m = _LAB_NUM_RE.search(dt)
            if not m or m.group(1) != num:
                continue
        candidates.append(doc)

    if not candidates:
        return None
    candidates.sort(key=_canonical_learning_row_score, reverse=True)
    return candidates[0]


def _content_fields_from_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Extract quiz-relevant content fields for canonical merge."""
    text = (doc.get("content_text") or "").strip()
    chars = int(doc.get("content_chars") or len(text))
    return {
        "content_text": text,
        "content_text_length": int(doc.get("content_text_length") or chars),
        "content_chars": chars,
        "content_hash": doc.get("content_hash"),
        "ready_for_quiz": bool(doc.get("ready_for_quiz")),
        "quiz_generation_eligible": bool(doc.get("quiz_generation_eligible")),
        "quiz_status": doc.get("quiz_status"),
        "extraction_status": doc.get("extraction_status"),
        "extraction_error": doc.get("extraction_error"),
        "failure_reason": doc.get("failure_reason"),
        "processed_at": doc.get("processed_at"),
        "last_attempted_at": doc.get("last_attempted_at"),
        "metadata_only": False,
        "extractor_version": doc.get("extractor_version") or CURRENT_EXTRACTOR_VERSION,
        "resolved_url": doc.get("resolved_url"),
        "last_upload_audit": doc.get("last_upload_audit"),
        "last_upload_audit_at": doc.get("last_upload_audit_at"),
    }


def merge_duplicate_content_in_course(course_id: str) -> Dict[str, Any]:
    """
    Move extracted content from duplicate URL/link/page rows onto canonical
    file rows shown in Quiz Generation (same lecture/lab/revision number).
    """
    course_id = str(course_id or "").strip()
    docs = material_repository.list_by_course(course_id)
    groups: Dict[Tuple[str, int], List[Dict[str, Any]]] = defaultdict(list)

    for doc in docs:
        title = doc.get("title") or ""
        ft = str(doc.get("file_type") or "")
        if not is_educational_material(title, ft) and not matches_educational_title(title):
            continue
        lecture_m = _LECTURE_NUM_RE.search(title)
        lab_m = _LAB_NUM_RE.search(title)
        if lecture_m:
            groups[("lecture", int(lecture_m.group(1)))].append(doc)
        elif lab_m:
            groups[("lab", int(lab_m.group(1)))].append(doc)

    merged_actions: List[Dict[str, Any]] = []

    for (kind, num), group in groups.items():
        if len(group) < 2:
            continue
        canonical = max(group, key=_canonical_learning_row_score)
        canonical_id = str(canonical.get("material_id") or "")
        canonical_chars = _content_chars_from_doc(canonical)
        for doc in group:
            donor_id = str(doc.get("material_id") or "")
            if not donor_id or donor_id == canonical_id:
                continue
            donor_chars = _content_chars_from_doc(doc)
            if donor_chars <= 0:
                continue
            if donor_chars <= canonical_chars:
                continue
            content_fields = _content_fields_from_doc(doc)
            if canonical_chars == 0 or _canonical_learning_row_score(canonical) >= _canonical_learning_row_score(doc):
                material_repository.upsert(
                    {
                        "course_id": course_id,
                        "material_id": canonical_id,
                        "title": canonical.get("title"),
                        "file_type": canonical.get("file_type"),
                        **content_fields,
                        "hidden_duplicate": False,
                        "duplicate_of": None,
                    }
                )
                merged_text = (content_fields.get("content_text") or "").strip()
                if merged_text:
                    probe_fields = _derive_readiness_from_probe(
                        merged_text,
                        str(canonical.get("file_type") or doc.get("file_type") or ""),
                    )
                    material_repository.upsert(
                        {
                            "course_id": course_id,
                            "material_id": canonical_id,
                            "ready_for_quiz": probe_fields["ready_for_quiz"],
                            "extraction_status": probe_fields["extraction_status"],
                            "extraction_error": probe_fields["extraction_error"],
                            "content_chars": probe_fields["content_chars"],
                            "probe_question_count": probe_fields.get("probe_question_count"),
                            "probe_engine": probe_fields.get("probe_engine"),
                        }
                    )
                material_repository.upsert(
                    {
                        "course_id": course_id,
                        "material_id": donor_id,
                        "duplicate_of": canonical_id,
                        "hidden_duplicate": True,
                        "content_text": "",
                        "content_chars": 0,
                        "metadata_only": True,
                        "ready_for_quiz": False,
                        "extraction_status": "not_uploaded",
                        "extraction_error": f"Content merged to canonical row {canonical_id}",
                    }
                )
                merged_actions.append(
                    {
                        "action": "merged_to_canonical",
                        "from_material_id": donor_id,
                        "from_title": doc.get("title"),
                        "to_material_id": canonical_id,
                        "to_title": canonical.get("title"),
                        "chars_moved": donor_chars,
                    }
                )
                canonical_chars = donor_chars

    return {
        "course_id": course_id,
        "merged_count": len(merged_actions),
        "actions": merged_actions,
    }


def _identity_result(
    doc: Optional[Dict[str, Any]],
    match_strategy: str,
    stable_key: Optional[str] = None,
    allocated_id: Optional[str] = None,
) -> Dict[str, Any]:
    if doc:
        return {
            "material_id": str(doc.get("material_id") or ""),
            "existing_doc": doc,
            "stable_material_key": doc.get("stable_material_key") or stable_key,
            "match_strategy": match_strategy,
            "db_id": _mongo_id_str(doc),
            "matched_db_title": doc.get("title"),
        }
    return {
        "material_id": allocated_id or "",
        "existing_doc": None,
        "stable_material_key": stable_key,
        "match_strategy": match_strategy,
        "db_id": None,
        "matched_db_title": None,
    }


def resolve_material_identity(
    course_id: str,
    norm: Dict[str, Any],
    batch_cmid_titles: Optional[Dict[str, str]] = None,
    db_id: Optional[str] = None,
    stable_material_key: Optional[str] = None,
    matched_material_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Single identity resolver for save-detected, preflight, and upload-for-quiz.
    Always returns the MongoDB material_id that Quiz Generation should display.
    """
    batch_cmid_titles = batch_cmid_titles or {}
    stable_key = stable_material_key or _compute_stable_material_key(course_id, norm)

    if matched_material_id:
        doc = material_repository.get(course_id, str(matched_material_id))
        if doc:
            canonical = _find_canonical_learning_row(
                course_id, norm.get("title") or "", norm.get("file_type") or ""
            )
            if canonical and canonical.get("material_id") != doc.get("material_id"):
                if _canonical_learning_row_score(canonical) > _canonical_learning_row_score(doc):
                    return _identity_result(canonical, "canonical_over_matched_id", stable_key)
            return _identity_result(doc, "matched_material_id", stable_key)

    result = resolve_canonical_material(
        course_id,
        norm,
        db_id=db_id,
        stable_material_key=stable_key,
        batch_cmid_titles=batch_cmid_titles,
    )

    existing = result.get("existing_doc")
    if existing:
        canonical = _find_canonical_learning_row(
            course_id, norm.get("title") or "", norm.get("file_type") or ""
        )
        if canonical and canonical.get("material_id") != existing.get("material_id"):
            if _canonical_learning_row_score(canonical) >= _canonical_learning_row_score(existing):
                return _identity_result(canonical, "canonical_over_existing", stable_key)
        return result

    return result


def _allocate_material_id(
    course_id: str,
    norm: Dict[str, Any],
    batch_cmid_titles: Dict[str, str],
) -> tuple[str, Optional[Dict[str, Any]], str]:
    """Choose material_id for upsert; mirrors save-detected key priority."""
    title = norm["title"]
    raw_file_type = norm["file_type"]
    activity_url = norm["activity_url"]
    resolved_url = norm["resolved_url"]
    cmid = str(norm.get("url_cmid") or "").strip()
    norm_title = _normalize_title(title)
    norm_url = _normalize_source_url(activity_url)
    norm_resolved = _normalize_source_url(resolved_url)

    for url in (activity_url, resolved_url):
        if not url:
            continue
        existing = material_repository.find_by_course_and_url(course_id, url)
        if existing and existing.get("material_id"):
            return str(existing["material_id"]), existing, "existing_url"

    if cmid:
        batch_title = batch_cmid_titles.get(cmid)
        cmid_unique_in_batch = not batch_title or batch_title == norm_title
        if cmid_unique_in_batch:
            existing_cmid = material_repository.get(course_id, cmid)
            if existing_cmid:
                existing_title = _normalize_title(existing_cmid.get("title") or "")
                existing_url = _normalize_source_url(existing_cmid.get("url") or "")
                same_material = (
                    existing_title == norm_title
                    or (norm_url and existing_url == norm_url)
                    or (norm_resolved and existing_url == norm_resolved)
                )
                if same_material:
                    if not batch_title:
                        batch_cmid_titles[cmid] = norm_title
                    return cmid, existing_cmid, "existing_cmid"
            else:
                batch_cmid_titles[cmid] = norm_title
                return cmid, None, "new_cmid"

    if norm_url:
        mid = _stable_hash_material_id("url", f"{course_id}|{norm_url}")
        existing = material_repository.get(course_id, mid)
        return mid, existing, "source_url_key"

    tft_key = f"{norm_title}|{raw_file_type.lower()}"
    mid = _stable_hash_material_id("tft", f"{course_id}|{tft_key}")
    existing = material_repository.get(course_id, mid)
    return mid, existing, "title_file_type_key"


_MIN_PROBE_READY = 5
_MIN_PROBE_LIMITED = 3


def _derive_readiness_from_probe(
    text: str,
    file_type: str,
) -> Dict[str, Any]:
    """
    Map stored content_text to DB readiness fields using the same probe pipeline
    as Quiz Generation display (no course-context fallback).
    """
    stripped = (text or "").strip()
    chars = len(stripped)
    base: Dict[str, Any] = {
        "content_chars": chars,
        "ready_for_quiz": False,
        "extraction_status": "not_uploaded",
        "extraction_error": "No readable text extracted yet",
        "probe_question_count": 0,
        "probe_engine": None,
        "probe_failure_reason": None,
        "quiz_probe_status": "not_uploaded",
    }
    if not stripped:
        return base

    _, reason_code, meta = assess_quiz_eligibility(
        stripped,
        file_type=file_type,
        probe=True,
    )
    probe_count = int(meta.get("probe_question_count") or 0)
    base.update(
        {
            "probe_question_count": probe_count,
            "probe_engine": meta.get("probe_engine"),
            "probe_failure_reason": meta.get("probe_failure_reason"),
            "cleaned_text_length": meta.get("cleaned_text_length"),
            "concept_candidate_count": meta.get("concept_candidate_count"),
        }
    )

    if probe_count >= _MIN_PROBE_READY:
        base.update(
            {
                "ready_for_quiz": True,
                "extraction_status": "success",
                "extraction_error": None,
                "quiz_probe_status": "ready",
            }
        )
        return base

    if probe_count >= _MIN_PROBE_LIMITED:
        base.update(
            {
                "ready_for_quiz": True,
                "extraction_status": "success",
                "extraction_error": meta.get("probe_failure_reason"),
                "quiz_probe_status": "limited_ready",
            }
        )
        return base

    if chars < MIN_QUIZ_CONTENT_CHARS:
        base.update(
            {
                "ready_for_quiz": False,
                "extraction_status": "insufficient_text",
                "extraction_error": reason_code or (
                    f"Only {chars} characters extracted (need at least "
                    f"{MIN_QUIZ_CONTENT_CHARS})."
                ),
                "quiz_probe_status": "extraction_too_short",
            }
        )
        return base

    base.update(
        {
            "ready_for_quiz": False,
            "extraction_status": "success",
            "extraction_error": reason_code or meta.get("probe_failure_reason")
            or "insufficient_quiz_structure",
            "quiz_probe_status": "not_enough_readable_text",
        }
    )
    return base


def reassess_course_material_readiness(course_id: str) -> Dict[str, Any]:
    """
    Re-run slide/PDF probe on stored content_text for educational materials.
    Does not download files or break upload caching for empty rows.
    """
    course_id = str(course_id or "").strip()
    if not course_id:
        raise ValueError("course_id required")

    now = datetime.utcnow()
    docs = material_repository.list_by_course(course_id)
    results: List[Dict[str, Any]] = []
    updated_count = 0

    for doc in docs:
        title = doc.get("title") or "Untitled"
        file_type = str(doc.get("file_type") or "unknown")
        material_id = str(doc.get("material_id") or "")
        if not material_id:
            continue

        is_non_quiz, non_quiz_reason = classify_non_quiz_material(title, file_type)
        if is_non_quiz or not is_educational_material(title, file_type):
            continue

        text = (doc.get("content_text") or "").strip()
        if not text:
            err = str(doc.get("extraction_error") or "")
            stale_failed = doc.get("extraction_status") == "extraction_failed"
            if doc.get("last_attempted_at") or doc.get("processed_at"):
                results.append(
                    {
                        "material_id": material_id,
                        "title": title,
                        "action": "skipped_no_content_after_attempt",
                        "quiz_status": doc.get("extraction_status") or "not_uploaded",
                        "chars": 0,
                        "reason": err or "Upload attempted but no content stored",
                    }
                )
                continue
            if stale_failed and matches_educational_title(title):
                material_repository.upsert(
                    {
                        "course_id": course_id,
                        "material_id": material_id,
                        "extraction_status": "not_uploaded",
                        "extraction_error": (
                            "File detected from Moodle but content was not extracted yet"
                        ),
                        "ready_for_quiz": False,
                        "content_chars": 0,
                        "metadata_only": True,
                    }
                )
                updated_count += 1
                results.append(
                    {
                        "material_id": material_id,
                        "title": title,
                        "action": "reset_stale_failed_to_not_uploaded",
                        "quiz_status": "not_uploaded",
                        "chars": 0,
                    }
                )
            else:
                results.append(
                    {
                        "material_id": material_id,
                        "title": title,
                        "action": "skipped_no_content",
                        "quiz_status": "not_uploaded",
                        "chars": 0,
                        "reason": err or "No content_text stored",
                    }
                )
            continue

        probe_fields = _derive_readiness_from_probe(text, file_type)
        sync_doc: Dict[str, Any] = {
            "course_id": course_id,
            "material_id": material_id,
            "title": title,
            "file_type": file_type,
            "content_text": text,
            "content_chars": probe_fields["content_chars"],
            "ready_for_quiz": probe_fields["ready_for_quiz"],
            "extraction_status": probe_fields["extraction_status"],
            "extraction_error": probe_fields["extraction_error"],
            "metadata_only": False,
            "processed_at": now,
            "extractor_version": CURRENT_EXTRACTOR_VERSION,
        }
        material_repository.upsert(sync_doc)
        updated_count += 1
        results.append(
            {
                "material_id": material_id,
                "title": title,
                "action": "synced_from_probe",
                "chars": probe_fields["content_chars"],
                "probe_question_count": probe_fields["probe_question_count"],
                "probe_engine": probe_fields.get("probe_engine"),
                "quiz_status": probe_fields["quiz_probe_status"],
                "ready_for_quiz": probe_fields["ready_for_quiz"],
                "reason": probe_fields.get("extraction_error"),
            }
        )

    ready = [r for r in results if r.get("quiz_status") == "ready"]
    limited = [r for r in results if r.get("quiz_status") == "limited_ready"]
    disabled = [r for r in results if r.get("quiz_status") not in ("ready", "limited_ready")]

    merge_summary = merge_duplicate_content_in_course(course_id)

    return {
        "course_id": course_id,
        "reassessed_total": len(results),
        "updated_count": updated_count,
        "ready_count": len(ready),
        "limited_ready_count": len(limited),
        "disabled_count": len(disabled),
        "ready_materials": ready,
        "limited_ready_materials": limited,
        "disabled_materials": disabled,
        "materials": results,
        "duplicate_merge": merge_summary,
    }


def save_detected_materials(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Upsert metadata for every material detected on a Moodle course page.

    Does not require file bytes. Educational url/html/link resources are saved
    with extraction_status=not_uploaded so the quiz UI shows real rows instead
    of synthetic gap placeholders.
    """
    course_id = str(payload.get("course_id") or "").strip()
    course_name = payload.get("course_name")
    materials_in = payload.get("materials") or []

    if not course_id:
        raise ValueError("course_id required")

    user_email = (payload.get("user_email") or payload.get("email") or "").strip().lower()
    academiq_user_id = payload.get("academiq_user_id")
    if user_email and not academiq_user_id:
        user = user_repository.find_by_email(user_email)
        if user:
            academiq_user_id = str(user["_id"])

    inserted = 0
    updated = 0
    skipped = 0
    results: List[Dict[str, Any]] = []
    audit: List[Dict[str, Any]] = []
    batch_cmid_titles: Dict[str, str] = {}

    for detected_index, item in enumerate(materials_in):
        norm = _normalize_incoming_material_item(item)
        title = norm["title"]
        raw_file_type = norm["file_type"]
        activity_url = norm["activity_url"]
        resolved_url = norm["resolved_url"]
        cmid = norm.get("url_cmid") or norm.get("material_id")

        is_learning = is_educational_material(title, raw_file_type)
        is_non_quiz, non_quiz_reason = classify_non_quiz_material(title, raw_file_type)
        downloadable = _is_downloadable_material(raw_file_type, activity_url, resolved_url)

        audit_row: Dict[str, Any] = {
            "detected_index": detected_index,
            "title": title,
            "href": activity_url or None,
            "source_url": activity_url or None,
            "cmid": cmid or None,
            "file_type": raw_file_type,
            "is_learning_material": is_learning and not is_non_quiz,
            "was_sent_to_save_detected": True,
            "was_saved_in_db": False,
            "saved_material_id": None,
            "saved_title": None,
            "saved_file_type": None,
            "saved_status": None,
            "reason_if_not_saved": None,
            "key_strategy": None,
        }

        identity = resolve_material_identity(course_id, norm, batch_cmid_titles)
        material_id = identity["material_id"]
        existing = identity["existing_doc"]
        key_strategy = identity["match_strategy"]
        stable_key = identity["stable_material_key"]
        audit_row["key_strategy"] = key_strategy

        if not material_id:
            skipped += 1
            audit_row["reason_if_not_saved"] = "missing_material_id"
            audit.append(audit_row)
            results.append(
                {
                    "material_id": None,
                    "title": title,
                    "saved": False,
                    "status": "skipped",
                    "reason": "missing_material_id",
                }
            )
            continue

        scraped: Dict[str, Any] = {
            "title": title,
            "url": activity_url or None,
            "resolved_url": resolved_url or None,
            "file_type": raw_file_type,
            "material_type": item.get("material_type") or item.get("type"),
            "material_id": material_id,
        }
        base_doc = build_material_doc(scraped, course_id, course_name)
        if not base_doc:
            skipped += 1
            audit_row["reason_if_not_saved"] = "could_not_build_doc"
            audit.append(audit_row)
            results.append(
                {
                    "material_id": material_id,
                    "title": title,
                    "saved": False,
                    "status": "skipped",
                    "reason": "could_not_build_doc",
                }
            )
            continue

        base_doc["material_id"] = material_id
        base_doc["source"] = "moodle_sync"
        base_doc["stable_material_key"] = stable_key
        base_doc.update(enrich_kind_fields(title, raw_file_type))
        if activity_url:
            base_doc["original_moodle_url"] = activity_url
        if activity_url:
            base_doc["normalized_source_url"] = _normalize_source_url(activity_url)
        if resolved_url:
            base_doc["normalized_resolved_url"] = _normalize_source_url(resolved_url)
        if cmid:
            base_doc["moodle_cmid"] = str(cmid)
        if academiq_user_id:
            base_doc["academiq_user_id"] = academiq_user_id
        if user_email:
            base_doc["uploaded_by_email"] = user_email

        is_metadata_only = not downloadable and not is_non_quiz and is_learning

        _PROTECTED_ON_EXISTING = frozenset(
            {
                "content_text",
                "content_chars",
                "extraction_status",
                "extraction_error",
                "ready_for_quiz",
                "processed_at",
                "extractor_version",
                "uploaded_by_email",
                "uploaded_by_user_id",
                "quiz_status",
                "metadata_only",
            }
        )

        if existing:
            safe_doc: Dict[str, Any] = {
                "course_id": course_id,
                "material_id": material_id,
                "title": title,
                "file_type": raw_file_type,
                "source": "moodle_sync",
                "stable_material_key": stable_key,
            }
            if activity_url:
                safe_doc["normalized_source_url"] = _normalize_source_url(activity_url)
            if resolved_url:
                safe_doc["normalized_resolved_url"] = _normalize_source_url(resolved_url)
            if course_name:
                safe_doc["course_name"] = course_name
            if activity_url:
                safe_doc["url"] = activity_url
            if resolved_url:
                safe_doc["resolved_url"] = resolved_url
            mat_type = item.get("material_type") or item.get("type")
            if mat_type:
                safe_doc["material_type"] = mat_type
            if cmid:
                safe_doc["moodle_cmid"] = str(cmid)
            if academiq_user_id:
                safe_doc["academiq_user_id"] = academiq_user_id
            if user_email:
                safe_doc["uploaded_by_email"] = user_email
            for key, value in base_doc.items():
                if key in _PROTECTED_ON_EXISTING:
                    continue
                if key in ("course_id", "material_id") or value is None:
                    continue
                safe_doc[key] = value
            is_new = material_repository.upsert(safe_doc)
        else:
            if is_non_quiz:
                base_doc["extraction_status"] = "not_quiz_material"
                base_doc["extraction_error"] = non_quiz_reason
                base_doc["ready_for_quiz"] = False
                base_doc["quiz_status"] = "not_quiz_material"
                base_doc["metadata_only"] = False
            else:
                base_doc["extraction_status"] = "not_uploaded"
                if downloadable:
                    base_doc["extraction_error"] = "File detected but not downloaded yet"
                elif resolved_url and downloadable:
                    base_doc["extraction_error"] = "Nested download link found but not extracted yet"
                else:
                    base_doc["extraction_error"] = (
                        "Moodle activity detected but downloadable file was not found"
                    )
                base_doc["ready_for_quiz"] = False
                base_doc["content_chars"] = 0
                base_doc["quiz_status"] = "not_uploaded"
                base_doc["metadata_only"] = is_metadata_only
            is_new = material_repository.upsert(base_doc)

        if is_new:
            inserted += 1
        else:
            updated += 1

        saved_doc = material_repository.get(course_id, material_id) or existing or base_doc
        if existing:
            status = str(saved_doc.get("extraction_status") or "already_saved")
            reason = saved_doc.get("extraction_error")
        elif is_non_quiz:
            status = "not_quiz_material"
            reason = non_quiz_reason
        else:
            status = "not_uploaded"
            reason = base_doc.get("extraction_error")

        audit_row.update(
            {
                "was_saved_in_db": True,
                "saved_material_id": material_id,
                "saved_title": saved_doc.get("title") or title,
                "saved_file_type": saved_doc.get("file_type") or raw_file_type,
                "saved_status": status,
            }
        )
        audit.append(audit_row)

        results.append(
            {
                "material_id": material_id,
                "title": title,
                "file_type": raw_file_type,
                "source_url": activity_url or None,
                "saved": True,
                "inserted": is_new,
                "status": status,
                "reason": reason,
                "downloadable": downloadable,
                "metadata_only": bool(saved_doc.get("metadata_only")),
                "key_strategy": key_strategy,
            }
        )

    db_rows = material_repository.list_by_course(course_id)
    metadata_saved_total = inserted + updated
    lecture_audit = [
        row for row in audit
        if re.search(r"(?i)\blecture\b", row.get("title") or "")
        or re.search(r"(?i)\blecture\b", row.get("saved_title") or "")
    ]
    reassess_summary = reassess_course_material_readiness(course_id)
    return {
        "course_id": course_id,
        "detected_total": len(materials_in),
        "metadata_saved_total": metadata_saved_total,
        "metadata_inserted": inserted,
        "metadata_updated": updated,
        "metadata_skipped": skipped,
        "saved_total": len(db_rows),
        "db_materials_found_for_course": len(db_rows),
        "total_metadata_only_materials": sum(1 for d in db_rows if d.get("metadata_only")),
        "total_content_materials": sum(
            1 for d in db_rows if _content_chars_from_doc(d) > 0
        ),
        "materials": results,
        "audit": audit,
        "lecture_audit": lecture_audit,
        "readiness_reassess": {
            "ready_count": reassess_summary.get("ready_count"),
            "limited_ready_count": reassess_summary.get("limited_ready_count"),
            "disabled_count": reassess_summary.get("disabled_count"),
            "ready_materials": reassess_summary.get("ready_materials"),
            "limited_ready_materials": reassess_summary.get("limited_ready_materials"),
            "disabled_materials": reassess_summary.get("disabled_materials"),
        },
    }


def _append_db_not_uploaded_retry_rows(
    course_id: str,
    all_docs: List[Dict[str, Any]],
    results: List[Dict[str, Any]],
    force_reupload: bool,
) -> int:
    """Add DB-only not_uploaded learning rows missing from the scrape preflight batch."""
    added = 0
    seen_ids = {str(r.get("material_id") or "") for r in results}
    seen_cmids: set[str] = set()
    for r in results:
        for u in (r.get("db_source_url"), r.get("debug", {}).get("incoming_source_url")):
            cmid = _material_id_from_url(str(u or ""))
            if cmid:
                seen_cmids.add(cmid)

    for doc in all_docs:
        material_id = str(doc.get("material_id") or "").strip()
        if not material_id or material_id in seen_ids:
            continue
        title = str(doc.get("title") or "Untitled").strip()
        raw_file_type = str(doc.get("file_type") or "unknown").strip()
        if not _is_targeted_not_uploaded_learning_material(title, raw_file_type, doc):
            continue
        activity_url = str(doc.get("url") or doc.get("source_url") or "").strip()
        resolved_url = str(doc.get("resolved_url") or "").strip()
        url_cmid = _material_id_from_url(activity_url) or _material_id_from_url(resolved_url)
        if url_cmid and url_cmid in seen_cmids:
            continue

        downloadable = _is_downloadable_material(raw_file_type, activity_url, resolved_url)
        should_reupload, out_status, reason, existing_chars, _ = _preflight_upload_decision(
            doc,
            title,
            raw_file_type,
            activity_url,
            resolved_url,
            force_reupload,
        )
        url_fields = _preflight_row_urls(doc, activity_url, resolved_url)
        identity = resolve_material_identity(
            course_id,
            {
                "title": title,
                "file_type": raw_file_type,
                "activity_url": activity_url,
                "resolved_url": resolved_url,
                "raw_material_id": material_id,
                "material_id": material_id,
                "url_cmid": url_cmid,
            },
            matched_material_id=material_id,
        )
        results.append(
            {
                "material_id": identity["material_id"],
                "title": identity.get("matched_db_title") or title,
                "file_type": raw_file_type,
                "should_upload": should_reupload,
                "status": out_status,
                "reason": reason,
                "content_text_length": existing_chars,
                "matched_by": "db_not_uploaded_retry",
                "downloadable": downloadable,
                "targeted_retry": True,
                "db_id": identity.get("db_id"),
                "stable_material_key": identity.get("stable_material_key"),
                "matched_db_id": identity.get("db_id"),
                "matched_db_title": identity.get("matched_db_title"),
                "matched_db_material_id": identity.get("material_id"),
                **url_fields,
                "debug": {
                    "material_id_sent": material_id,
                    "material_id_used": material_id,
                    "course_id": course_id,
                    "db_record_found": True,
                    "source": "db_retry_queue",
                },
            }
        )
        seen_ids.add(material_id)
        if url_cmid:
            seen_cmids.add(url_cmid)
        added += 1
    return added


def preflight_materials(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pre-upload check: return which materials need uploading without downloading files.

    Strategy: bulk-load ALL materials for the course once, then match each incoming
    item using four methods in priority order:
      A. material_id (cmid extracted from activity URL)
      B. activity URL (stored as 'url' in DB)
      C. resolved URL (pluginfile.php URL, stored as 'resolved_url')
      D. normalized title + file_type (catches cmid mismatches)

    Returns per-material: should_upload, status, reason, content_text_length,
    matched_by, and debug fields.
    """
    course_id = str(payload.get("course_id") or "").strip()
    materials_in = payload.get("materials") or []
    force_reupload = _is_force_reprocess(payload)

    if not course_id:
        raise ValueError("course_id required")

    # ── Phase 1: Bulk-load all materials for this course (ONE query) ─────────
    all_docs = material_repository.list_by_course(course_id)

    # Build in-memory lookup maps from the bulk load
    by_material_id: Dict[str, Any] = {}   # stored material_id → doc
    by_url: Dict[str, Any] = {}           # stored url/resolved_url → doc
    by_url_cmid: Dict[str, Any] = {}      # cmid extracted from stored URL → doc
    by_title_ft: Dict[str, Any] = {}      # (normalized_title, file_type) → doc

    for doc in all_docs:
        mid = str(doc.get("material_id") or "").strip()
        if mid:
            by_material_id[mid] = doc

        for url_field in ("url", "resolved_url", "source_url"):
            u = str(doc.get(url_field) or "").strip()
            if u:
                by_url[u] = doc
                # Also index by the cmid extracted from the stored URL — covers
                # cases where material_id was stored as the full URL or a hash
                stored_cmid = _material_id_from_url(u)
                if stored_cmid:
                    by_url_cmid[stored_cmid] = doc

        t_key = _normalize_title(doc.get("title") or "")
        ft = str(doc.get("file_type") or "").lower().strip()
        if t_key and ft and ft != "unknown":
            by_title_ft[(t_key, ft)] = doc
        if t_key:
            by_title_ft[(t_key, "")] = doc

    # Sample of stored material_ids for the response (helps debug course_id mismatches)
    db_sample = [
        {"material_id": d.get("material_id"), "url": (d.get("url") or "")[:60]}
        for d in all_docs[:5]
    ]

    # ── Per-material matching ─────────────────────────────────────────────────
    results: List[Dict[str, Any]] = []
    no_match_debug: List[Dict[str, Any]] = []   # populated for first 20 no_match items
    from app.config.database import course_materials_collection

    for item in materials_in:
        norm = _normalize_incoming_material_item(item)
        title = norm["title"]
        raw_file_type = norm["file_type"]
        activity_url = norm["activity_url"]
        resolved_url = norm["resolved_url"]
        raw_material_id = norm["raw_material_id"]
        url_cmid = norm["url_cmid"]
        material_id = norm["material_id"]
        downloadable = _is_downloadable_material(raw_file_type, activity_url, resolved_url)

        # ── A: Non-quiz classification (no DB needed) ─────────────────────────
        is_non_quiz, non_quiz_reason = classify_non_quiz_material(title, raw_file_type)
        if is_non_quiz:
            results.append({
                "material_id": material_id,
                "title": title,
                "should_upload": False,
                "status": "not_quiz_material",
                "reason": non_quiz_reason,
                "content_text_length": 0,
                "matched_by": "classification",
                **_preflight_row_urls(None, activity_url, resolved_url),
                "debug": {
                    "material_id_sent": raw_material_id,
                    "material_id_used": material_id,
                    "course_id": course_id,
                    "db_record_found": False,
                },
            })
            continue

        # ── B0: Shared canonical identity resolver (before fuzzy fallbacks) ───
        existing_doc = None
        matched_by = None
        identity_first = resolve_material_identity(
            course_id,
            norm,
            stable_material_key=str(item.get("stable_material_key") or "").strip() or None,
            matched_material_id=str(
                item.get("material_id") or item.get("id") or ""
            ).strip()
            or None,
        )
        if identity_first.get("existing_doc"):
            existing_doc = identity_first["existing_doc"]
            matched_by = f"identity:{identity_first.get('match_strategy')}"

        # ── B: Phase 1 — in-memory lookup (fast, uses bulk-load data) ─────────
        # M1: exact material_id (cmid)
        if material_id and material_id in by_material_id:
            existing_doc = by_material_id[material_id]
            matched_by = f"material_id:{material_id}"

        # M2: raw material_id sent by extension (before cmid extraction)
        if not existing_doc and raw_material_id and raw_material_id in by_material_id:
            existing_doc = by_material_id[raw_material_id]
            matched_by = f"raw_material_id:{raw_material_id}"

        # M3: cmid from incoming URL vs cmid extracted from stored URLs
        if not existing_doc and url_cmid and url_cmid in by_url_cmid:
            existing_doc = by_url_cmid[url_cmid]
            matched_by = f"url_cmid:{url_cmid}"

        # M4: exact activity URL string
        if not existing_doc and activity_url and activity_url in by_url:
            existing_doc = by_url[activity_url]
            matched_by = "activity_url"

        # M5: exact resolved URL string
        if not existing_doc and resolved_url and resolved_url in by_url:
            existing_doc = by_url[resolved_url]
            matched_by = "resolved_url"

        # M6: exact normalized title + file_type (handles punctuation/space diffs)
        if not existing_doc:
            t_key = _normalize_title(title)
            ft = raw_file_type.lower()
            if t_key and (t_key, ft) in by_title_ft:
                existing_doc = by_title_ft[(t_key, ft)]
                matched_by = f"title+ft:{t_key[:25]}"
            elif t_key and (t_key, "") in by_title_ft:
                existing_doc = by_title_ft[(t_key, "")]
                matched_by = f"title:{t_key[:25]}"

        # M7: fuzzy title — Jaccard word-overlap (threshold 0.45, same-filetype bonus)
        if not existing_doc and all_docs:
            t_key = _normalize_title(title)
            ft_lower = raw_file_type.lower()
            best_score = 0.0
            best_doc_fuzzy = None
            for doc in all_docs:
                stored_t = _normalize_title(doc.get("title") or "")
                if not stored_t:
                    continue
                score = _title_word_overlap(t_key, stored_t)
                if score > 0:
                    stored_ft = str(doc.get("file_type") or "").lower()
                    if stored_ft and ft_lower and stored_ft == ft_lower:
                        score = min(1.0, score * 1.1)
                if score > best_score:
                    best_score = score
                    best_doc_fuzzy = doc
            if best_score >= 0.45:
                existing_doc = best_doc_fuzzy
                matched_by = f"fuzzy_title:{best_score:.2f}"

        # M8: word-containment — all words of the shorter title are ⊆ words of longer.
        # Handles "Lab 4" ↔ "Week 1 Lab 4 File", "Lecture" ↔ "Lecture 1 Introduction".
        # Requires ≥ 2 significant words in the shorter set to avoid trivial matches.
        if not existing_doc and all_docs:
            t_key = _normalize_title(title)
            words_in = set(t_key.split()) - _TITLE_STOP_WORDS
            if len(words_in) >= 2:
                for doc in all_docs:
                    stored_t = _normalize_title(doc.get("title") or "")
                    words_stored = set(stored_t.split()) - _TITLE_STOP_WORDS
                    if not words_stored:
                        continue
                    if words_in.issubset(words_stored) or words_stored.issubset(words_in):
                        existing_doc = doc
                        matched_by = f"word_containment:{stored_t[:25]}"
                        break

        # ── C: Phase 2 fallback — direct MongoDB query (no course_id filter) ──
        # Handles course_id mismatches: Moodle cmids are globally unique.
        if not existing_doc:
            fallback_clauses: List[Dict[str, Any]] = []
            if material_id:
                fallback_clauses.append({"material_id": str(material_id)})
            if raw_material_id and raw_material_id != material_id:
                fallback_clauses.append({"material_id": str(raw_material_id)})
            if url_cmid and url_cmid not in (material_id, raw_material_id):
                fallback_clauses.append({"material_id": str(url_cmid)})
            if activity_url:
                fallback_clauses.append({"url": activity_url})
                fallback_clauses.append({"resolved_url": activity_url})
            if resolved_url:
                fallback_clauses.append({"url": resolved_url})
                fallback_clauses.append({"resolved_url": resolved_url})

            if fallback_clauses:
                existing_doc = course_materials_collection.find_one(
                    {"$or": fallback_clauses}
                )
                if existing_doc:
                    matched_by = f"fallback_db"

        # ── D: Build debug_info for this item ────────────────────────────────
        debug_info = {
            "material_id_sent": raw_material_id,
            "material_id_used": material_id,
            "incoming_cmid": url_cmid,
            "activity_url": activity_url[:80] if activity_url else None,
            "course_id": course_id,
            "db_record_found": existing_doc is not None,
            "matched_by": matched_by,
            "db_material_id": str(existing_doc.get("material_id") or "") if existing_doc else None,
        }

        if not existing_doc:
            # Collect no_match diagnostics (first 20) — top-3 closest stored titles
            if len(no_match_debug) < 20:
                t_key = _normalize_title(title)
                closest = sorted(
                    all_docs,
                    key=lambda d: _title_word_overlap(t_key, _normalize_title(d.get("title") or "")),
                    reverse=True,
                )[:3]
                no_match_debug.append({
                    "incoming_title": title,
                    "incoming_material_id": raw_material_id,
                    "incoming_material_id_used": material_id,
                    "incoming_source_url": activity_url[:80] if activity_url else None,
                    "incoming_cmid": url_cmid,
                    "incoming_file_type": raw_file_type,
                    "normalized_title": t_key,
                    "closest_existing_titles": [
                        {
                            "material_id": d.get("material_id"),
                            "title": d.get("title"),
                            "normalized": _normalize_title(d.get("title") or ""),
                            "overlap_score": round(_title_word_overlap(t_key, _normalize_title(d.get("title") or "")), 3),
                        }
                        for d in closest
                    ],
                    "reason_no_match": (
                        "No title overlap ≥0.6 and no ID/URL match"
                        if not closest or _title_word_overlap(t_key, _normalize_title(closest[0].get("title") or "")) < 0.6
                        else "Best fuzzy score just below threshold"
                    ),
                })

            results.append({
                "material_id": material_id,
                "title": title,
                "should_upload": downloadable,
                "status": "not_uploaded" if downloadable else "metadata_only",
                "reason": (
                    "No DB record found — file download needed"
                    if downloadable
                    else "Metadata-only Moodle resource — no downloadable file"
                ),
                "content_text_length": 0,
                "matched_by": None,
                "downloadable": downloadable,
                **_preflight_row_urls(None, activity_url, resolved_url),
                "debug": debug_info,
            })
            continue

        # ── C: Determine skip/upload decision from existing record ───────────
        should_reupload, out_status, reason, existing_chars, downloadable = _preflight_upload_decision(
            existing_doc,
            title,
            raw_file_type,
            activity_url,
            resolved_url,
            force_reupload,
        )

        identity = resolve_material_identity(
            course_id,
            norm,
            matched_material_id=str(existing_doc.get("material_id")) if existing_doc else None,
        )
        if identity.get("material_id"):
            material_id = identity["material_id"]
            existing_doc = identity.get("existing_doc") or existing_doc

        results.append({
            "material_id": material_id,
            "title": title if not identity.get("matched_db_title") else identity.get("matched_db_title"),
            "file_type": raw_file_type,
            "should_upload": should_reupload,
            "status": out_status,
            "reason": reason,
            "content_text_length": existing_chars,
            "matched_by": matched_by,
            "downloadable": downloadable,
            "targeted_retry": _is_targeted_not_uploaded_learning_material(
                title, raw_file_type, existing_doc
            ),
            "db_id": identity.get("db_id"),
            "stable_material_key": identity.get("stable_material_key"),
            "matched_db_id": identity.get("db_id"),
            "matched_db_title": identity.get("matched_db_title"),
            "matched_db_material_id": identity.get("material_id"),
            **_preflight_row_urls(existing_doc, activity_url, resolved_url),
            "debug": debug_info,
        })

    _db_retry_rows_added = _append_db_not_uploaded_retry_rows(course_id, all_docs, results, force_reupload)

    should_upload_count = sum(1 for r in results if r["should_upload"])
    matched_count = sum(1 for r in results if r.get("matched_by") is not None)
    no_match_count = sum(
        1 for r in results
        if r.get("matched_by") is None and r["status"] != "not_quiz_material"
    )
    status_summary: Dict[str, int] = {}
    match_method_summary: Dict[str, int] = {}
    for r in results:
        status_summary[r["status"]] = status_summary.get(r["status"], 0) + 1
        method = (r.get("matched_by") or "not_found").split(":")[0]
        match_method_summary[method] = match_method_summary.get(method, 0) + 1

    downloadable_count = sum(1 for r in results if r.get("downloadable"))

    unique_input_ids = {
        str(_normalize_incoming_material_item(item).get("material_id") or "")
        for item in materials_in
    }
    unique_input_ids.discard("")

    return {
        "course_id": course_id,
        "checked": len(results),
        "preflight_checked_total": len(results),
        "preflight_input_count": len(materials_in),
        "preflight_unique_input_count": len(unique_input_ids),
        "db_retry_rows_added": _db_retry_rows_added,
        "detected_total": len(materials_in),
        "downloadable_count": downloadable_count,
        "metadata_only_count": len(results) - downloadable_count,
        "should_upload_count": should_upload_count,
        "matched_count": matched_count,
        "no_match_count": no_match_count,
        # Per-status counts for popup display
        "already_ready": status_summary.get("already_ready", 0),
        "already_classified": (
            status_summary.get("already_classified", 0)
            + status_summary.get("already_processed", 0)
            + status_summary.get("already_saved", 0)
            + status_summary.get("not_quiz_material", 0)
        ),
        "extraction_failed": status_summary.get("extraction_failed", 0),
        "not_quiz_material": status_summary.get("not_quiz_material", 0),
        "total": len(results),
        "skip_count": len(results) - should_upload_count,
        "db_materials_found_for_course": len(all_docs),
        "status_summary": status_summary,
        "match_method_summary": match_method_summary,
        "db_sample": db_sample,
        "no_match_debug": no_match_debug,
        "materials": results,
    }


def _material_id_from_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    match = re.search(r"[?&](?:id|cmid)=(\d+)", url, re.I)
    return match.group(1) if match else None


def _build_upload_identity_audit(
    norm: Dict[str, Any],
    identity_before: Dict[str, Any],
    identity_after: Dict[str, Any],
    payload: Dict[str, Any],
    content_text_length: int,
    quiz_status: Optional[str],
) -> Dict[str, Any]:
    return {
        "incoming_title": norm.get("title"),
        "incoming_material_id": norm.get("raw_material_id"),
        "incoming_cmid": norm.get("url_cmid"),
        "incoming_source_url": norm.get("activity_url"),
        "incoming_resolved_url": norm.get("resolved_url"),
        "matched_db_id_before_upload": identity_before.get("db_id"),
        "matched_db_title_before_upload": identity_before.get("matched_db_title"),
        "matched_db_material_id_before_upload": identity_before.get("material_id"),
        "final_saved_db_id": identity_after.get("db_id"),
        "final_saved_title": identity_after.get("matched_db_title"),
        "final_saved_material_id": identity_after.get("material_id"),
        "content_text_length": content_text_length,
        "quiz_status": quiz_status,
        "match_strategy": identity_after.get("match_strategy"),
        "payload_db_id": payload.get("db_id") or payload.get("matched_db_id"),
        "payload_matched_material_id": payload.get("matched_material_id"),
    }


def _sync_extracted_content_to_canonical_row(
    course_id: str,
    written_material_id: str,
    norm: Dict[str, Any],
    content_fields: Dict[str, Any],
) -> str:
    """
    If content was written to a duplicate URL/page row, copy it to the canonical
  file row shown in Quiz Generation and mark the duplicate as hidden.
    """
    written = material_repository.get(course_id, written_material_id)
    if not written:
        return written_material_id
    text = (content_fields.get("content_text") or written.get("content_text") or "").strip()
    if not text:
        return written_material_id

    canonical = _find_canonical_learning_row(
        course_id, norm.get("title") or written.get("title") or "", norm.get("file_type") or ""
    )
    if not canonical:
        return written_material_id
    canonical_id = str(canonical.get("material_id") or "")
    if not canonical_id or canonical_id == written_material_id:
        return written_material_id
    if _canonical_learning_row_score(canonical) <= _canonical_learning_row_score(written):
        return written_material_id

    merge_doc: Dict[str, Any] = {
        "course_id": course_id,
        "material_id": canonical_id,
        "title": canonical.get("title"),
        "file_type": canonical.get("file_type"),
        **content_fields,
        "metadata_only": False,
        "hidden_duplicate": False,
        "duplicate_of": None,
    }
    if content_fields.get("resolved_url"):
        merge_doc["resolved_url"] = content_fields["resolved_url"]
    elif norm.get("resolved_url"):
        merge_doc["resolved_url"] = norm.get("resolved_url")
    if norm.get("activity_url"):
        merge_doc.setdefault("url", norm.get("activity_url"))
    material_repository.upsert(merge_doc)

    # Re-probe canonical row after merge
    merged_doc = material_repository.get(course_id, canonical_id) or merge_doc
    merged_text = (merged_doc.get("content_text") or content_fields.get("content_text") or "").strip()
    if merged_text:
        probe_fields = _derive_readiness_from_probe(
            merged_text, str(merged_doc.get("file_type") or canonical.get("file_type") or "")
        )
        material_repository.upsert(
            {
                "course_id": course_id,
                "material_id": canonical_id,
                "ready_for_quiz": probe_fields["ready_for_quiz"],
                "extraction_status": probe_fields["extraction_status"],
                "extraction_error": probe_fields["extraction_error"],
                "content_chars": probe_fields["content_chars"],
            }
        )

    material_repository.upsert(
        {
            "course_id": course_id,
            "material_id": written_material_id,
            "duplicate_of": canonical_id,
            "hidden_duplicate": True,
            "content_text": "",
            "content_chars": 0,
            "metadata_only": True,
            "extraction_status": "not_uploaded",
            "extraction_error": f"Content moved to canonical row {canonical_id}",
            "ready_for_quiz": False,
        }
    )
    return canonical_id


def _decode_payload_bytes(payload: Dict[str, Any]) -> tuple[bytes, Optional[str]]:
    b64 = payload.get("content_base64")
    if b64:
        try:
            return base64.b64decode(b64), None
        except Exception as exc:
            return b"", f"invalid_base64:{exc}"
    return b"", None


_TERMINAL_QUIZ_DISPLAY_STATUSES = frozenset(
    {
        "ready",
        "limited_ready",
        "extraction_failed",
        "not_enough_readable_text",
        "extraction_too_short",
        "not_quiz_material",
    }
)


def _normalize_upload_failure_reason(
    raw: str,
    payload: Optional[Dict[str, Any]] = None,
) -> str:
    """Map extension/backend errors to specific persisted failure reasons."""
    value = str(raw or "").strip()
    lowered = value.lower()
    audit = (payload or {}).get("upload_audit") or {}
    download_status = str(audit.get("download_status") or "").lower()

    if value in (
        "no_download_link_on_page",
        "no_download_link_found_on_resource_page",
        "no_pluginfile_found_on_resource_page",
    ):
        return "no_pluginfile_found_on_resource_page"

    if lowered.startswith("http_"):
        code = lowered.replace("http_", "").split(":")[0]
        if code in ("401", "403"):
            return "permission_or_session_error"
        return f"download_failed_http_{code}"

    if "unexpected_content_type" in lowered and "html" in lowered:
        return "html_returned_instead_of_pdf"
    if "unexpected_content_type" in download_status and "html" in download_status:
        return "html_returned_instead_of_pdf"

    if lowered in ("empty_response", "empty_file", "no_content"):
        return "empty_response"
    if "empty" in lowered and "content" in lowered:
        return "empty_response"

    if "permission" in lowered or "session" in lowered or lowered in ("401", "403"):
        return "permission_or_session_error"

    if lowered.startswith("invalid_base64") or lowered.startswith("parser"):
        return "parser_failed"

    if lowered in ("unsupported_file_type", "unsupported") or "unsupported" in lowered:
        return "unsupported_file_type"

    if (
        "not_enough" in lowered
        or "insufficient_text" in lowered
        or "too_short" in lowered
        or lowered == "content_extracted_but_not_enough_readable_text"
    ):
        return "content_extracted_but_not_enough_readable_text"

    if lowered.startswith("download_failed:"):
        inner = lowered.replace("download_failed:", "", 1)
        return _normalize_upload_failure_reason(inner, payload)

    if "pluginfile" in lowered or "no_download" in lowered:
        return "no_pluginfile_found_on_resource_page"

    if lowered in ("missing_db_id_from_preflight", "db_id_required_from_preflight"):
        return "db_id_required_from_preflight"

    if lowered == "upload_verification_failed_still_not_uploaded":
        return "upload_verification_failed_still_not_uploaded"

    return value or "download_failed_unknown"


def _persist_terminal_upload_failure(
    course_id: str,
    target_db_id: str,
    reason: str,
    source_url: Optional[str] = None,
    resolved_url: Optional[str] = None,
) -> bool:
    """Write terminal extraction_failed to the exact preflight db_id row."""
    doc = material_repository.get_by_object_id(target_db_id)
    if not doc:
        return False

    now = datetime.utcnow()
    normalized_reason = _normalize_upload_failure_reason(reason)
    fields: Dict[str, Any] = {
        "course_id": course_id,
        "material_id": str(doc.get("material_id") or ""),
        "title": doc.get("title"),
        "file_type": doc.get("file_type"),
        "extraction_status": "extraction_failed",
        "extraction_error": normalized_reason,
        "ready_for_quiz": False,
        "metadata_only": False,
        "last_attempted_at": now,
        "processed_at": now,
        "extractor_version": CURRENT_EXTRACTOR_VERSION,
    }
    if source_url:
        fields["url"] = source_url
    if resolved_url:
        fields["resolved_url"] = resolved_url

    updated = material_repository.update_by_object_id(target_db_id, fields)
    if not updated:
        material_repository.upsert(fields)
    return True


def _display_quiz_status_for_doc(doc: Dict[str, Any]) -> str:
    """Quiz status for verification — raw DB status, not soft not_uploaded remap."""
    extraction_status = str(doc.get("extraction_status") or "not_uploaded")
    if extraction_status == "extraction_failed":
        return "extraction_failed"
    if extraction_status in ("not_enough_readable_text", "too_short", "insufficient_text"):
        return "not_enough_readable_text"
    if extraction_status == "not_quiz_material":
        return "not_quiz_material"
    content_len = _content_chars_from_doc(doc)
    if content_len > 0:
        displays, _ = resolve_quiz_material_display([doc])
        if displays:
            return str(displays[0].get("quiz_status") or "not_uploaded")
    if doc.get("last_attempted_at") or doc.get("processed_at"):
        if extraction_status not in ("", "not_uploaded"):
            return extraction_status
    return "not_uploaded"


def _resolve_preflight_upload_target(
    course_id: str,
    payload: Dict[str, Any],
    title: str,
    file_type: str,
    norm: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Resolve the exact Mongo row Quiz Generation displays for this upload.
    Prefers db_id from preflight; falls back to identity resolution when missing.
    """
    target_db_id = str(
        payload.get("db_id") or payload.get("matched_db_id") or ""
    ).strip()
    target_doc: Optional[Dict[str, Any]] = None

    if target_db_id:
        target_doc = material_repository.get_by_object_id(target_db_id)

    if not target_doc and norm:
        identity = resolve_material_identity(
            course_id,
            norm,
            matched_material_id=str(
                payload.get("matched_material_id")
                or payload.get("material_id")
                or payload.get("id")
                or ""
            ).strip()
            or None,
            stable_material_key=str(payload.get("stable_material_key") or "").strip() or None,
        )
        target_doc = identity.get("existing_doc")
        if target_doc:
            target_db_id = _mongo_id_str(target_doc) or ""

    if not target_db_id or not target_doc:
        return None, None, {
            "status": "rejected",
            "reason": "db_id_required_from_preflight",
            "extraction_error": "db_id_required_from_preflight",
            "ok": False,
            "verified_ok": False,
            "attempted": True,
            "backend_called": True,
        }

    if str(target_doc.get("course_id") or "") != str(course_id):
        return None, None, {
            "status": "rejected",
            "reason": "db_id_course_mismatch",
            "extraction_error": "db_id_course_mismatch",
            "db_id": target_db_id,
            "ok": False,
            "verified_ok": False,
            "attempted": True,
            "backend_called": True,
        }

    canonical = _find_canonical_learning_row(course_id, title, file_type)
    if canonical:
        canonical_db_id = _mongo_id_str(canonical)
        if canonical_db_id and canonical_db_id != target_db_id:
            target_db_id = canonical_db_id
            target_doc = canonical

    return target_db_id, target_doc, None


def _read_verified_upload_state(
    course_id: str,
    target_db_id: str,
) -> Dict[str, Any]:
    """Re-read the exact preflight db_id from Mongo and map Quiz Generation display fields."""
    doc = material_repository.get_by_object_id(target_db_id)
    if not doc:
        return {
            "found": False,
            "db_id": target_db_id,
            "reason": "db_id_not_found_after_save",
        }

    displays, _ = resolve_quiz_material_display([doc])
    display = displays[0] if displays else {}
    content_len = int(display.get("content_text_length") or 0) or _content_chars_from_doc(doc)
    extraction_status = str(doc.get("extraction_status") or "not_uploaded")
    quiz_status = _display_quiz_status_for_doc(doc)
    reason = (
        doc.get("extraction_error")
        or display.get("reason")
        or display.get("why_not_ready")
        or ""
    )

    return {
        "found": True,
        "db_id": target_db_id,
        "material_id": str(doc.get("material_id") or ""),
        "title": display.get("title") or doc.get("title"),
        "content_text_length": content_len,
        "quiz_status": quiz_status,
        "extraction_status": extraction_status,
        "ready_for_quiz": bool(display.get("ready_for_quiz")),
        "probe_question_count": display.get("probe_question_count"),
        "reason": reason,
        "source_url": doc.get("url") or doc.get("source_url"),
        "resolved_url": doc.get("resolved_url"),
    }


def _compute_verified_upload_flags(
    state: Dict[str, Any],
    attempted: bool,
) -> Dict[str, bool]:
    content_len = int(state.get("content_text_length") or 0)
    quiz_status = str(state.get("quiz_status") or "not_uploaded")
    extraction_status = str(state.get("extraction_status") or "not_uploaded")

    terminal_extraction = extraction_status not in ("", "not_uploaded")
    terminal_quiz = quiz_status in _TERMINAL_QUIZ_DISPLAY_STATUSES

    verified_ready = quiz_status in ("ready", "limited_ready")
    verified_failed = (
        extraction_status == "extraction_failed"
        or quiz_status == "extraction_failed"
        or quiz_status in ("not_enough_readable_text", "extraction_too_short")
    )
    verified_uploaded = content_len > 0 or (
        attempted and (terminal_extraction or terminal_quiz)
    )
    verified_ok = (
        content_len > 0
        or verified_ready
        or verified_failed
        or (attempted and terminal_extraction)
    )
    if attempted and content_len == 0 and extraction_status == "not_uploaded":
        verified_ok = False
        verified_uploaded = False

    return {
        "verified_ok": verified_ok,
        "verified_uploaded": verified_uploaded,
        "verified_ready": verified_ready,
        "verified_failed": verified_failed,
        "verified_failure": verified_failed and attempted,
    }


def _repair_still_not_uploaded_row(
    course_id: str,
    target_db_id: str,
    reason: str,
    source_url: Optional[str] = None,
    resolved_url: Optional[str] = None,
) -> None:
    _persist_terminal_upload_failure(
        course_id,
        target_db_id,
        reason,
        source_url=source_url,
        resolved_url=resolved_url,
    )


def _package_upload_response(
    course_id: str,
    target_db_id: str,
    attempted: bool,
    payload: Dict[str, Any],
    body: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Attach verified Mongo re-read fields and set ok only when the exact db_id row
    was substantively updated (content or terminal status).
    """
    upload_audit = dict(payload.get("upload_audit") or {})
    upload_audit["backend_called"] = True
    upload_audit["attempted"] = attempted

    state = _read_verified_upload_state(course_id, target_db_id)
    if not state.get("found"):
        body.update(
            {
                "db_id": target_db_id,
                "ok": False,
                "verified_ok": False,
                "attempted": attempted,
                "backend_called": True,
                "reason": state.get("reason"),
                "verification_audit": upload_audit,
            }
        )
        return body

    if (
        attempted
        and state["content_text_length"] == 0
        and state["extraction_status"] == "not_uploaded"
    ):
        repair_reason = _normalize_upload_failure_reason(
            body.get("extraction_error")
            or upload_audit.get("failure_reason")
            or upload_audit.get("download_status")
            or "upload_verification_failed_still_not_uploaded",
            payload,
        )
        _repair_still_not_uploaded_row(
            course_id,
            target_db_id,
            repair_reason,
            source_url=state.get("source_url"),
            resolved_url=state.get("resolved_url"),
        )
        state = _read_verified_upload_state(course_id, target_db_id)

    flags = _compute_verified_upload_flags(state, attempted)
    verification_audit = {
        "title": state.get("title"),
        "db_id": target_db_id,
        "material_id": state.get("material_id"),
        "source_url": state.get("source_url"),
        "resolved_url": state.get("resolved_url"),
        "download_url_used": upload_audit.get("download_url_used"),
        "backend_response_status": body.get("status"),
        "attempted": attempted,
        "backend_called": True,
        "verified_content_text_length": state["content_text_length"],
        "verified_quiz_status": state["quiz_status"],
        "verified_extraction_status": state["extraction_status"],
        "reason": state.get("reason"),
        **flags,
    }

    body.update(
        {
            "db_id": target_db_id,
            "material_id": state.get("material_id"),
            "title": state.get("title"),
            "content_text_length": state["content_text_length"],
            "verified_content_text_length": state["content_text_length"],
            "chars": state["content_text_length"],
            "quiz_status": state["quiz_status"],
            "verified_quiz_status": state["quiz_status"],
            "extraction_status": state["extraction_status"],
            "verified_extraction_status": state["extraction_status"],
            "ready_for_quiz": state["ready_for_quiz"],
            "probe_question_count": state.get("probe_question_count"),
            "reason": state.get("reason"),
            "source_url": state.get("source_url"),
            "resolved_url": state.get("resolved_url"),
            "download_url_used": upload_audit.get("download_url_used"),
            "attempted": attempted,
            "backend_called": True,
            "verification_audit": verification_audit,
            **flags,
            "ok": flags["verified_ok"],
        }
    )
    return body


def process_material_upload_for_quiz(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Upsert material metadata + extracted text from extension upload.

    Accepts either content_base64 (file bytes) or content_text (pre-extracted).

    Caching:
      If a material already has content_text with enough characters, the
      re-extraction step is skipped and the response includes
      status="skipped_existing" so the extension can report a fast second upload.

    Readiness rule (simplified):
      Any material with extracted text >= MIN_QUIZ_CONTENT_CHARS is marked
      ready_for_quiz=True.  The strict probe-based check is removed — the quiz
      generator handles all content types via its four-engine pipeline (light →
      lecture → heavy → fragment).  Only truly failed extractions or empty files
      are marked not-ready.
    """
    course_id = str(payload.get("course_id") or "").strip()
    raw_material_id = str(
        payload.get("material_id") or payload.get("id") or stable_material_id(payload) or ""
    ).strip()
    source_url = payload.get("source_url") or payload.get("url")
    resolved_url_payload = str(
        payload.get("resolved_url") or payload.get("resolvedUrl") or ""
    ).strip() or None
    title = (payload.get("title") or "Untitled Material").strip()
    file_type = payload.get("file_type") or payload.get("fileType") or "unknown"

    norm = _normalize_incoming_material_item(
        {
            "title": title,
            "file_type": file_type,
            "url": source_url,
            "source_url": source_url,
            "resolved_url": resolved_url_payload,
            "material_id": raw_material_id,
            "id": raw_material_id,
        }
    )

    target_db_id, target_doc, reject = _resolve_preflight_upload_target(
        course_id, payload, title, str(file_type), norm
    )
    if reject:
        return reject

    material_id = str(target_doc.get("material_id") or raw_material_id)
    stable_key = target_doc.get("stable_material_key") or _compute_stable_material_key(
        course_id,
        {
            "title": title,
            "file_type": file_type,
            "activity_url": source_url,
            "resolved_url": resolved_url_payload,
            "raw_material_id": raw_material_id,
            "material_id": material_id,
        },
    )
    identity_before = _identity_result(target_doc, "preflight_db_id", stable_key)

    norm = _normalize_incoming_material_item(
        {
            "title": title,
            "file_type": file_type,
            "url": source_url,
            "source_url": source_url,
            "resolved_url": resolved_url_payload,
            "material_id": material_id,
            "id": material_id,
            "raw_material_id": raw_material_id,
        }
    )
    if not course_id or not material_id:
        return _package_upload_response(
            course_id,
            target_db_id,
            False,
            payload,
            {
                "status": "rejected",
                "reason": "course_id_and_material_id_required",
                "extraction_error": "course_id_and_material_id_required",
            },
        )

    course_name = payload.get("course_name")
    material_type = payload.get("material_type") or payload.get("type")
    content_type = payload.get("content_type") or ""

    user_email = (payload.get("user_email") or payload.get("email") or "").strip().lower()
    academiq_user_id = payload.get("academiq_user_id")
    if user_email and not academiq_user_id:
        user = user_repository.find_by_email(user_email)
        if user:
            academiq_user_id = str(user["_id"])

    force = _is_force_reprocess(payload)
    now = datetime.utcnow()

    # Extension could not download bytes — record terminal failure on exact db_id row.
    if payload.get("upload_attempt_failed"):
        raw_error = str(payload.get("extraction_error") or "download_failed_unknown")
        stored_error = _normalize_upload_failure_reason(raw_error, payload)
        existing_doc = material_repository.get_by_object_id(target_db_id) or target_doc
        existing_status = str((existing_doc or {}).get("extraction_status") or "not_uploaded")
        if existing_doc and not force:
            if existing_status == "extraction_failed" and existing_doc.get("last_attempted_at"):
                return _package_upload_response(
                    course_id,
                    target_db_id,
                    True,
                    payload,
                    {
                        "status": "skipped_existing",
                        "already_ready": False,
                        "course_id": course_id,
                        "material_id": material_id,
                        "resolved_from_material_id": (
                            raw_material_id if raw_material_id != material_id else None
                        ),
                        "title": existing_doc.get("title", title),
                        "chars": _content_chars_from_doc(existing_doc),
                        "ready_for_quiz": False,
                        "hasContent": False,
                        "extraction_status": existing_status,
                        "extraction_error": existing_doc.get("extraction_error"),
                        "quiz_status": "extraction_failed",
                        "content_note": "Previously recorded extraction failure",
                        "inserted": False,
                    },
                )
            if existing_status in _TERMINAL_EXTRACTION_STATUSES and existing_status != "not_uploaded":
                if _content_chars_from_doc(existing_doc) > 0 or existing_status != "extraction_failed":
                    return _package_upload_response(
                        course_id,
                        target_db_id,
                        True,
                        payload,
                        {
                            "status": "skipped_existing",
                            "already_ready": bool(existing_doc.get("ready_for_quiz")),
                            "course_id": course_id,
                            "material_id": material_id,
                            "resolved_from_material_id": (
                                raw_material_id if raw_material_id != material_id else None
                            ),
                            "title": existing_doc.get("title", title),
                            "chars": _content_chars_from_doc(existing_doc),
                            "ready_for_quiz": bool(existing_doc.get("ready_for_quiz")),
                            "hasContent": _content_chars_from_doc(existing_doc) >= MIN_QUIZ_CONTENT_CHARS,
                            "extraction_status": existing_status,
                            "extraction_error": existing_doc.get("extraction_error"),
                            "content_note": "Previously processed — download not retried",
                            "inserted": False,
                        },
                    )

        _persist_terminal_upload_failure(
            course_id,
            target_db_id,
            stored_error,
            source_url=str(source_url or "") or None,
            resolved_url=resolved_url_payload,
        )
        fail_audit = _build_upload_identity_audit(
            norm,
            identity_before,
            identity_before,
            payload,
            0,
            "extraction_failed",
        )
        upload_audit_payload = payload.get("upload_audit") or {}
        if isinstance(upload_audit_payload, dict):
            fail_audit.update(
                {k: v for k, v in upload_audit_payload.items() if v is not None}
            )
        fail_audit.update(
            {
                "backend_upload_called": True,
                "backend_response_status": "stored_failed",
                "failure_reason": stored_error,
                "final_content_text_length": 0,
                "final_quiz_status": "extraction_failed",
            }
        )
        if existing_doc:
            material_repository.update_by_object_id(
                target_db_id,
                {
                    "last_upload_audit": fail_audit,
                    "last_upload_audit_at": now,
                },
            )
        return _package_upload_response(
            course_id,
            target_db_id,
            True,
            payload,
            {
                "status": "stored_failed",
                "already_ready": False,
                "course_id": course_id,
                "material_id": material_id,
                "resolved_from_material_id": (
                    raw_material_id if raw_material_id != material_id else None
                ),
                "title": title,
                "chars": 0,
                "ready_for_quiz": False,
                "hasContent": False,
                "extraction_status": "extraction_failed",
                "extraction_error": stored_error,
                "quiz_status": "extraction_failed",
                "content_note": f"Download failed: {stored_error}",
                "inserted": True,
                "identity_audit": fail_audit,
            },
        )

    # ── Step 1: classify by title/type before any extraction work ────────────
    is_non_quiz, non_quiz_reason = classify_non_quiz_material(title, str(file_type))
    if is_educational_material(title, str(file_type)):
        is_non_quiz = False
        non_quiz_reason = None
    if is_non_quiz:
        existing_doc = material_repository.get(course_id, material_id)
        if existing_doc and existing_doc.get("extraction_status") == "not_quiz_material":
            return _package_upload_response(
                course_id,
                target_db_id,
                False,
                payload,
                {
                    "status": "already_classified",
                    "already_ready": False,
                    "course_id": course_id,
                    "material_id": material_id,
                    "resolved_from_material_id": (
                        raw_material_id if raw_material_id != material_id else None
                    ),
                    "title": existing_doc.get("title", title),
                    "chars": 0,
                    "ready_for_quiz": False,
                    "hasContent": False,
                    "extraction_status": "not_quiz_material",
                    "extraction_error": non_quiz_reason,
                    "quiz_status": "not_quiz_material",
                    "content_note": f"Not quiz material: {non_quiz_reason}",
                    "inserted": False,
                },
            )
        # Store minimal record so the material is visible in the UI
        minimal_doc = {
            "course_id": course_id,
            "material_id": material_id,
            "title": title,
            "file_type": file_type,
            "source": "moodle_sync",
            "ready_for_quiz": False,
            "extraction_status": "not_quiz_material",
            "extraction_error": non_quiz_reason,
            "processed_at": now,
            "extractor_version": CURRENT_EXTRACTOR_VERSION,
        }
        if course_name:
            minimal_doc["course_name"] = course_name
        if source_url:
            minimal_doc["url"] = source_url
        material_repository.upsert(minimal_doc)
        return _package_upload_response(
            course_id,
            target_db_id,
            False,
            payload,
            {
                "status": "classified",
                "already_ready": False,
                "course_id": course_id,
                "material_id": material_id,
                "resolved_from_material_id": (
                    raw_material_id if raw_material_id != material_id else None
                ),
                "title": title,
                "chars": 0,
                "ready_for_quiz": False,
                "hasContent": False,
                "extraction_status": "not_quiz_material",
                "extraction_error": non_quiz_reason,
                "quiz_status": "not_quiz_material",
                "content_note": f"Not quiz material: {non_quiz_reason}",
                "inserted": True,
            },
        )

    # ── Step 2: caching — skip re-extraction if already processed ───────────
    existing_doc = material_repository.get_by_object_id(target_db_id) or target_doc
    if existing_doc and not force and is_extraction_cache_hit(existing_doc, force):
        existing_chars = content_text_length(existing_doc)
        probe_fields = _derive_readiness_from_probe(
            existing_doc.get("content_text") or "", str(file_type),
        )
        already_ready = bool(existing_doc.get("ready_for_quiz")) or probe_fields["ready_for_quiz"]
        display = resolve_material_display(existing_doc)
        quiz_status_out = str(
            display.get("quiz_status")
            or existing_doc.get("quiz_status")
            or probe_fields.get("quiz_probe_status")
            or "not_uploaded"
        )
        return _package_upload_response(
            course_id,
            target_db_id,
            False,
            payload,
            {
                "status": "skipped_existing",
                "already_ready": already_ready,
                "course_id": course_id,
                "material_id": material_id,
                "resolved_from_material_id": (
                    raw_material_id if raw_material_id != material_id else None
                ),
                "title": existing_doc.get("title", title),
                "chars": existing_chars,
                "ready_for_quiz": already_ready,
                "hasContent": already_ready,
                "extraction_status": existing_doc.get("extraction_status")
                or probe_fields["extraction_status"],
                "extraction_error": existing_doc.get("extraction_error"),
                "probe_question_count": existing_doc.get("probe_question_count")
                or probe_fields.get("probe_question_count"),
                "quiz_status": quiz_status_out,
                "content_note": "Skipped — already processed (cache hit)",
                "inserted": False,
            },
        )

    if existing_doc and not force:
        existing_status = str(existing_doc.get("extraction_status") or "")
        existing_chars = content_text_length(existing_doc)

        if existing_status in _TERMINAL_EXTRACTION_STATUSES:
            return _package_upload_response(
                course_id,
                target_db_id,
                False,
                payload,
                {
                    "status": "already_classified",
                    "already_ready": False,
                    "course_id": course_id,
                    "material_id": material_id,
                    "resolved_from_material_id": (
                        raw_material_id if raw_material_id != material_id else None
                    ),
                    "title": existing_doc.get("title", title),
                    "chars": existing_chars,
                    "ready_for_quiz": False,
                    "hasContent": False,
                    "extraction_status": existing_status,
                    "extraction_error": existing_doc.get("extraction_error"),
                    "quiz_status": existing_status,
                    "content_note": f"Previously processed: {existing_status}",
                    "inserted": False,
                },
            )

        if existing_doc.get("processed_at") or existing_chars > 0:
            probe_fields = _derive_readiness_from_probe(
                existing_doc.get("content_text") or "", str(file_type),
            )
            if probe_fields["content_chars"] > 0:
                material_repository.upsert(
                    {
                        "course_id": course_id,
                        "material_id": material_id,
                        "ready_for_quiz": probe_fields["ready_for_quiz"],
                        "extraction_status": probe_fields["extraction_status"],
                        "extraction_error": probe_fields["extraction_error"],
                        "content_chars": probe_fields["content_chars"],
                        "metadata_only": False,
                    }
                )
            already_ready = probe_fields["ready_for_quiz"]
            return _package_upload_response(
                course_id,
                target_db_id,
                False,
                payload,
                {
                    "status": "skipped_existing",
                    "already_ready": already_ready,
                    "course_id": course_id,
                    "material_id": material_id,
                    "resolved_from_material_id": (
                        raw_material_id if raw_material_id != material_id else None
                    ),
                    "title": existing_doc.get("title", title),
                    "chars": existing_chars,
                    "ready_for_quiz": already_ready,
                    "hasContent": already_ready,
                    "extraction_status": probe_fields["extraction_status"],
                    "extraction_error": probe_fields["extraction_error"],
                    "probe_question_count": probe_fields.get("probe_question_count"),
                    "quiz_status": probe_fields.get("quiz_probe_status"),
                    "content_note": "Previously processed — not re-extracted",
                    "inserted": False,
                },
            )

    # ── Extract text ─────────────────────────────────────────────────────────
    text = (payload.get("content_text") or "").strip()
    extraction_error: Optional[str] = None

    if not text:
        data, decode_error = _decode_payload_bytes(payload)
        if decode_error:
            extraction_error = decode_error
        elif data:
            text, extraction_error = extract_text_from_bytes(
                data,
                file_type=str(file_type),
                filename=title,
                content_type=str(content_type),
            )
        else:
            extraction_error = "no_file_or_text_provided"

    text = (text or "").strip()
    chars = len(text)
    probe_fields: Dict[str, Any] = {}

    if extraction_error and not text:
        extraction_status = "extraction_failed"
        ready_for_quiz = False
        probe_count = 0
    elif not text:
        extraction_status = "no_content"
        ready_for_quiz = False
        probe_count = 0
    else:
        probe_fields = _derive_readiness_from_probe(text, str(file_type))
        extraction_status = probe_fields["extraction_status"]
        extraction_error = probe_fields["extraction_error"]
        ready_for_quiz = probe_fields["ready_for_quiz"]
        probe_count = probe_fields.get("probe_question_count", 0)

    extracted_payload = (
        build_extracted_content_fields(
            text,
            probe_fields if chars > 0 else {
                "extraction_status": extraction_status,
                "extraction_error": extraction_error,
                "ready_for_quiz": ready_for_quiz,
                "quiz_probe_status": extraction_status if extraction_status == "extraction_failed" else "not_uploaded",
            },
            source_url=str(source_url or "") or None,
            resolved_url=resolved_url_payload,
        )
        if chars > 0
        else {
            "content_text": "",
            "content_text_length": 0,
            "content_chars": 0,
            "content_hash": None,
            "ready_for_quiz": False,
            "quiz_generation_eligible": False,
            "quiz_status": (
                "extraction_failed"
                if extraction_status == "extraction_failed"
                else extraction_status
            ),
            "extraction_status": extraction_status,
            "extraction_error": extraction_error,
            "failure_reason": extraction_error,
            "processed_at": now,
            "last_attempted_at": now,
            "metadata_only": False,
        }
    )

    material_doc = build_material_doc(
        {
            "id": material_id,
            "material_id": material_id,
            "title": title,
            "material_type": material_type,
            "type": material_type,
            "file_type": file_type,
            "fileType": file_type,
            "url": source_url,
            "source": "moodle_sync",
        },
        course_id,
        course_name,
    ) or {
        "course_id": course_id,
        "material_id": material_id,
        "title": title,
    }

    material_doc.update(
        {
            "source": "moodle_sync",
            "uploaded_by_email": user_email or None,
            "uploaded_by_user_id": academiq_user_id,
            "extractor_version": CURRENT_EXTRACTOR_VERSION,
            **extracted_payload,
        }
    )
    material_doc.update(enrich_kind_fields(title, str(file_type)))
    if source_url:
        material_doc["url"] = source_url
    if resolved_url_payload:
        material_doc["resolved_url"] = resolved_url_payload
    stable_key = identity_before.get("stable_material_key") or _compute_stable_material_key(
        course_id, norm
    )
    material_doc["stable_material_key"] = stable_key
    if source_url:
        material_doc["normalized_source_url"] = _normalize_source_url(str(source_url))
    if resolved_url_payload:
        material_doc["normalized_resolved_url"] = _normalize_source_url(resolved_url_payload)

    inserted = material_repository.upsert(material_doc)

    if extraction_status == "extraction_failed":
        normalized_fail = _normalize_upload_failure_reason(
            str(extraction_error or ""), payload
        )
        extracted_payload["extraction_error"] = normalized_fail
        extracted_payload["failure_reason"] = normalized_fail

    material_repository.update_by_object_id(
        target_db_id,
        {
            **extracted_payload,
            "extractor_version": CURRENT_EXTRACTOR_VERSION,
        },
    )

    if chars > 0:
        sync_fields = {
            **extracted_payload,
            "extractor_version": CURRENT_EXTRACTOR_VERSION,
        }
        synced_id = _sync_extracted_content_to_canonical_row(
            course_id, material_id, norm, sync_fields
        )
        if synced_id != material_id:
            material_id = synced_id
            title = (material_repository.get(course_id, material_id) or {}).get("title", title)

    identity_after = resolve_material_identity(
        course_id, norm, matched_material_id=material_id
    )
    quiz_status_out = (
        probe_fields.get("quiz_probe_status") if chars > 0 else extraction_status
    )
    identity_audit = _build_upload_identity_audit(
        norm,
        identity_before,
        identity_after,
        payload,
        chars,
        quiz_status_out,
    )
    upload_audit_payload = payload.get("upload_audit") or {}
    if isinstance(upload_audit_payload, dict):
        identity_audit.update(
            {k: v for k, v in upload_audit_payload.items() if v is not None}
        )
    identity_audit["backend_upload_called"] = True
    identity_audit["backend_response_status"] = "stored"
    identity_audit["final_content_text_length"] = chars
    identity_audit["final_quiz_status"] = quiz_status_out
    material_doc["last_upload_audit"] = identity_audit
    material_doc["last_upload_audit_at"] = now

    merge_duplicate_content_in_course(course_id)

    content_note = None
    if not ready_for_quiz:
        if extraction_status == "extraction_failed":
            content_note = (
                "No readable text extracted — file may be scanned/image-only, "
                f"encrypted, or in an unsupported format. Reason: {extraction_error}"
            )
        elif extraction_status == "insufficient_text":
            content_note = (
                f"Only {chars} characters extracted (need at least {MIN_QUIZ_CONTENT_CHARS}). "
                "Try uploading a text-based PDF or PPTX."
            )
        else:
            content_note = "No readable text could be extracted from this file."

    return _package_upload_response(
        course_id,
        target_db_id,
        True,
        payload,
        {
            "status": "stored",
            "course_id": course_id,
            "material_id": material_id,
            "resolved_from_material_id": raw_material_id if raw_material_id != material_id else None,
            "title": title,
            "chars": chars,
            "ready_for_quiz": ready_for_quiz,
            "hasContent": ready_for_quiz,
            "extraction_status": extraction_status,
            "extraction_error": extraction_error,
            "probe_question_count": probe_count,
            "quiz_status": probe_fields.get("quiz_probe_status") if chars > 0 else extraction_status,
            "download_attempted": True,
            "download_status": "extracted" if chars > 0 else extraction_status,
            "content_note": content_note,
            "inserted": inserted,
            "identity_audit": identity_audit,
        },
    )

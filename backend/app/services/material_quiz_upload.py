"""
Handle Moodle material uploads from the Chrome extension for quiz generation.
"""

from __future__ import annotations

import base64
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.material import build_material_doc, stable_material_id
from app.repositories import material_repository, user_repository
from app.services.material_text_extract import extract_text_from_bytes
from app.services.material_quiz_display import (
    classify_non_quiz_material,
    is_educational_material,
)
from app.services.student_data import (
    MIN_QUIZ_CONTENT_CHARS,
    MIN_EDUCATIONAL_REPROCESS_CHARS,
)

_DOWNLOADABLE_FILE_TYPES = {"pdf", "pptx", "ppt", "docx", "doc", "txt", "text"}

# Bump when extraction logic changes materially — preflight may re-offer upload once.
CURRENT_EXTRACTOR_VERSION = "2"

_READY_EXTRACTION_STATUSES = frozenset(
    {"success", "ready", "ready_for_quiz", "extracted"}
)

# After upload, these statuses are terminal — normal preflight must not re-download.
_TERMINAL_EXTRACTION_STATUSES = frozenset(
    {
        "not_quiz_material",
        "too_short",
        "insufficient_text",
        "insufficient_quiz_structure",
        "unsupported",
        "extraction_failed",
        "failed",
        "no_text",
        "no_content",
        "not_educational",
        "not_enough_readable_text",
        "admin_file",
        "folder",
        "assignment",
        "grades",
        "project_requirements",
    }
)


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

    Hard rule: any matched DB record skips upload unless force_reprocess is set.
  Only unmatched materials may upload (first-time downloadable files).
    """
    downloadable = _is_downloadable_material(raw_file_type, activity_url, resolved_url)

    if not existing_doc:
        if not downloadable:
            return (
                False,
                "metadata_only",
                "Metadata-only Moodle resource — no downloadable file",
                0,
                False,
            )
        return (
            True,
            "not_uploaded",
            "No DB record found — file download needed",
            0,
            True,
        )

    existing_chars = _content_chars_from_doc(existing_doc)

    if force and downloadable:
        return (
            True,
            "force_reprocess",
            "Force reprocess requested",
            existing_chars,
            True,
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

    inserted = 0
    updated = 0
    skipped = 0
    results: List[Dict[str, Any]] = []

    for item in materials_in:
        norm = _normalize_incoming_material_item(item)
        material_id = norm["material_id"]
        title = norm["title"]
        raw_file_type = norm["file_type"]
        activity_url = norm["activity_url"]
        resolved_url = norm["resolved_url"]

        if not material_id:
            skipped += 1
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

        is_non_quiz, non_quiz_reason = classify_non_quiz_material(title, raw_file_type)
        existing = material_repository.get(course_id, material_id)
        downloadable = _is_downloadable_material(raw_file_type, activity_url, resolved_url)

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
            }
        )

        if existing:
            safe_doc: Dict[str, Any] = {
                "course_id": course_id,
                "material_id": material_id,
                "title": title,
                "file_type": raw_file_type,
                "source": "moodle_sync",
            }
            if course_name:
                safe_doc["course_name"] = course_name
            if activity_url:
                safe_doc["url"] = activity_url
            if resolved_url:
                safe_doc["resolved_url"] = resolved_url
            mat_type = item.get("material_type") or item.get("type")
            if mat_type:
                safe_doc["material_type"] = mat_type
            for key, value in base_doc.items():
                if key in _PROTECTED_ON_EXISTING:
                    continue
                if key in ("course_id", "material_id") or value is None:
                    continue
                safe_doc[key] = value
            is_new = material_repository.upsert(safe_doc)
        else:
            existing_processed = False
            if is_non_quiz:
                base_doc["extraction_status"] = "not_quiz_material"
                base_doc["extraction_error"] = non_quiz_reason
                base_doc["ready_for_quiz"] = False
            else:
                base_doc["extraction_status"] = "not_uploaded"
                if downloadable:
                    base_doc["extraction_error"] = "File detected but not downloaded yet"
                else:
                    base_doc["extraction_error"] = (
                        "Content not extracted yet — Moodle link or page resource"
                    )
                base_doc["ready_for_quiz"] = False
                base_doc["content_chars"] = 0
            is_new = material_repository.upsert(base_doc)

        if is_new:
            inserted += 1
        else:
            updated += 1

        if existing:
            status = str(existing.get("extraction_status") or "already_saved")
            reason = existing.get("extraction_error")
        elif is_non_quiz:
            status = "not_quiz_material"
            reason = non_quiz_reason
        else:
            status = "not_uploaded"
            reason = base_doc.get("extraction_error")
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
            }
        )

    metadata_saved_total = inserted + updated
    return {
        "course_id": course_id,
        "detected_total": len(materials_in),
        "metadata_saved_total": metadata_saved_total,
        "metadata_inserted": inserted,
        "metadata_updated": updated,
        "metadata_skipped": skipped,
        "saved_total": metadata_saved_total,
        "materials": results,
    }


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
                "debug": {
                    "material_id_sent": raw_material_id,
                    "material_id_used": material_id,
                    "course_id": course_id,
                    "db_record_found": False,
                },
            })
            continue

        # ── B: Phase 1 — in-memory lookup (fast, uses bulk-load data) ─────────
        existing_doc = None
        matched_by = None

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

        results.append({
            "material_id": material_id,
            "title": title,
            "should_upload": should_reupload,
            "status": out_status,
            "reason": reason,
            "content_text_length": existing_chars,
            "matched_by": matched_by,
            "downloadable": downloadable,
            "debug": debug_info,
        })

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

    return {
        "course_id": course_id,
        "checked": len(results),
        "preflight_checked_total": len(results),
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


def _resolve_material_id(
    course_id: str, material_id: str, source_url: Optional[str]
) -> str:
    """Align upload key with Moodle sync rows (cmid from URL, then URL lookup)."""
    url_id = _material_id_from_url(source_url)
    if url_id:
        material_id = url_id
    if source_url:
        existing = material_repository.find_by_course_and_url(course_id, source_url)
        if existing and existing.get("material_id"):
            material_id = str(existing["material_id"])
    return str(material_id).strip()


def _decode_payload_bytes(payload: Dict[str, Any]) -> tuple[bytes, Optional[str]]:
    b64 = payload.get("content_base64")
    if b64:
        try:
            return base64.b64decode(b64), None
        except Exception as exc:
            return b"", f"invalid_base64:{exc}"
    return b"", None


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
    material_id = _resolve_material_id(course_id, raw_material_id, source_url)
    if not course_id or not material_id:
        raise ValueError("course_id and material_id are required")

    title = (payload.get("title") or "Untitled Material").strip()
    course_name = payload.get("course_name")
    material_type = payload.get("material_type") or payload.get("type")
    file_type = payload.get("file_type") or payload.get("fileType") or "unknown"
    content_type = payload.get("content_type") or ""

    user_email = (payload.get("user_email") or payload.get("email") or "").strip().lower()
    academiq_user_id = payload.get("academiq_user_id")
    if user_email and not academiq_user_id:
        user = user_repository.find_by_email(user_email)
        if user:
            academiq_user_id = str(user["_id"])

    force = _is_force_reprocess(payload)
    now = datetime.utcnow()

    # Extension could not download bytes — record terminal failure so preflight skips retry.
    if payload.get("upload_attempt_failed"):
        extraction_error = str(payload.get("extraction_error") or "download_failed")
        existing_doc = material_repository.get(course_id, material_id)
        if existing_doc and not force:
            if existing_doc.get("processed_at") or (
                existing_doc.get("extraction_status") in _TERMINAL_EXTRACTION_STATUSES
            ):
                return {
                    "status": "skipped_existing",
                    "already_ready": False,
                    "course_id": course_id,
                    "material_id": material_id,
                    "resolved_from_material_id": (
                        raw_material_id if raw_material_id != material_id else None
                    ),
                    "title": existing_doc.get("title", title),
                    "chars": _content_chars_from_doc(existing_doc),
                    "ready_for_quiz": bool(existing_doc.get("ready_for_quiz")),
                    "hasContent": _content_chars_from_doc(existing_doc) >= MIN_QUIZ_CONTENT_CHARS,
                    "extraction_status": existing_doc.get("extraction_status"),
                    "extraction_error": existing_doc.get("extraction_error"),
                    "content_note": "Previously processed — download not retried",
                    "inserted": False,
                    "ok": True,
                }
        fail_doc: Dict[str, Any] = {
            "course_id": course_id,
            "material_id": material_id,
            "title": title,
            "file_type": file_type,
            "source": "moodle_sync",
            "ready_for_quiz": False,
            "extraction_status": "extraction_failed",
            "extraction_error": f"download_failed:{extraction_error}",
            "processed_at": now,
            "extractor_version": CURRENT_EXTRACTOR_VERSION,
        }
        if course_name:
            fail_doc["course_name"] = course_name
        if source_url:
            fail_doc["url"] = source_url
        inserted = material_repository.upsert(fail_doc)
        return {
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
            "extraction_error": fail_doc["extraction_error"],
            "content_note": f"Download failed: {extraction_error}",
            "inserted": inserted,
            "ok": True,
        }

    # ── Step 1: classify by title/type before any extraction work ────────────
    # Non-quiz materials (grades, folders, admin, forums, etc.) are stored with
    # minimal metadata but NO text extraction — fast and idempotent on re-upload.
    is_non_quiz, non_quiz_reason = classify_non_quiz_material(title, str(file_type))
    if is_non_quiz:
        existing_doc = material_repository.get(course_id, material_id)
        if existing_doc and existing_doc.get("extraction_status") == "not_quiz_material":
            # Already classified — return immediately without touching the DB
            return {
                "status": "already_classified",
                "already_ready": False,
                "course_id": course_id,
                "material_id": material_id,
                "resolved_from_material_id": raw_material_id if raw_material_id != material_id else None,
                "title": existing_doc.get("title", title),
                "chars": 0,
                "ready_for_quiz": False,
                "hasContent": False,
                "extraction_status": "not_quiz_material",
                "extraction_error": non_quiz_reason,
                "content_note": f"Not quiz material: {non_quiz_reason}",
                "inserted": False,
            }
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
        return {
            "status": "classified",
            "already_ready": False,
            "course_id": course_id,
            "material_id": material_id,
            "resolved_from_material_id": raw_material_id if raw_material_id != material_id else None,
            "title": title,
            "chars": 0,
            "ready_for_quiz": False,
            "hasContent": False,
            "extraction_status": "not_quiz_material",
            "extraction_error": non_quiz_reason,
            "content_note": f"Not quiz material: {non_quiz_reason}",
            "inserted": True,
        }

    # ── Step 2: caching — skip re-extraction if already processed ───────────
    existing_doc = material_repository.get(course_id, material_id)
    if existing_doc and not force:
        existing_status = str(existing_doc.get("extraction_status") or "")
        existing_chars = _content_chars_from_doc(existing_doc)

        if existing_status in _TERMINAL_EXTRACTION_STATUSES:
            return {
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
                "content_note": f"Previously processed: {existing_status}",
                "inserted": False,
                "ok": True,
            }

        if existing_doc.get("processed_at") or existing_chars > 0:
            already_ready = existing_chars >= MIN_QUIZ_CONTENT_CHARS
            return {
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
                "extraction_status": existing_doc.get("extraction_status", "success"),
                "extraction_error": existing_doc.get("extraction_error"),
                "content_note": "Previously processed — not re-extracted",
                "inserted": False,
                "ok": True,
            }

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

    # ── Determine readiness (simplified — no probe, just text length check) ──
    #
    # The quiz generator uses a four-engine pipeline (light → lecture → heavy →
    # fragment) that handles any educational content type.  We no longer run a
    # per-material probe at upload time because:
    #   1. It was rejecting valid lab/PPTX/fragmented materials.
    #   2. The fragment fallback now covers any text with ≥4 readable sentences.
    # Only true failures (no bytes, corrupted file, unsupported format) are
    # marked not-ready.
    if extraction_error and not text:
        extraction_status = "extraction_failed"
        ready_for_quiz = False
    elif not text:
        extraction_status = "no_content"
        ready_for_quiz = False
    elif chars < MIN_QUIZ_CONTENT_CHARS:
        # Confirmed too-short after extraction — stored as "insufficient_text" so
        # subsequent preflights classify it as "already_classified" and stop re-uploading.
        extraction_status = "insufficient_text"
        extraction_error = extraction_error or (
            f"Extracted only {chars} characters; need at least {MIN_QUIZ_CONTENT_CHARS}."
        )
        ready_for_quiz = False
    else:
        extraction_status = "success"
        extraction_error = None
        ready_for_quiz = True

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
            "content_text": text,
            "content_chars": chars,
            "ready_for_quiz": ready_for_quiz,
            "extraction_status": extraction_status,
            "extraction_error": extraction_error,
            "uploaded_by_email": user_email or None,
            "uploaded_by_user_id": academiq_user_id,
            "processed_at": now,
            "extractor_version": CURRENT_EXTRACTOR_VERSION,
        }
    )

    inserted = material_repository.upsert(material_doc)

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

    return {
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
        "content_note": content_note,
        "inserted": inserted,
    }

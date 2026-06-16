"""
Handle Moodle material uploads from the Chrome extension for quiz generation.
"""

from __future__ import annotations

import base64
import re
from typing import Any, Dict, List, Optional

from app.models.material import build_material_doc, stable_material_id
from app.repositories import material_repository, user_repository
from app.services.material_text_extract import extract_text_from_bytes
from app.services.student_data import MIN_QUIZ_CONTENT_CHARS, _classify_non_quiz_material


def preflight_materials(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pre-upload check: return which materials need uploading without downloading files.

    The extension calls this BEFORE fetching any file bytes.  For every item in
    the request list we check:
      1. Is the title/type a known non-quiz material? → skip immediately.
      2. Does MongoDB already have enough extracted text? → skip (already ready).
      3. Did a previous extraction fail?  → skip (don't retry unless forced).
      4. Otherwise → should_upload: true.

    Returns per-material: should_upload, status, reason, content_text_length.
    """
    course_id = str(payload.get("course_id") or "").strip()
    materials_in = payload.get("materials") or []

    if not course_id:
        raise ValueError("course_id required")

    results: List[Dict[str, Any]] = []

    for item in materials_in:
        title = (item.get("title") or "Untitled").strip()
        raw_file_type = str(item.get("file_type") or item.get("fileType") or "unknown")
        # activity_url = Moodle activity URL (/mod/resource/view.php?id=cmid) — used for cmid extraction
        # resolved_url = actual file URL after redirect (pluginfile.php) — used as fallback
        activity_url = str(item.get("source_url") or item.get("url") or "").strip()
        resolved_url = str(item.get("resolved_url") or "").strip()
        raw_material_id = str(
            item.get("material_id") or item.get("id") or stable_material_id(item) or ""
        ).strip()

        # Prefer the activity URL for cmid extraction (has ?id=), fall back to resolved_url
        material_id = _resolve_material_id(
            course_id, raw_material_id, activity_url or resolved_url
        )

        # ── 1. Non-quiz classification ─────────────────────────────────────────
        is_non_quiz, non_quiz_reason = _classify_non_quiz_material(title, raw_file_type)
        if is_non_quiz:
            results.append({
                "material_id": material_id,
                "title": title,
                "should_upload": False,
                "status": "not_quiz_material",
                "reason": non_quiz_reason,
                "content_text_length": 0,
            })
            continue

        # ── 2. Check existing DB record (by ID, then by activity URL, then resolved URL) ──
        existing_doc = material_repository.get(course_id, material_id)
        if not existing_doc and activity_url:
            existing_doc = material_repository.find_by_course_and_url(course_id, activity_url)
        if not existing_doc and resolved_url:
            existing_doc = material_repository.find_by_course_and_url(course_id, resolved_url)

        if existing_doc:
            existing_status = existing_doc.get("extraction_status") or ""
            existing_text = (existing_doc.get("content_text") or "").strip()
            existing_chars = (
                len(existing_text)
                if existing_text
                else (existing_doc.get("content_chars") or 0)
            )

            if existing_status == "not_quiz_material":
                results.append({
                    "material_id": material_id,
                    "title": title,
                    "should_upload": False,
                    "status": "not_quiz_material",
                    "reason": existing_doc.get("extraction_error") or "Classified as non-quiz material",
                    "content_text_length": 0,
                })
            elif existing_chars >= MIN_QUIZ_CONTENT_CHARS:
                results.append({
                    "material_id": material_id,
                    "title": title,
                    "should_upload": False,
                    "status": "ready",
                    "reason": f"Already has {existing_chars} characters of extracted text",
                    "content_text_length": existing_chars,
                })
            elif existing_status == "extraction_failed":
                # Don't retry a failed extraction unless force_reupload is set
                force = bool(payload.get("force_reupload"))
                results.append({
                    "material_id": material_id,
                    "title": title,
                    "should_upload": force,
                    "status": "extraction_failed",
                    "reason": existing_doc.get("extraction_error") or "Extraction previously failed",
                    "content_text_length": existing_chars,
                })
            elif existing_chars > 0:
                # Some text extracted but below threshold
                results.append({
                    "material_id": material_id,
                    "title": title,
                    "should_upload": False,
                    "status": "too_short",
                    "reason": f"Only {existing_chars} chars extracted (need ≥{MIN_QUIZ_CONTENT_CHARS})",
                    "content_text_length": existing_chars,
                })
            else:
                # Record exists but no content — try uploading
                results.append({
                    "material_id": material_id,
                    "title": title,
                    "should_upload": True,
                    "status": "not_uploaded",
                    "reason": "Record exists but no extracted text yet",
                    "content_text_length": 0,
                })
        else:
            # No DB record at all — full upload needed
            results.append({
                "material_id": material_id,
                "title": title,
                "should_upload": True,
                "status": "not_uploaded",
                "reason": "Not yet uploaded",
                "content_text_length": 0,
            })

    should_upload_count = sum(1 for r in results if r["should_upload"])
    skip_count = len(results) - should_upload_count
    status_summary: Dict[str, int] = {}
    for r in results:
        status_summary[r["status"]] = status_summary.get(r["status"], 0) + 1

    return {
        "course_id": course_id,
        "total": len(results),
        "should_upload_count": should_upload_count,
        "skip_count": skip_count,
        "status_summary": status_summary,
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

    # ── Step 1: classify by title/type before any extraction work ────────────
    # Non-quiz materials (grades, folders, admin, forums, etc.) are stored with
    # minimal metadata but NO text extraction — fast and idempotent on re-upload.
    is_non_quiz, non_quiz_reason = _classify_non_quiz_material(title, str(file_type))
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

    # ── Step 2: caching — skip re-extraction if already processed ────────────
    existing_doc = material_repository.get(course_id, material_id)
    if existing_doc:
        existing_status = existing_doc.get("extraction_status") or ""
        existing_text = (existing_doc.get("content_text") or "").strip()
        existing_chars = len(existing_text)

        if existing_chars >= MIN_QUIZ_CONTENT_CHARS:
            # Already has enough content — skip re-extraction entirely
            already_ready = bool(existing_doc.get("ready_for_quiz", True))
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
                "extraction_error": None,
                "content_note": None,
                "inserted": False,
            }

        if existing_status == "extraction_failed":
            # Extraction was already attempted and failed — skip unless force_reupload
            force = bool(payload.get("force_reupload"))
            if not force:
                return {
                    "status": "skipped_existing",
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
                    "extraction_status": "extraction_failed",
                    "extraction_error": existing_doc.get("extraction_error"),
                    "content_note": (
                        "Extraction previously failed. "
                        "Re-upload with force_reupload=true to retry."
                    ),
                    "inserted": False,
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
        extraction_status = "insufficient_text"
        extraction_error = extraction_error or (
            f"Extracted only {chars} characters; need at least {MIN_QUIZ_CONTENT_CHARS}."
        )
        ready_for_quiz = False
    else:
        # Any material with enough extracted text is selectable for quiz generation.
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

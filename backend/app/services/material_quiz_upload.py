"""
Handle Moodle material uploads from the Chrome extension for quiz generation.
"""

from __future__ import annotations

import base64
import re
from typing import Any, Dict, Optional

from app.models.material import build_material_doc, stable_material_id
from app.repositories import material_repository, user_repository
from app.services.material_text_extract import extract_text_from_bytes
from app.services.student_data import MIN_QUIZ_CONTENT_CHARS


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

    # ── Caching: skip re-extraction if text already saved ────────────────────
    existing_doc = material_repository.get(course_id, material_id)
    if existing_doc:
        existing_text = (existing_doc.get("content_text") or "").strip()
        existing_chars = len(existing_text)
        if existing_chars >= MIN_QUIZ_CONTENT_CHARS:
            # Material already processed — skip re-extraction, return cached result
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

"""
Handle Moodle material uploads from the Chrome extension for quiz generation.
"""

from __future__ import annotations

import base64
from typing import Any, Dict, Optional

from app.models.material import build_material_doc, stable_material_id
from app.repositories import material_repository, user_repository
from app.services.material_text_extract import extract_text_from_bytes
from app.services.student_data import MIN_QUIZ_CONTENT_CHARS


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
    """
    course_id = str(payload.get("course_id") or "").strip()
    material_id = str(
        payload.get("material_id") or payload.get("id") or stable_material_id(payload) or ""
    ).strip()
    if not course_id or not material_id:
        raise ValueError("course_id and material_id are required")

    title = (payload.get("title") or "Untitled Material").strip()
    course_name = payload.get("course_name")
    material_type = payload.get("material_type") or payload.get("type")
    file_type = payload.get("file_type") or payload.get("fileType") or "unknown"
    source_url = payload.get("source_url") or payload.get("url")
    content_type = payload.get("content_type") or ""

    user_email = (payload.get("user_email") or payload.get("email") or "").strip().lower()
    academiq_user_id = payload.get("academiq_user_id")
    if user_email and not academiq_user_id:
        user = user_repository.find_by_email(user_email)
        if user:
            academiq_user_id = str(user["_id"])

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
    ready_for_quiz = chars >= MIN_QUIZ_CONTENT_CHARS

    if extraction_error and not text:
        extraction_status = "extraction_failed"
    elif not text:
        extraction_status = "no_content"
    elif not ready_for_quiz:
        extraction_status = "insufficient_text"
        extraction_error = extraction_error or (
            f"Extracted only {chars} characters; need at least {MIN_QUIZ_CONTENT_CHARS}."
        )
    else:
        extraction_status = "success"
        extraction_error = None

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
                "Content not available — file text could not be extracted. "
                f"Reason: {extraction_error}"
            )
        elif extraction_status == "insufficient_text":
            content_note = (
                "Material uploaded but has limited text for quiz generation. "
                f"({chars} chars; need {MIN_QUIZ_CONTENT_CHARS}+)."
            )
        else:
            content_note = "Content not available yet."

    return {
        "status": "stored",
        "course_id": course_id,
        "material_id": material_id,
        "title": title,
        "chars": chars,
        "ready_for_quiz": ready_for_quiz,
        "hasContent": ready_for_quiz,
        "extraction_status": extraction_status,
        "extraction_error": extraction_error,
        "content_note": content_note,
        "inserted": inserted,
    }

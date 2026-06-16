"""
Determine whether stored material text can produce a quiz.

Readiness for the UI must match what POST /courses/{id}/quiz can actually generate.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional, Tuple

from app.services.student_data import MIN_QUIZ_CONTENT_CHARS

logger = logging.getLogger(__name__)

_MIN_PROBE_QUESTIONS = 3

_REASON_MESSAGES = {
    "missing_content_text": (
        "Material is listed from Moodle but quiz content is not extracted yet. "
        "Use the Chrome extension → Upload materials for quiz."
    ),
    "content_too_short": (
        "Material has limited extracted text. Upload the PDF via the Chrome "
        "extension to enable quiz generation."
    ),
    "insufficient_quiz_structure": (
        "Text was extracted but does not contain enough teachable definitions "
        "for quiz generation. Try a lecture PDF or slides with clear concepts."
    ),
    "unsupported_material_format": (
        "This file type or layout is not supported for automatic quiz generation."
    ),
}


def normalize_quiz_text(text: str) -> str:
    """Clean PDF/slide extraction noise before quiz parsing."""
    cleaned = text or ""
    cleaned = cleaned.replace("\x00", " ")
    cleaned = re.sub(r"[\uf000-\uf8ff]", " ", cleaned)
    cleaned = re.sub(r"[\u25a0-\u25ff\u2022\u2023\u2043]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def reason_message(code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    return _REASON_MESSAGES.get(code, f"Quiz generation unavailable ({code}).")


def probe_question_count(text: str, num_questions: int = 8) -> Tuple[int, str]:
    """
    Try lightweight then heavy generators. Returns (count, engine_used).
    Does not raise — used for eligibility probes and debug endpoints.
    """
    normalized = normalize_quiz_text(text)
    if not normalized:
        return 0, "none"

    try:
        from app.services.quiz_gen_light import generate_lightweight

        light = generate_lightweight(normalized, num_questions=num_questions)
        if len(light) >= _MIN_PROBE_QUESTIONS:
            return len(light), "light"
    except Exception as exc:
        logger.warning("Lightweight quiz probe failed: %s", exc)

    try:
        from app.services import quiz_gen

        if quiz_gen.available():
            heavy = quiz_gen.generate_from_text(normalized, num_questions=num_questions)
            if len(heavy) >= _MIN_PROBE_QUESTIONS:
                return len(heavy), "heavy"
            if heavy:
                return len(heavy), "heavy_partial"
    except Exception as exc:
        logger.warning("Heavy quiz probe failed: %s", exc)

    return 0, "none"


def assess_quiz_eligibility(
    text: str,
    *,
    file_type: Optional[str] = None,
    probe: bool = True,
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Return (eligible, reason_code, meta).

    reason_code is one of:
      missing_content_text | content_too_short | insufficient_quiz_structure |
      unsupported_material_format | None when eligible
    """
    normalized = normalize_quiz_text(text)
    meta: Dict[str, Any] = {
        "content_text_length": len(normalized),
        "file_type": (file_type or "unknown").lower(),
    }

    if not normalized:
        return False, "missing_content_text", meta

    if len(normalized) < MIN_QUIZ_CONTENT_CHARS:
        return False, "content_too_short", meta

    unsupported_types = {"html", "link", "zip", "xlsx", "unknown"}
    ft = meta["file_type"]
    if ft in unsupported_types and len(normalized) < 500:
        return False, "unsupported_material_format", meta

    if probe:
        count, engine = probe_question_count(normalized)
        meta["probe_question_count"] = count
        meta["probe_engine"] = engine
        if count >= _MIN_PROBE_QUESTIONS:
            meta["quiz_generation_eligible"] = True
            return True, None, meta

    try:
        from app.services.quiz_gen_light import extract_definitions

        pairs = extract_definitions(normalized)
        meta["definition_pair_count"] = len(pairs)
        if len(pairs) >= _MIN_PROBE_QUESTIONS:
            meta["quiz_generation_eligible"] = True
            return True, None, meta
    except Exception as exc:
        logger.warning("Definition extraction failed during eligibility: %s", exc)
        meta["parsing_error"] = str(exc)
        return False, "parsing_error", meta

    return False, "insufficient_quiz_structure", meta


def assess_material_doc(doc: Optional[Dict[str, Any]], *, probe: bool = True) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """Assess a course_materials document."""
    if not doc:
        return False, "missing_content_text", {"material_exists": False}

    text = doc.get("content_text") or ""
    eligible, reason, meta = assess_quiz_eligibility(
        text,
        file_type=doc.get("file_type"),
        probe=probe,
    )
    meta["material_exists"] = True
    meta["material_id"] = str(doc.get("material_id") or "")
    meta["course_id"] = str(doc.get("course_id") or "")
    meta["title"] = doc.get("title")
    meta["source"] = doc.get("source") or doc.get("seed_source")
    meta["ready_for_quiz"] = bool(doc.get("ready_for_quiz"))
    meta["quiz_generation_eligible"] = eligible
    return eligible, reason, meta

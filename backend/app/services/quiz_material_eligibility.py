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

_MIN_LIMITED_QUESTIONS = 3
_MIN_READY_QUESTIONS = 5

_REASON_MESSAGES = {
    "missing_content_text": (
        "Material is listed from Moodle but quiz content is not extracted yet. "
        "Use the Chrome extension → Upload materials for quiz."
    ),
    "content_too_short": (
        "Material has very little extracted text (under 200 characters). "
        "Upload the full PDF via the Chrome extension to enable quiz generation."
    ),
    "content_mostly_noise": (
        "Extracted text appears to be mostly filenames, page numbers, or formatting "
        "noise with no meaningful content. Try uploading the lecture PDF directly."
    ),
    "no_meaningful_concepts": (
        "Text was extracted but no teachable concepts were found. "
        "This may be a grades sheet, schedule, or non-lecture document."
    ),
    "insufficient_quiz_structure": (
        "Text was extracted but does not contain enough structured concepts "
        "for quiz generation. Works best with lecture slides or lab handouts "
        "that describe concepts, steps, or definitions."
    ),
    "unsupported_material_format": (
        "This file type or layout is not supported for automatic quiz generation. "
        "Try uploading a PDF or PPTX lecture file instead."
    ),
}


def normalize_quiz_text(text: str) -> str:
    """Clean PDF/slide extraction noise before quiz parsing (collapses whitespace)."""
    cleaned = text or ""
    cleaned = cleaned.replace("\x00", " ")
    cleaned = re.sub(r"[\uf000-\uf8ff]", " ", cleaned)
    cleaned = re.sub(r"[\u25a0-\u25ff\u2022\u2023\u2043]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


# ── Patterns for deep structural cleaning ────────────────────────────────────
_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)
_MAILTO_LINK_RE = re.compile(
    r"\[.*?\]\(mailto:[^\)]+\)",   # Markdown mailto: [text](mailto:email)
    re.IGNORECASE,
)
_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_PAGE_NUM_LINE_RE = re.compile(
    r"^\s*(?:page\s+\d+(?:\s+of\s+\d+)?|\d+\s*/\s*\d+|slide\s+\d+)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_TOC_NOISE_LINE_RE = re.compile(
    r"^\s*(?:table\s+of\s+contents?|contents?|what\??|index|outline"
    r"|agenda|overview|introduction)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
# "Topic ........... 3"  — table of contents entries with dotted leaders
_TOC_ENTRY_RE = re.compile(r"^[^\n]+\.{3,}\s*\d+\s*$", re.MULTILINE)
# Lines that are only a person's name (possibly with role/email notation)
# e.g. "Prof. Amira Mohamed"  "Dr. Youssef Al-Said [ysaid@...]"
_NAME_ONLY_LINE_RE = re.compile(
    r"^\s*(?:Prof\.?\s+|Dr\.?\s+|Eng\.?\s+|Instructor:?\s+|Ass(?:t\.?\s+|ociate\s+)Prof\.?\s+)?"
    r"[A-Z][a-z]{1,20}(?:\s+[A-Z][a-z]{1,20}){1,4}"  # 2-5 capitalised name words
    r"(?:\s+[\[\(][^\]\)]{0,60}[\]\)])?"              # optional [email] or (role)
    r"\s*$",
    re.MULTILINE,
)
# Lines that look like "Course: SWE412" or "Section: A2" or "By: Name"
_HEADER_LABEL_LINE_RE = re.compile(
    r"^\s*(?:course|section|semester|by|prepared\s+by|submitted\s+by"
    r"|instructor|student|id|date|year|group)\s*:\s*.{0,80}\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def deep_clean_quiz_text(text: str) -> str:
    """
    Remove structural and semantic noise from extracted PDF/PPTX text while
    PRESERVING newlines so line-aware engines can still detect headings and lists.

    Removes:
      - Email addresses and mailto: links
      - URLs
      - Page / slide number lines
      - Table-of-contents lines and dotted-leader entries
      - Person-name-only lines (author, instructor headers)
      - Metadata label lines (Course:, By:, Date:, etc.)
      - Isolated noise tokens: "Contents", "What?", "Index"
    """
    if not text:
        return ""

    t = text

    # Inline substitutions (apply before line filtering)
    t = _MAILTO_LINK_RE.sub(" ", t)
    t = _EMAIL_RE.sub(" ", t)
    t = _URL_RE.sub(" ", t)
    t = _TOC_ENTRY_RE.sub("", t)     # remove dotted ToC entries first

    # Line-level filtering
    cleaned_lines: list[str] = []
    for line in t.splitlines():
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue

        # After email/URL removal a line may become very short or just noise —
        # skip lines whose ALPHABETIC content is < 25 chars (not a real sentence)
        alpha_content = re.sub(r"[^A-Za-z\s]", "", stripped).strip()
        if len(alpha_content) < 25:
            continue

        # Skip page/slide numbers
        if _PAGE_NUM_LINE_RE.match(stripped):
            continue
        # Skip pure ToC noise lines
        if _TOC_NOISE_LINE_RE.match(stripped):
            continue
        # Skip name-only lines (handle hyphenated surnames too)
        _stripped_for_name = re.sub(r"[\[\(][^\]\)]{0,60}[\]\)]", "", stripped).strip()
        if _NAME_ONLY_LINE_RE.match(_stripped_for_name) and len(_stripped_for_name.split()) <= 6:
            continue
        # Also catch lines that are 1-4 capitalised words only (names without salutation)
        name_words = _stripped_for_name.split()
        if (1 <= len(name_words) <= 5
                and all(re.match(r"[A-Z][a-z\-]{1,}", w) for w in name_words)):
            continue
        # Skip metadata header lines
        if _HEADER_LABEL_LINE_RE.match(stripped):
            continue
        # Skip lines that are purely a course code
        if re.match(r"^[A-Z]{2,6}\d{3,4}(?:[-/]\w+)?\s*$", stripped):
            continue
        # Skip lines that are "What?" or "Contents" after the above patterns
        if re.match(r"^(?:what\??|contents?\??|this\??)$", stripped, re.I):
            continue
        cleaned_lines.append(line)

    t = "\n".join(cleaned_lines)
    # Collapse 3+ consecutive blank lines to at most 2
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def reason_message(code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    return _REASON_MESSAGES.get(code, f"Quiz generation unavailable ({code}).")


def probe_question_count(text: str, num_questions: int = 8) -> Tuple[int, str]:
    """
    Try lightweight → lecture → heavy generators. Returns (count, engine_used).
    Always returns the best question count found (even 1–4), not only when ≥5.
    """
    normalized = normalize_quiz_text(text)
    if not normalized:
        return 0, "none"

    best_count = 0
    best_engine = "none"

    try:
        from app.services.quiz_gen_light import generate_lightweight

        light = generate_lightweight(normalized, num_questions=num_questions)
        if len(light) > best_count:
            best_count = len(light)
            best_engine = "light"
    except Exception as exc:
        logger.warning("Lightweight quiz probe failed: %s", exc)

    try:
        from app.services.quiz_gen_lecture import generate_lecture_quiz

        lecture = generate_lecture_quiz(normalized, num_questions=num_questions)
        if len(lecture) > best_count:
            best_count = len(lecture)
            best_engine = "lecture"
    except Exception as exc:
        logger.warning("Lecture quiz probe failed: %s", exc)

    try:
        from app.services import quiz_gen

        if quiz_gen.available():
            heavy = quiz_gen.generate_from_text(normalized, num_questions=num_questions)
            if len(heavy) > best_count:
                best_count = len(heavy)
                best_engine = "heavy" if len(heavy) >= _MIN_READY_QUESTIONS else "heavy_partial"
    except Exception as exc:
        logger.warning("Heavy quiz probe failed: %s", exc)

    return best_count, best_engine


def assess_quiz_eligibility(
    text: str,
    *,
    file_type: Optional[str] = None,
    probe: bool = True,
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Return (eligible, reason_code, meta).

    reason_code is one of:
      missing_content_text | content_too_short | content_mostly_noise |
      no_meaningful_concepts | insufficient_quiz_structure |
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

    # Detect text that is almost entirely noise (short tokens, no real words)
    words = normalized.split()
    long_words = [w for w in words if len(w) >= 4]
    if len(words) > 20 and len(long_words) / len(words) < 0.25:
        meta["long_word_ratio"] = round(len(long_words) / len(words), 2)
        return False, "content_mostly_noise", meta

    unsupported_types = {"html", "link", "zip", "xlsx"}
    ft = meta["file_type"]
    if ft in unsupported_types and len(normalized) < 500:
        return False, "unsupported_material_format", meta

    # Quick lecture concept count (fast, no heavy engine)
    try:
        from app.services.quiz_gen_lecture import count_lecture_concepts
        lecture_count = count_lecture_concepts(normalized)
        meta["lecture_concept_count"] = lecture_count
    except Exception:
        lecture_count = 0
        meta["lecture_concept_count"] = 0

    if probe:
        count, engine = probe_question_count(normalized)
        meta["probe_question_count"] = count
        meta["probe_engine"] = engine
        if count >= _MIN_LIMITED_QUESTIONS:
            meta["quiz_generation_eligible"] = True
            return True, None, meta

    # Fallback: check definition pairs + lecture concepts without full probe
    definition_pair_count = 0
    try:
        from app.services.quiz_gen_light import extract_definitions
        pairs = extract_definitions(normalized)
        definition_pair_count = len(pairs)
        meta["definition_pair_count"] = definition_pair_count
    except Exception as exc:
        logger.warning("Definition extraction failed during eligibility: %s", exc)
        meta["parsing_error"] = str(exc)

    total_concepts = definition_pair_count + lecture_count
    meta["total_concepts"] = total_concepts

    if total_concepts >= _MIN_LIMITED_QUESTIONS:
        meta["quiz_generation_eligible"] = True
        return True, None, meta

    # Distinguish between "no concepts found" and "some concepts but too few"
    if total_concepts == 0 and len(normalized) > 500:
        return False, "no_meaningful_concepts", meta

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

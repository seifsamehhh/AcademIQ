"""
Shared sort order + quiz readiness for Quiz Generation UI and debug endpoints.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

from app.services.quiz_material_eligibility import (
    assess_quiz_eligibility,
    reason_message,
)
from app.services.student_data import (
    MIN_QUIZ_CONTENT_CHARS,
    _classify_non_quiz_material,
    _is_educational_material,
    _material_stored_content_length,
    _PROCESSED_EXTRACTION_STATUSES,
)

MIN_READY_QUESTIONS = 5
MIN_LIMITED_QUESTIONS = 3
LIMITED_QUIZ_NOTE = (
    "Limited quiz generated because the material has limited readable content."
)

_SORT_GROUP_LABELS = [
    "Lecture",
    "Lab",
    "Revision",
    "Notes/Tutorial/Slides",
    "Other Educational",
    "Non-quiz / Admin",
]

# Numbers after lecture/lab/lec only — never course codes like SWE423.
_LECTURE_NUM_RE = re.compile(r"(?i)\b(?:lecture|lec)\s*#?(\d+)")
_LAB_NUM_RE = re.compile(r"(?i)\blab(?:\s+(?:assignment\s*)?)?\s*#?(\d+)")
_REVISION_NUM_RE = re.compile(r"(?i)\b(?:revision|review|summary)\s*#?(\d+)")
_CHAPTER_NUM_RE = re.compile(r"(?i)\bchapters?\s*#?(\d+)")
_WEEK_NUM_RE = re.compile(r"(?i)\bweek\s*#?(\d+)")

_LECTURE_TYPE_RE = re.compile(r"(?i)\b(?:lecture|lec)(?:\s*#?\d|\b)")
_LAB_TYPE_RE = re.compile(r"(?i)\blab(?:\s*#?\d|\b)")
_REVISION_TYPE_RE = re.compile(r"(?i)\b(?:revision|review|summary)(?:\s*#?\d|\b)")
_NOTES_TYPE_RE = re.compile(
    r"(?i)\b(?:notes?|tutorial|handout|slides?|worksheets?|chapters?|exercises?|modules?|week\b|problems?\b)"
)


def material_sort_group(title: str, is_non_quiz: bool) -> int:
    if is_non_quiz:
        return 5
    t = title or ""
    if _LECTURE_TYPE_RE.search(t):
        return 0
    if _LAB_TYPE_RE.search(t):
        return 1
    if _REVISION_TYPE_RE.search(t):
        return 2
    if _NOTES_TYPE_RE.search(t):
        return 3
    return 4


def material_sort_number(title: str, sort_group: Optional[int] = None) -> int:
    """Extract lecture/lab/revision number; ignore course-code digits like SWE423."""
    t = title or ""
    sg = sort_group if sort_group is not None else material_sort_group(t, False)

    if sg == 0:
        m = _LECTURE_NUM_RE.search(t)
        return int(m.group(1)) if m else 9999
    if sg == 1:
        m = _LAB_NUM_RE.search(t)
        return int(m.group(1)) if m else 9999
    if sg == 2:
        m = _REVISION_NUM_RE.search(t)
        return int(m.group(1)) if m else 9999
    if sg == 3:
        for pattern in (_CHAPTER_NUM_RE, _WEEK_NUM_RE, _NOTES_TYPE_RE):
            m = pattern.search(t)
            if m and m.lastindex:
                return int(m.group(1))
        return 9999
    return 9999


def _map_eligibility_to_status(
    reason_code: Optional[str],
    content_len: int,
    probe_count: int,
) -> Tuple[str, Optional[str]]:
    """Map assess_quiz_eligibility output to UI quiz_status + human reason."""
    if probe_count >= MIN_READY_QUESTIONS:
        return "ready", None

    if probe_count >= MIN_LIMITED_QUESTIONS:
        return "limited_ready", LIMITED_QUIZ_NOTE

    if content_len < MIN_QUIZ_CONTENT_CHARS:
        return (
            "extraction_too_short",
            f"Only {content_len} characters extracted (need at least "
            f"{MIN_QUIZ_CONTENT_CHARS}). Re-upload via the Chrome extension.",
        )

    msg = reason_message(reason_code) or (
        "Not enough readable educational text to generate a reliable quiz "
        "from this material alone."
    )

    if reason_code == "unsupported_material_format":
        return "unsupported", msg

    if reason_code == "content_too_short":
        return "extraction_too_short", msg

    return "not_enough_readable_text", msg


def resolve_material_display(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Single source of truth for Quiz Generation list item:
    status, visibility, sort fields, and whether generation will succeed.
    """
    title = doc.get("title") or "Untitled"
    file_type = (doc.get("file_type") or doc.get("category") or "file")
    raw_file_type = str(file_type).lower()
    content = (doc.get("content_text") or "").strip()
    content_len = len(content) if content else _material_stored_content_length(doc)
    extraction_status = (doc.get("extraction_status") or "").strip()

    is_non_quiz, non_quiz_reason = _classify_non_quiz_material(title, raw_file_type)
    if not is_non_quiz and extraction_status == "not_quiz_material":
        is_non_quiz = True
        non_quiz_reason = doc.get("extraction_error") or "Non-educational material"

    is_educ = _is_educational_material(title, raw_file_type) if not is_non_quiz else False

    if is_non_quiz or not is_educ:
        reason = non_quiz_reason or (
            "Not quiz material — only lectures, labs, revisions, notes, "
            "and similar learning materials appear in the main list."
        )
        sg = 5
        return {
            "quiz_status": "not_quiz_material",
            "quiz_status_reason": reason,
            "is_educational_material": False,
            "is_non_quiz_material": True,
            "content_text_length": content_len,
            "quiz_generation_eligible": False,
            "ready_for_quiz": False,
            "will_generate_successfully": False,
            "why_not_ready": reason,
            "sort_group": sg,
            "sort_group_label": _SORT_GROUP_LABELS[sg],
            "sort_number": material_sort_number(title, sg),
            "visible_in_main_list": False,
            "visible_in_other_items": True,
            "selectable": False,
            "probe_question_count": 0,
            "question_count_possible": 0,
            "min_questions_required": MIN_LIMITED_QUESTIONS,
        }

    # ── Educational learning material ───────────────────────────────────────
    will_generate = False
    why_not_ready: Optional[str] = None
    probe_count = 0
    eligibility_meta: Dict[str, Any] = {}
    content_note: Optional[str] = None
    quiz_status = "not_uploaded"

    if extraction_status == "extraction_failed":
        quiz_status = "extraction_failed"
        content_note = (
            doc.get("extraction_error")
            or "No readable text could be extracted. Try re-uploading a text-based PDF."
        )
    elif content_len == 0 and extraction_status not in _PROCESSED_EXTRACTION_STATUSES:
        quiz_status = "not_uploaded"
        content_note = (
            "No readable text extracted yet. "
            "Use the Chrome extension → 'Upload materials for quiz' on the Moodle course page."
        )
    elif content_len == 0 and extraction_status in _PROCESSED_EXTRACTION_STATUSES:
        quiz_status = "extraction_failed"
        content_note = (
            doc.get("extraction_error")
            or "Material was processed but no readable text was stored."
        )
    elif not content:
        quiz_status = "extraction_too_short"
        content_note = (
            "No stored content text for quiz generation. Re-upload via the Chrome extension."
        )
    else:
        _, reason_code, eligibility_meta = assess_quiz_eligibility(
            content,
            file_type=raw_file_type,
            probe=True,
        )
        probe_count = int(eligibility_meta.get("probe_question_count") or 0)
        quiz_status, content_note = _map_eligibility_to_status(
            reason_code, len(content), probe_count,
        )
        will_generate = quiz_status in ("ready", "limited_ready")
        if not will_generate:
            why_not_ready = content_note

    selectable = quiz_status in ("ready", "limited_ready")
    quiz_ready = quiz_status == "ready"
    sg = material_sort_group(title, False)

    return {
        "quiz_status": quiz_status,
        "quiz_status_reason": content_note,
        "is_educational_material": True,
        "is_non_quiz_material": False,
        "content_text_length": content_len,
        "quiz_generation_eligible": selectable,
        "ready_for_quiz": quiz_ready,
        "will_generate_successfully": will_generate,
        "why_not_ready": why_not_ready,
        "sort_group": sg,
        "sort_group_label": _SORT_GROUP_LABELS[sg],
        "sort_number": material_sort_number(title, sg),
        "visible_in_main_list": True,
        "visible_in_other_items": False,
        "selectable": selectable,
        "probe_question_count": probe_count,
        "question_count_possible": probe_count,
        "min_questions_required": MIN_LIMITED_QUESTIONS,
        "eligibility_meta": {
            k: eligibility_meta.get(k)
            for k in (
                "probe_engine",
                "lecture_concept_count",
                "definition_pair_count",
                "total_concepts",
            )
            if eligibility_meta.get(k) is not None
        },
    }

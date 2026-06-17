"""
Single source of truth for Quiz Generation material list:
classification, visibility, sort order, and quiz readiness.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from app.services.quiz_material_eligibility import (
    assess_quiz_eligibility,
    reason_message,
)
from app.services.student_data import (
    MIN_QUIZ_CONTENT_CHARS,
    _material_stored_content_length,
    _PROCESSED_EXTRACTION_STATUSES,
)

MIN_READY_QUESTIONS = 5
MIN_LIMITED_QUESTIONS = 3
LIMITED_QUIZ_NOTE = (
    "Limited quiz generated because the material has limited readable content."
)
LINK_WRAPPER_REASON = "Link / wrapper item, not quiz material"

_SORT_GROUP_LABELS = [
    "Lecture",
    "Lab",
    "Revision",
    "Notes/Tutorial/Slides",
    "Other Educational",
    "Non-quiz / Admin",
]

_KIND_SORT_GROUP: Dict[str, int] = {
    "lecture": 0,
    "lecture_link": 0,
    "lab": 1,
    "lab_link": 1,
    "revision": 2,
    "notes": 3,
    "other_educational": 4,
    "other_moodle_item": 5,
}

_LINK_FILE_TYPES = frozenset({"link", "url", "html"})
_REAL_CONTENT_FILE_TYPES = frozenset({
    "pdf", "pptx", "ppt", "docx", "doc", "txt", "text",
})

_NON_QUIZ_ACTIVITY_TYPES = frozenset({
    "folder", "assign", "forum", "quiz", "choice",
    "feedback", "survey", "chat", "glossary", "wiki", "workshop",
    "scorm", "lti", "attendance", "book", "label", "page",
})
_NON_QUIZ_FILE_EXTENSIONS = frozenset({"xlsx", "xls", "csv", "ods"})

_NON_QUIZ_TITLE_RE = re.compile(
    r"\b(?:"
    r"grade[sd]?|grading|mark[sd]?|marking|score\s+sheet|grade\s+sheet"
    r"|mark\s+sheet|grade\s+book|mark\s+book|final\s+(?:mark[sd]?|grade[sd]?|score[sd]?)"
    r"|student\s+scores?|scores?\s+(?:sheet|list|record|file)"
    r"|grading\s+criteria"
    r"|attendance|absent(?:ee)?|student\s+(?:list|roster|record[sd]?)"
    r"|submission\s+(?:report|status|list|guide|form)"
    r"|assignment\s+(?:submission|status|report|list)"
    r"|submissions?"
    r"|project\s+(?:requirements?|criteria|rubric|description|brief|plan|outline|guide|specs?)"
    r"|final\s+project(?:\s+(?:criteria|requirements?|brief|description))?"
    r"|task[_\s-]*details?"
    r"|requirements?\s+file"
    r"|assignment\s+(?:instructions?|brief|description|rubric|criteria|requirements?)"
    r"|rubric[sd]?|criteria\s+(?:sheet|form|file)"
    r"|evaluation\s+(?:form|sheet|rubric|criteria)|evaluation\b"
    r"|marking\s+(?:scheme|guide|rubric|sheet)"
    r"|answer\s+(?:key|sheet|model)|model\s+answer[sd]?"
    r"|lab\s+report\s+(?:template|form|sheet)"
    r"|test(?:ing)?\s+phase"
    r"|course\s+(?:outline|plan|schedule|syllabus|calendar|timetable|guide)"
    r"|semester\s+(?:plan|schedule|calendar|timetable)"
    r"|exam\s+(?:schedule|timetable|calendar)"
    r"|due\s+dates?|deadline[sd]?"
    r"|announcements?|course\s+contents?|table\s+of\s+contents?"
    r"|admin(?:istration)?\s+(?:file[sd]?|doc(?:ument)?[sd]?)"
    r")\b",
    re.I,
)

_EDUCATIONAL_TITLE_RE = re.compile(
    r"\b(?:"
    r"lecture|lec(?:\s*#?\d|\b)"
    r"|lab(?:\s*#?\d|\b)"
    r"|tutorial|notes?|slides?|handout|revision|review|summary|chapter"
    r"|worksheet|exercise|module|session|reading|lesson|study"
    r"|week(?:\s*#?\d|\b)|problems?\b|problems?\s+sheet"
    r"|class\s+material|introduction|topic"
    r"|problem\b|svm\b"
    r")\b",
    re.I,
)

_LAB_ASSIGNMENT_RE = re.compile(r"(?i)\blab\s+(?:assignment\s*)?#?\d+")

# Numbers after lecture/lab/lec only — never SWE423/CSC344.
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
_LECTURE_LINK_TITLE_RE = re.compile(
    r"(?i)\b(?:lecture|lec)\s*#?\d+\s*(?:url|link)\b"
)
_LAB_LINK_TITLE_RE = re.compile(r"(?i)\blab\s*#?\d+\s*(?:url|link)\b")
_EXPLICIT_LINK_TITLE_RE = re.compile(
    r"(?i)(?:\b(?:lecture|lec|lab)\s*#?\d+\s*(?:url|link)\b|\burl\s*$|\blink\s*$)"
)


def detect_link_wrapper(title: str, file_type: str) -> bool:
    """
    True only for explicit URL/link wrapper rows (e.g. 'Lecture 7 URL').

    Moodle resources titled 'Lecture 2 File' with file_type url are NOT wrappers —
    they are external-link learning resources and must stay in the main list.
    """
    t = (title or "").strip()
    if _LECTURE_LINK_TITLE_RE.search(t) or _LAB_LINK_TITLE_RE.search(t):
        return True
    if _EXPLICIT_LINK_TITLE_RE.search(t):
        return True
    return False


def classify_non_quiz_material(title: str, file_type: str) -> Tuple[bool, Optional[str]]:
    ft = (file_type or "").lower().strip()
    normalized = re.sub(r"[_]+", " ", (title or ""))

    if _LAB_ASSIGNMENT_RE.search(title or "") or _LAB_ASSIGNMENT_RE.search(normalized):
        return False, None

    if ft in _NON_QUIZ_ACTIVITY_TYPES:
        if ft in _LINK_FILE_TYPES and _EDUCATIONAL_TITLE_RE.search(title or ""):
            if not detect_link_wrapper(title, file_type):
                return False, None
        else:
            return True, f"Moodle activity: {ft}"

    if ft in _NON_QUIZ_FILE_EXTENSIONS:
        return True, f"Spreadsheet file (.{ft}) — likely grades or data export"

    if _NON_QUIZ_TITLE_RE.search(title or "") or _NON_QUIZ_TITLE_RE.search(normalized):
        return True, "Not quiz material — admin, project, grade, or non-lecture content"

    return False, None


def is_educational_material(title: str, file_type: str) -> bool:
    ft = (file_type or "").lower().strip()
    normalized = re.sub(r"[_]+", " ", (title or ""))

    if ft in _NON_QUIZ_FILE_EXTENSIONS:
        return False

    if ft in _NON_QUIZ_ACTIVITY_TYPES:
        if ft in _LINK_FILE_TYPES and _EDUCATIONAL_TITLE_RE.search(title or ""):
            if not detect_link_wrapper(title, file_type):
                return True
        return False

    if _NON_QUIZ_TITLE_RE.search(title or "") or _NON_QUIZ_TITLE_RE.search(normalized):
        return False

    if _EDUCATIONAL_TITLE_RE.search(title or "") or _EDUCATIONAL_TITLE_RE.search(normalized):
        return True

    return False


def classify_material_kind(
    title: str,
    file_type: str,
    is_non_quiz: bool,
) -> str:
    if is_non_quiz:
        return "other_moodle_item"
    if detect_link_wrapper(title, file_type):
        if _LAB_TYPE_RE.search(title or "") or re.search(r"(?i)\blab", title or ""):
            return "lab_link"
        return "lecture_link"
    t = title or ""
    if _LECTURE_TYPE_RE.search(t):
        return "lecture"
    if _LAB_TYPE_RE.search(t):
        return "lab"
    if _REVISION_TYPE_RE.search(t):
        return "revision"
    if _NOTES_TYPE_RE.search(t):
        return "notes"
    return "other_educational"


def extract_material_number(title: str, material_kind: str) -> int:
    t = title or ""
    if material_kind in ("lecture", "lecture_link"):
        m = _LECTURE_NUM_RE.search(t)
        return int(m.group(1)) if m else 9999
    if material_kind in ("lab", "lab_link"):
        m = _LAB_NUM_RE.search(t)
        return int(m.group(1)) if m else 9999
    if material_kind == "revision":
        m = _REVISION_NUM_RE.search(t)
        return int(m.group(1)) if m else 9999
    if material_kind == "notes":
        for pattern in (_CHAPTER_NUM_RE, _WEEK_NUM_RE):
            m = pattern.search(t)
            if m:
                return int(m.group(1))
        return 9999
    return 9999


def material_display_sort_key(display: Dict[str, Any]) -> Tuple[int, int, int, str]:
    sg = display.get("sort_group")
    sn = display.get("material_number")
    slr = display.get("sort_link_rank")
    return (
        int(sg if sg is not None else 5),
        int(sn if sn is not None else 9999),
        int(slr if slr is not None else 0),
        (display.get("title") or "").lower(),
    )


def _is_real_lecture_lab_file(display: Dict[str, Any]) -> bool:
    """True for stored PDF/PPTX/DOCX/TXT lecture/lab files (quiz sources)."""
    if display.get("is_link_wrapper"):
        return False
    kind = display.get("material_kind")
    if kind not in ("lecture", "lab"):
        return False
    ft = (display.get("file_type") or "").lower()
    if ft in _REAL_CONTENT_FILE_TYPES:
        return True
    if ft in _LINK_FILE_TYPES:
        return False
    return kind in ("lecture", "lab")


def _apply_link_wrapper_visibility(displays: List[Dict[str, Any]]) -> None:
    real_keys: Set[Tuple[str, int]] = set()
    for d in displays:
        if _is_real_lecture_lab_file(d):
            kind = d["material_kind"]
            num = d.get("material_number")
            if num is not None and num < 9999:
                real_keys.add((kind, num))

    for d in displays:
        if not d.get("is_link_wrapper"):
            d.setdefault("has_real_file_sibling", False)
            continue

        kind = d.get("material_kind")
        num = d.get("material_number")
        base = "lecture" if kind == "lecture_link" else "lab" if kind == "lab_link" else None
        sibling = (
            base is not None
            and num is not None
            and num < 9999
            and (base, num) in real_keys
        )
        d["has_real_file_sibling"] = sibling

        if sibling:
            d["visible_in_main_list"] = False
            d["visible_in_other_items"] = True
            d["selectable"] = False
            d["quiz_generation_eligible"] = False
            d["ready_for_quiz"] = False
            d["will_generate_successfully"] = False
            d["quiz_status"] = "not_quiz_material"
            d["quiz_status_reason"] = LINK_WRAPPER_REASON
            d["why_not_ready"] = LINK_WRAPPER_REASON
            d["is_non_quiz_material"] = True
            d["is_educational_material"] = False
            d["sort_group"] = 5
            d["material_kind"] = "other_moodle_item"


def _detect_missing_lecture_numbers(displays: List[Dict[str, Any]]) -> List[int]:
    nums: Set[int] = set()
    for d in displays:
        if d.get("material_kind") in ("lecture", "lecture_link"):
            n = d.get("material_number")
            if n is not None and n < 9999:
                nums.add(n)
    if len(nums) < 2:
        return []
    lo, hi = min(nums), max(nums)
    return [n for n in range(lo, hi + 1) if n not in nums]


def _map_eligibility_to_status(
    reason_code: Optional[str],
    content_len: int,
    probe_count: int,
) -> Tuple[str, Optional[str]]:
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


def _resolve_one_material(doc: Dict[str, Any]) -> Dict[str, Any]:
    title = doc.get("title") or "Untitled"
    file_type = (doc.get("file_type") or doc.get("category") or "file")
    raw_file_type = str(file_type).lower()
    content = (doc.get("content_text") or "").strip()
    content_len = len(content) if content else _material_stored_content_length(doc)
    extraction_status = (doc.get("extraction_status") or "").strip()
    material_id = str(doc.get("material_id") or "")

    is_link_wrapper = detect_link_wrapper(title, raw_file_type)
    is_non_quiz, non_quiz_reason = classify_non_quiz_material(title, raw_file_type)

    if not is_non_quiz and extraction_status == "not_quiz_material":
        is_non_quiz = True
        non_quiz_reason = doc.get("extraction_error") or "Non-educational material"

    material_kind = classify_material_kind(title, raw_file_type, is_non_quiz)
    material_number = extract_material_number(title, material_kind)
    sort_link_rank = 1 if is_link_wrapper else 0
    sort_group = _KIND_SORT_GROUP.get(material_kind, 5)
    is_educ = is_educational_material(title, raw_file_type) if not is_non_quiz else False

    base: Dict[str, Any] = {
        "material_id": material_id,
        "title": title,
        "file_type": raw_file_type,
        "material_kind": material_kind,
        "material_number": material_number,
        "is_link_wrapper": is_link_wrapper,
        "has_real_file_sibling": False,
        "sort_link_rank": sort_link_rank,
        "sort_group": sort_group,
        "sort_group_label": (
            _SORT_GROUP_LABELS[sort_group] if sort_group < len(_SORT_GROUP_LABELS) else "Other"
        ),
        "sort_number": material_number,
        "content_text_length": content_len,
        "probe_question_count": 0,
        "question_count_possible": 0,
        "min_questions_required": MIN_LIMITED_QUESTIONS,
        "missing_from_db": False,
    }

    if is_non_quiz or not is_educ:
        reason = non_quiz_reason or (
            "Not quiz material — only lectures, labs, revisions, notes, "
            "and similar learning materials appear in the main list."
        )
        return {
            **base,
            "quiz_status": "not_quiz_material",
            "quiz_status_reason": reason,
            "reason": reason,
            "is_educational_material": False,
            "is_non_quiz_material": True,
            "quiz_generation_eligible": False,
            "ready_for_quiz": False,
            "will_generate_successfully": False,
            "why_not_ready": reason,
            "visible_in_main_list": False,
            "visible_in_other_items": True,
            "selectable": False,
            "material_kind": "other_moodle_item",
            "sort_group": 5,
        }

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

    return {
        **base,
        "quiz_status": quiz_status,
        "quiz_status_reason": content_note,
        "reason": content_note,
        "is_educational_material": True,
        "is_non_quiz_material": False,
        "quiz_generation_eligible": selectable,
        "ready_for_quiz": quiz_status == "ready",
        "will_generate_successfully": will_generate,
        "why_not_ready": why_not_ready,
        "visible_in_main_list": True,
        "visible_in_other_items": False,
        "selectable": selectable,
        "probe_question_count": probe_count,
        "question_count_possible": probe_count,
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


def _is_metadata_only_doc(doc: Dict[str, Any]) -> bool:
    """True when Moodle metadata was saved but no extractable file content exists."""
    if doc.get("metadata_only"):
        return True
    ft = str(doc.get("file_type") or "").lower()
    if _material_stored_content_length(doc) > 0:
        return False
    status = str(doc.get("extraction_status") or "")
    if status == "not_quiz_material":
        return False
    return ft in _LINK_FILE_TYPES or status == "not_uploaded"


def _find_saved_lecture_doc_for_number(
    materials: List[Dict[str, Any]],
    lecture_num: int,
) -> Optional[Dict[str, Any]]:
    """Return a saved Mongo row for this lecture number, if any."""
    for doc in materials:
        title = doc.get("title") or ""
        if not _LECTURE_TYPE_RE.search(title):
            continue
        m = _LECTURE_NUM_RE.search(title)
        if m and int(m.group(1)) == lecture_num:
            return doc
    return None


_METADATA_ONLY_LECTURE_REASON = (
    "File detected from Moodle but content was not extracted yet"
)


def _apply_metadata_only_lecture_display(display: Dict[str, Any]) -> None:
    display["quiz_status"] = "not_uploaded"
    display["quiz_status_reason"] = _METADATA_ONLY_LECTURE_REASON
    display["reason"] = _METADATA_ONLY_LECTURE_REASON
    display["why_not_ready"] = _METADATA_ONLY_LECTURE_REASON
    display["selectable"] = False
    display["quiz_generation_eligible"] = False
    display["ready_for_quiz"] = False
    display["will_generate_successfully"] = False
    display["visible_in_main_list"] = True
    display["visible_in_other_items"] = False
    display["missing_from_db"] = False


def _reconcile_missing_lecture_numbers(
    materials: List[Dict[str, Any]],
    displays: List[Dict[str, Any]],
    missing_numbers: List[int],
) -> List[int]:
    """
    Replace synthetic gap placeholders with saved metadata rows when possible.

    If a lecture number has a MongoDB row but was not counted in gap detection
    (e.g. url/html metadata-only), surface that row instead of a placeholder.
    """
    still_missing: List[int] = []
    by_id = {str(d.get("material_id") or ""): d for d in displays}

    for lecture_num in missing_numbers:
        doc = _find_saved_lecture_doc_for_number(materials, lecture_num)
        if not doc:
            still_missing.append(lecture_num)
            continue

        mid = str(doc.get("material_id") or "")
        if mid in by_id:
            existing = by_id[mid]
            if _is_metadata_only_doc(doc):
                _apply_metadata_only_lecture_display(existing)
            continue

        display = _resolve_one_material(doc)
        if _is_metadata_only_doc(doc):
            _apply_metadata_only_lecture_display(display)
        displays.append(display)
        by_id[mid] = display

    return still_missing


def _append_missing_lecture_placeholders(
    displays: List[Dict[str, Any]],
    missing_numbers: List[int],
) -> None:
    """Surface lecture numbers present in sequence gaps but not stored in MongoDB."""
    for n in missing_numbers:
        reason = (
            f"Lecture {n} is not saved in the database yet. "
            "Use the Chrome extension → 'Upload materials for quiz' on the Moodle course page."
        )
        displays.append({
            "material_id": f"missing-lecture-{n}",
            "title": f"Lecture {n} (not synced to database yet)",
            "file_type": "missing",
            "material_kind": "lecture",
            "material_number": n,
            "is_link_wrapper": False,
            "has_real_file_sibling": False,
            "sort_link_rank": 0,
            "sort_group": 0,
            "sort_group_label": "Lecture",
            "sort_number": n,
            "content_text_length": 0,
            "probe_question_count": 0,
            "question_count_possible": 0,
            "min_questions_required": MIN_LIMITED_QUESTIONS,
            "missing_from_db": True,
            "quiz_status": "not_uploaded",
            "quiz_status_reason": reason,
            "reason": reason,
            "is_educational_material": True,
            "is_non_quiz_material": False,
            "quiz_generation_eligible": False,
            "ready_for_quiz": False,
            "will_generate_successfully": False,
            "why_not_ready": reason,
            "visible_in_main_list": True,
            "visible_in_other_items": False,
            "selectable": False,
        })


def resolve_quiz_material_display(
    materials: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Resolve classification, visibility, sort, and quiz status for all course materials.

    Returns (displays sorted for UI, course_meta with gap diagnostics).
    """
    displays = [_resolve_one_material(doc) for doc in materials]
    _apply_link_wrapper_visibility(displays)
    displays.sort(key=material_display_sort_key)

    missing_lectures = _detect_missing_lecture_numbers(displays)
    if missing_lectures:
        missing_lectures = _reconcile_missing_lecture_numbers(
            materials, displays, missing_lectures,
        )
        if missing_lectures:
            _append_missing_lecture_placeholders(displays, missing_lectures)
        displays.sort(key=material_display_sort_key)
    main_count = sum(1 for d in displays if d.get("visible_in_main_list"))
    other_count = sum(1 for d in displays if d.get("visible_in_other_items"))

    meta = {
        "total_saved_materials": len(displays),
        "main_list_count": main_count,
        "other_items_count": other_count,
        "missing_educational_count": len(missing_lectures),
        "missing_lecture_numbers": missing_lectures,
    }
    return displays, meta


def resolve_material_display(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve a single material (used by quiz generation validation)."""
    displays, _ = resolve_quiz_material_display([doc])
    return displays[0] if displays else _resolve_one_material(doc)


# Legacy aliases
def apply_course_material_visibility(displays: List[Dict[str, Any]]) -> None:
    _apply_link_wrapper_visibility(displays)


def material_sort_group(title: str, is_non_quiz: bool) -> int:
    kind = classify_material_kind(title, "", is_non_quiz)
    return _KIND_SORT_GROUP.get(kind, 5)


def material_sort_number(title: str, sort_group: Optional[int] = None) -> int:
    sg = sort_group if sort_group is not None else material_sort_group(title, False)
    kind = "lecture" if sg == 0 else "lab" if sg == 1 else "revision" if sg == 2 else "notes" if sg == 3 else "other_educational"
    return extract_material_number(title, kind)

"""
Demo material repair: restore Lecture 2 / Lab 2 / Lab 4 visibility and readiness.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.repositories import material_repository
from app.services.material_quiz_display import (
    _LAB_NUM_EMBEDDED_RE,
    _LECTURE_NUM_RE,
    classify_material_kind,
    classify_non_quiz_material,
    resolve_material_number,
)
from app.services.material_quiz_upload import (
    _canonical_learning_row_score,
    _content_fields_from_doc,
)
from app.services.student_data import _material_stored_content_length

_IMPORT_SOURCE = "course_material_import"
_SOURCE_NOTE = "Content imported from provided course material file."
_MIN_READY_CHARS = 301
_MIN_LIMITED_CHARS = 100

RepairTarget = Tuple[str, str, int]  # course_id, kind, number

REPAIR_TARGETS: List[RepairTarget] = [
    ("666", "lecture", 2),
    ("808", "lecture", 2),
    ("666", "lab", 2),
    ("808", "lab", 2),
    ("808", "lab", 4),
]


def _content_len(doc: Dict[str, Any]) -> int:
    return _material_stored_content_length(doc)


def _matches_kind_number(
    doc: Dict[str, Any],
    kind: str,
    number: int,
) -> bool:
    title = str(doc.get("title") or "")
    fn = str(doc.get("original_filename") or "")
    ft = str(doc.get("file_type") or "")
    combined = f"{title} {fn}"
    is_non, _ = classify_non_quiz_material(title, ft)
    stored_kind = str(doc.get("material_kind") or "")
    if not stored_kind or stored_kind == "other_moodle_item":
        stored_kind = classify_material_kind(title, ft, is_non)

    if kind == "lecture":
        if stored_kind in ("lab", "lab_link") and not re.search(r"(?i)\blecture|\blec\b", combined):
            return False
        if re.search(r"(?i)\blab\s*#?\s*\d", combined) and not re.search(
            r"(?i)\b(?:lecture|lec)\s*#?\s*\d", combined
        ):
            return False
        m = _LECTURE_NUM_RE.search(combined)
        if m and int(m.group(1)) == number:
            return True
        if stored_kind in ("lecture", "lecture_link") and resolve_material_number(
            doc, title, "lecture"
        ) == number:
            return True
        return False

    if kind == "lab":
        if stored_kind in ("lecture", "lecture_link") and not re.search(r"(?i)\blab", combined):
            if not re.search(rf"(?i)\blab\s*#?\s*{number}", combined):
                return False
        if re.search(r"(?i)\b(?:lecture|lec)\s*#?\s*\d", combined) and not re.search(
            r"(?i)\blab", combined
        ):
            return False
        for src in (title, fn):
            if re.search(rf"(?i)\blab\s*#?\s*{number}(?:\b|[^0-9])", src):
                return True
            if re.search(rf"(?i)lab{number}(?:\b|[^0-9])", src.replace("_", "").replace(" ", "")):
                return True
            emb = _LAB_NUM_EMBEDDED_RE.search(src)
            if emb and int(emb.group(1) or emb.group(2)) == number:
                return True
        if stored_kind in ("lab", "lab_link") and resolve_material_number(
            doc, title, "lab"
        ) == number:
            return True
        return False

    return False


def _canonical_score(doc: Dict[str, Any], kind: str) -> int:
    score = _canonical_learning_row_score(doc)
    stored_kind = str(doc.get("material_kind") or "").lower()
    if stored_kind.startswith(kind):
        score += 200
    if doc.get("hidden_duplicate"):
        score -= 300
    if doc.get("demo_quiz_hidden"):
        score -= 300
    if str(doc.get("material_id") or "").startswith("url_"):
        score -= 80
    score += min(_content_len(doc) // 50, 100)
    return score


def _source_score(doc: Dict[str, Any], kind: str, number: int) -> int:
    score = _content_len(doc)
    if doc.get("content_source") == _IMPORT_SOURCE:
        score += 8000
    fn = str(doc.get("original_filename") or "").lower()
    title = str(doc.get("title") or "").lower()
    if kind == "lecture":
        if re.search(rf"(?:lecture|lec)\s*#?\s*{number}", fn + title):
            score += 3000
    else:
        if re.search(rf"lab\s*#?\s*{number}|lab{number}", fn.replace("_", "") + title):
            score += 3000
    return score


def _display_title(kind: str, number: int, source: Dict[str, Any]) -> str:
    if kind == "lab":
        return f"Lab {number}"
    title = str(source.get("title") or "")
    fn = str(source.get("original_filename") or "")
    combined = f"{title} {fn}".replace("_", " ")
    m = re.search(
        r"(?i)(?:lecture|lec)\s*#?\s*(\d+)\s*(?:[-–—:]\s*)?(.+)$",
        combined,
    )
    if not m:
        m = re.search(
            r"(?i)(?:lecture|lec)(\d+)\s+(.+?)(?:\.(?:pdf|pptx?|ppsx|docx?))?\s*$",
            combined,
        )
    if m and int(m.group(1)) == number:
        topic = (m.group(2) or "").strip()
        for _ in range(2):
            topic = re.sub(r"\s*\.\w{2,5}\s*$", "", topic).strip()
            topic = re.sub(r"\s*\(\d+\)\s*$", "", topic).strip()
        topic = re.sub(r"^(?:SWE\d+|CSC\d+).*?(?=\b[A-Z])", "", topic).strip()
        if topic and not re.match(r"^(file|moodle)$/i", topic):
            return f"Lecture {number} — {topic[:80]}"
    return f"Lecture {number}"


def _ready_fields(clen: int) -> Dict[str, Any]:
    if clen > _MIN_READY_CHARS - 1:
        return {
            "quiz_status": "ready",
            "ready_for_quiz": True,
            "quiz_generation_eligible": True,
            "extraction_status": "success",
        }
    if clen >= _MIN_LIMITED_CHARS:
        return {
            "quiz_status": "limited_ready",
            "ready_for_quiz": True,
            "quiz_generation_eligible": True,
            "extraction_status": "success",
        }
    return {
        "quiz_status": "not_uploaded",
        "ready_for_quiz": False,
        "quiz_generation_eligible": False,
        "extraction_status": "not_uploaded",
    }


def _find_matching_rows(course_id: str, kind: str, number: int) -> List[Dict[str, Any]]:
    rows = [
        d
        for d in material_repository.list_by_course(course_id)
        if _matches_kind_number(d, kind, number)
    ]
    if rows:
        return rows

    for doc in material_repository.list_by_course(course_id):
        title = str(doc.get("title") or "")
        fn = str(doc.get("original_filename") or "")
        combined = f"{title} {fn}"
        if kind == "lecture":
            if re.search(rf"(?i)(?:lecture|lec)\s*#?\s*{number}\b", combined):
                if re.search(r"(?i)\blab\s*#?\s*\d", combined) and not re.search(
                    r"(?i)(?:lecture|lec)\s*#?\s*\d", combined
                ):
                    continue
                rows.append(doc)
            elif re.search(rf"(?i)lecture{number}(?:[^0-9]|$)", combined.replace(" ", "")):
                rows.append(doc)
        else:
            if re.search(rf"(?i)\blab\s*#?\s*{number}(?:\b|[^0-9])", combined):
                rows.append(doc)
            elif re.search(rf"(?i)lab{number}(?:\b|[^0-9])", combined.replace("_", "")):
                rows.append(doc)
    return rows


def repair_target(course_id: str, kind: str, number: int) -> Dict[str, Any]:
    course_id = str(course_id).strip()
    rows = _find_matching_rows(course_id, kind, number)

    if not rows:
        return {
            "course_id": course_id,
            "kind": kind,
            "number": number,
            "fixed": False,
            "not_found": True,
            "reason": "no_matching_rows",
        }

    sources = [r for r in rows if _content_len(r) >= _MIN_LIMITED_CHARS]
    if not sources:
        return {
            "course_id": course_id,
            "kind": kind,
            "number": number,
            "fixed": False,
            "not_found": True,
            "reason": "no_content_over_100",
            "matching_titles": [r.get("title") for r in rows],
        }

    if kind == "lab":
        lab_only = []
        for s in sources:
            combined = f"{s.get('title') or ''} {s.get('original_filename') or ''}"
            if re.search(rf"(?i)\blab\s*#?\s*{number}|lab{number}", combined.replace("_", "")):
                if re.search(r"(?i)(?:lecture|lec)\s*#?\s*\d", combined) and not re.search(
                    r"(?i)\blab", combined
                ):
                    continue
                lab_only.append(s)
        if lab_only:
            sources = lab_only

    best_source = max(sources, key=lambda d: _source_score(d, kind, number))
    source_len = _content_len(best_source)

    candidates = [r for r in rows if not r.get("hidden_duplicate")]
    if not candidates:
        candidates = rows
    canonical = max(candidates, key=lambda d: _canonical_score(d, kind))
    canonical_id = str(canonical.get("material_id") or "")
    stored_kind = str(canonical.get("material_kind") or "").lower()
    if kind == "lecture" and stored_kind.startswith("lab"):
        canonical_id = f"repair_lecture_{number}"
    elif kind == "lab" and stored_kind.startswith("lecture"):
        canonical_id = f"repair_lab_{number}"
    if not canonical_id:
        canonical_id = f"repair_{kind}_{number}"

    content_fields = _content_fields_from_doc(best_source)
    text = (content_fields.get("content_text") or "").strip()
    clen = len(text) if text else source_len
    ready = _ready_fields(clen)
    display_title = _display_title(kind, number, best_source)
    now = datetime.utcnow()

    material_repository.upsert(
        {
            "course_id": course_id,
            "material_id": canonical_id,
            "title": display_title,
            "file_type": canonical.get("file_type") or best_source.get("file_type") or "pdf",
            "material_kind": kind,
            "material_number": number,
            "content_text": text,
            "content_text_length": clen,
            "content_chars": clen,
            "content_hash": content_fields.get("content_hash") or best_source.get("content_hash"),
            "content_source": _IMPORT_SOURCE if clen > 0 else best_source.get("content_source"),
            "source_note": _SOURCE_NOTE if clen > 0 else None,
            "processed_at": now,
            "metadata_only": False,
            "hidden_duplicate": False,
            "duplicate_of": None,
            "demo_quiz_hidden": False,
            "visible_in_main_list": True,
            **ready,
        }
    )

    best_source_id = str(best_source.get("material_id") or "")
    if best_source_id and best_source_id != canonical_id:
        material_repository.upsert(
            {
                "course_id": course_id,
                "material_id": best_source_id,
                "title": best_source.get("title"),
                "file_type": best_source.get("file_type"),
                "duplicate_of": canonical_id,
                "hidden_duplicate": True,
            }
        )

    for row in rows:
        rid = str(row.get("material_id") or "")
        if not rid or rid in (canonical_id, best_source_id):
            continue
        material_repository.upsert(
            {
                "course_id": course_id,
                "material_id": rid,
                "title": row.get("title"),
                "file_type": row.get("file_type"),
                "duplicate_of": canonical_id,
                "hidden_duplicate": True,
            }
        )

    return {
        "course_id": course_id,
        "kind": kind,
        "number": number,
        "fixed": True,
        "not_found": False,
        "canonical_row_id": canonical_id,
        "canonical_title": display_title,
        "source_title": best_source.get("title"),
        "source_content_text_length": source_len,
        "quiz_status": ready.get("quiz_status"),
    }


def doc_get(doc: Dict[str, Any], key: str) -> Any:
    return doc.get(key)


def repair_all_demo_targets() -> Dict[str, Any]:
    results = [repair_target(cid, kind, num) for cid, kind, num in REPAIR_TARGETS]
    fixed = [r for r in results if r.get("fixed")]
    missing = [r for r in results if not r.get("fixed")]
    return {
        "fixed_count": len(fixed),
        "not_found_count": len(missing),
        "fixed_rows": fixed,
        "missing_targets": missing,
    }

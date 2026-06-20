"""
Surgical repair for specific lab rows (666 Lab 2, 808 Lab 2, 808 Lab 4).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.repositories import material_repository
from app.services.material_quiz_display import (
    _LAB_NUM_EMBEDDED_RE,
    _LAB_NUM_RE,
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
_MIN_SOURCE_CHARS = 301

TARGETS: List[Tuple[str, int]] = [
    ("666", 2),
    ("808", 2),
    ("808", 4),
]


def _content_len(doc: Dict[str, Any]) -> int:
    return _material_stored_content_length(doc)


def _matches_lab_number(doc: Dict[str, Any], lab_num: int) -> bool:
    title = str(doc.get("title") or "")
    fn = str(doc.get("original_filename") or "")
    ft = str(doc.get("file_type") or "")
    combined = f"{title} {fn}"

    if re.search(r"(?i)\blecture\s*#?\s*\d", combined) and not re.search(
        r"(?i)\blab\s*#?\s*\d", combined
    ):
        return False

    is_non, _ = classify_non_quiz_material(title, ft)
    kind = str(doc.get("material_kind") or "")
    if not kind or kind == "other_moodle_item":
        kind = classify_material_kind(title, ft, is_non)
    if kind in ("lecture", "lecture_link"):
        return False

    resolved = resolve_material_number(doc, title, kind if kind in ("lab", "lab_link") else "lab")
    if kind in ("lab", "lab_link") and resolved == lab_num:
        return True

    for src in (title, fn):
        if not src:
            continue
        if re.search(rf"(?i)\blab\s*#?\s*{lab_num}(?:\b|[^0-9])", src):
            return True
        if re.search(rf"(?i)lab{lab_num}(?:\b|[^0-9])", src.replace(" ", "").replace("_", "")):
            return True
        embedded = _LAB_NUM_EMBEDDED_RE.search(src)
        if embedded:
            n = embedded.group(1) or embedded.group(2)
            if n and int(n) == lab_num:
                return True
    return False


def _canonical_lab_score(doc: Dict[str, Any]) -> int:
    score = _canonical_learning_row_score(doc)
    if doc.get("hidden_duplicate"):
        score -= 500
    if doc.get("demo_quiz_hidden"):
        score -= 500
    if str(doc.get("material_id") or "").startswith("url_"):
        score -= 100
    score += min(_content_len(doc) // 100, 80)
    return score


def _find_lab_rows(course_id: str, lab_num: int) -> List[Dict[str, Any]]:
    return [
        d
        for d in material_repository.list_by_course(course_id)
        if _matches_lab_number(d, lab_num)
    ]


def repair_specific_lab(course_id: str, lab_num: int) -> Dict[str, Any]:
    course_id = str(course_id).strip()
    rows = _find_lab_rows(course_id, lab_num)

    if not rows:
        return {
            "course_id": course_id,
            "lab_number": lab_num,
            "fixed": False,
            "not_found": True,
            "reason": "no_matching_lab_rows",
        }

    sources = [r for r in rows if _content_len(r) >= _MIN_SOURCE_CHARS]
    if not sources:
        return {
            "course_id": course_id,
            "lab_number": lab_num,
            "fixed": False,
            "not_found": True,
            "reason": "no_source_with_content_over_300",
            "matching_titles": [r.get("title") for r in rows],
        }

    def _source_score(doc: Dict[str, Any]) -> int:
        score = _content_len(doc)
        if doc.get("content_source") == _IMPORT_SOURCE:
            score += 5000
        fn = str(doc.get("original_filename") or "").lower()
        title = str(doc.get("title") or "").lower()
        if re.search(rf"(?:^|[^0-9])lab\s*#?\s*{lab_num}(?:[^0-9]|$)", fn + title):
            score += 2000
        if re.search(rf"lab{lab_num}", fn.replace("_", "")):
            score += 1500
        return score

    best_source = max(sources, key=_source_score)
    source_len = _content_len(best_source)

    candidates = [
        r
        for r in rows
        if not r.get("hidden_duplicate")
        and (
            str(r.get("material_kind") or "").lower() in ("lab", "lab_link")
            or re.search(r"(?i)\blab", str(r.get("title") or ""))
            or re.search(r"(?i)lab", str(r.get("original_filename") or ""))
        )
    ]
    if not candidates:
        candidates = rows
    canonical = max(candidates, key=_canonical_lab_score)
    canonical_id = str(canonical.get("material_id") or "")
    if not canonical_id:
        canonical_id = f"repair_lab_{lab_num}"
        canonical = {"material_id": canonical_id, "title": f"Lab {lab_num}"}

    content_fields = _content_fields_from_doc(best_source)
    text = (content_fields.get("content_text") or "").strip()
    now = datetime.utcnow()
    clen = len(text) if text else source_len

    material_repository.upsert(
        {
            "course_id": course_id,
            "material_id": canonical_id,
            "title": f"Lab {lab_num}",
            "file_type": canonical.get("file_type") or best_source.get("file_type") or "pdf",
            "material_kind": "lab",
            "material_number": lab_num,
            "content_text": text,
            "content_text_length": clen,
            "content_chars": clen,
            "content_hash": content_fields.get("content_hash") or best_source.get("content_hash"),
            "extraction_status": "success",
            "extraction_error": None,
            "quiz_status": "ready",
            "ready_for_quiz": True,
            "quiz_generation_eligible": True,
            "content_source": _IMPORT_SOURCE,
            "source_note": _SOURCE_NOTE,
            "processed_at": now,
            "metadata_only": False,
            "hidden_duplicate": False,
            "duplicate_of": None,
            "demo_quiz_hidden": False,
            "visible_in_main_list": True,
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
                "demo_quiz_hidden": False,
            }
        )

    for row in rows:
        rid = str(row.get("material_id") or "")
        if not rid or rid == canonical_id or rid == best_source_id:
            continue
        if _content_len(row) > 0 and rid != best_source_id:
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
        "lab_number": lab_num,
        "fixed": True,
        "not_found": False,
        "canonical_row_id": canonical_id,
        "source_title": best_source.get("title"),
        "source_content_text_length": source_len,
        "canonical_content_text_length": clen,
    }


def repair_all_targets() -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    fixed_count = 0
    not_found_count = 0
    for course_id, lab_num in TARGETS:
        result = repair_specific_lab(course_id, lab_num)
        results.append(result)
        if result.get("fixed"):
            fixed_count += 1
        else:
            not_found_count += 1
    return {
        "fixed_count": fixed_count,
        "not_found_count": not_found_count,
        "results": results,
    }

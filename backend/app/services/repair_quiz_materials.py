"""
Repair MongoDB course materials for Quiz Generation demo readiness.

Merges imported content into canonical lecture/lab rows, hides non-demo items,
marks ready/limited by content length, and deduplicates.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from app.repositories import material_repository, metrics_repository, user_repository
from app.services.material_quiz_display import (
    _DEMO_LIMITED_MIN_CHARS,
    _DEMO_READY_MIN_CHARS,
    _IMPORT_SOURCE,
    _LAB_NUM_EMBEDDED_RE,
    _LAB_NUM_RE,
    _LECTURE_NUM_RE,
    classify_material_kind,
    classify_non_quiz_material,
    is_core_demo_material_kind,
    is_demo_hidden_title,
    is_standalone_exercise_title,
    resolve_material_number,
)
from app.services.material_quiz_upload import (
    _canonical_learning_row_score,
    _content_fields_from_doc,
    _derive_readiness_from_probe,
)
from app.services.student_data import _material_stored_content_length

_DEMO_HIDDEN_EXTRA_RE = re.compile(
    r"(?i)^(?:test\s+notes|algorithm\s+steps|multi\s+class\s+classification)"
)


def _content_len(doc: Dict[str, Any]) -> int:
    return _material_stored_content_length(doc)


def _group_key(doc: Dict[str, Any]) -> Optional[Tuple[str, int]]:
    title = str(doc.get("title") or "")
    fn = str(doc.get("original_filename") or "")
    is_non, _ = classify_non_quiz_material(title, str(doc.get("file_type") or ""))
    kind = str(doc.get("material_kind") or "")
    if not kind or kind == "other_moodle_item":
        kind = classify_material_kind(title, str(doc.get("file_type") or ""), is_non)
    num = resolve_material_number(doc, title, kind)
    for src in (title, fn):
        if _LECTURE_NUM_RE.search(src):
            m = _LECTURE_NUM_RE.search(src)
            if m:
                return ("lecture", int(m.group(1)))
        lab_m = _LAB_NUM_RE.search(src) or _LAB_NUM_EMBEDDED_RE.search(src)
        if lab_m:
            n = lab_m.group(1) or lab_m.group(2)
            if n:
                return ("lab", int(n))
    if "revision" in kind or re.search(r"(?i)revision", title):
        if re.search(r"(?i)final\s+revision", title):
            return ("revision", 0)
        return ("revision", num if num < 9999 else 0)
    if kind in ("lecture", "lecture_link") and num < 9999:
        return ("lecture", num)
    if kind in ("lab", "lab_link") and num < 9999:
        return ("lab", num)
    return None


def _canonical_pick_score(doc: Dict[str, Any]) -> int:
    score = _canonical_learning_row_score(doc)
    if doc.get("content_source") == _IMPORT_SOURCE:
        score -= 40
    if doc.get("demo_quiz_hidden"):
        score -= 200
    if doc.get("hidden_duplicate"):
        score -= 200
    score += min(_content_len(doc) // 100, 80)
    if doc.get("ready_for_quiz"):
        score += 30
    qs = str(doc.get("quiz_status") or "")
    if qs == "ready":
        score += 50
    return score


def _should_hide_demo(doc: Dict[str, Any]) -> bool:
    title = str(doc.get("title") or "")
    ft = str(doc.get("file_type") or "")
    if doc.get("demo_quiz_hidden"):
        return True
    if is_standalone_exercise_title(title):
        return True
    if is_demo_hidden_title(title):
        return True
    if _DEMO_HIDDEN_EXTRA_RE.search(title):
        return True
    is_non, _ = classify_non_quiz_material(title, ft)
    kind = str(doc.get("material_kind") or classify_material_kind(title, ft, is_non))
    clen = _content_len(doc)
    if not is_core_demo_material_kind(kind, title):
        if clen < 1000:
            return True
    return False


def _mark_ready_fields(doc: Dict[str, Any], text: str, file_type: str) -> Dict[str, Any]:
    clen = len(text.strip())
    probe = _derive_readiness_from_probe(text, file_type)
    if clen > _DEMO_READY_MIN_CHARS - 1:
        quiz_status = "ready"
        ready = True
        extraction_status = "success"
    elif clen >= _DEMO_LIMITED_MIN_CHARS:
        quiz_status = "limited_ready"
        ready = True
        extraction_status = "success"
    else:
        quiz_status = "extraction_too_short"
        ready = False
        extraction_status = "insufficient_text"
    return {
        "content_text": text,
        "content_chars": clen,
        "content_text_length": clen,
        "ready_for_quiz": ready,
        "quiz_status": quiz_status,
        "quiz_generation_eligible": clen >= _DEMO_LIMITED_MIN_CHARS,
        "extraction_status": extraction_status,
        "extraction_error": None if ready else probe.get("extraction_error"),
        "metadata_only": False,
        "probe_question_count": probe.get("probe_question_count"),
        "probe_engine": probe.get("probe_engine"),
        "processed_at": datetime.utcnow(),
    }


def merge_imported_into_canonical(course_id: str) -> List[Dict[str, Any]]:
    """Copy imported / richer content onto canonical Moodle file rows."""
    course_id = str(course_id).strip()
    docs = [d for d in material_repository.list_by_course(course_id) if not d.get("hidden_duplicate")]
    groups: Dict[Tuple[str, int], List[Dict[str, Any]]] = defaultdict(list)

    for doc in docs:
        key = _group_key(doc)
        if key:
            groups[key].append(doc)

    actions: List[Dict[str, Any]] = []
    for key, group in groups.items():
        if not group:
            continue
        by_content = sorted(group, key=lambda d: _content_len(d), reverse=True)
        richest = by_content[0]
        richest_len = _content_len(richest)
        canonical = max(group, key=_canonical_pick_score)
        canonical_id = str(canonical.get("material_id") or "")
        canonical_len = _content_len(canonical)

        if richest_len > canonical_len and str(richest.get("material_id")) != canonical_id:
            donor = richest
            donor_id = str(donor.get("material_id") or "")
            content_fields = _content_fields_from_doc(donor)
            text = (content_fields.get("content_text") or "").strip()
            ft = str(canonical.get("file_type") or donor.get("file_type") or "pdf")
            ready_fields = _mark_ready_fields(canonical, text, ft)
            material_repository.upsert(
                {
                    "course_id": course_id,
                    "material_id": canonical_id,
                    "title": canonical.get("title"),
                    "file_type": canonical.get("file_type"),
                    **content_fields,
                    **ready_fields,
                    "hidden_duplicate": False,
                    "duplicate_of": None,
                    "demo_quiz_hidden": False,
                }
            )
            if donor_id != canonical_id:
                material_repository.upsert(
                    {
                        "course_id": course_id,
                        "material_id": donor_id,
                        "duplicate_of": canonical_id,
                        "hidden_duplicate": True,
                        "content_text": "",
                        "content_chars": 0,
                        "content_text_length": 0,
                        "metadata_only": True,
                        "ready_for_quiz": False,
                        "quiz_status": "not_quiz_material",
                        "extraction_status": "not_quiz_material",
                        "extraction_error": f"Content merged to canonical row {canonical_id}",
                    }
                )
            actions.append(
                {
                    "action": "merged",
                    "kind": key[0],
                    "number": key[1],
                    "from_material_id": donor_id,
                    "from_title": donor.get("title"),
                    "to_material_id": canonical_id,
                    "to_title": canonical.get("title"),
                    "chars_moved": richest_len,
                }
            )
            canonical_len = richest_len

        if canonical_len > 0:
            doc = material_repository.get(course_id, canonical_id) or canonical
            if not doc.get("ready_for_quiz") or str(doc.get("quiz_status") or "") not in (
                "ready", "limited_ready",
            ):
                text = (doc.get("content_text") or "").strip()
                if text:
                    ready_fields = _mark_ready_fields(
                        doc, text, str(doc.get("file_type") or "pdf"),
                    )
                    material_repository.upsert(
                        {
                            "course_id": course_id,
                            "material_id": canonical_id,
                            "title": doc.get("title"),
                            "file_type": doc.get("file_type"),
                            **ready_fields,
                        }
                    )
                    actions.append(
                        {
                            "action": "marked_ready",
                            "material_id": canonical_id,
                            "title": doc.get("title"),
                            "chars": canonical_len,
                            "quiz_status": ready_fields["quiz_status"],
                        }
                    )

    return actions


def hide_non_demo_rows(course_id: str) -> List[Dict[str, Any]]:
    course_id = str(course_id).strip()
    hidden: List[Dict[str, Any]] = []
    for doc in material_repository.list_by_course(course_id):
        if doc.get("hidden_duplicate"):
            continue
        if not _should_hide_demo(doc):
            continue
        mid = str(doc.get("material_id") or "")
        if not mid:
            continue
        material_repository.upsert(
            {
                "course_id": course_id,
                "material_id": mid,
                "title": doc.get("title"),
                "file_type": doc.get("file_type"),
                "demo_quiz_hidden": True,
                "extraction_status": "not_quiz_material",
                "quiz_status": "not_quiz_material",
                "ready_for_quiz": False,
                "quiz_generation_eligible": False,
            }
        )
        hidden.append({"material_id": mid, "title": doc.get("title")})
    return hidden


def deduplicate_course(course_id: str) -> List[Dict[str, Any]]:
    """Hide weaker duplicates in each lecture/lab/revision group."""
    course_id = str(course_id).strip()
    docs = material_repository.list_by_course(course_id)
    groups: Dict[Tuple[str, int], List[Dict[str, Any]]] = defaultdict(list)
    for doc in docs:
        if doc.get("hidden_duplicate") or doc.get("demo_quiz_hidden"):
            continue
        key = _group_key(doc)
        if key:
            groups[key].append(doc)

    hidden: List[Dict[str, Any]] = []
    for key, group in groups.items():
        if len(group) < 2:
            continue
        ranked = sorted(group, key=_canonical_pick_score, reverse=True)
        winner = ranked[0]
        winner_id = str(winner.get("material_id") or "")
        for loser in ranked[1:]:
            loser_id = str(loser.get("material_id") or "")
            if not loser_id or loser_id == winner_id:
                continue
            if _content_len(loser) > _content_len(winner) and loser.get("content_source") == _IMPORT_SOURCE:
                continue
            material_repository.upsert(
                {
                    "course_id": course_id,
                    "material_id": loser_id,
                    "title": loser.get("title"),
                    "file_type": loser.get("file_type"),
                    "hidden_duplicate": True,
                    "duplicate_of": winner_id,
                    "visible_in_main_list": False,
                }
            )
            hidden.append(
                {
                    "material_id": loser_id,
                    "title": loser.get("title"),
                    "duplicate_of": winner_id,
                    "kind": key[0],
                    "number": key[1],
                }
            )
    return hidden


def repair_course(course_id: str) -> Dict[str, Any]:
    merged = merge_imported_into_canonical(course_id)
    hidden = hide_non_demo_rows(course_id)
    deduped = deduplicate_course(course_id)
    merge_imported_into_canonical(course_id)

    from app.services.material_quiz_display import resolve_quiz_material_display

    docs = material_repository.list_by_course(course_id)
    displays, _ = resolve_quiz_material_display(docs)
    ready_rows = [
        d.get("title")
        for d in displays
        if d.get("visible_in_main_list")
        and d.get("quiz_status") in ("ready", "limited_ready")
    ]
    not_synced = [
        {
            "title": d.get("title"),
            "material_id": d.get("material_id"),
            "quiz_status": d.get("quiz_status"),
            "content_text_length": d.get("content_text_length"),
        }
        for d in displays
        if d.get("is_educational_material")
        and is_core_demo_material_kind(
            str(d.get("material_kind") or ""), str(d.get("title") or ""),
        )
        and d.get("quiz_status") == "not_uploaded"
    ]

    return {
        "course_id": course_id,
        "merged_actions": merged,
        "hidden_rows": hidden,
        "deduplicated_rows": deduped,
        "ready_main_list_count": len(ready_rows),
        "ready_titles": ready_rows,
        "remaining_not_synced_educational": not_synced,
    }


def repair_user_courses(email: str) -> Dict[str, Any]:
    email = (email or "").strip().lower()
    user = user_repository.find_by_email(email)
    course_ids: Set[str] = set()
    if user:
        for m in metrics_repository.list_for_user(str(user["_id"])):
            cid = m.get("course_id")
            if cid and str(cid) != "_overall":
                course_ids.add(str(cid))
    from app.config.database import course_materials_collection

    for doc in course_materials_collection.find({}, {"course_id": 1}):
        if doc.get("course_id"):
            course_ids.add(str(doc["course_id"]))

    results = [repair_course(cid) for cid in sorted(course_ids)]
    return {
        "email": email,
        "user_found": user is not None,
        "courses_repaired": len(results),
        "courses": results,
    }

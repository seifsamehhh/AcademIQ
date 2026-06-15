"""
Moodle payload normalization.

Turns a (possibly duplicated) extension payload into the normalized collections:

    course_materials   — each material stored ONCE, deduped by (course_id, material_id)
    student_metrics    — per-(user, course) metric snapshots + overall behaviour
    student_events     — per-user event stream, deduped by event id

`materials_from_payload` understands BOTH the new slim shape (a single
`materials` array) and the legacy duplicated shapes
(`learning_materials` / `materialsByCourse` / `knowledge_base`), so the same
code powers live ingestion and the one-off migration of old documents.
"""

from typing import Any, Dict, List, Optional

from app.models.material import build_material_doc, stable_material_id
from app.repositories import (
    event_repository,
    material_repository,
    metrics_repository,
)

# Fields removed from the raw payload before it's stored for audit — these are
# the duplicated material/event structures now normalized into their own
# collections.
_HEAVY_FIELDS = (
    "materials",
    "learning_materials",
    "materialsByCourse",
    "knowledge_base",
    "events",
)


# Course "links" that aren't real enrolled courses (Moodle site home is id 1).
_GENERIC_COURSE_NAMES = {"my courses", "home", "dashboard", "site home", "my moodle", "courses", "profile"}


def is_real_course(course_id: Any, name: str = None) -> bool:
    """Reject the dashboard / site-home (id 1) / nav links masquerading as courses."""
    cid = str(course_id or "").strip()
    if not cid.isdigit() or cid == "1":
        return False
    if name and name.strip().lower() in _GENERIC_COURSE_NAMES:
        return False
    return True


def _is_bare_course_name(name: Optional[str], course_id: Any) -> bool:
    cid = str(course_id or "").strip()
    n = (name or "").strip()
    if not n:
        return True
    if n == cid or n == f"Course {cid}":
        return True
    cleaned = n
    if cleaned.lower().startswith("course "):
        cleaned = cleaned[7:].strip()
    return cleaned == cid or cleaned.isdigit()


def _course_name_map(payload: Dict[str, Any], academiq_user_id: str = "") -> Dict[str, str]:
    """Build course_id -> course_name, preferring real titles over numeric fallbacks."""
    del academiq_user_id  # reserved for future metrics lookup during ingest
    names: Dict[str, str] = {}

    def consider(cid: Any, name: Any) -> None:
        cid_str = str(cid or "").strip()
        if not cid_str or not name:
            return
        cleaned = str(name).strip()
        if cleaned.lower().startswith("course "):
            cleaned = cleaned[7:].strip()
        existing = names.get(cid_str)
        if not existing:
            names[cid_str] = cleaned
            return
        if _is_bare_course_name(existing, cid_str) and not _is_bare_course_name(cleaned, cid_str):
            names[cid_str] = cleaned
        elif not _is_bare_course_name(cleaned, cid_str) and len(cleaned) > len(existing):
            names[cid_str] = cleaned

    for course in payload.get("courses", []) or []:
        consider(course.get("course_id"), course.get("course_name"))
    for cid, metrics in (payload.get("metricsByCourse") or {}).items():
        consider(cid, metrics.get("course_name"))
    return names


def materials_from_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Return a flat, de-duplicated list of scraped materials from a payload,
    supporting both the new (`materials`) and legacy shapes. Dedup key is
    (course_id, material_id).
    """
    raw: List[Dict[str, Any]] = []

    if isinstance(payload.get("materials"), list):
        raw = list(payload["materials"])
    else:
        # Legacy shapes (used by the migration of existing documents).
        raw.extend(payload.get("learning_materials", []) or [])
        for items in (payload.get("materialsByCourse") or {}).values():
            raw.extend(items or [])
        for course in (payload.get("knowledge_base") or {}).values():
            for items in (course or {}).values():
                raw.extend(items or [])

    seen = set()
    unique: List[Dict[str, Any]] = []
    for material in raw:
        cid = str(material.get("course_id") or material.get("courseId") or "")
        mid = stable_material_id(material)
        if not mid:
            continue
        key = (cid, mid)
        if key in seen:
            continue
        seen.add(key)
        unique.append(material)
    return unique


def normalize_payload(payload: Dict[str, Any], academiq_user_id: str) -> Dict[str, Any]:
    """
    Write a payload's materials / metrics / events into the normalized
    collections. Returns a summary with dedup counts.
    """
    names = _course_name_map(payload, academiq_user_id)

    # --- Materials → course_materials (upsert, deduped) -------------------
    materials = materials_from_payload(payload)
    materials_new = 0
    for material in materials:
        cid = material.get("course_id") or material.get("courseId")
        if not is_real_course(cid, names.get(str(cid or ""))):
            continue  # skip site-home / nav "courses"
        doc = build_material_doc(material, cid, names.get(str(cid or "")))
        if doc is None:
            continue
        doc["source"] = "moodle_sync"
        if material_repository.upsert(doc):
            materials_new += 1

    # Materials are course-scoped, so they're stored even without a user. The
    # per-student collections below require a user id; skip them if absent.
    if not academiq_user_id:
        return {
            "materials_seen": len(materials),
            "materials_new": materials_new,
            "metrics_courses": 0,
            "events_new": 0,
        }

    # --- Metrics → student_metrics (per course + overall) ----------------
    metrics_by_course = payload.get("metricsByCourse") or {}
    if not metrics_by_course:
        # Fall back to the courses array if metricsByCourse isn't present.
        metrics_by_course = {
            str(c.get("course_id")): c
            for c in payload.get("courses", []) or []
            if c.get("course_id")
        }
    for course_id, metrics in metrics_by_course.items():
        if not is_real_course(course_id, (metrics or {}).get("course_name")):
            continue  # skip the bogus "My courses" (id 1) etc.
        course_metrics = dict(metrics or {})
        course_metrics["activity_source"] = "synced"
        metrics_repository.upsert(academiq_user_id, str(course_id), course_metrics)

    behavior = payload.get("behavior")
    if behavior:
        overall = dict(behavior)
        overall["activity_source"] = "synced"
        metrics_repository.upsert(academiq_user_id, metrics_repository.OVERALL, overall)

    # --- Events → student_events (deduped) -------------------------------
    events_new = event_repository.upsert_many(academiq_user_id, payload.get("events", []))

    return {
        "materials_seen": len(materials),
        "materials_new": materials_new,
        "metrics_courses": len(metrics_by_course),
        "events_new": events_new,
    }


def slim_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of the payload without the heavy/duplicated structures.

    Used for the audit record kept in `raw_moodle_payload_collection`.
    """
    return {k: v for k, v in payload.items() if k not in _HEAVY_FIELDS}

"""Detect whether a user has live Moodle-synced data (vs seeded demo only)."""

from __future__ import annotations

from app.config.database import raw_moodle_payload_collection
from app.repositories import metrics_repository


def has_synced_moodle_data(user_id: str) -> bool:
    """True when this user has Moodle-synced metrics or a live raw payload."""
    for row in metrics_repository.list_for_user(user_id):
        metrics = row.get("metrics") or {}
        if metrics.get("activity_source") == "synced":
            return True

    raw = raw_moodle_payload_collection.find_one({"academiq_user_id": user_id})
    if not raw:
        return False
    if raw.get("grades_source") == "seeded":
        return False
    return bool(
        raw.get("sync_count")
        or raw.get("courses")
        or raw.get("metricsByCourse")
        or raw.get("behavior")
    )

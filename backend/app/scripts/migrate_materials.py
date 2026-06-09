"""
One-off migration: de-duplicate Moodle materials in existing records.

Converts old bloated `raw_moodle_payload` documents (which embedded the same
materials in `learning_materials` + `materialsByCourse` + `knowledge_base`) into
the normalized collections:

    course_materials   (each material stored ONCE)
    student_metrics
    student_events

and then slims each raw payload by removing the duplicated arrays.

Safe by default: runs as a DRY RUN unless `--apply` is passed. With `--apply`
it first writes a JSON backup of the raw payloads to backend/backups/.

Usage (from backend/, venv active):
    python -m app.scripts.migrate_materials            # dry run (no writes)
    python -m app.scripts.migrate_materials --apply     # backup + migrate
"""

import argparse
import os
from datetime import datetime

import bson
from bson import json_util

from app.config.database import (
    course_materials_collection,
    ensure_indexes,
    raw_moodle_payload_collection,
    student_events_collection,
    student_metrics_collection,
)
from app.services.moodle_ingest import (
    _HEAVY_FIELDS,
    materials_from_payload,
    normalize_payload,
)
from app.services.user_provisioning import extract_identity, resolve_or_create_user

BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "backups")


def _bson_size(doc) -> int:
    try:
        return len(bson.BSON.encode(doc))
    except Exception:
        return 0


def _counts() -> dict:
    return {
        "course_materials": course_materials_collection.count_documents({}),
        "student_metrics": student_metrics_collection.count_documents({}),
        "student_events": student_events_collection.count_documents({}),
    }


def backup() -> str:
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(BACKUP_DIR, f"raw_moodle_payloads_{ts}.json")
    docs = list(raw_moodle_payload_collection.find())
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json_util.dumps(docs, indent=2))
    print(f"[backup] wrote {len(docs)} raw payload(s) -> {path}")
    return path


def migrate(apply: bool) -> None:
    ensure_indexes()
    payloads = list(raw_moodle_payload_collection.find())

    before_bytes = sum(_bson_size(d) for d in payloads)
    print(f"\nMode: {'APPLY' if apply else 'DRY RUN (no writes)'}")
    print(f"Raw payloads: {len(payloads)}  (total {before_bytes/1024:.1f} KB)")
    print(f"Before -> {_counts()}")

    if apply:
        backup()

    total_unique_materials = 0
    for doc in payloads:
        # Dry run is strictly read-only: count unique materials, write nothing.
        unique = materials_from_payload(doc)
        total_unique_materials += len(unique)
        if not apply:
            continue

        uid = doc.get("academiq_user_id")
        if not uid:
            # Legacy doc without a linked account — resolve by Moodle identity
            # (creating one only when applying the migration).
            user, _, _, _ = resolve_or_create_user(extract_identity(doc), payload=doc)
            uid = str(user["_id"])

        normalize_payload(doc, uid)
        raw_moodle_payload_collection.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {"academiq_user_id": uid},
                "$unset": {field: "" for field in _HEAVY_FIELDS},
            },
        )

    print(f"\nUnique materials found across payloads: {total_unique_materials}")

    if apply:
        slimmed = list(raw_moodle_payload_collection.find())
        after_bytes = sum(_bson_size(d) for d in slimmed)
        print(f"After  -> {_counts()}")
        print(
            f"Raw payload size: {before_bytes/1024:.1f} KB -> {after_bytes/1024:.1f} KB "
            f"({100*(before_bytes-after_bytes)/before_bytes:.0f}% smaller)"
            if before_bytes else ""
        )
        print("\n[done] Migration applied.")
    else:
        print("\n[dry run] No changes written. Re-run with --apply to migrate.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="De-duplicate Moodle materials.")
    parser.add_argument("--apply", action="store_true", help="Actually write changes (default: dry run).")
    args = parser.parse_args()
    migrate(apply=args.apply)

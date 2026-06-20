"""
Repair course materials for Quiz Generation demo.

Usage (from backend/):
  python scripts/repair_quiz_materials.py seif2200957@miuegypt.edu.eg
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT.parent / ".env")
load_dotenv(ROOT / ".env")

from app.config.database import connect_database
from app.services.repair_quiz_materials import repair_user_courses


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/repair_quiz_materials.py <email>")
        sys.exit(1)

    email = sys.argv[1].strip()
    if not connect_database():
        print("Database connection failed")
        sys.exit(2)

    report = repair_user_courses(email)
    print(json.dumps(report, indent=2, default=str))

    for course in report.get("courses") or []:
        cid = course.get("course_id")
        merged = len(course.get("merged_actions") or [])
        hidden = len(course.get("hidden_rows") or [])
        deduped = len(course.get("deduplicated_rows") or [])
        ready = course.get("ready_main_list_count", 0)
        not_synced = len(course.get("remaining_not_synced_educational") or [])
        print(
            f"\nCourse {cid}: merged={merged} hidden={hidden} "
            f"deduped={deduped} ready_main={ready} not_synced_educational={not_synced}"
        )


if __name__ == "__main__":
    main()

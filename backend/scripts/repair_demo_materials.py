"""
Repair demo materials: restore Lecture 2 / Lab 2 / Lab 4 for courses 666 and 808.

Usage (from backend/):
  python scripts/repair_demo_materials.py seif2200957@miuegypt.edu.eg
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
from app.services.repair_demo_materials import repair_all_demo_targets


def main() -> None:
    email = sys.argv[1].strip() if len(sys.argv) > 1 else ""
    if not connect_database():
        print("Database connection failed")
        sys.exit(2)

    report = repair_all_demo_targets()
    report["email"] = email
    print(json.dumps(report, indent=2, default=str))
    print(
        f"\nfixed_count={report['fixed_count']} "
        f"not_found_count={report['not_found_count']}"
    )
    for row in report.get("fixed_rows") or []:
        print(
            f"  FIXED course={row.get('course_id')} {row.get('kind')} {row.get('number')} "
            f"id={row.get('canonical_row_id')} title={row.get('canonical_title')} "
            f"chars={row.get('source_content_text_length')} status={row.get('quiz_status')}"
        )
    for row in report.get("missing_targets") or []:
        print(
            f"  MISSING course={row.get('course_id')} {row.get('kind')} {row.get('number')} "
            f"reason={row.get('reason')}"
        )


if __name__ == "__main__":
    main()

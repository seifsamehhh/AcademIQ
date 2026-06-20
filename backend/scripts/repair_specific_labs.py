"""
Surgical repair for AAI 666 Lab 2 and DIA 808 Lab 2 / Lab 4.

Usage (from backend/):
  python scripts/repair_specific_labs.py seif2200957@miuegypt.edu.eg
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
from app.services.repair_specific_labs import repair_all_targets


def main() -> None:
    email = sys.argv[1].strip() if len(sys.argv) > 1 else ""
    if not connect_database():
        print("Database connection failed")
        sys.exit(2)

    report = repair_all_targets()
    report["email"] = email
    print(json.dumps(report, indent=2, default=str))
    print(
        f"\nfixed_count={report['fixed_count']} "
        f"not_found_count={report['not_found_count']}"
    )
    for row in report.get("results") or []:
        status = "FIXED" if row.get("fixed") else "NOT FOUND"
        print(
            f"  [{status}] course={row.get('course_id')} lab={row.get('lab_number')} "
            f"canonical={row.get('canonical_row_id')} "
            f"source={row.get('source_title')} "
            f"chars={row.get('source_content_text_length')}"
        )


if __name__ == "__main__":
    main()

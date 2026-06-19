"""
Audit material extraction cache for a course.

Usage:
  python scripts/audit_material_cache.py seif2200957@miuegypt.edu.eg 666
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
from app.services.material_cache import audit_material_cache


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python scripts/audit_material_cache.py <email> <course_id>")
        sys.exit(1)

    email = sys.argv[1]
    course_id = sys.argv[2]

    if not connect_database():
        print("Database connection failed")
        sys.exit(2)

    report = audit_material_cache(email, course_id)
    print(json.dumps(report, indent=2, default=str))
    print(
        "\n--- Summary ---\n"
        f"Ready: {report.get('ready_count')} | "
        f"Limited: {report.get('limited_ready_count')} | "
        f"Imported: {report.get('imported_count')} "
        f"(ready: {report.get('imported_ready_count')}) | "
        f"Duplicates: {report.get('duplicates_count')} | "
        f"Missing expected: {len(report.get('missing_expected_materials') or [])}"
    )
    va = report.get("quiz_visibility_audit") or {}
    if va:
        print(
            "\n--- Quiz visibility ---\n"
            f"Visible lectures: {va.get('visible_lectures')} "
            f"(imported w/content: {va.get('expected_imported_lectures')}) | "
            f"Visible labs: {va.get('visible_labs')} "
            f"(imported w/content: {va.get('expected_imported_labs')}) | "
            f"Wrongly not uploaded: {len(va.get('wrongly_not_uploaded_imported') or [])} | "
            f"Wrongly in Other Moodle: {len(va.get('wrongly_classified_other_moodle') or [])}"
        )


if __name__ == "__main__":
    main()

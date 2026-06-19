"""
Import local course material files into MongoDB for Quiz Generation.

Usage (from backend/):
  python scripts/import_course_materials.py <email> <course_id|all> <import_folder>

Examples:
  python scripts/import_course_materials.py seif2200957@miuegypt.edu.eg 666 import_materials/666
  python scripts/import_course_materials.py seif2200957@miuegypt.edu.eg all import_materials

Options:
  --force   Re-import even when content_hash matches an existing course_material_import row
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT.parent / ".env")
load_dotenv(ROOT / ".env")

from app.config.database import connect_database
from app.services.course_material_import import (
    COURSE_NAMES,
    import_all_courses,
    import_course_folder,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import local course materials for quiz")
    parser.add_argument("email", help="Student email (audit / user lookup)")
    parser.add_argument(
        "course_id",
        help="Moodle course id (666, 808, …) or 'all' for every numeric subfolder",
    )
    parser.add_argument(
        "import_folder",
        help="Folder path relative to backend/ (e.g. import_materials/666 or import_materials)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-process even when import cache hash matches",
    )
    args = parser.parse_args()

    if not connect_database():
        print("Database connection failed")
        sys.exit(2)

    folder_arg = Path(args.import_folder)
    if not folder_arg.is_absolute():
        folder_arg = ROOT / folder_arg

    email = args.email.strip()
    course_id = args.course_id.strip().lower()

    if course_id == "all":
        summaries = import_all_courses(email, folder_arg, force=args.force)
        print(json.dumps([s.to_dict() for s in summaries], indent=2, default=str))
        total_imported = sum(s.imported_count for s in summaries)
        print(f"\nTotal imported/updated: {total_imported} across {len(summaries)} courses")
        sys.exit(0 if summaries else 1)

    if course_id not in COURSE_NAMES:
        print(f"Warning: course {course_id} not in known 26S map; proceeding anyway.")

    if course_id not in folder_arg.name and folder_arg.name != "import_materials":
        # Allow import_materials/666 when course is 666
        candidate = folder_arg / course_id
        if candidate.is_dir():
            folder_arg = candidate

    summary = import_course_folder(email, course_id, folder_arg, force=args.force)
    print(json.dumps(summary.to_dict(), indent=2, default=str))
    print(
        f"\nImported: {summary.imported_count} | "
        f"matched: {summary.matched_count} | "
        f"created: {summary.created_count} | "
        f"skipped: {summary.skipped_count} | "
        f"failed: {summary.failed_count}"
    )


if __name__ == "__main__":
    main()

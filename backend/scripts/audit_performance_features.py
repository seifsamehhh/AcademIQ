"""
CLI: python scripts/audit_performance_features.py {email}

Per-course ML feature audit with sources and trust eligibility.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from app.config.database import connect_database
from app.services.performance_feature_audit import audit_performance_features_for_email


def main() -> None:
    email = sys.argv[1] if len(sys.argv) > 1 else "seif2200957@miuegypt.edu.eg"
    if not connect_database():
        print("Database unavailable")
        sys.exit(1)
    report = audit_performance_features_for_email(email)
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()

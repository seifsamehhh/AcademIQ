"""Hardcoded demo dashboard results for seeded presentation accounts."""

from typing import Any, Dict

DEMO_RESULTS: Dict[str, Dict[str, Any]] = {
    "student1": {
        "name": "Seif Sameh",
        "gpa": 3.5,
        "risk": "Low",
        "courses": [
            {"name": "Programming", "grade": 85},
            {"name": "Database", "grade": 78},
            {"name": "Computer Vision", "grade": 82},
            {"name": "Artificial Intelligence", "grade": 88},
            {"name": "Software Engineering", "grade": 80},
        ],
    },
    "student2": {
        "name": "Aly Ehab",
        "gpa": 2.8,
        "risk": "Medium",
        "courses": [
            {"name": "Programming", "grade": 74},
            {"name": "Database", "grade": 69},
            {"name": "Web Development", "grade": 84},
            {"name": "Data Structures", "grade": 76},
            {"name": "Machine Learning", "grade": 72},
        ],
    },
}

DEMO_STUDENT_IDS = frozenset(DEMO_RESULTS.keys())

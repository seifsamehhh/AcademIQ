"""
conftest.py — shared fixtures for AcademIQ backend tests.

IMPORTANT: Set MONGODB_URI in your environment (or backend/.env) before
running these tests. The FastAPI app reads it at import time.
If you want to run tests without a real DB, the compute_features tests
are fully unit-level and do NOT touch MongoDB.
"""

import os
import sys
from pathlib import Path

# Make sure the project root is importable (same as what uvicorn does)
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

# Load .env before anything imports the app
from dotenv import load_dotenv
_env = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_env)

import pytest
from httpx import AsyncClient, ASGITransport


# ---------------------------------------------------------------------------
# Minimal payload builders
# ---------------------------------------------------------------------------

def make_session(start_ts: int = 1_700_000_000_000,
                 duration_ms: int = 3_600_000) -> dict:
    """Return a valid session dict (1 hour by default)."""
    return {
        "start": start_ts,
        "end": start_ts + duration_ms,
        "duration_ms": duration_ms,
    }


def make_assignment(title: str = "HW1",
                    grade: str = "18/20",
                    submitted: bool = True,
                    due_date: str = "2024-12-01T23:59:00",
                    submitted_at: str = "2024-11-30T20:00:00") -> dict:
    return {
        "title": title,
        "grade": grade,
        "submitted": submitted,
        "due_date": due_date,
        "submitted_at": submitted_at,
    }


def make_quiz(title: str = "Quiz 1",
              attempts: int = 1,
              score: float = 85.0,
              time_spent_ms: int = 600_000) -> dict:
    return {
        "title": title,
        "attempts": attempts,
        "score": score,
        "time_spent_ms": time_spent_ms,
    }


def make_course(course_id: str = "CS101",
                name: str = "Intro to CS",
                visits: int = 10,
                time_spent_ms: int = 7_200_000,
                assignments: list | None = None,
                quizzes: list | None = None,
                final_grade: str | None = "85%") -> dict:
    # Use `is None` check so that an explicit empty list ([]) stays empty
    return {
        "course_id": course_id,
        "name": name,
        "visits": visits,
        "time_spent_ms": time_spent_ms,
        "assignments": [make_assignment()] if assignments is None else assignments,
        "quizzes": [make_quiz()] if quizzes is None else quizzes,
        "final_grade": final_grade,
    }


def make_payload(student_id: str = "S001",
                 clicks: int = 42,
                 sessions: list | None = None,
                 courses: dict | None = None) -> dict:
    return {
        "student_id": student_id,
        "clicks": clicks,
        "lastActivity": 1_700_000_000_000,
        "sessions": sessions if sessions is not None else [make_session()],
        "courses": courses if courses is not None else {"CS101": make_course()},
    }


# ---------------------------------------------------------------------------
# Async HTTP client fixture (skips if MONGODB_URI is missing)
# ---------------------------------------------------------------------------

@pytest.fixture
async def client():
    """Async test client for the FastAPI app.

    Skipped automatically when MONGODB_URI is unavailable (offline / CI).
    The compute_features unit tests never use this fixture.
    """
    if not os.getenv("MONGODB_URI"):
        pytest.skip("MONGODB_URI not set — skipping integration tests")

    # Import inside fixture to defer DB connection until it's actually needed
    from backend.app.backend import app
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

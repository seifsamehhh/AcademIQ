"""
store.py — In-memory session and feature store for AcademIQ.

Provides always-available in-process storage.  MongoDB is the persistent
layer when reachable; this module is the fallback that keeps the app
working without a DB connection.

Populated by:
  POST /api/auth/login           → store_token()
  POST /ingest                   → store_features()  (via compute_features)
  POST /api/extension/sync       → store_features()  (via extension native format)
Read by:
  GET  /api/student/dashboard    → get_features()
  GET  /api/student/insights     → get_features()
"""
from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# Token / session store
# { token: { "username": str, "student_id": str, "created_at": datetime } }
# ---------------------------------------------------------------------------
_TOKEN_STORE: dict = {}


def store_token(token: str, username: str, student_id: str) -> None:
    _TOKEN_STORE[token] = {
        "username": username,
        "student_id": student_id,
        "created_at": datetime.utcnow(),
    }


def get_session(token: str) -> Optional[dict]:
    """Return session dict or None if token is unknown."""
    return _TOKEN_STORE.get(token)


# ---------------------------------------------------------------------------
# Feature store  (populated by /ingest or /api/extension/sync)
# { student_id: { "features": dict, "stored_at": datetime } }
# Keys match the output of compute_features():
#   total_time_spent, active_days, access_frequency,
#   avg_quiz_score, quiz_score_std, avg_assignment_score,
#   late_submission_ratio, avg_final_grade
# ---------------------------------------------------------------------------
_FEATURES_STORE: dict = {}


def store_features(student_id: str, features: dict) -> None:
    _FEATURES_STORE[student_id] = {
        "features": features,
        "stored_at": datetime.utcnow(),
    }


def get_features(student_id: str) -> Optional[dict]:
    """Return stored feature dict or None if not yet ingested."""
    entry = _FEATURES_STORE.get(student_id)
    return entry["features"] if entry else None

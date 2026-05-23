"""
extension.py — Chrome extension → backend sync endpoint.

POST /api/extension/sync
  Accepts the Chrome extension's native storage format (background.js schema),
  converts it to the compute_features() output format, and stores the features
  in the in-memory store keyed by the authenticated student's ID.

The endpoint requires  Authorization: Bearer <token>  from POST /api/auth/login.
This links the anonymous Moodle student_id (from the extension) to the
authenticated session so the dashboard can show real data.
"""
import statistics
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from ..store import get_session, store_features

router = APIRouter(prefix="/api/extension", tags=["Extension"])


# ── Token / session helpers ────────────────────────────────────────────────────

def _get_bearer_token(authorization: Optional[str] = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header",
        )
    return authorization.removeprefix("Bearer ").strip()


def _require_session(token: str = Depends(_get_bearer_token)) -> dict:
    session = get_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return session


# ── Extension payload schemas ──────────────────────────────────────────────────

class StudentInfo(BaseModel):
    student_id: Optional[str] = None
    program: Optional[str] = None
    enrollment_year: Optional[str] = None


class Behavior(BaseModel):
    total_time_spent_on_moodle: float = 0     # seconds
    active_days_count: int = 0
    session_count: int = 0
    average_session_duration: float = 0       # seconds
    clicks_per_session: float = 0
    peak_activity_hours: List[int] = []


class CourseMetrics(BaseModel):
    course_id: Optional[str] = None
    course_name: Optional[str] = "Unknown Course"
    total_visits: int = 0
    total_time_spent_seconds: float = 0
    number_of_resources_clicked: int = 0
    number_of_assignments_viewed: int = 0
    number_of_quizzes_viewed: int = 0
    active_days_count: int = 0
    click_count: int = 0
    quiz_attempts: int = 0
    assignment_submissions: int = 0


class GradeEntry(BaseModel):
    course_id: Optional[str] = None
    item_name: Optional[str] = None
    item_type: Optional[str] = None
    grade: Optional[str] = None
    max_grade: Optional[str] = None
    percentage: Optional[float] = None
    submission_status: Optional[str] = None
    submission_time: Optional[str] = None


class ExtensionPayload(BaseModel):
    student: Optional[StudentInfo] = None
    behavior: Optional[Behavior] = None
    metricsByCourse: Optional[Dict[str, Any]] = None
    grades: Optional[List[GradeEntry]] = []


class SyncResponse(BaseModel):
    status: str
    student_id: str
    data_source: str
    features_stored: dict


# ── Conversion logic ───────────────────────────────────────────────────────────

def _convert_to_features(payload: ExtensionPayload) -> dict:
    """
    Convert the Chrome extension's native data format to the compute_features()
    output schema so the dashboard endpoints can consume it uniformly.

    Output keys (match compute_features() return value):
        total_time_spent        — milliseconds of total session time
        active_days             — unique calendar days with activity
        access_frequency        — mean visits per course
        avg_quiz_score          — 0-100 mean quiz percentage
        quiz_score_std          — sample std of quiz percentages
        avg_assignment_score    — 0-1 mean assignment percentage
        late_submission_ratio   — 0-1 (not determinable from extension data → 0)
        avg_final_grade         — 0-1 (not available from extension → 0)
    """
    behavior   = payload.behavior or Behavior()
    metrics    = payload.metricsByCourse or {}
    grades     = payload.grades or []

    # ── total_time_spent (ms) ─────────────────────────────────────────────
    total_time_spent = behavior.total_time_spent_on_moodle * 1_000  # s → ms

    # ── active_days ───────────────────────────────────────────────────────
    active_days = behavior.active_days_count

    # ── access_frequency (mean visits per course) ─────────────────────────
    visit_counts = [
        v.get("total_visits", 0) if isinstance(v, dict) else getattr(v, "total_visits", 0)
        for v in metrics.values()
    ]
    access_frequency = statistics.mean(visit_counts) if visit_counts else 0.0

    # ── quiz scores (from grades list) ────────────────────────────────────
    quiz_pcts: List[float] = []
    asgn_pcts: List[float] = []

    for g in grades:
        if not isinstance(g, GradeEntry):
            continue
        pct = g.percentage
        if pct is None:
            continue
        item_type = (g.item_type or "").lower()
        if "quiz" in item_type:
            quiz_pcts.append(float(pct))
        elif "assign" in item_type:
            asgn_pcts.append(float(pct))

    avg_quiz_score = statistics.mean(quiz_pcts) if quiz_pcts else 0.0
    quiz_score_std = (
        statistics.stdev(quiz_pcts) if len(quiz_pcts) > 1 else 0.0
    )

    avg_assignment_score = (
        statistics.mean(asgn_pcts) / 100.0 if asgn_pcts else 0.0
    )

    return {
        "total_time_spent":      total_time_spent,
        "active_days":           active_days,
        "access_frequency":      access_frequency,
        "avg_quiz_score":        avg_quiz_score,
        "quiz_score_std":        quiz_score_std,
        "avg_assignment_score":  avg_assignment_score,
        "late_submission_ratio": 0.0,   # not determinable from extension data
        "avg_final_grade":       0.0,   # final grades not scraped by extension
    }


# ── Endpoint ───────────────────────────────────────────────────────────────────

@router.post("/sync", response_model=SyncResponse)
async def sync_extension_data(
    payload: ExtensionPayload,
    session: dict = Depends(_require_session),
) -> SyncResponse:
    """
    Accept the Chrome extension's collected Moodle data, convert to ML features,
    and persist them under the authenticated user's student_id.

    After a successful sync, GET /api/student/dashboard will return
    data_source="live" for this user.
    """
    student_id = session["student_id"]

    features = _convert_to_features(payload)
    store_features(student_id, features)

    return SyncResponse(
        status="ok",
        student_id=student_id,
        data_source="live",
        features_stored=features,
    )

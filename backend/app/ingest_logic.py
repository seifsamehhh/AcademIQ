"""
ingest_logic.py — Pure Pydantic models and compute_features function.

This module has ZERO database or framework dependencies so it can be
imported safely in unit tests without triggering MongoDB connections.

Imported by backend.py (FastAPI app) and by test suite directly.
"""

import statistics
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel


# ── Pydantic schemas (raw Moodle payload from Chrome extension) ──────────────

class Assignment(BaseModel):
    title: str
    due_date: Optional[str] = None
    submitted: bool = True
    submitted_at: Optional[str] = None   # ISO timestamp of actual submission
    grade: Optional[str] = None          # e.g. "18/20" or "85%"


class Quiz(BaseModel):
    title: str
    attempts: Optional[int] = None
    score: Optional[float] = None
    time_spent_ms: Optional[int] = None


class Course(BaseModel):
    course_id: str
    name: str
    visits: int
    time_spent_ms: int
    assignments: List[Assignment]
    quizzes: List[Quiz]
    final_grade: Optional[str] = None   # e.g. "85%"


class Session(BaseModel):
    start: int          # epoch ms
    end: int            # epoch ms
    duration_ms: int


class RawMoodlePayload(BaseModel):
    student_id: Optional[str] = None
    clicks: int
    lastActivity: int
    sessions: List[Session]
    courses: Dict[str, Course]


# ── Feature computation ───────────────────────────────────────────────────────

def compute_features(payload: RawMoodlePayload) -> dict:
    """
    Transform a raw Moodle payload into ML-ready numeric features.

    Returns a dict with keys:
        total_time_spent, active_days, access_frequency,
        avg_quiz_score, quiz_score_std, avg_assignment_score,
        late_submission_ratio, avg_final_grade
    """

    # ── Total time spent (sum of session durations in ms) ──
    total_time_spent = sum(s.duration_ms for s in payload.sessions)

    # ── Active days (unique calendar days with any session) ──
    active_days = len(
        {datetime.fromtimestamp(s.start / 1000).date() for s in payload.sessions}
    )

    # ── Access frequency (mean visits per course) ──
    if payload.courses:
        visit_counts = [c.visits for c in payload.courses.values()]
        access_frequency = statistics.mean(visit_counts) if visit_counts else 0.0
    else:
        access_frequency = 0.0

    # ── Quiz scores ──
    quiz_scores: List[float] = []
    for course in payload.courses.values():
        for q in course.quizzes:
            if q.score is not None:
                quiz_scores.append(q.score)

    avg_quiz_score = float(statistics.mean(quiz_scores)) if quiz_scores else 0.0
    quiz_score_std = float(statistics.stdev(quiz_scores)) if len(quiz_scores) > 1 else 0.0

    # ── Assignment scores & late submission rate ──
    assignment_scores: List[float] = []
    late_count = 0
    total_assignments = 0

    for course in payload.courses.values():
        for a in course.assignments:
            total_assignments += 1

            # Parse "val/max" grade format
            if a.grade:
                try:
                    val, max_val = a.grade.split("/")
                    assignment_scores.append(float(val) / float(max_val))
                except Exception:
                    pass  # unparseable grade — skip silently

            # Late = submitted AFTER due_date (requires both timestamps)
            if a.submitted and a.due_date and a.submitted_at:
                try:
                    due = datetime.fromisoformat(a.due_date)
                    sub = datetime.fromisoformat(a.submitted_at)
                    if sub > due:
                        late_count += 1
                except Exception:
                    pass  # unparseable date — skip silently

    avg_assignment_score = float(statistics.mean(assignment_scores)) if assignment_scores else 0.0
    late_submission_ratio = float(late_count / total_assignments) if total_assignments else 0.0

    # ── Average final grade (strip "%" and normalise to 0–1) ──
    final_grades: List[float] = []
    for course in payload.courses.values():
        if course.final_grade:
            try:
                val = float(course.final_grade.strip("%")) / 100
                final_grades.append(val)
            except Exception:
                pass

    avg_final_grade = float(statistics.mean(final_grades)) if final_grades else 0.0

    return {
        "total_time_spent": total_time_spent,
        "active_days": active_days,
        "access_frequency": access_frequency,
        "avg_quiz_score": avg_quiz_score,
        "quiz_score_std": quiz_score_std,
        "avg_assignment_score": avg_assignment_score,
        "late_submission_ratio": late_submission_ratio,
        "avg_final_grade": avg_final_grade,
    }


def generate_recommendation(risk_cluster: int) -> str:
    """Return a human-readable recommendation for a risk cluster."""
    recommendations = {
        0: "Low risk — Keep up the good work!",
        1: "Medium risk — Focus on weak courses.",
        2: "High risk — Immediate intervention recommended!",
    }
    return recommendations.get(risk_cluster, "Unknown risk level")

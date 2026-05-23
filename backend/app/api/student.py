"""
student.py — Student-facing dashboard and insights endpoints.

GET /api/student/dashboard
  Returns chart data, course predictions, study engagement, and burnout risk.
  Live path: uses features stored by POST /ingest or POST /api/extension/sync.
  Mock path: returns mock data matching mockData.ts so the UI always works.

GET /api/student/insights
  Runs the ML pass/fail + risk pipeline and returns a personalized report.
  Same live/mock dual-path strategy.

Both endpoints require  Authorization: Bearer <token>  from POST /api/auth/login.
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional

from ..store import get_session, get_features
from ..ml.model_loader import ModelLoader

router = APIRouter(prefix="/api/student", tags=["Student"])

# ── ML model (loaded once at import time — mirrors Predictor pattern) ─────────
_model_loader = ModelLoader()


# ── Mock feature vector — keys match FEATURE_ORDER in model_loader.py ────────
# These are representative values for a high-performing student.
# total_time_spent is in milliseconds (18 active days × ~3.8 hrs/day).
_MOCK_FEATURES = {
    "total_time_spent":      13_680_000.0,  # ~228 hours in ms
    "active_days":           18,
    "access_frequency":      10.0,
    "avg_quiz_score":        83.0,           # 0-100
    "quiz_score_std":        5.5,
    "avg_assignment_score":  0.875,          # 0-1
    "late_submission_ratio": 0.125,          # 0-1
    "risk_cluster":          0,              # LOW (no clustering model available)
    "risk_cluster_encoded":  0,
    "avg_final_grade":       0.0,            # not yet available from extension
}

# ── Mock dashboard data (mirrors mockData.ts exactly) ─────────────────────────
_MOCK_WEEKLY = [
    {"date": "Mon", "score": 72},
    {"date": "Tue", "score": 78},
    {"date": "Wed", "score": 85},
    {"date": "Thu", "score": 82},
    {"date": "Fri", "score": 88},
    {"date": "Sat", "score": 90},
    {"date": "Sun", "score": 85},
]

_MOCK_PREDICTIONS = [
    {"courseId": "cs101",   "courseName": "Introduction to Programming", "score": 89, "trend": "up"},
    {"courseId": "cs201",   "courseName": "Data Structures",             "score": 78, "trend": "up"},
    {"courseId": "cs301",   "courseName": "Database",                    "score": 66, "trend": "down"},
    {"courseId": "cs401",   "courseName": "Software Engineering",        "score": 92, "trend": "up"},
    {"courseId": "math201", "courseName": "Linear Algebra",              "score": 81, "trend": "flat"},
    {"courseId": "eng101",  "courseName": "English",                     "score": 88, "trend": "up"},
]

# Engagement hours that do NOT always trigger burnout (original mock did: max 7.2 > avg 3.4 * 2 = 6.8)
_MOCK_ENGAGEMENT = [
    {"day": "Mon", "hours": 2.1},
    {"day": "Tue", "hours": 2.4},
    {"day": "Wed", "hours": 2.0},
    {"day": "Thu", "hours": 3.5},
    {"day": "Fri", "hours": 3.8},
    {"day": "Sat", "hours": 2.5},
    {"day": "Sun", "hours": 2.8},
]

_MOCK_PROGRESS = [
    {"week": "W1", "engagement": 55, "quiz": 60, "predicted": 62},
    {"week": "W2", "engagement": 60, "quiz": 65, "predicted": 66},
    {"week": "W3", "engagement": 68, "quiz": 70, "predicted": 71},
    {"week": "W4", "engagement": 72, "quiz": 75, "predicted": 76},
    {"week": "W5", "engagement": 78, "quiz": 80, "predicted": 81},
    {"week": "W6", "engagement": 82, "quiz": 84, "predicted": 85},
    {"week": "W7", "engagement": 85, "quiz": 88, "predicted": 87},
    {"week": "W8", "engagement": 88, "quiz": 90, "predicted": 89},
]

_MOCK_TIMELINE = [
    {"week": "Week 1", "text": "Improve quiz participation",                 "tone": "warning"},
    {"week": "Week 2", "text": "Submit assignments on time",                 "tone": "warning"},
    {"week": "Week 3", "text": "Engagement improved by 15%",                "tone": "success"},
    {"week": "Week 4", "text": "Quiz accuracy trending upward",             "tone": "success"},
    {"week": "Week 5", "text": "Student behavior becoming more consistent", "tone": "success"},
    {"week": "Week 6", "text": "Maintain current weekly pace",              "tone": "info"},
]

_MOCK_RECOMMENDATIONS = [
    {"title": "Review lecture materials regularly", "description": "Spend 30 minutes daily revisiting recent lectures.",   "priority": "High"},
    {"title": "Start assignments earlier",          "description": "Begin work within 48 hours of assignment release.",    "priority": "High"},
    {"title": "Practice more quizzes",              "description": "Take at least two practice quizzes per week.",         "priority": "Medium"},
    {"title": "Increase study consistency",         "description": "Maintain a steady weekly study schedule.",             "priority": "Medium"},
    {"title": "Maintain current engagement",        "description": "Keep up your participation in discussions.",           "priority": "Low"},
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _overall_status(avg: float) -> str:
    if avg < 70:
        return "At Risk"
    if avg < 85:
        return "Good"
    return "Perfect"


def _burnout(hours: list) -> bool:
    if not hours:
        return False
    avg = sum(hours) / len(hours)
    return bool(max(hours) > avg * 2)


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


# ── Dashboard ──────────────────────────────────────────────────────────────────

@router.get("/dashboard")
async def get_dashboard(session: dict = Depends(_require_session)):
    """
    Return frontend-ready dashboard data.

    Live path  — real Moodle data has been synced via the Chrome extension;
                 high-level stats (avg score, engagement, burnout) are derived
                 from compute_features() output stored in the feature store.
    Mock path  — feature store is empty; returns mockData.ts-equivalent values
                 so the dashboard is always usable without the extension.
    """
    student_id = session["student_id"]
    features   = get_features(student_id)

    if features:
        # ── Live path ──────────────────────────────────────────────────────
        # compute_features() returns avg_quiz_score already in 0-100 range
        avg_score = round(float(features.get("avg_quiz_score", 83.0)), 1)

        # Scale study engagement from real total session time + active days
        total_ms   = float(features.get("total_time_spent", 0))
        active_days = max(int(features.get("active_days", 7)), 1)
        avg_hours_real = (total_ms / 3_600_000) / active_days

        mock_avg = sum(d["hours"] for d in _MOCK_ENGAGEMENT) / len(_MOCK_ENGAGEMENT)
        scale = (avg_hours_real / mock_avg) if (mock_avg > 0 and avg_hours_real > 0) else 1.0
        scale = max(0.3, min(scale, 3.0))   # clamp to sensible range

        engagement = [
            {"day": d["day"], "hours": round(d["hours"] * scale, 1)}
            for d in _MOCK_ENGAGEMENT
        ]
        data_source = "live"
    else:
        # ── Mock path ──────────────────────────────────────────────────────
        avg_score   = 83.0
        engagement  = _MOCK_ENGAGEMENT
        data_source = "mock"

    hours_list   = [d["hours"] for d in engagement]
    burnout_risk = _burnout(hours_list)

    return {
        "student_id":         student_id,
        "username":           session["username"],
        "data_source":        data_source,
        "avg_score":          avg_score,
        "overall_status":     _overall_status(avg_score),
        "weekly_performance": _MOCK_WEEKLY,
        "course_predictions": _MOCK_PREDICTIONS,
        "study_engagement":   engagement,
        "burnout_risk":       burnout_risk,
        "quick_stats": {
            "enrolled_courses": 6,
            "pending_tasks":    8,
            "upcoming_quizzes": 3,
        },
    }


# ── Insights ───────────────────────────────────────────────────────────────────

@router.get("/insights")
async def get_insights(session: dict = Depends(_require_session)):
    """
    Run the ML pass/fail + risk pipeline and return a personalized report.

    Feature vector is built from real ingested data when available, otherwise
    the mock vector is used so the ML pipeline is always exercised.
    """
    student_id = session["student_id"]
    features   = get_features(student_id)

    if features:
        # compute_features() already returns keys matching FEATURE_ORDER exactly.
        # Only addition needed: risk_cluster / risk_cluster_encoded (clustering
        # model not available — default 0 = LOW risk).
        avg_qs = float(features.get("avg_quiz_score", 83.0))
        late_r = float(features.get("late_submission_ratio", 0.0))
        active = max(int(features.get("active_days", 18)), 1)

        feature_vec = {
            "total_time_spent":      float(features.get("total_time_spent", 0)),
            "active_days":           active,
            "access_frequency":      float(features.get("access_frequency", 10.0)),
            "avg_quiz_score":        avg_qs,
            "quiz_score_std":        float(features.get("quiz_score_std", 0.0)),
            "avg_assignment_score":  float(features.get("avg_assignment_score", 0.0)),
            "late_submission_ratio": late_r,
            "risk_cluster":          0,   # clustering model not available
            "risk_cluster_encoded":  0,
            "avg_final_grade":       float(features.get("avg_final_grade", 0.0)),
        }
        data_source = "live"
    else:
        feature_vec = _MOCK_FEATURES
        avg_qs      = _MOCK_FEATURES["avg_quiz_score"]
        late_r      = _MOCK_FEATURES["late_submission_ratio"]
        active      = _MOCK_FEATURES["active_days"]
        data_source = "mock"

    # ── Run ML model ───────────────────────────────────────────────────────
    pass_prob        = 0.72
    risk_level       = "LOW"
    engagement_score = 0.5

    try:
        ml = _model_loader.predict(feature_vec)
        pass_prob        = float(ml["pass_probability"])
        engagement_score = float(ml["engagement_score"])
        rl = ml["risk_level"]
        risk_level = (
            {0: "LOW", 1: "MEDIUM", 2: "HIGH"}.get(rl, "MEDIUM")
            if isinstance(rl, int) else str(rl)
        )
    except Exception:
        pass  # defaults already set above

    # ── Classification from pass probability ───────────────────────────────
    if pass_prob >= 0.70:
        classification = "High Performer"
        confidence     = round(pass_prob * 100)
    elif pass_prob >= 0.45:
        classification = "Average Performer"
        confidence     = round(pass_prob * 100)
    else:
        classification = "At Risk"
        confidence     = round((1.0 - pass_prob) * 100)

    confidence = max(50, min(99, confidence))

    # ── Behavioural insights derived from features ─────────────────────────
    strengths:  list = []
    weaknesses: list = []

    if late_r < 0.15:
        strengths.append("Consistent on-time assignment submissions")
    if avg_qs >= 80.0:
        strengths.append("Strong quiz performance across modules")
    if active >= 15:
        strengths.append("High activity and consistent engagement")
    if not strengths:
        strengths.append("Consistent attendance in live sessions")

    if late_r > 0.25:
        weaknesses.append("Late assignment submissions above average")
    if avg_qs < 70.0:
        weaknesses.append("Quiz performance needs improvement")
    if active < 10:
        weaknesses.append("Inconsistent weekly study behavior")
    if not weaknesses:
        weaknesses.append("Low interaction with reading materials")

    return {
        "student_id":       student_id,
        "data_source":      data_source,
        "classification":   classification,
        "confidence":       confidence,
        "pass_probability": round(pass_prob, 4),
        "risk_level":       risk_level,
        "engagement_score": round(engagement_score, 4),
        "strengths":        strengths,
        "weaknesses":       weaknesses,
        "recommendations":  _MOCK_RECOMMENDATIONS,
        "progress_data":    _MOCK_PROGRESS,
        "timeline":         _MOCK_TIMELINE,
    }

from fastapi import APIRouter
from datetime import datetime
from typing import List
from app.schemas.ingest import IngestPayload, MoodleEvent
from app.schemas.response import DashboardResponse, Predictions, EngagementStats, Trends
from app.services.feature_extractor import FeatureExtractor
from app.services.predictor import Predictor

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"]
)

predictor = Predictor()  # load ML models once

@router.post("/", response_model=DashboardResponse)
def generate_dashboard(payload: IngestPayload):
    """
    End-to-end dashboard prediction:
    raw events → feature extraction → ML → frontend-ready JSON
    """

    # Step 1: Feature extraction
    features = FeatureExtractor.extract(
        student_id=payload.student_id,
        course_id=payload.course_id,
        events=payload.events
    )

    # Step 2: ML predictions
    predictions_dict = predictor.predict_from_features(features)

    # Step 3: Engagement stats
    engagement_stats = EngagementStats(
        active_days=features.active_days,
        avg_session_minutes=features.avg_session_duration_minutes,
        days_since_last_activity=features.days_since_last_activity
    )

    # Step 4: Trends (placeholder: simple heuristic)
    if features.avg_daily_events >= 5:
        activity_trend = "INCREASING"
    elif features.avg_daily_events >= 2:
        activity_trend = "STABLE"
    else:
        activity_trend = "DECLINING"

    trends = Trends(activity_trend=activity_trend)

    # Step 5: Return response
    return DashboardResponse(
        student_id=features.student_id,
        course_id=features.course_id,
        predictions=Predictions(**predictions_dict),
        engagement_stats=engagement_stats,
        trends=trends,
        generated_at=datetime.utcnow()
    )

from pydantic import BaseModel, constr, Field
from typing import Literal
from datetime import datetime

class EngagementStats(BaseModel):
    active_days: int = Field(..., ge=0)
    avg_session_minutes: float = Field(..., ge=0.0)
    days_since_last_activity: int = Field(..., ge=0)

class Trends(BaseModel):
    activity_trend: Literal["INCREASING", "STABLE", "DECLINING"]

class Predictions(BaseModel):
    pass_probability: float = Field(..., ge=0.0, le=1.0)
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    engagement_score: float = Field(..., ge=0.0)

class DashboardResponse(BaseModel):
    student_id: constr(min_length=1)
    course_id: constr(min_length=1)
    predictions: Predictions
    engagement_stats: EngagementStats
    trends: Trends
    generated_at: datetime

from pydantic import BaseModel, Field, constr

class FeatureVector(BaseModel):
    student_id: constr(min_length=1)
    course_id: constr(min_length=1)

    total_events: int = Field(0, ge=0)
    active_days: int = Field(0, ge=0)
    avg_daily_events: float = Field(0.0, ge=0.0)
    total_time_spent_minutes: float = Field(0.0, ge=0.0)
    avg_session_duration_minutes: float = Field(0.0, ge=0.0)

    page_views: int = Field(0, ge=0)
    quiz_attempts: int = Field(0, ge=0)
    assignments_submitted: int = Field(0, ge=0)

    avg_quiz_score_ratio: float = Field(0.0, ge=0.0, le=1.0)
    submission_ratio: float = Field(0.0, ge=0.0, le=1.0)
    days_since_last_activity: int = Field(0, ge=0)

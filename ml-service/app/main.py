"""
AcademIQ ML service — FastAPI app for Hugging Face Docker Space.

Endpoints:
  GET  /health
  POST /predict/performance
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app import performance_model

app = FastAPI(
    title="AcademIQ ML Service",
    version="0.1.0",
    description="Performance Model v4 inference (independent from Vercel API backend).",
)


class PerformanceFeatures(BaseModel):
    all_clicks: float = 0
    active_days: float = 0
    access_frequency: float = 0.0
    material_clicks: float = 0
    quiz_attempts: float = 0
    assignment_submissions: float = 0
    total_time_spent: float = 0
    procrastination_index: float = 0.0
    late_submission_count: float = 0


class PerformancePredictionRequest(BaseModel):
    """Feature vector JSON — same 9 raw fields the Vercel backend will send later."""

    features: PerformanceFeatures = Field(
        ...,
        description="Behavioural feature vector for Performance Model v4.",
    )


class PerformancePredictionResponse(BaseModel):
    mlAvailable: bool
    engine: Literal["ml", "placeholder"]
    predictedGrade: int | None = None
    status: Literal["Good", "Average", "At Risk"] | None = None
    probability: float | None = None
    confidence: float | None = None
    message: str | None = None
    classification: str | None = None


PLACEHOLDER_MESSAGE = (
    "Performance Model v4 artifacts are not loaded. "
    "Copy models/performance_model into ml-service/models/performance_model "
    "or set MODEL_DIR before starting the service."
)


@app.on_event("startup")
def _startup() -> None:
    performance_model.try_load_on_startup()


@app.get("/health")
def health() -> dict[str, Any]:
    status = performance_model.model_status()
    return {
        "status": "ok",
        "service": "academiq-ml",
        "model": "performance_model_v4",
        "mlAvailable": status["mlAvailable"],
        "engine": "ml" if status["mlAvailable"] else "placeholder",
        "modelDir": status["modelDir"],
        "message": None if status["mlAvailable"] else (status["loadError"] or PLACEHOLDER_MESSAGE),
    }


@app.post("/predict/performance", response_model=PerformancePredictionResponse)
def predict_performance(body: PerformancePredictionRequest) -> PerformancePredictionResponse:
    status = performance_model.model_status()
    if not status["mlAvailable"]:
        return PerformancePredictionResponse(
            mlAvailable=False,
            engine="placeholder",
            predictedGrade=None,
            status=None,
            probability=None,
            confidence=None,
            message=status["loadError"] or PLACEHOLDER_MESSAGE,
            classification=None,
        )

    try:
        result = performance_model.predict_performance(
            body.features.model_dump(),
        )
        return PerformancePredictionResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Inference failed: {exc}") from exc

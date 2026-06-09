"""
Performance Model v4 loader and inference.

Artifacts (from repo root):
  models/performance_model/
    model_calibrated.pkl
    model_raw.pkl
    shap_explainer.pkl
    features_behavioral.pkl
    hp_train_medians.pkl
    train_medians.pkl

Required pip packages: scikit-learn, joblib, pandas, numpy, shap, lightgbm
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

ARTIFACT_FILES = {
    "calibrated_model": "model_calibrated.pkl",
    "raw_model": "model_raw.pkl",
    "shap_explainer": "shap_explainer.pkl",
    "behavioral_features": "features_behavioral.pkl",
    "hp_train_medians": "hp_train_medians.pkl",
    "train_medians": "train_medians.pkl",
}

REQUIRED_FEATURES = [
    "all_clicks",
    "active_days",
    "access_frequency",
    "material_clicks",
    "quiz_attempts",
    "assignment_submissions",
    "total_time_spent",
    "procrastination_index",
    "late_submission_count",
]

_LOAD_ERROR: str | None = None
_calibrated_model = None
_behavioral_features = None
_train_medians = None


def _resolve_model_dir() -> Path:
    """Resolve artifact directory: env MODEL_DIR, then local copies, then monorepo sibling."""
    if raw := os.environ.get("MODEL_DIR", "").strip():
        return Path(raw)

    service_root = Path(__file__).resolve().parent.parent
    candidates = [
        service_root / "models" / "performance_model",
        service_root.parent / "models" / "performance_model",
    ]
    for path in candidates:
        if (path / ARTIFACT_FILES["calibrated_model"]).is_file():
            return path
    return service_root / "models" / "performance_model"


def load_artifacts() -> None:
    """Load Performance Model v4 artifacts once. Raises on failure."""
    global _LOAD_ERROR, _calibrated_model, _behavioral_features, _train_medians

    model_dir = _resolve_model_dir()
    if not model_dir.is_dir():
        raise FileNotFoundError(f"Model directory not found: {model_dir}")

    missing = [
        name
        for name in ARTIFACT_FILES.values()
        if not (model_dir / name).is_file()
    ]
    if missing:
        raise FileNotFoundError(
            f"Missing artifacts in {model_dir}: {', '.join(missing)}"
        )

    artifacts = {
        key: joblib.load(model_dir / filename)
        for key, filename in ARTIFACT_FILES.items()
    }

    _calibrated_model = artifacts["calibrated_model"]
    _behavioral_features = artifacts["behavioral_features"]
    _train_medians = artifacts["train_medians"]
    _LOAD_ERROR = None


def model_status() -> dict[str, Any]:
    """Return whether the real model is loaded."""
    loaded = _calibrated_model is not None
    return {
        "mlAvailable": loaded,
        "modelDir": str(_resolve_model_dir()),
        "loadError": _LOAD_ERROR,
    }


def _engineer_features(row: pd.Series, train_medians: pd.Series) -> pd.Series:
    row = row.copy()
    row["clicks_per_day"] = row["all_clicks"] / (row["active_days"] + 1)
    row["time_per_click"] = row["total_time_spent"] / (row["all_clicks"] + 1)
    row["engagement_consistency"] = row["active_days"] / (row["total_time_spent"] / 60 + 1)
    row["behavioral_risk_score"] = (
        max(row["procrastination_index"], 0) * 0.6
        + row["late_submission_count"] * 10 * 0.4
    )
    for col in ["all_clicks", "total_time_spent", "active_days"]:
        median_val = train_medians.get(col, 1)
        row[f"{col}_relative"] = row[col] / (median_val + 1)
    return row


def _status_from_probability(probability: float) -> str:
    if probability >= 0.5:
        return "Good"
    if probability >= 0.4:
        return "Average"
    return "At Risk"


def predict_performance(raw_features: dict[str, Any]) -> dict[str, Any]:
    """Run inference when artifacts are loaded."""
    if _calibrated_model is None:
        raise RuntimeError("Performance model artifacts are not loaded.")

    missing = [k for k in REQUIRED_FEATURES if k not in raw_features]
    if missing:
        raise ValueError(f"Missing features: {missing}")

    base = pd.Series({k: raw_features.get(k, 0) for k in REQUIRED_FEATURES})
    engineered = _engineer_features(base, _train_medians)
    x_df = pd.DataFrame(
        [engineered[_behavioral_features].values],
        columns=_behavioral_features,
    )

    probability = float(_calibrated_model.predict_proba(x_df)[0][1])
    classification = "High Performer" if probability >= 0.5 else "Not High Performer"
    predicted_grade = int(round(probability * 100))
    confidence = round(probability * 100, 1)

    return {
        "mlAvailable": True,
        "engine": "ml",
        "predictedGrade": predicted_grade,
        "status": _status_from_probability(probability),
        "probability": round(probability, 4),
        "confidence": confidence,
        "message": None,
        "classification": classification,
    }


def try_load_on_startup() -> None:
    """Best-effort load; records error without raising."""
    global _LOAD_ERROR
    try:
        load_artifacts()
        print(f"[OK] Performance Model v4 loaded from {_resolve_model_dir()}")
    except Exception as exc:
        _LOAD_ERROR = str(exc)
        print(f"[WARN] Performance model not loaded: {exc}")

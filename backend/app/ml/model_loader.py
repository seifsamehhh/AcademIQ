"""
ML Model Loader — AcademIQ
Loads trained scikit-learn models from the artifacts/ directory.

Available models (as of project audit May 2026):
  - pass_fail_model.pkl  → binary classifier (pass=1 / fail=0)
  - logistic_model.pkl   → alternative logistic regression pass/fail
  - pass_fail_scaler.pkl → StandardScaler for pass_fail features
  - scaler.pkl           → general-purpose scaler

Missing (graceful degradation applied):
  - risk_model.pkl       → returns MEDIUM risk when absent
  - engagement_model.pkl → returns 0.5 engagement when absent
"""

import logging
import joblib
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Feature order expected by the trained models — confirmed by inspecting
# pass_fail_model.pkl and pass_fail_scaler.pkl feature_names_in_ attributes.
# These match the compute_features() output format + two clustering fields
# (risk_cluster, risk_cluster_encoded) that default to 0 when unavailable.
FEATURE_ORDER = [
    "total_time_spent",       # milliseconds of total session time
    "active_days",            # unique calendar days with activity
    "access_frequency",       # mean visits per course
    "avg_quiz_score",         # 0-100 mean quiz score
    "quiz_score_std",         # sample std of quiz scores
    "avg_assignment_score",   # 0-1 mean assignment percentage
    "late_submission_ratio",  # 0-1 fraction of late submissions
    "risk_cluster",           # 0 = LOW (default when clustering unavailable)
    "risk_cluster_encoded",   # same value, kept for model compatibility
    "avg_final_grade",        # 0-1 mean final grade
]

# Artifacts directory (sibling of this file)
ARTIFACTS_DIR = Path(__file__).parent / "artifacts"


def _try_load(filename: str) -> Optional[Any]:
    """Attempt to load a model file, returning None if missing."""
    path = ARTIFACTS_DIR / filename
    if not path.exists():
        logger.warning("Model artifact not found: %s — will use fallback.", path)
        return None
    try:
        model = joblib.load(path)
        logger.info("Loaded model: %s", filename)
        return model
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load %s: %s", filename, exc)
        return None


class ModelLoader:
    """Singleton-style loader; instantiate once at app startup."""

    def __init__(self):
        self.models: Dict[str, Any] = {}
        self.scalers: Dict[str, Any] = {}
        self._load_all()

    # ------------------------------------------------------------------ #
    # Loading
    # ------------------------------------------------------------------ #

    def _load_all(self):
        """Load all available model artifacts. Missing ones get fallbacks."""
        # Pass/fail — prefer pass_fail_model, fall back to logistic_model
        self.models["pass_fail"] = (
            _try_load("pass_fail_model.pkl") or _try_load("logistic_model.pkl")
        )
        if self.models["pass_fail"] is None:
            logger.error("No pass/fail model found — predictions will be unavailable.")

        # Risk model (optional)
        self.models["risk"] = _try_load("risk_model.pkl")

        # Engagement model (optional)
        self.models["engagement"] = _try_load("engagement_model.pkl")

        # Scalers
        self.scalers["pass_fail"] = (
            _try_load("pass_fail_scaler.pkl") or _try_load("scaler.pkl")
        )

    # ------------------------------------------------------------------ #
    # Prediction
    # ------------------------------------------------------------------ #

    def predict(self, features) -> Dict[str, float]:
        """
        Given a FeatureVector (or dict), return model predictions.

        Returns:
            {
                "pass_probability": float,   # 0.0 – 1.0
                "risk_level": int,           # 0=LOW, 1=MEDIUM, 2=HIGH
                "engagement_score": float,   # 0.0 – 1.0 (or raw model output)
            }
        Raises:
            RuntimeError if the pass/fail model is unavailable.
        """
        if self.models["pass_fail"] is None:
            raise RuntimeError(
                "Pass/fail model is not loaded. Check that pass_fail_model.pkl "
                "or logistic_model.pkl exists in backend/app/ml/artifacts/."
            )

        # Build feature matrix in training order
        if hasattr(features, "__dict__"):
            raw = {k: getattr(features, k, 0.0) for k in FEATURE_ORDER}
        elif isinstance(features, dict):
            raw = {k: features.get(k, 0.0) for k in FEATURE_ORDER}
        else:
            raise TypeError(f"Unsupported features type: {type(features)}")

        X = [[raw[f] for f in FEATURE_ORDER]]

        # Apply scaler if available
        if self.scalers["pass_fail"] is not None:
            try:
                X = self.scalers["pass_fail"].transform(X)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Scaler transform failed (%s) — using raw features.", exc)

        # Pass / fail probability
        try:
            pass_prob = float(self.models["pass_fail"].predict_proba(X)[0][1])
        except AttributeError:
            # Model doesn't support predict_proba — use binary prediction
            pass_prob = float(self.models["pass_fail"].predict(X)[0])

        # Risk level — fallback: derive from pass_prob when model missing
        if self.models["risk"] is not None:
            try:
                risk_level = int(self.models["risk"].predict(X)[0])
            except Exception:  # noqa: BLE001
                risk_level = self._fallback_risk(pass_prob)
        else:
            risk_level = self._fallback_risk(pass_prob)

        # Engagement score — fallback: 0.5 (neutral) when model missing
        if self.models["engagement"] is not None:
            try:
                engagement_score = float(self.models["engagement"].predict(X)[0])
            except Exception:  # noqa: BLE001
                engagement_score = 0.5
        else:
            engagement_score = 0.5

        return {
            "pass_probability": pass_prob,
            "risk_level": risk_level,
            "engagement_score": engagement_score,
        }

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _fallback_risk(pass_prob: float) -> int:
        """Derive a rough risk level from pass probability when risk model is absent."""
        if pass_prob >= 0.70:
            return 0  # LOW
        elif pass_prob >= 0.45:
            return 1  # MEDIUM
        else:
            return 2  # HIGH

    def is_ready(self) -> bool:
        """Returns True if the minimum required model (pass_fail) is loaded."""
        return self.models.get("pass_fail") is not None

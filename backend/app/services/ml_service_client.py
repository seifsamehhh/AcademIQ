"""
HTTP client for the external AcademIQ ML service (Hugging Face Docker Space).

Uses stdlib urllib only — no heavy ML deps on the Vercel API backend.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from app.config.settings import ML_SERVICE_TIMEOUT_SECONDS, ML_SERVICE_URL

logger = logging.getLogger(__name__)

PERFORMANCE_FEATURE_KEYS = (
    "all_clicks",
    "active_days",
    "access_frequency",
    "material_clicks",
    "quiz_attempts",
    "assignment_submissions",
    "total_time_spent",
    "procrastination_index",
    "late_submission_count",
)


def ml_service_configured() -> bool:
    return bool(ML_SERVICE_URL)


def build_performance_payload(features: Dict[str, Any]) -> Dict[str, Any]:
    """Shape expected by POST /predict/performance on the ML service."""
    return {
        "features": {
            key: features.get(key, 0) if features.get(key) is not None else 0
            for key in PERFORMANCE_FEATURE_KEYS
        }
    }


def predict_performance_remote(features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Call the external ML service. Returns parsed JSON when mlAvailable is true
    and engine is ml; otherwise None (caller keeps honest fallback).
    """
    if not ML_SERVICE_URL:
        return None

    url = f"{ML_SERVICE_URL.rstrip('/')}/predict/performance"
    body = json.dumps(build_performance_payload(features)).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=ML_SERVICE_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        logger.warning("ML service request failed: %s", exc)
        return None
    except Exception as exc:
        logger.warning("ML service unexpected error: %s", exc)
        return None

    if not isinstance(payload, dict):
        return None
    if not payload.get("mlAvailable") or payload.get("engine") != "ml":
        return None
    if payload.get("predictedGrade") is None or not payload.get("status"):
        return None

    return payload

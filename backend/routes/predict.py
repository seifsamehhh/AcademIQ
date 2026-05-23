from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import joblib
import numpy as np

app = FastAPI()

# ------------------------------
# Load trained model (already trained)
# ------------------------------
# Replace with your actual model path
MODEL_PATH = "backend/models/ai_model.pkl"
try:
    model = joblib.load(MODEL_PATH)
except Exception as e:
    print(f"⚠️ Failed to load model: {e}")
    model = None

# ------------------------------
# Request schema: features dict
# ------------------------------
class FeaturesPayload(BaseModel):
    total_time_spent: float
    active_days: float
    access_frequency: float
    avg_quiz_score: float
    quiz_score_std: float
    avg_assignment_score: float
    late_submission_ratio: float
    avg_final_grade: float

# ------------------------------
# Response schema
# ------------------------------
def generate_recommendation(risk_cluster: int) -> str:
    recommendations = {
        0: "Low risk – Keep up the good work!",
        1: "Medium risk – Focus on weak courses.",
        2: "High risk – Immediate intervention recommended!"
    }
    return recommendations.get(risk_cluster, "Unknown risk level")

# ------------------------------
# Predict endpoint
# ------------------------------
@app.post("/predict")
async def predict(features: FeaturesPayload):
    if model is None:
        raise HTTPException(status_code=500, detail="Model not loaded")

    try:
        # Convert features to model input
        X = np.array([[ 
            features.total_time_spent,
            features.active_days,
            features.access_frequency,
            features.avg_quiz_score,
            features.quiz_score_std,
            features.avg_assignment_score,
            features.late_submission_ratio,
            features.avg_final_grade
        ]])

        # Predict risk cluster
        risk_cluster = int(model.predict(X)[0])
        risk_encoded = risk_cluster  # if needed for consistency with dataset

        recommendation = generate_recommendation(risk_cluster)

        return {
            "status": "ok",
            "risk_cluster": risk_cluster,
            "risk_cluster_encoded": risk_encoded,
            "recommendation": recommendation
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# backend/app/routes/student.py

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any
from datetime import datetime

from app.services.auth_service import get_current_user

router = APIRouter(prefix="/api/student", tags=["Student"])

# Demo results — always mountable without ML dependencies.
demo_router = APIRouter(prefix="/student", tags=["Student Demo"])

DEMO_RESULTS: Dict[str, Dict[str, Any]] = {
    "student1": {
        "name": "Seif Sameh",
        "gpa": 3.5,
        "risk": "Low",
        "courses": [
            {"name": "Programming", "grade": 85},
            {"name": "Database", "grade": 78},
        ],
    },
    "student2": {
        "name": "Aly Ehab",
        "gpa": 2.8,
        "risk": "Medium",
        "courses": [
            {"name": "Programming", "grade": 65},
            {"name": "Web Dev", "grade": 72},
        ],
    },
}


@demo_router.get("/{student_id}/results")
async def get_student_results(
    student_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Return demo academic results — JWT required; students see only their own."""
    role = current_user.get("role")
    if role != "admin" and current_user.get("student_id") != student_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this resource",
        )
    return DEMO_RESULTS.get(student_id, {})

def get_latest_features(student_id: str) -> Dict[str, Any]:
    from app.config.database import feature_vectors_collection

    doc = feature_vectors_collection.find_one(
        {"student_id": student_id},
        sort=[("created_at", -1)]
    )
    if not doc:
        return None
    return doc.get("features", {})

def store_prediction(student_id: str, model_name: str, input_features: Dict[str, Any], prediction: Dict[str, Any]):
    from app.config.database import ml_results_collection

    doc = {
        "student_id": student_id,
        "model_name": model_name,
        "input_features_snapshot": input_features,
        "prediction": prediction,
        "created_at": datetime.utcnow()
    }
    ml_results_collection.insert_one(doc)

@router.get("/insights/{student_id}")
async def get_insights(student_id: str):
    features = get_latest_features(student_id)
    if not features:
        raise HTTPException(status_code=404, detail="No feature vector found for this student")

    # Prepare input for performance model (9 raw behavioural features)
    raw_input = {
        "all_clicks": features.get("all_clicks", 0),
        "active_days": features.get("active_days", 0),
        "access_frequency": features.get("access_frequency", 0.0),
        "material_clicks": features.get("material_clicks", 0),
        "quiz_attempts": features.get("quiz_attempts", 0),
        "assignment_submissions": features.get("assignment_submissions", 0),
        "total_time_spent": features.get("total_time_spent", 0),
        "procrastination_index": features.get("procrastination_index", 0.0),
        "late_submission_count": features.get("late_submission_count", 0)
    }

    try:
        from app.services.performance_predict import predict_performance

        result = predict_performance(raw_input)
        store_prediction(student_id, "performance_model_v4", raw_input, result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Performance model inference failed: {str(e)}")

    # Derive strengths/weaknesses from features (simple example)
    strengths = []
    weaknesses = []
    if features.get("avg_quiz_score", 0) >= 70:
        strengths.append("Good quiz performance")
    if features.get("active_days", 0) >= 15:
        strengths.append("Consistent activity")
    if features.get("late_submission_count", 0) > 2:
        weaknesses.append("Late submissions detected")
    if features.get("procrastination_index", 0) > 5:
        weaknesses.append("High procrastination index")

    return {
        "student_id": student_id,
        "data_source": "live",
        "classification": result["classification"],
        "confidence": round(result["probability"] * 100, 1),
        "pass_probability": result["probability"],
        "risk_level": result.get("tier", "Unknown"),
        "engagement_score": result.get("engagement_score", 0.5),
        "strengths": strengths,
        "weaknesses": weaknesses,
        "recommendations": result["recommendations"],
        "progress_data": [],
        "timeline": []
    }

@router.get("/grade-risk/{student_id}")
async def get_grade_risk(student_id: str):
    features = get_latest_features(student_id)
    if not features:
        raise HTTPException(status_code=404, detail="No feature vector found for this student")

    # Required features for grade/risk model (11 features, including avg_quiz_score and avg_assignment_score)
    required = {
        "all_clicks": features.get("all_clicks", 0),
        "active_days": features.get("active_days", 0),
        "access_frequency": features.get("access_frequency", 0.0),
        "material_clicks": features.get("material_clicks", 0),
        "avg_quiz_score": features.get("avg_quiz_score", 0.0),
        "quiz_attempts": features.get("quiz_attempts", 0),
        "avg_assignment_score": features.get("avg_assignment_score", 0.0),
        "assignment_submissions": features.get("assignment_submissions", 0),
        "total_time_spent": features.get("total_time_spent", 0),
    }

    try:
        from app.services.grade_risk_predict import predict_grade_and_risk

        result = predict_grade_and_risk(required)
        store_prediction(student_id, "grade_risk_v1", required, result)
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"Grade/risk model not available (TensorFlow required): {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Grade/risk inference failed: {str(e)}")

    return {
        "student_id": student_id,
        "risk_cluster": result["risk_cluster"],
        "risk_label": result.get("risk_label", "Unknown"),
        "predicted_grade": result["predicted_grade"],
        "grade_letter": result.get("grade_letter", "?")
    }
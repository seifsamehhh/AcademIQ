from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Optional

app = FastAPI()

# ------------------------------
# In-memory store for student features
# ------------------------------
# Key: student_id, Value: feature dict + risk
STUDENT_RESULTS: Dict[str, dict] = {}

# ------------------------------
# Request schema: store result
# ------------------------------
class StoreResultPayload(BaseModel):
    student_id: str
    features: dict
    risk_cluster: Optional[int] = None
    risk_cluster_encoded: Optional[int] = None
    recommendation: Optional[str] = None

# ------------------------------
# POST endpoint to store latest result
# ------------------------------
@app.post("/store_result")
async def store_result(payload: StoreResultPayload):
    if not payload.student_id:
        raise HTTPException(status_code=400, detail="student_id is required")
    STUDENT_RESULTS[payload.student_id] = {
        "features": payload.features,
        "risk_cluster": payload.risk_cluster,
        "risk_cluster_encoded": payload.risk_cluster_encoded,
        "recommendation": payload.recommendation
    }
    return {"status": "ok", "message": "Result stored"}

# ------------------------------
# GET endpoint to fetch latest result
# ------------------------------
@app.get("/student_results")
async def get_student_result(student_id: str = Query(...)):
    result = STUDENT_RESULTS.get(student_id)
    if not result:
        raise HTTPException(status_code=404, detail="No result found for this student")
    return {"status": "ok", "student_id": student_id, "result": result}

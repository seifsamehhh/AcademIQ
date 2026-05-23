from fastapi import APIRouter, HTTPException
from app.schemas.ingest import IngestPayload

router = APIRouter(
    prefix="/ingest",
    tags=["Ingest"]
)

@router.post("/", response_model=dict)
def ingest_events(payload: IngestPayload):
    """
    Accept raw Moodle events, validate, and store.
    Currently, just echoes the received payload.
    """
    # TODO: replace with storage logic
    try:
        # For now, just return number of events
        return {
            "status": "success",
            "student_id": payload.student_id,
            "course_id": payload.course_id,
            "received_events": len(payload.events)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

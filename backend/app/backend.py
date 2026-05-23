from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import traceback
import os
import sys

# Load .env so MONGODB_URI and FRONTEND_ORIGIN are available before any import
try:
    from dotenv import load_dotenv
    from pathlib import Path
    _env = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(dotenv_path=_env)
except ImportError:
    pass

# Ensure project root is on sys.path so sibling packages (e.g. `config`, `schema`, `models`)
# can be imported when running `uvicorn` from the `backend/` directory.
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Pure logic — no DB dependency (safe to import in tests)
from .ingest_logic import (
    RawMoodlePayload, Assignment, Quiz, Course, Session,
    compute_features, generate_recommendation,
)

# In-memory store — populated by /ingest, read by /api/student/*
from .store import store_features

# Local app-level modules
from .database import ping_db
from ..routes.route import router

# New REST API routers: auth, student dashboard/insights, extension sync
from .api.auth      import router as auth_router
from .api.student   import router as student_router
from .api.extension import router as extension_router

# ---------------------------------------------------------------------------
# Initialize FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="academIQ Backend", version="2.0")

# Existing CRUD routes (todos, assignments, sessions, quizzes, courses)
app.include_router(router)

# New student-facing REST API
app.include_router(auth_router)
app.include_router(student_router)
app.include_router(extension_router)


@app.on_event("startup")
def startup_db():
    try:
        ping_db()
    except Exception as e:
        # Don't prevent the app from starting; log for debugging
        print(f"startup_db: ping_db() failed — running without MongoDB: {e}")
        print(traceback.format_exc())


# ---------------------------------------------------------------------------
# CORS
# Frontend runs on port 8080 (vite.config.ts), backend on 8000.
# FRONTEND_ORIGIN env var lets this be overridden without editing source.
# ---------------------------------------------------------------------------
_CHROME_EXT = "chrome-extension://pelgaliljjfhhboggbncepdblmjobgan"
_FRONTEND   = os.getenv("FRONTEND_ORIGIN", "http://localhost:8080")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[_CHROME_EXT, _FRONTEND, "http://localhost:8000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
from pydantic import BaseModel  # noqa: E402


class FeaturesPayload(BaseModel):
    total_time_spent: float
    active_days: float
    access_frequency: float
    avg_quiz_score: float
    quiz_score_std: float
    avg_assignment_score: float
    late_submission_ratio: float
    avg_final_grade: float


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------
@app.get("/")
def root():
    try:
        return {"message": "academIQ backend is running", "version": "2.0"}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "trace": traceback.format_exc()},
        )


@app.exception_handler(Exception)
def global_exception_handler(request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "trace": traceback.format_exc()},
    )


# ---------------------------------------------------------------------------
# POST /ingest — receive raw Moodle payload from Chrome extension
# Also stores computed features in the in-memory store keyed by student_id
# so GET /api/student/dashboard can retrieve them without a DB.
# ---------------------------------------------------------------------------
@app.post("/ingest")
async def ingest(raw_data: RawMoodlePayload):
    try:
        features = compute_features(raw_data)

        # Persist features for dashboard retrieval
        if raw_data.student_id:
            store_features(raw_data.student_id, features)

        return {
            "status":     "ok",
            "features":   features,
            "student_id": raw_data.student_id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# POST /analyze — alias for /ingest with optional persist_mongo flag.
# Accepts the same RawMoodlePayload; persist_mongo query param is accepted
# but ignored (MongoDB persistence happens via the feature store).
# This endpoint existed in earlier versions of the API and is kept for
# backward compatibility with any scripts or tools that call it.
# ---------------------------------------------------------------------------
@app.post("/analyze")
async def analyze(
    raw_data: RawMoodlePayload,
    persist_mongo: bool = False,
):
    try:
        features = compute_features(raw_data)

        if raw_data.student_id:
            store_features(raw_data.student_id, features)

        return {
            "status":        "ok",
            "features":      features,
            "student_id":    raw_data.student_id,
            "persist_mongo": persist_mongo,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

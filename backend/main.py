# backend/main.py

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config.database import client, connect_database, ensure_indexes
from app.config.settings import ALLOWED_ORIGINS
from app.bootstrap import maybe_run_student_bootstrap
from app.routes import moodle, auth, admin, student_data

app = FastAPI(title="AcademIQ Backend", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"chrome-extension://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def ensure_db_connection(request: Request, call_next):
    """Reconnect on serverless cold starts before auth/data routes run."""
    if request.url.path not in ("/health", "/"):
        if connect_database():
            maybe_run_student_bootstrap()
    return await call_next(request)


@app.on_event("startup")
def _startup():
    try:
        if connect_database():
            ensure_indexes()
    except Exception as exc:
        print(f"Could not ensure indexes: {exc}")

    if os.environ.get("BOOTSTRAP_ADMIN", "").lower() == "true":
        try:
            from app.scripts.seed_admin import seed_admin

            seed_admin()
        except Exception as exc:
            print(f"Admin bootstrap skipped: {exc}")

    if os.environ.get("BOOTSTRAP_STUDENTS", "").lower() == "true":
        try:
            print("BOOTSTRAP_STUDENTS=true — running student bootstrap at startup")
            maybe_run_student_bootstrap()
        except Exception as exc:
            print(f"Student bootstrap skipped: {exc}")


@app.get("/")
def root():
    return {"message": "AcademIQ Backend running. Go to /docs for API docs."}


@app.get("/health")
def health():
    """Liveness probe — always 200 when the serverless function is running."""
    return {"status": "ok"}


@app.get("/health/db")
def health_db():
    """Readiness probe — verifies MongoDB connectivity."""
    if not connect_database() or client is None:
        raise HTTPException(status_code=503, detail="Database unreachable")
    try:
        client.admin.command("ping")
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database unreachable: {e}")


# Known collections — keys are stable API labels; values are MongoDB collection names.
_DEBUG_COLLECTIONS: dict[str, str] = {
    "users": "users",
    "raw_moodle_payloads": "raw_moodle_payload_collection",
    "course_materials": "course_materials",
    "student_metrics": "student_metrics",
    "feature_vectors": "feature_vectors",
}


@app.get("/debug/db-info")
def debug_db_info():
    """
    Temporary safe diagnostics: database name, collection list, and document counts.
    Does not return connection strings, credentials, or document contents.
    """
    from app.config.database import db
    from app.config.settings import DATABASE_NAME

    if not connect_database() or db is None:
        raise HTTPException(status_code=503, detail="Database unreachable")

    document_counts: dict[str, int | None] = {}
    for label, coll_name in _DEBUG_COLLECTIONS.items():
        try:
            document_counts[label] = db[coll_name].count_documents({})
        except Exception:
            document_counts[label] = None

    try:
        collection_names = sorted(db.list_collection_names())
    except Exception:
        collection_names = []

    return {
        "database_name": DATABASE_NAME,
        "collection_names": collection_names,
        "document_counts": document_counts,
    }


@app.get("/debug/user-data/{email}")
def debug_user_data(email: str):
    """
    Safe per-user sync summary (no passwords, tokens, or document bodies).
  """
    from app.services.synced_user_data import summarize_user_by_email

    if not connect_database():
        raise HTTPException(status_code=503, detail="Database unreachable")
    return summarize_user_by_email(email)


@app.get("/debug/course-material-coverage/{email}")
def debug_course_material_coverage(email: str):
    """
    Account-level quiz material coverage across ALL synced Moodle courses.
    Shows per-course status counts (ready / not_uploaded / not_quiz_material /
    extraction_failed / too_short) and per-material details.
    No content_text, passwords, tokens, or connection strings.
    """
    from app.services.quiz_materials_debug import debug_course_material_coverage as _coverage

    if not connect_database():
        raise HTTPException(status_code=503, detail="Database unreachable")
    return _coverage(email)


@app.get("/debug/quiz-materials/{email}/{course_id}")
def debug_quiz_materials(email: str, course_id: str):
    """
    Safe quiz-material readiness diagnostics for a user + course.
    No passwords, tokens, connection strings, or full content_text bodies.
    """
    from app.services.quiz_materials_debug import debug_quiz_materials_for_email

    if not connect_database():
        raise HTTPException(status_code=503, detail="Database unreachable")
    return debug_quiz_materials_for_email(email, course_id)


@app.get("/debug/quiz-material/{material_id}")
def debug_single_quiz_material(material_id: str):
    """
    Safe per-material quiz eligibility check across all courses.
    Shows content_text_length, ready_for_quiz, quiz_generation_eligible, failure_reason.
    Does not return content_text, passwords, tokens, or connection strings.
    """
    from app.services.quiz_materials_debug import debug_single_material

    if not connect_database():
        raise HTTPException(status_code=503, detail="Database unreachable")
    return debug_single_material(material_id)


@app.get("/debug/raw-course-materials/{course_id}")
def debug_raw_course_materials(course_id: str):
    """
    Show all materials stored in MongoDB for a given Moodle course_id.
    Returns material_id, title, url, extraction_status, content_chars for each.
    Does NOT return content_text, passwords, or tokens.
    Use this to verify what the preflight lookup will find.
    """
    from app.repositories import material_repository

    if not connect_database():
        raise HTTPException(status_code=503, detail="Database unreachable")

    docs = material_repository.list_by_course(course_id)
    rows = []
    for d in docs:
        text = (d.get("content_text") or "").strip()
        chars = len(text) if text else int(d.get("content_chars") or 0)
        rows.append({
            "material_id": d.get("material_id"),
            "title": d.get("title"),
            "url": d.get("url"),
            "resolved_url": d.get("resolved_url"),
            "file_type": d.get("file_type"),
            "extraction_status": d.get("extraction_status"),
            "content_chars": chars,
            "source": d.get("source"),
            "_id": str(d.get("_id", "")),
        })
    rows.sort(key=lambda r: r["title"] or "")
    return {
        "course_id": course_id,
        "total": len(rows),
        "materials": rows,
    }


@app.get("/debug/synced-courses/{email}")
def debug_synced_courses(email: str):
    """
    Safe Moodle course extraction diagnostics for a synced user.
    No passwords, tokens, connection strings, or raw document bodies.
    """
    from app.services.moodle_course_display import debug_synced_courses_for_email

    if not connect_database():
        raise HTTPException(status_code=503, detail="Database unreachable")
    return debug_synced_courses_for_email(email)


@app.exception_handler(RuntimeError)
async def runtime_error_handler(_request: Request, exc: RuntimeError):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


# Core routers — student JWT auth + dashboard results (no ML required).
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(moodle.router)
app.include_router(student_data.router)

from app.routes.student import demo_router as student_demo_router

app.include_router(student_demo_router)

# ML routers optional — skipped on Vercel auth-only deploy (no heavy deps/models).
try:
    from app.routes import student, performance

    app.include_router(student.router)
    app.include_router(performance.router)
    print("[OK] ML routes mounted.")
except Exception as exc:
    print(f"[INFO] ML routes not mounted (auth-only or missing deps): {exc}")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

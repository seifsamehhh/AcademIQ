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

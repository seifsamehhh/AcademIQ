"""
auth.py — Authentication endpoints for AcademIQ.

POST /api/auth/login
  Accepts username + password (same validation rules as the React form).
  Generates a cryptographically secure bearer token and stores the session
  in the in-memory store (no real user DB — known limitation per AUDIT_REPORT.md).

The token must be sent as  Authorization: Bearer <token>  on all protected
endpoints (/api/student/dashboard, /api/student/insights).
"""
import secrets
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..store import store_token

router = APIRouter(prefix="/api/auth", tags=["Auth"])


# ── Schemas ────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    student_id: str
    username: str


# ── Endpoint ───────────────────────────────────────────────────────────────

@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest) -> LoginResponse:
    """
    Validate credentials and return a bearer token.

    Rules mirror the frontend form:
      - username  ≥ 3 characters (stripped)
      - password  ≥ 6 characters

    Any username/password pair that satisfies the rules succeeds.
    (Real auth with a user DB is out of scope — see known limitations.)
    """
    username = body.username.strip()

    if len(username) < 3:
        raise HTTPException(
            status_code=400,
            detail="Username must be at least 3 characters",
        )
    if len(body.password) < 6:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 6 characters",
        )

    token      = secrets.token_hex(32)
    student_id = username.lower().replace(" ", "_")

    store_token(token, username, student_id)

    return LoginResponse(token=token, student_id=student_id, username=username)

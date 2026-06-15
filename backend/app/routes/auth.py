# backend/app/routes/auth.py
"""
Authentication routes: JWT-based student login and current-user lookup.

POST /api/auth/login accepts student_id + password, verifies against MongoDB,
and returns a signed JWT access token.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.repositories import user_repository
from app.services.auth_service import (
    create_access_token,
    get_current_user,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    student_id: str
    password: str


def _display_name(user: dict) -> str:
    return user.get("name") or user.get("full_name") or ""


@router.post("/login")
async def login(payload: LoginRequest):
    """Authenticate with student_id or email + password; returns a JWT access token."""
    login_id = payload.student_id.strip()
    user = user_repository.find_by_student_id(login_id)
    if not user and "@" in login_id:
        user = user_repository.find_by_email(login_id.lower())
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid login")

    name = _display_name(user)
    access_token = create_access_token(
        user_id=str(user["_id"]),
        student_id=user.get("student_id") or user.get("email"),
        name=name,
        role=user.get("role", "student"),
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "student_id": user.get("student_id") or user.get("email"),
        "name": name,
        "role": user.get("role", "student"),
    }


@router.post("/logout")
async def logout():
    """Stateless JWT logout — client discards the token."""
    return {"status": "logged_out"}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    """Return the currently authenticated user from the JWT."""
    return {
        "student_id": user.get("student_id"),
        "name": user.get("name"),
        "role": user.get("role"),
    }

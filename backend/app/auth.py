# backend/app/auth.py
"""
Authentication & authorisation dependencies.

Sessions are opaque tokens kept in the `sessions` collection. A request is
authenticated if it presents a valid, unexpired session token via EITHER:

    * the `academiq_session` httpOnly cookie (web app), or
    * an `Authorization: Bearer <token>` header (Chrome extension / API clients).

`require_role(...)` builds a dependency that additionally enforces role-based
access so students can never reach admin endpoints.
"""

from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Request, status

from app.config.settings import SESSION_COOKIE_NAME
from app.models.user import serialize_user
from app.repositories import session_repository, user_repository
from app.services.security import hash_token


def _extract_bearer_token(request: Request) -> Optional[str]:
    """Pull a Bearer token from the Authorization header, if present."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return None


def _extract_token(request: Request) -> Optional[str]:
    """Pull the session token from the cookie or a Bearer header."""
    cookie_token = request.cookies.get(SESSION_COOKIE_NAME)
    if cookie_token:
        return cookie_token
    return _extract_bearer_token(request)


def _user_from_jwt(token: str) -> Optional[Dict[str, Any]]:
    """If the bearer value is a valid JWT, return the MongoDB user document."""
    try:
        from jose import JWTError, jwt

        from app.config.settings import JWT_ALGORITHM, JWT_SECRET_KEY

        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None
    return user_repository.find_by_id(str(user_id))


def get_current_user(request: Request) -> Dict[str, Any]:
    """Resolve the authenticated user or raise 401. Returns the raw user doc."""
    bearer = _extract_bearer_token(request)
    if bearer:
        user = _user_from_jwt(bearer)
        if user:
            return user

        session = session_repository.find_valid_session(hash_token(bearer))
        if session:
            user = user_repository.find_by_id(session["user_id"])
            if user:
                return user
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer exists")

        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session")

    cookie_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not cookie_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    session = session_repository.find_valid_session(hash_token(cookie_token))
    if not session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session")

    user = user_repository.find_by_id(session["user_id"])
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer exists")
    return user


def get_current_user_public(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Same as `get_current_user` but serialised (no password hash)."""
    return serialize_user(user)


def require_role(*roles: str):
    """
    Build a dependency that requires the current user to hold one of `roles`.

    Usage:
        @router.get("/admin/...", dependencies=[Depends(require_role("admin"))])
    """

    def dependency(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        if user.get("role") not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "You do not have permission to access this resource",
            )
        return user

    return dependency

"""
Moodle → AcademIQ identity mapping & automatic account provisioning.

Whenever Moodle data is imported, we must attach it to exactly one AcademIQ
account and never create duplicates. Matching uses stable identifiers only
(never name matching), in priority order:

    1. Moodle User ID  (moodle_user_id)
    2. Student ID      (student_id)
    3. Email           (last-resort tie-breaker)
    4. Synthesized email from stable Moodle/payload fingerprint (never shared "unknown")

If no account matches, a new `student` account is created automatically with a
secure random password, and a credentials email is sent.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, Optional, Tuple

from pymongo.errors import DuplicateKeyError

from app.models.user import ROLE_STUDENT, build_user_document
from app.repositories import user_repository
from app.services.email_service import send_account_created_email
from app.services.security import hash_password
from app.utils.password import generate_password


def _first_non_empty(*values: Optional[str]) -> Optional[str]:
    for value in values:
        if value not in (None, ""):
            return str(value).strip()
    return None


def _sanitize_email_part(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9._+-]", "_", str(value).strip().lower())
    return (cleaned[:80] or "sync").strip("_") or "sync"


def _payload_identity_hash(payload: Dict[str, Any]) -> str:
    """Stable fingerprint when Moodle exposes no user identifiers."""
    student = payload.get("student") or {}
    fingerprint = {
        "anon_id": student.get("anon_id"),
        "courses": sorted(
            str(c.get("course_id"))
            for c in (payload.get("courses") or [])
            if c.get("course_id")
        ),
        "metrics_keys": sorted(
            str(k) for k in (payload.get("metricsByCourse") or {}).keys()
        ),
        "behavior": payload.get("behavior") or {},
    }
    raw = json.dumps(fingerprint, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def synthesize_provisioning_email(
    identity: Dict[str, Optional[str]],
    payload: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Build a unique placeholder email — never a shared fixed address for all users.
    Priority: moodle_user_id → student_id → payload fingerprint hash.
    """
    moodle_user_id = identity.get("moodle_user_id")
    student_id = identity.get("student_id")
    if moodle_user_id:
        return f"moodle+uid_{_sanitize_email_part(moodle_user_id)}@academiq.local"
    if student_id:
        return f"moodle+sid_{_sanitize_email_part(student_id)}@academiq.local"
    digest = _payload_identity_hash(payload or {})
    return f"moodle+sync_{digest}@academiq.local"


def extract_identity(payload: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """
    Pull the identity fields out of a Chrome-extension payload.

    Tolerates both the new explicit fields and the older `student.student_id`
    shape so existing payloads keep working.
    """
    student = payload.get("student", {}) or {}
    return {
        "moodle_user_id": _first_non_empty(
            student.get("moodle_user_id"), payload.get("moodle_user_id")
        ),
        "student_id": _first_non_empty(
            student.get("student_id"), payload.get("student_id")
        ),
        "full_name": _first_non_empty(
            student.get("full_name"), student.get("name"), payload.get("full_name")
        ),
        "email": _first_non_empty(student.get("email"), payload.get("email")),
    }


def find_matching_user(
    moodle_user_id: Optional[str] = None,
    student_id: Optional[str] = None,
    email: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Locate the AcademIQ account for a Moodle identity, by priority."""
    if moodle_user_id:
        match = user_repository.find_by_moodle_user_id(moodle_user_id)
        if match:
            return match
    if student_id:
        match = user_repository.find_by_student_id(student_id)
        if match:
            return match
    if email:
        return user_repository.find_by_email(email)
    return None


def _backfill_identity(
    user: Dict[str, Any], identity: Dict[str, Optional[str]]
) -> Tuple[Dict[str, Any], bool]:
    """Fill in identity fields that are missing on an existing account."""
    updates: Dict[str, Any] = {}
    for field in ("moodle_user_id", "student_id"):
        if not user.get(field) and identity.get(field):
            updates[field] = identity[field]
    if not user.get("full_name") and identity.get("full_name"):
        updates["full_name"] = identity["full_name"]

    if updates:
        refreshed = user_repository.update(str(user["_id"]), updates)
        if refreshed:
            return refreshed, True
    return user, False


def _provisioning_result(
    user: Dict[str, Any],
    *,
    created: bool,
    updated: bool,
    temporary_password: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "user": user,
        "created": created,
        "updated": updated,
        "temporary_password": temporary_password,
    }


def issue_demo_sync_temporary_password(user_id: str) -> str:
    """
    Demo only: regenerate an AcademIQ login password when Moodle re-syncs to an
    existing account so the Chrome extension can display usable credentials.

    This never reads, stores, or returns the university Moodle password.
    Production should send a password-reset email instead of returning plaintext.
    """
    password = generate_password()
    user_repository.update(user_id, {"password_hash": hash_password(password)})
    return password


def resolve_or_create_user(
    identity: Dict[str, Optional[str]],
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Return provisioning outcome for a Moodle identity, creating an account if needed.

    Returns a dict:
        user                 — MongoDB user document
        created              — True when a new account was provisioned
        updated              — True when an existing account was backfilled
        temporary_password   — plaintext password when created (demo/API only)

    Production should email credentials or force password reset instead of relying
    on temporary_password in API responses long term.
    """
    moodle_user_id = identity.get("moodle_user_id")
    student_id = identity.get("student_id")
    email = (identity.get("email") or "").strip().lower() or None
    full_name = identity.get("full_name") or ""

    existing = find_matching_user(moodle_user_id, student_id, email)
    if existing:
        user, updated = _backfill_identity(existing, identity)
        return _provisioning_result(user, created=False, updated=updated)

    if not email:
        email = synthesize_provisioning_email(identity, payload)
        existing = find_matching_user(None, None, email)
        if existing:
            user, updated = _backfill_identity(existing, identity)
            return _provisioning_result(user, created=False, updated=updated)

    password = generate_password()
    document = build_user_document(
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        role=ROLE_STUDENT,
        moodle_user_id=moodle_user_id,
        student_id=student_id,
    )

    try:
        created_user = user_repository.create(document)
    except DuplicateKeyError:
        existing = user_repository.find_by_email(email)
        if not existing:
            raise
        user, updated = _backfill_identity(existing, identity)
        return _provisioning_result(user, created=False, updated=updated)

    try:
        send_account_created_email(email, full_name, password)
    except Exception as exc:
        print(f"[WARN] Could not send account-created email to {email}: {exc}")

    # Demo: return plaintext password once for extension visibility. Production
    # should send credentials by email or force password reset instead.
    return _provisioning_result(
        created_user,
        created=True,
        updated=False,
        temporary_password=password,
    )

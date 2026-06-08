"""
Centralised, environment-driven configuration for the AcademIQ backend.

Copy `backend/.env.example` to `backend/.env` for local development.
In production (Vercel), set all required variables in the Vercel project dashboard.

If `python-dotenv` is installed, a local `.env` is loaded automatically.
"""

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass


def _get(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    return value.strip() if value not in (None, "") else default


def _get_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# --- Environment ------------------------------------------------------------
# "development" enables local-only defaults. Set to "production" on Vercel.
ENVIRONMENT: str = _get("ENVIRONMENT", "development").lower()

_DEV_JWT_SECRET = "DEV-ONLY-change-me-in-production-academiq-jwt-secret"
_DEV_ALLOWED_ORIGINS = (
    "http://localhost:3000,http://127.0.0.1:3000,"
    "http://localhost:3001,http://localhost:5173,http://localhost:8080"
)


def _require(name: str, *, dev_default: str = "") -> str:
    """Return env value, or dev_default in development, or raise in production."""
    value = _get(name)
    if value:
        return value
    if ENVIRONMENT == "development" and dev_default:
        return dev_default
    if ENVIRONMENT == "development":
        return ""
    raise RuntimeError(
        f"Missing required environment variable: {name}. "
        f"See backend/.env.example"
    )


# --- Database (required in production) --------------------------------------
MONGODB_URI: str = _require("MONGODB_URI")
MONGODB_DB_NAME: str = _get("DATABASE_NAME") or _get("MONGODB_DB_NAME", "todo_db")
DATABASE_NAME: str = MONGODB_DB_NAME

# --- JWT --------------------------------------------------------------------
JWT_SECRET_KEY: str = _get("JWT_SECRET_KEY") or (
    _DEV_JWT_SECRET if ENVIRONMENT == "development" else ""
)
JWT_ALGORITHM: str = _get("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES: int = _get_int("ACCESS_TOKEN_EXPIRE_MINUTES", 60)

if ENVIRONMENT == "production":
    if not JWT_SECRET_KEY or JWT_SECRET_KEY == _DEV_JWT_SECRET:
        raise RuntimeError(
            "JWT_SECRET_KEY must be set to a secure random value in production"
        )

# --- CORS (comma-separated origins) -----------------------------------------
_allowed_raw = _get("ALLOWED_ORIGINS") or (
    _DEV_ALLOWED_ORIGINS if ENVIRONMENT == "development" else ""
)
ALLOWED_ORIGINS: list[str] = [
    origin.strip() for origin in _allowed_raw.split(",") if origin.strip()
]

if ENVIRONMENT == "production" and not ALLOWED_ORIGINS:
    raise RuntimeError(
        "ALLOWED_ORIGINS must list your Vercel frontend URL(s) in production"
    )

# --- Sessions (legacy cookie routes — admin / extension) --------------------
SESSION_COOKIE_NAME: str = _get("SESSION_COOKIE_NAME", "academiq_session")
SESSION_TTL_HOURS: int = _get_int("SESSION_TTL_HOURS", 24)
SESSION_COOKIE_SECURE: bool = _get_bool("SESSION_COOKIE_SECURE", False)
SESSION_COOKIE_SAMESITE: str = _get("SESSION_COOKIE_SAMESITE", "lax")

# --- Frontend / email -------------------------------------------------------
APP_LOGIN_URL: str = _get(
    "APP_LOGIN_URL",
    "http://localhost:3000/signin" if ENVIRONMENT == "development" else "",
)

SMTP_HOST: str = _get("SMTP_HOST", "")
SMTP_PORT: int = _get_int("SMTP_PORT", 587)
SMTP_USER: str = _get("SMTP_USER", "")
SMTP_PASSWORD: str = _get("SMTP_PASSWORD", "")
SMTP_FROM: str = _get("SMTP_FROM", "AcademIQ <no-reply@academiq.local>")
SMTP_USE_TLS: bool = _get_bool("SMTP_USE_TLS", True)
EMAIL_ENABLED: bool = bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)

# --- Bootstrap scripts (optional, idempotent) -------------------------------
BOOTSTRAP_STUDENTS: bool = _get_bool("BOOTSTRAP_STUDENTS", False)

# --- Initial admin (used by scripts/seed_admin.py) ----------------------------
ADMIN_EMAIL: str = _get("ADMIN_EMAIL", "admin@academiq.local")
ADMIN_PASSWORD: str = _get("ADMIN_PASSWORD", "Admin@12345")
ADMIN_NAME: str = _get("ADMIN_NAME", "AcademIQ Admin")

"""
config/database.py — MongoDB collections for the route layer.
Credentials are loaded from environment variables (see backend/.env).
"""

import os
from pathlib import Path
from pymongo import MongoClient

# Load .env from backend/ directory if python-dotenv is installed
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent.parent / "backend" / ".env"
    load_dotenv(dotenv_path=_env_path)
except ImportError:
    pass  # env vars already injected in production

# Require MONGODB_URI — no hardcoded fallback
uri = os.getenv("MONGODB_URI")
if not uri:
    raise RuntimeError(
        "MONGODB_URI environment variable is not set. "
        "Copy backend/.env.example to backend/.env and fill in your credentials."
    )

# Short timeout so failures surface quickly during development.
# Wrapped in try/except: SRV URIs resolve DNS in the constructor and will
# throw if the cluster is unreachable. Setting client=None lets the rest of
# the app (auth, insights, extension sync) run without MongoDB.
try:
    client = MongoClient(uri, serverSelectionTimeoutMS=3000)
    db = client.todo_db
    collection_name               = db["todo_collection"]
    assignments_collection        = db["assignments_collection"]
    sessions_collection           = db["sessions_collection"]
    quizzes_collection            = db["quizzes_collection"]
    courses_collection            = db["courses_collection"]
    raw_moodle_payload_collection = db["raw_moodle_payload_collection"]
except Exception as _e:
    print(f"config/database.py: MongoDB client creation failed (running without DB): {_e}")
    client = None  # type: ignore[assignment]
    db = None      # type: ignore[assignment]
    collection_name               = None  # type: ignore[assignment]
    assignments_collection        = None  # type: ignore[assignment]
    sessions_collection           = None  # type: ignore[assignment]
    quizzes_collection            = None  # type: ignore[assignment]
    courses_collection            = None  # type: ignore[assignment]
    raw_moodle_payload_collection = None  # type: ignore[assignment]

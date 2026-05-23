import os
from pathlib import Path
from pymongo import MongoClient
from pymongo.server_api import ServerApi

# Load .env if python-dotenv is available (dev convenience)
try:
    from dotenv import load_dotenv
    # Walk up from this file to find backend/.env
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(dotenv_path=_env_path)
except ImportError:
    pass  # In production, env vars are injected directly

# Require MONGODB_URI — no hardcoded fallback (security rule)
uri = os.getenv("MONGODB_URI")
if not uri:
    raise RuntimeError(
        "MONGODB_URI environment variable is not set. "
        "Copy backend/.env.example to backend/.env and fill in your credentials."
    )

# Create client — wrapped in try/except because SRV URIs do DNS resolution
# immediately in the constructor. If DNS fails (no internet / wrong URI),
# client is set to None so the rest of the app can still run without MongoDB.
try:
    client = MongoClient(uri, server_api=ServerApi('1'), serverSelectionTimeoutMS=3000)
except Exception as _e:
    print(f"MongoDB client creation failed (running without DB): {_e}")
    client = None  # type: ignore[assignment]


def ping_db() -> bool:
    """Ping the MongoDB deployment to verify connectivity.

    Returns True if ping succeeds, False otherwise. Logs errors to stdout.
    """
    if client is None:
        print("MongoDB client is not initialised — skipping ping.")
        return False
    try:
        client.admin.command('ping')
        print("Pinged your deployment. You successfully connected to MongoDB!")
        return True
    except Exception as e:
        print(f"MongoDB ping failed: {e}")
        return False


# Exported names: `client` and `ping_db` are available for import
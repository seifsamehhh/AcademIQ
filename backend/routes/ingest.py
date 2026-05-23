"""
routes/ingest.py — DEPRECATED standalone app removed.

This file previously contained a duplicate FastAPI app instance with its own
/ingest endpoint. That duplicated backend/app/backend.py and was never mounted
anywhere in the main application.

The canonical /ingest endpoint now lives in backend/app/backend.py.
This file is kept as a placeholder to avoid import errors from any legacy
references. It exports nothing.

If you need to add ingest-related sub-routes in the future, add them to the
main `router` in backend/routes/route.py or create a new APIRouter here and
include it in backend/app/backend.py.
"""

"""
One-time idempotent bootstrap for demo data on serverless cold starts.

Vercel may not reliably run FastAPI startup hooks; this runs after the first
successful DB connection when BOOTSTRAP_STUDENTS=true.
"""

from __future__ import annotations

import logging
import os
import threading

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_done = False


def maybe_run_student_bootstrap() -> None:
    """Run seed_students once per process when BOOTSTRAP_STUDENTS=true."""
    global _done
    if _done:
        return
    if os.environ.get("BOOTSTRAP_STUDENTS", "").strip().lower() != "true":
        return

    with _lock:
        if _done:
            return
        try:
            from app.config.database import connect_database
            from app.config.settings import DATABASE_NAME

            if not connect_database():
                logger.warning(
                    "BOOTSTRAP_STUDENTS=true but database connection failed — seed skipped"
                )
                return

            logger.info(
                "BOOTSTRAP_STUDENTS=true — running seed_students on database=%s",
                DATABASE_NAME,
            )
            from app.scripts.seed_students import seed_students

            seed_students()
            logger.info("BOOTSTRAP_STUDENTS seed_students completed")
            _done = True
        except Exception as exc:
            logger.exception("Student bootstrap failed: %s", exc)

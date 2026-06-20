"""
Quiz generation from learning-material text — fast path with 12s budget.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MAX_TOTAL_SECONDS = 12.0
MAX_PRIMARY_SECONDS = 8.0
MAX_FALLBACK_ATTEMPTS = 10
DEFAULT_QUESTIONS = 5
RICH_CONTENT_CHARS = 1000


def generate_questions(
    text: str,
    num_questions: int = 5,
    material_title: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], str]:
    """Generate MCQs within a hard time budget. One primary attempt, then fallback."""
    start = time.monotonic()
    deadline = start + MAX_TOTAL_SECONDS

    if not text or not text.strip():
        logger.warning("Quiz generation skipped: no content_text")
        return [], "no_text"

    raw_text = text.strip()
    try:
        from app.services.quiz_material_eligibility import prepare_quiz_generation_text
        text = prepare_quiz_generation_text(raw_text)
    except Exception:
        text = raw_text

    if not text.strip():
        return [], "no_text"

    content_len = len(text.strip())
    target = max(num_questions, DEFAULT_QUESTIONS) if content_len > RICH_CONTENT_CHARS else num_questions

    ai_attempted = False
    ai_time = 0.0
    primary_drafts: List[Dict[str, Any]] = []
    engine = "fallback"

    remaining_for_primary = min(
        MAX_PRIMARY_SECONDS,
        max(0.5, deadline - time.monotonic() - 3.0),
    )
    if remaining_for_primary >= 0.5:
        ai_attempted = True
        primary_start = time.monotonic()
        try:
            from app.services.quiz_gen_light import generate_lightweight

            with ThreadPoolExecutor(max_workers=1) as pool:
                fut = pool.submit(
                    generate_lightweight, text, num_questions=target + 2,
                )
                primary_drafts = fut.result(timeout=remaining_for_primary)
        except FuturesTimeout:
            logger.warning("Primary quiz engine timed out after %.1fs", remaining_for_primary)
            primary_drafts = []
        except Exception as exc:
            logger.warning("Primary quiz engine failed: %s", exc)
            primary_drafts = []
        ai_time = time.monotonic() - primary_start
        if primary_drafts:
            engine = "light"

    from app.services.quiz_question_quality import (
        finalize_quiz_fast,
        log_quiz_generation_stats,
    )

    final, valid_ai, fallback_count = finalize_quiz_fast(
        primary_drafts,
        text,
        material_title,
        target=target,
        deadline=deadline,
        fallback_text=raw_text,
    )

    if not primary_drafts or fallback_count > 0:
        engine = "fallback" if not primary_drafts else f"{engine}+fallback"

    log_quiz_generation_stats(
        material_title=material_title,
        content_length=content_len,
        ai_attempted=ai_attempted,
        ai_time_seconds=round(ai_time, 2),
        valid_ai_count=valid_ai,
        fallback_count=fallback_count,
        final_count=len(final),
    )

    elapsed = time.monotonic() - start
    logger.info("Quiz generation completed in %.2fs engine=%s", elapsed, engine)
    return final, engine

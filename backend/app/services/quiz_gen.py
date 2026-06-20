"""
Quiz generation from learning-material text.

Wraps rule-based generators and validates output for demo-quality MCQs.
"""

import io
import logging
import os
import sys
from typing import Any, Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_QUIZ_DIR = os.path.join(_REPO, "ai", "quiz_generator-main")

_ready = False
_generator = None
_DocumentContent = None

DEFAULT_QUESTIONS = 5
MIN_RICH_CONTENT_CHARS = 1000


def _ensure_ready() -> None:
    global _ready, _generator, _DocumentContent
    if _ready:
        return
    if _QUIZ_DIR not in sys.path:
        sys.path.insert(0, _QUIZ_DIR)

    import nltk
    for pkg in ("punkt", "punkt_tab", "stopwords", "wordnet", "omw-1.4"):
        try:
            nltk.download(pkg, quiet=True)
        except Exception:
            pass

    from quiz_generator import QuizGenerator
    from data_structures import DocumentContent

    _generator = QuizGenerator()
    _DocumentContent = DocumentContent
    _ready = True


def available() -> bool:
    try:
        _ensure_ready()
        return True
    except Exception:
        return False


def extract_pdf_text(data: bytes) -> str:
    import PyPDF2
    reader = PyPDF2.PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def generate_from_text(text: str, num_questions: int = 8) -> List[Dict[str, Any]]:
    if not text or not text.strip():
        return []
    _ensure_ready()

    loader = _generator.loader
    extractor = _generator.extractor
    text_clean, sentences, paragraphs = loader.process_text(text)
    concepts = extractor.extract_real_concepts(text_clean)
    definitions = extractor.extract_definitions(text_clean)
    relationships = extractor.extract_relationships(text_clean, concepts)

    document = _DocumentContent(
        raw_text=text_clean,
        sentences=sentences,
        paragraphs=paragraphs,
        concepts=concepts,
        definitions=definitions,
        relationships=relationships,
    )
    raw_questions = _generator.generate_quiz(document, num_questions)

    out: List[Dict[str, Any]] = []
    for i, q in enumerate(raw_questions):
        options = list(getattr(q, "options", None) or [])
        correct = getattr(q, "correct_answer", None)
        if len(options) < 2 or correct not in options:
            continue
        out.append({
            "id": f"q{i + 1}",
            "question": q.question,
            "options": options,
            "correctIndex": options.index(correct),
        })
    return out


def _supplement_to_target(
    primary: List[Dict[str, Any]],
    text: str,
    num_questions: int,
    primary_engine: str,
) -> Tuple[List[Dict[str, Any]], str]:
    if len(primary) >= num_questions:
        return primary[:num_questions], primary_engine

    needed = num_questions - len(primary)
    try:
        from app.services.quiz_gen_fragment import generate_fragment_quiz

        fragments = generate_fragment_quiz(text, num_questions=needed + 4)
        if not fragments:
            return primary, primary_engine

        existing_keys = {q["question"].lower()[:60] for q in primary}
        combined = list(primary)
        for q in fragments:
            if len(combined) >= num_questions:
                break
            key = q["question"].lower()[:60]
            if key not in existing_keys:
                q = dict(q)
                q["id"] = f"q{len(combined) + 1}"
                combined.append(q)
                existing_keys.add(key)

        added = len(combined) - len(primary)
        engine = f"{primary_engine}+fragment" if added > 0 else primary_engine
        return combined, engine
    except Exception as exc:
        logger.warning("Fragment supplement failed: %s", exc)
        return primary, primary_engine


def _collect_drafts(
    text: str,
    draft_count: int,
) -> Tuple[List[Dict[str, Any]], str]:
    """Gather draft MCQs from all engines; finalize once at the end."""
    drafts: List[Dict[str, Any]] = []
    engine = "failed"

    try:
        from app.services.quiz_gen_light import generate_lightweight

        light = generate_lightweight(text, num_questions=draft_count)
        if light:
            combined, eng = _supplement_to_target(light, text, draft_count, "light")
            drafts.extend(combined)
            engine = eng
    except Exception as exc:
        logger.warning("Lightweight engine failed: %s", exc)

    try:
        from app.services.quiz_gen_lecture import generate_lecture_quiz

        lecture = generate_lecture_quiz(text, num_questions=draft_count)
        if lecture:
            combined, eng = _supplement_to_target(lecture, text, draft_count, "lecture")
            drafts.extend(combined)
            engine = eng if engine == "failed" else f"{engine}+lecture"
    except Exception as exc:
        logger.warning("Lecture engine failed: %s", exc)

    if available():
        try:
            heavy = generate_from_text(text, num_questions=draft_count)
            if heavy:
                combined, eng = _supplement_to_target(heavy, text, draft_count, "heavy")
                drafts.extend(combined)
                engine = eng if engine == "failed" else f"{engine}+heavy"
        except Exception as exc:
            logger.warning("Heavy engine failed: %s", exc)

    try:
        from app.services.quiz_gen_fragment import generate_fragment_quiz

        fragment = generate_fragment_quiz(text, num_questions=draft_count)
        if fragment:
            drafts.extend(fragment)
            if engine == "failed":
                engine = "fragment"
    except Exception as exc:
        logger.warning("Fragment engine failed: %s", exc)

    return drafts, engine


def _guarantee_rich_content(
    questions: List[Dict[str, Any]],
    text: str,
    material_title: Optional[str],
    num_questions: int,
    engine: str,
) -> Tuple[List[Dict[str, Any]], str]:
    content_len = len(text.strip())
    min_needed = num_questions if content_len > MIN_RICH_CONTENT_CHARS else min(3, num_questions)

    if len(questions) >= min_needed:
        return questions[:num_questions], engine

    if content_len <= MIN_RICH_CONTENT_CHARS:
        return questions[:num_questions], engine

    from app.services.quiz_gen_fallback import generate_deterministic_fallback
    from app.services.quiz_question_quality import finalize_quiz_questions

    fb = generate_deterministic_fallback(text, material_title, num_questions + 2)
    merged = finalize_quiz_questions(
        questions + fb, text, material_title, target=num_questions,
    )
    if len(merged) >= min_needed:
        return merged[:num_questions], "deterministic_fallback"

    fb_relaxed = generate_deterministic_fallback(
        text, material_title, num_questions + 2, relax_validation=True,
    )
    merged = finalize_quiz_questions(
        questions + fb_relaxed, text, material_title, target=num_questions,
    )
    if merged:
        return merged[:num_questions], "deterministic_fallback_relaxed"

    return questions[:num_questions], engine


def generate_questions(
    text: str,
    num_questions: int = 5,
    material_title: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], str]:
    if not text or not text.strip():
        logger.warning("Quiz generation skipped: no content_text")
        return [], "no_text"

    try:
        from app.services.quiz_material_eligibility import prepare_quiz_generation_text
        text = prepare_quiz_generation_text(text)
    except Exception:
        pass

    if not text.strip():
        return [], "no_text"

    target = max(num_questions, DEFAULT_QUESTIONS)
    draft_count = max(target * 3, 12)

    logger.info(
        "Quiz generation start title=%s content_len=%d target=%d",
        (material_title or "")[:80],
        len(text),
        target,
    )

    drafts, engine = _collect_drafts(text, draft_count)

    from app.services.quiz_question_quality import finalize_quiz_questions

    finalized = finalize_quiz_questions(
        drafts, text, material_title, target=target,
    )

    if not finalized:
        from app.services.quiz_gen_fallback import generate_deterministic_fallback

        fb = generate_deterministic_fallback(text, material_title, target + 2)
        finalized = finalize_quiz_questions(fb, text, material_title, target=target)
        engine = "deterministic_fallback"

    finalized, engine = _guarantee_rich_content(
        finalized, text, material_title, target, engine,
    )

    logger.info(
        "Quiz generation done title=%s engine=%s final_count=%d",
        (material_title or "")[:80],
        engine,
        len(finalized),
    )

    return finalized, engine

"""
Quiz generation from learning-material text.

Wraps the rule-based generator in `ai/quiz_generator-main` (nltk + PyPDF2 +
python-pptx — no heavy ML/LLM). PDFs live behind Moodle auth, so the extension
uploads each material's bytes; here we extract the text (PyPDF2) and, on demand,
turn it into multiple-choice questions in the frontend's QuizQuestion shape
({id, question, options, correctIndex}).

All heavy work is lazy/guarded so the API still boots if the deps aren't
installed.
"""

import io
import logging
import os
import sys
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_QUIZ_DIR = os.path.join(_REPO, "ai", "quiz_generator-main")

_ready = False
_generator = None
_DocumentContent = None


def _ensure_ready() -> None:
    """Lazily import the generator + ensure nltk data is present."""
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
    """Extract text from PDF bytes (same library the generator uses)."""
    import PyPDF2
    reader = PyPDF2.PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def generate_from_text(text: str, num_questions: int = 8) -> List[Dict[str, Any]]:
    """
    Build the generator's DocumentContent from raw text and return MCQs mapped
    to the frontend shape. Short-answer / option-less questions are skipped
    (the UI needs options + a correct index).
    """
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
            continue  # need a real MCQ
        out.append({
            "id": f"q{i + 1}",
            "question": q.question,
            "options": options,
            "correctIndex": options.index(correct),
        })
    return out


def generate_questions(text: str, num_questions: int = 8) -> Tuple[List[Dict[str, Any]], str]:
    """
    Generate MCQs from stored content_text.

    Tries the heavy ai/quiz_generator-main path when available (local dev), then
    falls back to the Vercel-safe lightweight generator. Returns (questions, engine).
    """
    if not text or not text.strip():
        logger.warning("Quiz generation skipped: no content_text")
        return [], "no_text"

    if available():
        try:
            heavy = generate_from_text(text, num_questions=num_questions)
            if len(heavy) >= 5:
                logger.info("Quiz generated via heavy engine (%d questions)", len(heavy))
                return heavy, "heavy"
            logger.warning(
                "Heavy quiz engine returned only %d questions; trying lightweight",
                len(heavy),
            )
        except Exception as exc:
            logger.warning("Heavy quiz engine failed: %s", exc, exc_info=True)

    try:
        from app.services.quiz_gen_light import generate_lightweight

        light = generate_lightweight(text, num_questions=num_questions)
        if light:
            logger.info("Quiz generated via lightweight engine (%d questions)", len(light))
            return light, "light"
        logger.warning("Lightweight quiz engine returned no questions")
    except Exception as exc:
        logger.error("Lightweight quiz engine failed: %s", exc, exc_info=True)

    return [], "failed"

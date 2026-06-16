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

    Engine priority (content-grounded first):
      1. Lightweight (regex, definition/concept extraction) — always available,
         all distractors come from the SAME material text.
      2. Lecture fallback (arrow notation, heading+bullet groups) — for slide/lab PDFs.
      3. Heavy NLTK (ai/quiz_generator-main) — local-dev only, used as last resort
         because its question templates can sound domain-inappropriate for technical
         content (electronics, hardware, etc.).

    Keeping heavy as last resort means:
      - Lab and lecture PDFs always get content-grounded questions first.
      - Seeded demo content (rich prose) still works via lightweight (≥5 pairs).
    """
    if not text or not text.strip():
        logger.warning("Quiz generation skipped: no content_text")
        return [], "no_text"

    # Normalise before passing to any engine — removes Unicode private-use chars
    # (e.g. \uf0a1) that PyPDF2 produces and that break regex matching.
    try:
        from app.services.quiz_material_eligibility import normalize_quiz_text
        text = normalize_quiz_text(text)
    except Exception:
        pass  # normalisation is best-effort

    if not text.strip():
        return [], "no_text"

    # ── 1. Lightweight (content-grounded, all distractors from the same material) ──
    try:
        from app.services.quiz_gen_light import generate_lightweight

        light = generate_lightweight(text, num_questions=num_questions)
        if light:
            logger.info("Quiz generated via lightweight engine (%d questions)", len(light))
            return light, "light"
        logger.warning("Lightweight quiz engine returned no questions")
    except Exception as exc:
        logger.error("Lightweight quiz engine failed: %s", exc, exc_info=True)

    # ── 2. Lecture fallback (arrow notation, bullet/heading groups) ──────────────
    try:
        from app.services.quiz_gen_lecture import generate_lecture_quiz

        lecture = generate_lecture_quiz(text, num_questions=num_questions)
        if lecture:
            logger.info("Quiz generated via lecture engine (%d questions)", len(lecture))
            return lecture, "lecture"
        logger.warning("Lecture quiz engine returned no questions")
    except Exception as exc:
        logger.error("Lecture quiz engine failed: %s", exc, exc_info=True)

    # ── 3. Heavy NLTK (last resort — local dev only, may use generic templates) ──
    if available():
        try:
            heavy = generate_from_text(text, num_questions=num_questions)
            if len(heavy) >= 3:
                logger.info("Quiz generated via heavy engine (%d questions)", len(heavy))
                return heavy, "heavy"
            logger.warning(
                "Heavy quiz engine returned only %d questions",
                len(heavy),
            )
        except Exception as exc:
            logger.warning("Heavy quiz engine failed: %s", exc, exc_info=True)

    return [], "failed"

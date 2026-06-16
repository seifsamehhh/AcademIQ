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


def _supplement_to_target(
    primary: List[Dict[str, Any]],
    text: str,
    num_questions: int,
    primary_engine: str,
) -> Tuple[List[Dict[str, Any]], str]:
    """
    If primary has fewer than num_questions, fill the gap with fragment-engine
    recall questions drawn from the same material text.

    Deduplicates by comparing the first 60 chars of each question string.
    Renumbers all question IDs sequentially.
    Returns (combined, combined_engine_label).
    """
    if len(primary) >= num_questions:
        return primary[:num_questions], primary_engine

    needed = num_questions - len(primary)
    try:
        from app.services.quiz_gen_fragment import generate_fragment_quiz

        # Request a few extra candidates to absorb duplicates
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
        logger.info(
            "Supplemented %s quiz: %d → %d questions (+%d fragment)",
            primary_engine, len(primary), len(combined), added,
        )
        return combined, engine
    except Exception as exc:
        logger.warning("Fragment supplement failed: %s", exc)
        return primary, primary_engine


def generate_questions(text: str, num_questions: int = 5) -> Tuple[List[Dict[str, Any]], str]:
    """
    Generate MCQs from stored content_text.

    Engine priority (content-grounded first):
      1. Lightweight (regex, definition/concept extraction) — always available,
         all distractors come from the SAME material text.
      2. Lecture fallback (arrow notation, heading+bullet groups) — for slide/lab PDFs.
      3. Heavy NLTK (ai/quiz_generator-main) — local-dev only.
      4. Fragment fallback (content-recall MCQs from any readable sentences).

    After each primary engine produces questions, if the count is below
    num_questions, the fragment engine is used to supplement up to the target.
    This guarantees exactly num_questions whenever there is sufficient text.
    """
    if not text or not text.strip():
        logger.warning("Quiz generation skipped: no content_text")
        return [], "no_text"

    # Deep-clean: removes emails, ToC lines, name headers, page numbers while
    # PRESERVING newlines so line-aware engines still work correctly.
    try:
        from app.services.quiz_material_eligibility import deep_clean_quiz_text
        text = deep_clean_quiz_text(text)
    except Exception:
        pass

    if not text.strip():
        return [], "no_text"

    # ── 1. Lightweight ────────────────────────────────────────────────────────
    try:
        from app.services.quiz_gen_light import generate_lightweight

        light = generate_lightweight(text, num_questions=num_questions)
        if light:
            logger.info("Lightweight engine: %d questions", len(light))
            return _supplement_to_target(light, text, num_questions, "light")
        logger.warning("Lightweight engine returned 0 questions")
    except Exception as exc:
        logger.error("Lightweight engine failed: %s", exc, exc_info=True)

    # ── 2. Lecture fallback ───────────────────────────────────────────────────
    try:
        from app.services.quiz_gen_lecture import generate_lecture_quiz

        lecture = generate_lecture_quiz(text, num_questions=num_questions)
        if lecture:
            logger.info("Lecture engine: %d questions", len(lecture))
            return _supplement_to_target(lecture, text, num_questions, "lecture")
        logger.warning("Lecture engine returned 0 questions")
    except Exception as exc:
        logger.error("Lecture engine failed: %s", exc, exc_info=True)

    # ── 3. Heavy NLTK (local dev only) ────────────────────────────────────────
    if available():
        try:
            heavy = generate_from_text(text, num_questions=num_questions)
            if len(heavy) >= 3:
                logger.info("Heavy engine: %d questions", len(heavy))
                return _supplement_to_target(heavy, text, num_questions, "heavy")
            logger.warning("Heavy engine: only %d questions", len(heavy))
        except Exception as exc:
            logger.warning("Heavy engine failed: %s", exc, exc_info=True)

    # ── 4. Fragment fallback (pure content-recall) ────────────────────────────
    try:
        from app.services.quiz_gen_fragment import generate_fragment_quiz

        fragment = generate_fragment_quiz(text, num_questions=num_questions)
        if fragment:
            logger.info("Fragment engine: %d questions", len(fragment))
            return fragment[:num_questions], "fragment"
        logger.warning("Fragment engine returned 0 questions")
    except Exception as exc:
        logger.error("Fragment engine failed: %s", exc, exc_info=True)

    return [], "failed"

"""
Lightweight rule-based quiz generator — Vercel-safe (stdlib only).

Reads stored content_text (no PDF required) and builds multiple-choice questions
from definition-style sentences. Used when the heavy ai/quiz_generator-main
bundle is unavailable in serverless deploys.
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Dict, List, Set, Tuple

logger = logging.getLogger(__name__)

_MIN_DEFINITION_LEN = 20
_MAX_DEFINITION_LEN = 160
_MAX_OPTION_LEN = 110
_MIN_QUESTIONS = 3

_DEFINITION_PATTERNS = [
    re.compile(
        r"\b([A-Z][A-Za-z0-9]+(?:\s+[A-Za-z0-9]+){0,5})\s+is\s+(?:a|an|the)\s+([^.\n]+?)\.",
        re.MULTILINE,
    ),
    re.compile(
        r"\b([A-Z][A-Za-z0-9]+(?:\s+[A-Za-z0-9]+){0,5})\s+is\s+([^.\n]+?)\.",
        re.MULTILINE,
    ),
    re.compile(
        r"\b([A-Z][A-Za-z0-9]+(?:\s+[A-Za-z0-9]+){0,5})\s+are\s+([^.\n]+?)\.",
        re.MULTILINE,
    ),
    re.compile(
        r"\b([A-Z][A-Za-z0-9]+(?:\s+[A-Za-z0-9]+){0,5})\s+(?:refers to|means)\s+([^.\n]+?)\.",
        re.IGNORECASE | re.MULTILINE,
    ),
]

_SECTION_HEADERS = (
    "Definitions",
    "Key Concepts",
    "Examples",
    "Comparisons",
    "Summary",
    "Quiz Review",
    "Glossary for Review",
    "Seeded Demo Lecture",
)


def _strip_section_headers(text: str) -> str:
    cleaned = text
    for header in _SECTION_HEADERS:
        cleaned = cleaned.replace(header, " ")
    return cleaned


_INVALID_CONCEPTS = {
    "for example",
    "for instance",
    "in summary",
    "introduction",
    "summary",
    "programming lecture",
    "database lecture",
    "seeded demo material",
    "academiq test content",
}

_GENERIC_DISTRACTORS = [
    "A fixed hardware port used only for display output.",
    "A manual paper form submitted outside the application.",
    "An optional visual theme with no effect on program logic.",
    "A deprecated protocol no longer used in modern systems.",
    "A network cable standard unrelated to software design.",
    "A spreadsheet macro that only formats cell colors.",
    "A backup schedule that never interacts with source code.",
    "A printer setting that controls page margins only.",
]


def _normalize_concept(raw: str) -> str:
    concept = re.sub(r"\s+", " ", raw.strip())
    concept = re.sub(r"^(A|An|The)\s+", "", concept, flags=re.IGNORECASE)
    return concept.strip()


def _normalize_definition(raw: str) -> str:
    definition = re.sub(r"\s+", " ", raw.strip())
    definition = definition.rstrip(",;:")
    if definition and not definition.endswith("."):
        definition += "."
    return definition


def _definition_option(concept: str, definition: str) -> str:
    """Render a definition as a complete, readable MCQ option."""
    body = definition.strip().rstrip(".")
    body = re.sub(r"^(a|an|the)\s+", "", body, flags=re.IGNORECASE)
    if len(concept.split()) == 1:
        first_word = (body.split() or [""])[0].lower()
        article = "an" if first_word[:1] in "aeiou" else "a"
        text = f"{concept} is {article} {body}."
    elif concept.split()[-1].lower().endswith("s"):
        text = f"{concept} are {body}."
    else:
        text = f"{concept} refers to {body}."
    return _format_option(text)


def _format_option(text: str, *, max_len: int = _MAX_OPTION_LEN) -> str:
    """Turn a definition fragment into a clean, complete option line."""
    text = re.sub(r"\s+", " ", text.strip())
    text = text.rstrip(",;:")
    if not text:
        return ""
    if text[0].islower():
        text = text[0].upper() + text[1:]
    if not text.endswith("."):
        text += "."
    if len(text) <= max_len:
        return text
    cut = text[: max_len - 1].rsplit(" ", 1)[0]
    return cut.rstrip(".,;") + "."


def _option_key(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())[:90]


def _valid_concept(concept: str) -> bool:
    if not concept or len(concept) < 3:
        return False
    lower = concept.lower()
    if lower in _INVALID_CONCEPTS:
        return False
    words = concept.split()
    if len(words) > 5 or len(words) < 1:
        return False
    if any(bad in lower for bad in ("introduction", "summary", "lecture", "seeded", "demo material")):
        return False
    if len(words) >= 2 and words[-1].lower() == words[0].lower():
        return False
    if re.search(r"\sA\s+[A-Z]", concept):
        return False
    if " and " in lower and len(words) > 3:
        return False
    if len(words) >= 2 and concept.lower().count(words[0].lower()) > 1:
        return False
    return True


def _valid_definition(defn: str) -> bool:
    core = defn.rstrip(".")
    if len(core) < _MIN_DEFINITION_LEN or len(core) > _MAX_DEFINITION_LEN:
        return False
    if len(core.split()) < 5:
        return False
    return True


def extract_definitions(text: str) -> List[Tuple[str, str]]:
    """Pull concept/definition pairs from lecture-style prose."""
    seen: set[str] = set()
    pairs: List[Tuple[str, str]] = []
    normalized = re.sub(r"\s+", " ", _strip_section_headers(text).replace("\n", " "))
    sentences = re.split(r"(?<=[.!?])\s+", normalized)

    for sentence in sentences:
        if len(sentence.split()) < 6:
            continue
        lower_sentence = sentence.lower()
        if " while " in lower_sentence or " whereas " in lower_sentence:
            continue
        for pattern in _DEFINITION_PATTERNS:
            for match in pattern.findall(sentence):
                if len(match) == 2:
                    concept_raw, defn_raw = match
                else:
                    continue
                concept = _normalize_concept(concept_raw)
                definition = _normalize_definition(defn_raw)
                key = concept.lower()
                if not _valid_concept(concept) or not _valid_definition(definition):
                    continue
                if key in seen:
                    continue
                seen.add(key)
                pairs.append((concept, definition))

    return pairs


def _question_prompt(concept: str) -> str:
    words = concept.split()
    if words and words[-1].lower().endswith("s") and len(words) <= 3:
        return f"What are {concept}?"
    article = "an" if concept[:1].lower() in "aeiou" else "a"
    if len(words) == 1:
        return f"What is {article} {concept}?"
    return f"Which statement best describes {concept}?"


def _stable_shuffle(options: List[str], salt: str) -> Tuple[List[str], int]:
    """Shuffle options deterministically; return list and correct index."""
    correct = options[0]
    seed = int(hashlib.md5(salt.encode()).hexdigest(), 16)
    ordered = list(options)
    for i in range(len(ordered) - 1, 0, -1):
        j = seed % (i + 1)
        seed //= (i + 1)
        ordered[i], ordered[j] = ordered[j], ordered[i]
    return ordered, ordered.index(correct)


def _pick_distractors(
    concept: str,
    correct: str,
    pool: List[Tuple[str, str]],
    used_global: Set[str],
    n: int = 3,
) -> List[str]:
    """Build distinct wrong answers from other concepts' definitions."""
    correct_key = _option_key(correct)
    candidates: List[str] = []

    for other_concept, other_def in pool:
        if other_concept.lower() == concept.lower():
            continue
        option = _definition_option(other_concept, other_def)
        key = _option_key(option)
        if key == correct_key or key in used_global or option in candidates:
            continue
        candidates.append(option)

    for filler in _GENERIC_DISTRACTORS:
        if len(candidates) >= n:
            break
        option = _format_option(filler)
        key = _option_key(option)
        # Generic fillers may repeat across questions; only avoid the correct answer.
        if key != correct_key and option not in candidates:
            candidates.append(option)

    return candidates[:n]


def _build_question(
    idx: int,
    concept: str,
    definition: str,
    pool: List[Tuple[str, str]],
    used_global: Set[str],
) -> Dict[str, Any] | None:
    correct = _definition_option(concept, definition)
    if not correct:
        return None

    distractors = _pick_distractors(concept, correct, pool, used_global, n=3)
    if len(distractors) < 3:
        return None

    options_raw = [correct] + distractors
    # Ensure four unique options inside the question.
    unique: List[str] = []
    seen_local: Set[str] = set()
    for opt in options_raw:
        key = _option_key(opt)
        if key in seen_local:
            continue
        seen_local.add(key)
        unique.append(opt)
    if len(unique) < 4:
        return None

    options, correct_idx = _stable_shuffle(unique[:4], f"{concept}:{idx}")
    # Track correct answers globally so the same concept is not quizzed twice.
    used_global.add(_option_key(correct))

    return {
        "id": f"q{idx}",
        "question": _question_prompt(concept),
        "options": options,
        "correctIndex": correct_idx,
    }


def generate_lightweight(text: str, num_questions: int = 8) -> List[Dict[str, Any]]:
    """
    Build MCQ questions from content_text using definition extraction only.
    Returns [] when the text has no usable structure.
    """
    if not text or not text.strip():
        logger.warning("Lightweight quiz gen: empty text")
        return []

    pairs = extract_definitions(text)
    logger.info("Lightweight quiz gen: extracted %d definition pairs", len(pairs))

    if len(pairs) < 3:
        logger.warning("Lightweight quiz gen: insufficient definitions (%d)", len(pairs))
        return []

    target = max(_MIN_QUESTIONS, min(num_questions, len(pairs)))
    questions: List[Dict[str, Any]] = []
    used_global: Set[str] = set()

    for concept, definition in pairs:
        if len(questions) >= target:
            break
        q = _build_question(len(questions) + 1, concept, definition, pairs, used_global)
        if q:
            questions.append(q)

    logger.info("Lightweight quiz gen: produced %d questions", len(questions))
    return questions if len(questions) >= _MIN_QUESTIONS else []

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
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

_MIN_DEFINITION_LEN = 12
_MAX_DEFINITION_LEN = 220
_MIN_QUESTIONS = 5

_DEFINITION_PATTERNS = [
    re.compile(
        r"\b([A-Z][A-Za-z0-9]+(?:\s+[A-Za-z0-9]+){0,7})\s+is\s+(?:a|an|the)\s+([^.\n]+?)\.",
        re.MULTILINE,
    ),
    re.compile(
        r"\b([A-Z][A-Za-z0-9]+(?:\s+[A-Za-z0-9]+){0,7})\s+is\s+([^.\n]+?)\.",
        re.MULTILINE,
    ),
    re.compile(
        r"\b([A-Z][A-Za-z0-9]+(?:\s+[A-Za-z0-9]+){0,7})\s+are\s+([^.\n]+?)\.",
        re.MULTILINE,
    ),
    re.compile(
        r"\b([A-Z][A-Za-z0-9]+(?:\s+[A-Za-z0-9]+){0,7})\s+(?:refers to|means)\s+([^.\n]+?)\.",
        re.IGNORECASE | re.MULTILINE,
    ),
    re.compile(
        r"\b([A-Z][A-Za-z0-9]+(?:\s+[A-Za-z0-9]+){0,7})\s+involves\s+([^.\n]+?)\.",
        re.IGNORECASE | re.MULTILINE,
    ),
    re.compile(
        r"\b([A-Z][A-Za-z0-9]+(?:\s+[A-Za-z0-9]+){0,7})\s+consists of\s+([^.\n]+?)\.",
        re.IGNORECASE | re.MULTILINE,
    ),
]

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


def _normalize_concept(raw: str) -> str:
    concept = re.sub(r"\s+", " ", raw.strip())
    concept = re.sub(r"^(A|An|The)\s+", "", concept, flags=re.IGNORECASE)
    return concept.strip()


def _normalize_definition(raw: str) -> str:
    definition = re.sub(r"\s+", " ", raw.strip())
    if definition.endswith(","):
        definition = definition[:-1]
    return definition.strip()


def _valid_concept(concept: str) -> bool:
    if not concept or len(concept) < 3:
        return False
    lower = concept.lower()
    if lower in _INVALID_CONCEPTS:
        return False
    words = concept.split()
    if len(words) > 6 or len(words) < 1:
        return False
    if any(bad in lower for bad in ("introduction", "summary", "lecture", "seeded", "demo material")):
        return False
    if len(words) >= 2 and words[-1].lower() == words[0].lower():
        return False
    if re.search(r"\sA\s+[A-Z]", concept):
        return False
    if " and " in lower and len(words) > 4:
        return False
    if len(words) >= 2 and concept.lower().count(words[0].lower()) > 1:
        return False
    if not re.search(r"[A-Za-z]", concept):
        return False
    return True


def _valid_definition(defn: str) -> bool:
    if len(defn) < _MIN_DEFINITION_LEN or len(defn) > _MAX_DEFINITION_LEN:
        return False
    if len(defn.split()) < 4:
        return False
    return True


def extract_definitions(text: str) -> List[Tuple[str, str]]:
    """Pull concept/definition pairs from lecture-style prose."""
    seen: set[str] = set()
    pairs: List[Tuple[str, str]] = []
    normalized = re.sub(r"\s+", " ", text.replace("\n", " "))
    sentences = re.split(r"(?<=[.!?])\s+", normalized)

    for sentence in sentences:
        if len(sentence.split()) < 8:
            continue
        for pattern in _DEFINITION_PATTERNS:
            for concept_raw, defn_raw in pattern.findall(sentence):
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


def _stable_shuffle(options: List[str], concept: str) -> Tuple[List[str], int]:
    """Shuffle options deterministically; return list and correct index."""
    correct = options[0]
    rest = options[1:]
    seed = int(hashlib.md5(concept.encode()).hexdigest(), 16)
    ordered = [correct] + rest
    for i in range(len(ordered) - 1, 0, -1):
        j = seed % (i + 1)
        seed //= (i + 1)
        ordered[i], ordered[j] = ordered[j], ordered[i]
    return ordered, ordered.index(correct)


def _distractors(
    concept: str,
    correct: str,
    pool: List[Tuple[str, str]],
    n: int = 3,
) -> List[str]:
    """Build wrong answers from other definitions in the same document."""
    candidates: List[str] = []
    for other_concept, other_def in pool:
        if other_concept.lower() == concept.lower():
            continue
        snippet = other_def if len(other_def) <= 120 else other_def[:117] + "..."
        if snippet.lower() != correct.lower() and snippet not in candidates:
            candidates.append(snippet)

    fillers = [
        "A unrelated process that does not apply to this topic.",
        "A deprecated technique no longer used in modern systems.",
        "An optional cosmetic feature with no effect on program behavior.",
        "A hardware component unrelated to software design.",
        "A manual administrative task performed outside the application.",
    ]
    for filler in fillers:
        if len(candidates) >= n:
            break
        if filler.lower() != correct.lower():
            candidates.append(filler)

    return candidates[:n]


def _build_question(
    idx: int,
    concept: str,
    definition: str,
    pool: List[Tuple[str, str]],
    *,
    reverse: bool = False,
) -> Dict[str, Any] | None:
    distractors = _distractors(concept, definition, pool, n=3)
    if len(distractors) < 3:
        return None

    if reverse:
        question = f"Which term is defined as: \"{definition[:140]}{'...' if len(definition) > 140 else ''}\"?"
        correct_option = concept
        wrong = [c for c, _ in pool if c.lower() != concept.lower()][:3]
        while len(wrong) < 3:
            wrong.append(f"Concept variant {len(wrong) + 1}")
        options, correct_idx = _stable_shuffle([correct_option] + wrong[:3], concept + str(idx))
    else:
        question = f"Which statement best describes {concept}?"
        options, correct_idx = _stable_shuffle([definition] + distractors, concept)

    return {
        "id": f"q{idx}",
        "question": question,
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

    if len(pairs) < 2:
        logger.warning("Lightweight quiz gen: insufficient definitions (%d)", len(pairs))
        return []

    target = max(_MIN_QUESTIONS, min(num_questions, len(pairs) * 2))
    questions: List[Dict[str, Any]] = []

    for i, (concept, definition) in enumerate(pairs):
        if len(questions) >= target:
            break
        q = _build_question(len(questions) + 1, concept, definition, pairs, reverse=False)
        if q:
            questions.append(q)

    for i, (concept, definition) in enumerate(pairs):
        if len(questions) >= target:
            break
        q = _build_question(len(questions) + 1, concept, definition, pairs, reverse=True)
        if q:
            questions.append(q)

    logger.info("Lightweight quiz gen: produced %d questions", len(questions))
    return questions[:num_questions] if len(questions) >= _MIN_QUESTIONS else questions

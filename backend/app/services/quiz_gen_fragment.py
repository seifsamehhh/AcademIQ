"""
Concept-extraction fallback quiz generator.

Used when the primary engines (lightweight definition extractor, lecture
structural parser) produce fewer than num_questions questions.

Strategy:
  - Extract (term, explanation) pairs using RELAXED patterns:
    "Term is a/an/the ..."  "Term refers to..."  "Term: ..."  "Term – ..."
  - Trim every answer option to ≤ MAX_ANSWER_LEN characters at a word boundary.
  - Generate concept questions:  "What does X refer to?",
    "What is the purpose of X?",  "Which statement best describes X?" etc.
  - All distractors come from OTHER extracted pairs in the SAME material.
  - Returns [] if fewer than 3 valid (term, explanation) pairs are found.

IMPORTANT: This engine NEVER produces generic recall questions such as
  "Which of the following statements is from this material?"
Every question names a real concept extracted from the selected material.
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_ANSWER_LEN = 120   # hard character cap per answer option
MIN_ANSWER_LEN = 15    # skip trivially short answers
MIN_TERM_LEN   = 3     # skip single-char tokens
MAX_TERM_WORDS = 8     # skip overly long noun phrases

_ARTIFACT_RE = re.compile(
    r"[\uf000-\uf8ff\ufffd\u25a0-\u25ff\u2013\u2014\u2022\u25cf\u00b7]"
)
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# ── Vague first-word filter (mirrors quiz_gen_light blacklist) ────────────────
_VAGUE_TERMS: frozenset[str] = frozenset(
    "it its this that these those they their there what which when where "
    "who how why note example use case step output result method overview "
    "introduction conclusion summary basically generally typically usually "
    "often always never sometimes".split()
)

# ── Relaxed (term, explanation) extraction patterns ──────────────────────────
# More permissive than quiz_gen_light: case-insensitive, more verbs, dash lines.
_PAIR_PATTERNS: List[re.Pattern] = [
    # "Term is a/an/the explanation."
    re.compile(
        r"\b([A-Z][A-Za-z0-9]+(?:\s+[A-Za-z0-9]+){0,6})"
        r"\s+is\s+(?:a|an|the)\s+([^.\n]{15,200})\.",
        re.MULTILINE,
    ),
    # "Term is explanation."
    re.compile(
        r"\b([A-Z][A-Za-z0-9]+(?:\s+[A-Za-z0-9]+){0,6})"
        r"\s+is\s+([^.\n]{15,200})\.",
        re.MULTILINE,
    ),
    # "Term refers/means/allows/enables/provides/represents/involves explanation."
    re.compile(
        r"\b([A-Z][A-Za-z0-9]+(?:\s+[A-Za-z0-9]+){0,6})"
        r"\s+(?:refers?\s+to|means?|allows?|enables?|provides?|represents?|involves?)\s+([^.\n]{15,200})\.",
        re.IGNORECASE | re.MULTILINE,
    ),
    # "Term: explanation."  (colon — common in slide notes and labs)
    re.compile(
        r"(?:^|\n)\s*([A-Z][A-Za-z0-9][A-Za-z0-9 /&\-]{1,50}?)\s*:\s+([^.\n]{15,200})\.",
        re.MULTILINE,
    ),
    # "Term – explanation." or "Term — explanation."  (dash — common in bullets)
    re.compile(
        r"(?:^|\n)\s*([A-Z][A-Za-z0-9][A-Za-z0-9 /&\-]{1,40}?)\s+[\u2013\u2014\-]\s+([^.\n]{15,200})\.",
        re.MULTILINE,
    ),
    # "Term (ABBREV) is a/an explanation."
    re.compile(
        r"\b([A-Z][A-Za-z][A-Za-z0-9\s/&\-]{1,40}?)\s+\(\s*([A-Z][A-Z0-9]{1,7})\s*\)"
        r"\s+is\s+(?:a|an|the)?\s*([^.\n]{15,200})\.",
        re.MULTILINE,
    ),
]

# ── Question templates cycled across questions ────────────────────────────────
_QUESTION_TEMPLATES: List[str] = [
    "What does {} refer to?",
    "What is the purpose of {}?",
    "Which statement best describes {}?",
    "What is {}?",
    "What is one key aspect of {}?",
    "How is {} defined in this material?",
    "Which concept is described as {}?",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clean_term(raw: str) -> Optional[str]:
    """Validate and normalise a candidate concept term."""
    term = re.sub(r"\s+", " ", raw.strip())
    term = re.sub(r"^(?:a|an|the)\s+", "", term, flags=re.IGNORECASE)
    term = term.strip()
    if len(term) < MIN_TERM_LEN:
        return None
    words = term.split()
    if len(words) > MAX_TERM_WORDS:
        return None
    if words[0].lower() in _VAGUE_TERMS:
        return None
    if _ARTIFACT_RE.search(term):
        return None
    # Must contain at least one real alphabetic word of ≥3 chars
    if not any(re.match(r"[A-Za-z]{3,}", w) for w in words):
        return None
    return term


def _trim_to_len(text: str, max_len: int = MAX_ANSWER_LEN) -> str:
    """Trim text to max_len at a word boundary, preserving terminal punctuation."""
    text = re.sub(r"\s+", " ", text.strip()).rstrip(".,;:")
    if len(text) <= max_len:
        return text
    trimmed = ""
    for word in text.split():
        candidate = (trimmed + " " + word).strip()
        if len(candidate) <= max_len:
            trimmed = candidate
        else:
            break
    return trimmed or text[:max_len]


def _clean_answer(raw: str) -> Optional[str]:
    """Validate, trim, and format an answer option."""
    ans = re.sub(r"\s+", " ", raw.strip()).rstrip(".,;:")
    if _ARTIFACT_RE.search(ans):
        return None
    if _EMAIL_RE.search(ans):
        return None
    if len(ans) < MIN_ANSWER_LEN:
        return None
    ans = _trim_to_len(ans, MAX_ANSWER_LEN)
    if len(ans) < MIN_ANSWER_LEN:
        return None
    ans = ans[0].upper() + ans[1:]
    if ans[-1] not in ".!?":
        ans += "."
    return ans


def _extract_pairs(text: str) -> List[Tuple[str, str]]:
    """
    Extract (term, explanation) pairs using relaxed patterns.

    Returns a deduplicated list ordered by first appearance.
    For ABBREV patterns (3 groups), the main term is used as the key and
    the explanation is taken from group 3.
    """
    seen_terms: Set[str] = set()
    pairs: List[Tuple[str, str]] = []

    for pattern in _PAIR_PATTERNS:
        for m in pattern.finditer(text):
            groups = m.groups()
            if len(groups) < 2:
                continue
            # ABBREV pattern produces 3 groups: (full_name, abbrev, explanation)
            if len(groups) == 3:
                term_raw, _, ans_raw = groups
            else:
                term_raw, ans_raw = groups[0], groups[-1]

            term = _clean_term(term_raw)
            ans = _clean_answer(ans_raw)
            if not term or not ans:
                continue
            term_key = term.lower().strip()
            if term_key in seen_terms:
                continue
            seen_terms.add(term_key)
            pairs.append((term, ans))

    return pairs


def _stable_shuffle(options: List[str], salt: str) -> Tuple[List[str], int]:
    """Deterministic Fisher-Yates shuffle; returns (shuffled_list, correct_index)."""
    correct = options[0]
    seed = int(hashlib.md5(salt.encode()).hexdigest(), 16)
    ordered = list(options)
    for i in range(len(ordered) - 1, 0, -1):
        j = seed % (i + 1)
        seed //= (i + 1)
        ordered[i], ordered[j] = ordered[j], ordered[i]
    return ordered, ordered.index(correct)


# ── Public API ────────────────────────────────────────────────────────────────

def generate_fragment_quiz(text: str, num_questions: int = 5) -> List[Dict[str, Any]]:
    """
    Concept-based fallback quiz generator.

    Extracts (term, explanation) pairs using relaxed patterns from any
    educational text and builds real MCQ questions — never generic recall
    questions like "Which statement is from this material?".

    All answer options are trimmed to ≤ MAX_ANSWER_LEN chars.
    All distractors are drawn from other extracted pairs in the same material.

    Returns [] when fewer than 3 valid (term, explanation) pairs are found.
    """
    pairs = _extract_pairs(text)
    logger.info("Fragment quiz gen: %d concept pairs extracted", len(pairs))

    if len(pairs) < 3:
        logger.warning(
            "Fragment quiz gen: only %d pairs (need ≥3) — returning []", len(pairs)
        )
        return []

    target = min(num_questions, len(pairs))
    answers_pool = [ans for _, ans in pairs]
    questions: List[Dict[str, Any]] = []

    for i, (term, correct_ans) in enumerate(pairs):
        if len(questions) >= target:
            break

        distractors = [a for a in answers_pool if a != correct_ans][:3]
        if len(distractors) < 3:
            break

        template = _QUESTION_TEMPLATES[i % len(_QUESTION_TEMPLATES)]
        question_text = template.format(term)

        options_raw = [correct_ans] + distractors
        options, correct_idx = _stable_shuffle(
            options_raw, f"frag:{i}:{term[:20]}"
        )

        questions.append({
            "id": f"q{len(questions) + 1}",
            "question": question_text,
            "options": options,
            "correctIndex": correct_idx,
        })

    logger.info("Fragment quiz gen: produced %d questions", len(questions))
    return questions if len(questions) >= 3 else []

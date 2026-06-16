"""
Last-resort quiz generator — works on any extractable text.

Used when definition-extraction (lightweight), structural-pattern (lecture),
and NLTK (heavy) engines all fail.  Generates MCQs by selecting the most
informative sentences from the material and using other sentences from the
same material as distractors.

Questions are purely content-recall:
  "Which of the following statements is from this material?"

All four options (correct + 3 distractors) come from the SAME selected
material — nothing is invented or imported from elsewhere.

Returns [] only if the text has fewer than 4 usable sentences.
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Dict, List, Set, Tuple

logger = logging.getLogger(__name__)

_MIN_WORDS = 7        # minimum words in a usable sentence
_MAX_CHARS = 160      # trim long sentences to this length
_ARTIFACT_RE = re.compile(r"[\uf000-\uf8ff\ufffd\u25a0-\u25ff\u2013\u2014]")

# Question stems — rotated to reduce monotony across multiple questions
_QUESTION_STEMS = [
    "Which of the following statements is from this material?",
    "Which statement was mentioned in this material?",
    "Which of the following was described in this material?",
    "Which statement accurately represents content from this material?",
    "Which of the following is covered in this material?",
]


def _clean_sentence(s: str, max_chars: int = _MAX_CHARS) -> str:
    """Trim, capitalise, and ensure terminal punctuation."""
    s = s.strip()
    words = s.split()
    if len(s) > max_chars:
        s = " ".join(words[:22])
    if not s:
        return ""
    s = s[0].upper() + s[1:]
    if not s[-1] in ".!?":
        s += "."
    return s


def _info_score(sentence: str) -> int:
    """Score a sentence by information density (more unique long words = higher)."""
    words = re.findall(r"[a-zA-Z]{4,}", sentence)
    return len(set(w.lower() for w in words))


def _extract_sentences(text: str) -> List[str]:
    """
    Extract meaningful, clean sentences from any material text.
    Filtered to remove headers, noise, and artifact lines.
    """
    blob = re.sub(r"\s+", " ", (text or "").strip())
    raw = re.split(r"(?<=[.!?])\s+", blob)

    result: List[str] = []
    seen: Set[str] = set()

    for s in raw:
        s = s.strip()
        words = s.split()
        if len(words) < _MIN_WORDS:
            continue
        # Skip artifact characters (PDF private-use, geometric bullets)
        if _ARTIFACT_RE.search(s):
            continue
        # Skip mostly-numeric/symbolic lines
        if re.match(r"^[\d\s\W]+$", s):
            continue
        # Skip document-title patterns (em-dash + parenthetical)
        if re.search(r"[\u2013\u2014]", s) and re.search(r"\(.*\)", s):
            continue
        # Skip if >40% uppercase (slide headers)
        if sum(1 for c in s if c.isupper()) / max(len(s), 1) > 0.4:
            continue
        cleaned = _clean_sentence(s)
        if not cleaned or len(cleaned) < 25:
            continue
        key = cleaned.lower()[:60]
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)

    # Sort by information density so the most informative sentences become questions
    result.sort(key=_info_score, reverse=True)
    return result


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


def generate_fragment_quiz(text: str, num_questions: int = 8) -> List[Dict[str, Any]]:
    """
    Generate MCQs from any extractable text.

    Strategy:
      - Extract all meaningful sentences from the material.
      - Sort by information density (most informative first).
      - Each question uses one sentence as the correct answer and three
        other sentences from the same material as distractors.
      - All four options are grounded in the selected material.

    Returns [] if the text has fewer than 4 usable sentences.
    """
    sentences = _extract_sentences(text)
    logger.info("Fragment quiz gen: %d usable sentences extracted", len(sentences))

    if len(sentences) < 4:
        logger.warning("Fragment quiz gen: not enough sentences (%d < 4)", len(sentences))
        return []

    target = min(num_questions, len(sentences))
    questions: List[Dict[str, Any]] = []
    used_keys: Set[str] = set()

    for i, correct_sentence in enumerate(sentences):
        if len(questions) >= target:
            break
        key = correct_sentence.lower()[:60]
        if key in used_keys:
            continue

        # Three distractors: other sentences from the same material, avoiding duplicates
        distractors: List[str] = [
            s for s in sentences if s != correct_sentence and s.lower()[:60] not in used_keys
        ][:3]
        if len(distractors) < 3:
            break

        stem = _QUESTION_STEMS[len(questions) % len(_QUESTION_STEMS)]
        options_raw = [correct_sentence] + distractors
        options, correct_idx = _stable_shuffle(options_raw, f"frag:{i}:{correct_sentence[:20]}")
        used_keys.add(key)

        questions.append(
            {
                "id": f"q{len(questions) + 1}",
                "question": stem,
                "options": options,
                "correctIndex": correct_idx,
            }
        )

    logger.info("Fragment quiz gen: produced %d questions", len(questions))
    return questions if len(questions) >= 3 else []

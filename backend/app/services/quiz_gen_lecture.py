"""
Lecture-based MCQ fallback generator — for slide/lab PDFs that lack clean "X is Y" sentences.

Handles:
  - "Concept → definition" arrow notation
  - Heading + numbered/bullet list groups  → association questions
  - Any remaining meaningful concept-description pairs

Used as a third fallback after heavy + lightweight engines fail.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

_MIN_CONCEPTS = 3
_MAX_OPTION_LEN = 110

# ─────────────────────────── Text Cleaning ──────────────────────────────────

def _structure_normalize(text: str) -> str:
    """Clean noise chars, merge hyphenated line breaks, preserve newlines."""
    cleaned = text or ""
    cleaned = cleaned.replace("\x00", " ")
    cleaned = re.sub(r"[\uf000-\uf8ff]", " ", cleaned)
    cleaned = re.sub(r"[\u25a0-\u25ff\u2022\u2023\u2043]", " ", cleaned)
    cleaned = re.sub(r"-\n[ \t]*-?[ \t]*", "", cleaned)
    cleaned = re.sub(r"\n[ \t]*-\n[ \t]*", "", cleaned)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in cleaned.splitlines()]
    return "\n".join(l for l in lines if l)


def _remove_repeated_lines(text: str, threshold: int = 3) -> str:
    """Remove lines that appear ≥ threshold times (page headers/footers)."""
    lines = text.splitlines()
    counts = Counter(l.strip() for l in lines if l.strip())
    return "\n".join(l for l in lines if not l.strip() or counts[l.strip()] < threshold)


def _remove_noise_lines(text: str) -> str:
    """Drop lines that are pure numbers, single chars, or obvious noise."""
    result = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if re.match(r"^[\d\W]+$", s):   # all digits/punctuation
            continue
        if len(s) < 3:
            continue
        result.append(line)
    return "\n".join(result)


def clean_lecture_text(raw: str) -> str:
    """Full cleaning pipeline preserving newlines."""
    text = _structure_normalize(raw)
    text = _remove_repeated_lines(text, threshold=3)
    text = _remove_noise_lines(text)
    return text


# ─────────────────────────── Pair Extraction ────────────────────────────────

# "X → description" or "X ⟶ description" (arrow notation in slides)
_ARROW_RE = re.compile(
    r"([A-Z][A-Za-z][A-Za-z0-9\s/&\-]{1,45}?)\s*[→⟶⇒]\s*([^→⟶⇒\n]{15,200})",
    re.MULTILINE,
)

# "Note: concept → description" (common in lecture notes)
_NOTE_ARROW_RE = re.compile(
    r"(?:Note|Hint|Recall|Key|Definition)[:\s]+([A-Z][A-Za-z][A-Za-z0-9\s/&\-]{1,45}?)\s*[→⟶⇒:]\s*([^→⟶⇒\n]{15,200})",
    re.IGNORECASE | re.MULTILINE,
)


def _add_pair(
    pairs: List[Tuple[str, str]],
    seen: Set[str],
    concept: str,
    description: str,
) -> None:
    concept = re.sub(r"\s+", " ", concept.strip())
    description = re.sub(r"\s+", " ", description.strip()).rstrip(".,;:")
    if not description.endswith("."):
        description += "."
    key = concept.lower()
    if key in seen or len(concept) < 3 or len(description) < 20:
        return
    if len(concept.split()) > 8:
        return
    bad_concepts = {
        "for example", "for instance", "note", "summary",
        "introduction", "conclusion", "example", "hint",
    }
    if key in bad_concepts:
        return
    seen.add(key)
    pairs.append((concept, description))


def _extract_arrow_pairs(
    blob: str,
    seen: Set[str],
    pairs: List[Tuple[str, str]],
) -> None:
    for m in _NOTE_ARROW_RE.finditer(blob):
        _add_pair(pairs, seen, m.group(1), m.group(2))
    for m in _ARROW_RE.finditer(blob):
        _add_pair(pairs, seen, m.group(1), m.group(2))


# ─────────────────────────── Group Extraction ───────────────────────────────

# Numbered list item: "1- X", "1. X", "1) X"
_NUM_ITEM_RE = re.compile(r"^\d[\-.)]\s*(.{3,80})$")
# Bullet list item: "• X", "- X", "* X", "· X"
_BULLET_ITEM_RE = re.compile(r"^[•\-*·]\s*(.{3,80})$")


def _collect_list_items(lines: List[str], start: int, max_skip: int = 2) -> Tuple[List[str], int]:
    """
    Starting from `start`, collect consecutive numbered or bulleted items.
    Returns (items, end_index_exclusive).

    max_skip: maximum non-list lines to allow before giving up when no items found yet.
    This prevents a heading on line 1 from "claiming" a list on line 30.
    """
    items: List[str] = []
    i = start
    skipped_before_start = 0
    while i < len(lines):
        line = lines[i].strip()
        m = _NUM_ITEM_RE.match(line) or _BULLET_ITEM_RE.match(line)
        if m:
            item = m.group(1).strip()
            if len(item.split()) >= 1 and len(item) >= 3 and not re.match(r"^\d+$", item):
                items.append(item)
                skipped_before_start = 0  # reset once items start
        elif items and line:
            # Non-list line after items started — stop
            break
        elif not items and line:
            skipped_before_start += 1
            if skipped_before_start > max_skip:
                # Too many non-list lines before any items — heading is not for this list
                break
        i += 1
    return items, i


# Heading patterns for group extraction
_GROUP_HEADING_RE = re.compile(
    r"^([A-Z][A-Za-z][A-Za-z0-9\s/&\-]{2,60}?)\s*:?\s*$"
)


def extract_concept_groups(
    structured_text: str,
) -> List[Tuple[str, List[str]]]:
    """
    Extract (topic, [item1, item2, ...]) groups from heading + list patterns.
    Works on line-structured (newline-preserved) text.
    """
    lines = [l.strip() for l in structured_text.splitlines() if l.strip()]
    groups: List[Tuple[str, List[str]]] = []
    seen_topics: Set[str] = set()
    i = 0
    while i < len(lines):
        line = lines[i]
        # Detect a heading: ends with ":" or is a short all-caps-words line
        is_heading = False
        heading_text = ""
        if line.endswith(":"):
            heading_text = line.rstrip(":").strip()
            is_heading = True
        elif _GROUP_HEADING_RE.match(line) and len(line.split()) <= 7:
            heading_text = line
            is_heading = True

        # Non-colon headings must have ≥2 words to avoid matching course codes (CSC399-SWE412)
        if is_heading and heading_text and (
            line.endswith(":") or len(heading_text.split()) >= 2
        ):
            topic_key = heading_text.lower()
            if topic_key not in seen_topics and i + 1 < len(lines):
                items, end = _collect_list_items(lines, i + 1)
                if len(items) >= 2:
                    seen_topics.add(topic_key)
                    groups.append((heading_text, items))
                    i = end
                    continue
        i += 1
    return groups


# ─────────────────────────── MCQ Building ───────────────────────────────────

def _format_option(text: str) -> str:
    text = re.sub(r"\s+", " ", text.strip()).rstrip(".,;:")
    if not text:
        return ""
    if text[0].islower():
        text = text[0].upper() + text[1:]
    if not text.endswith("."):
        text += "."
    return text[:_MAX_OPTION_LEN].rsplit(" ", 1)[0].rstrip(".,;") + "." if len(text) > _MAX_OPTION_LEN else text


def _stable_shuffle(options: List[str], salt: str) -> Tuple[List[str], int]:
    correct = options[0]
    seed = int(hashlib.md5(salt.encode()).hexdigest(), 16)
    ordered = list(options)
    for i in range(len(ordered) - 1, 0, -1):
        j = seed % (i + 1)
        seed //= (i + 1)
        ordered[i], ordered[j] = ordered[j], ordered[i]
    return ordered, ordered.index(correct)


def _build_description_question(
    idx: int,
    concept: str,
    description: str,
    pool: List[Tuple[str, str]],
) -> Optional[Dict[str, Any]]:
    """'Which statement best describes [concept]?' from a concept-description pair."""
    correct = _format_option(description)
    if not correct or len(correct) < 20:
        return None

    distractors: List[str] = []
    for other_c, other_d in pool:
        if other_c.lower() == concept.lower():
            continue
        dist = _format_option(other_d)
        if dist and dist.lower() != correct.lower():
            distractors.append(dist)
        if len(distractors) >= 3:
            break

    if len(distractors) < 3:
        return None

    options = [correct] + distractors[:3]
    unique = list(dict.fromkeys(options))
    if len(unique) < 4:
        return None

    options_shuffled, correct_idx = _stable_shuffle(unique[:4], f"lecdesc:{concept}:{idx}")

    words = concept.split()
    if len(words) <= 3:
        question = f"Which statement best describes {concept}?"
    else:
        question = f"Which of the following best describes {concept}?"

    return {
        "id": f"q{idx}",
        "question": question,
        "options": options_shuffled,
        "correctIndex": correct_idx,
    }


def _build_association_question(
    idx: int,
    topic: str,
    correct_item: str,
    all_groups: List[Tuple[str, List[str]]],
    fallback_pool: List[Tuple[str, str]],
) -> Optional[Dict[str, Any]]:
    """'Which of the following is associated with [topic]?' from a concept group."""
    correct = _format_option(correct_item)
    if not correct or len(correct) < 3:
        return None

    distractors: List[str] = []
    # Prefer items from OTHER groups as distractors
    for other_topic, other_items in all_groups:
        if other_topic.lower() == topic.lower():
            continue
        for item in other_items:
            dist = _format_option(item)
            if dist and dist.lower() != correct.lower():
                distractors.append(dist)
            if len(distractors) >= 3:
                break
        if len(distractors) >= 3:
            break

    # Fall back to concept names from the definition pool
    if len(distractors) < 3:
        for concept, _desc in fallback_pool:
            dist = _format_option(concept)
            if dist and dist.lower() != correct.lower() and dist not in distractors:
                distractors.append(dist)
            if len(distractors) >= 3:
                break

    if len(distractors) < 3:
        return None

    options = [correct] + distractors[:3]
    unique = list(dict.fromkeys(options))
    if len(unique) < 4:
        return None

    options_shuffled, correct_idx = _stable_shuffle(unique[:4], f"lecassoc:{topic}:{correct_item}:{idx}")

    return {
        "id": f"q{idx}",
        "question": f"Which of the following is associated with {topic}?",
        "options": options_shuffled,
        "correctIndex": correct_idx,
    }


# ─────────────────────────── Public API ─────────────────────────────────────

def count_lecture_concepts(text: str) -> int:
    """
    Quick count of extractable lecture concepts (for eligibility checks).
    Does not build full MCQs — fast probe only.
    """
    structured = clean_lecture_text(text)
    blob = re.sub(r"\s+", " ", structured)

    seen: Set[str] = set()
    pairs: List[Tuple[str, str]] = []
    _extract_arrow_pairs(blob, seen, pairs)

    groups = extract_concept_groups(structured)
    # Each group with ≥2 items contributes at least 1 quizzable concept
    group_concepts = sum(1 for _, items in groups if len(items) >= 2)

    return len(pairs) + group_concepts


def generate_lecture_quiz(text: str, num_questions: int = 8) -> List[Dict[str, Any]]:
    """
    Generate MCQs from lecture/slide content.

    Uses:
      1. Arrow notation definitions  (Concept → description)
      2. Heading + numbered/bullet-list groups  (association questions)
      3. Definition pairs from quiz_gen_light as fallback pool for distractors

    Returns [] when there is truly not enough structured content.
    """
    from app.services.quiz_material_eligibility import normalize_quiz_text

    normalized = normalize_quiz_text(text)
    if not normalized:
        return []

    structured = clean_lecture_text(normalized)
    blob = re.sub(r"\s+", " ", structured)

    # ── Extract concept pairs ──────────────────────────────────────────────
    seen: Set[str] = set()
    pairs: List[Tuple[str, str]] = []
    _extract_arrow_pairs(blob, seen, pairs)

    # Also pull any definition pairs from the lightweight extractor
    try:
        from app.services.quiz_gen_light import extract_definitions
        for concept, definition in extract_definitions(text):
            _add_pair(pairs, seen, concept, definition)
    except Exception:
        pass

    # ── Extract concept groups ─────────────────────────────────────────────
    groups = extract_concept_groups(structured)

    logger.info(
        "Lecture quiz gen: %d concept pairs, %d concept groups",
        len(pairs),
        len(groups),
    )

    if len(pairs) < _MIN_CONCEPTS and len(groups) < 2:
        logger.warning(
            "Lecture quiz gen: insufficient content (%d pairs, %d groups)",
            len(pairs),
            len(groups),
        )
        return []

    questions: List[Dict[str, Any]] = []
    used: Set[str] = set()
    target = min(num_questions, max(_MIN_CONCEPTS, len(pairs) + sum(len(g) for _, g in groups)))

    # ── Description questions from concept pairs ───────────────────────────
    for concept, description in pairs:
        if len(questions) >= target:
            break
        key = f"desc:{concept.lower()}"
        if key in used:
            continue
        q = _build_description_question(len(questions) + 1, concept, description, pairs)
        if q:
            questions.append(q)
            used.add(key)

    # ── Association questions from concept groups ──────────────────────────
    for topic, items in groups:
        for item in items[:3]:
            if len(questions) >= target:
                break
            key = f"assoc:{topic.lower()}:{item.lower()}"
            if key in used:
                continue
            q = _build_association_question(
                len(questions) + 1, topic, item, groups, pairs
            )
            if q:
                questions.append(q)
                used.add(key)
        if len(questions) >= target:
            break

    logger.info("Lecture quiz gen: produced %d questions", len(questions))
    return questions if len(questions) >= _MIN_CONCEPTS else []

"""
Validate and repair vague quiz question stems so every question names a concept.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

_VAGUE_STEM_RE = re.compile(
    r"^what\s+(?:is|are)\s+(?:the\s+)?(?:definition|purpose|advantages?|disadvantages?|types?|role|function)\s*\??\s*$",
    re.I,
)
_VAGUE_SHORT_RE = re.compile(
    r"^what\s+(?:is|are)\s+(?:used\s+for\s+this|this|it)\s*\??\s*$",
    re.I,
)
_GENERIC_OPTION_RE = re.compile(
    r"^(none of the above|all of the above|not applicable|n/?a|true|false|yes|no|other)\s*$",
    re.I,
)

_CONCEPT_FROM_TEXT_RE = re.compile(
    r"(?:^|\n)\s*([A-Z][A-Za-z0-9][A-Za-z0-9 /&\-]{2,55})\s*(?:\n|:)",
    re.MULTILINE,
)
_HEADING_RE = re.compile(
    r"(?:^|\n)\s*([A-Z][A-Za-z0-9][\w\s/&\-]{3,55})\s*$",
    re.MULTILINE,
)


def _extract_concepts(text: str, limit: int = 40) -> List[str]:
    concepts: List[str] = []
    seen: Set[str] = set()
    for pattern in (_CONCEPT_FROM_TEXT_RE, _HEADING_RE):
        for m in pattern.finditer(text or ""):
            term = (m.group(1) or "").strip()
            if len(term) < 3 or len(term) > 60:
                continue
            key = term.lower()
            if key in seen:
                continue
            if re.search(r"\b(page|slide|lecture|lab|chapter)\s*\d", key):
                continue
            seen.add(key)
            concepts.append(term)
            if len(concepts) >= limit:
                return concepts
    return concepts


def _is_vague_stem(question: str) -> bool:
    q = (question or "").strip()
    if not q:
        return True
    if _VAGUE_STEM_RE.match(q) or _VAGUE_SHORT_RE.match(q):
        return True
    if re.match(r"^what\s+is\s+the\s+\w+\s*\??\s*$", q, re.I):
        words = q.split()
        if len(words) <= 5:
            return True
    return False


def _rewrite_vague_stem(stem: str, concept: str) -> str:
    s = stem.strip().rstrip("?").lower()
    c = concept.strip()
    if "definition" in s:
        return f"What is the definition of {c}?"
    if "purpose" in s:
        return f"What is the purpose of {c}?"
    if "advantage" in s:
        return f"What are the advantages of {c}?"
    if "disadvantage" in s:
        return f"What are the disadvantages of {c}?"
    if "types" in s or "type" in s:
        return f"What are the types of {c}?"
    if "role" in s:
        return f"What is the role of {c}?"
    if "function" in s:
        return f"What is the function of {c}?"
    return f"What is {c}?"


def _options_too_generic(options: List[str]) -> bool:
    if len(options) < 2:
        return True
    generic = sum(1 for o in options if _GENERIC_OPTION_RE.match((o or "").strip()))
    return generic >= len(options) - 1


def _build_concept_question(
    concept: str,
    text: str,
    used: Set[str],
) -> Optional[Dict[str, Any]]:
    c = concept.strip()
    if not c or c.lower() in used:
        return None
    pattern = re.compile(
        rf"\b{re.escape(c)}\b\s+(?:is|are|refers to|means)\s+([^.\n]{{10,120}})",
        re.I,
    )
    m = pattern.search(text)
    if not m:
        return None
    answer = m.group(1).strip()
    if len(answer) < 8:
        return None
    # Truncate long answers for MCQ
    if len(answer) > 100:
        answer = answer[:97].rsplit(" ", 1)[0] + "…"
    distractors: List[str] = []
    for other in _extract_concepts(text, 20):
        if other.lower() != c.lower() and len(other) > 3:
            snippet = other[:80]
            if snippet not in distractors and snippet != answer:
                distractors.append(snippet)
        if len(distractors) >= 3:
            break
    while len(distractors) < 3:
        distractors.append(f"Related concept: {c} variant {len(distractors) + 1}")
    options = [answer] + distractors[:3]
    return {
        "question": f"What is {c}?",
        "options": options,
        "correctIndex": 0,
    }


def validate_and_improve_questions(
    questions: List[Dict[str, Any]],
    source_text: str,
    material_title: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return questions with vague stems rewritten or replaced from source text."""
    if not questions:
        return []

    concepts = _extract_concepts(source_text)
    if material_title:
        title_clean = re.sub(r"\b[A-Z]{2,6}\d{3,4}\b", "", material_title).strip()
        if title_clean and title_clean.lower() not in {c.lower() for c in concepts}:
            concepts.insert(0, title_clean)

    improved: List[Dict[str, Any]] = []
    used_concepts: Set[str] = set()
    concept_idx = 0

    for i, q in enumerate(questions):
        question = str(q.get("question") or "").strip()
        options = list(q.get("options") or [])
        correct_idx = int(q.get("correctIndex") or 0)

        if _is_vague_stem(question) or _options_too_generic(options):
            concept = None
            while concept_idx < len(concepts):
                candidate = concepts[concept_idx]
                concept_idx += 1
                if candidate.lower() not in used_concepts:
                    concept = candidate
                    break
            if concept:
                new_q = _build_concept_question(concept, source_text, used_concepts)
                if new_q:
                    used_concepts.add(concept.lower())
                    new_q["id"] = q.get("id") or f"q{i + 1}"
                    improved.append(new_q)
                    continue
                question = _rewrite_vague_stem(question, concept)
                used_concepts.add(concept.lower())

        if _is_vague_stem(question) and concepts:
            concept = concepts[min(i, len(concepts) - 1)]
            question = _rewrite_vague_stem(question, concept)

        if len(options) >= 2 and 0 <= correct_idx < len(options):
            improved.append(
                {
                    "id": q.get("id") or f"q{i + 1}",
                    "question": question,
                    "options": options,
                    "correctIndex": correct_idx,
                }
            )

    # Renumber ids
    for j, item in enumerate(improved):
        item["id"] = f"q{j + 1}"

    return improved

"""
Validate and repair vague quiz question stems so every question names a concept.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

_VAGUE_EXACT_RE = re.compile(
    r"^what\s+(?:is|are)\s+(?:the\s+)?(?:definition|purpose|advantages?|disadvantages?|types?|role|function|difference)\s*\??\s*$",
    re.I,
)
_VAGUE_SHORT_RE = re.compile(
    r"^what\s+(?:is|are)\s+(?:used\s+for\s+this|this|it|used)\s*\??\s*$",
    re.I,
)
_VAGUE_GENERIC_RE = re.compile(
    r"^what\s+(?:is|are)\s+(?:the\s+)?(\w+)\s*\??\s*$",
    re.I,
)
_GENERIC_WORDS = frozenset(
    {
        "definition",
        "purpose",
        "advantage",
        "advantages",
        "disadvantage",
        "disadvantages",
        "type",
        "types",
        "role",
        "function",
        "difference",
        "used",
        "meaning",
    }
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
_DEFINITION_RE = re.compile(
    r"\b([A-Za-z][A-Za-z0-9 /&\-]{2,50})\s+(?:is|are|refers to|means)\s+([^.\n]{8,120})",
    re.I,
)


def is_vague_question(question: str, material_title: Optional[str] = None) -> bool:
    """True when the stem lacks a concrete concept/topic noun phrase."""
    q = (question or "").strip()
    if not q:
        return True
    if _VAGUE_EXACT_RE.match(q) or _VAGUE_SHORT_RE.match(q):
        return True
    gm = _VAGUE_GENERIC_RE.match(q)
    if gm and gm.group(1).lower() in _GENERIC_WORDS:
        return True
    if re.search(r"\bdefinition\s*\??\s*$", q, re.I) and " of " not in q.lower():
        return True
    if re.search(r"\bpurpose\s*\??\s*$", q, re.I) and " of " not in q.lower():
        return True
    if re.search(r"\badvantages?\s*\??\s*$", q, re.I) and " of " not in q.lower():
        return True
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", q)
    skip = _GENERIC_WORDS | frozenset(
        {"what", "which", "how", "why", "when", "the", "are", "is", "does", "do"}
    )
    substantive = [t for t in tokens if t.lower() not in skip]
    if len(substantive) < 1 and len(q.split()) <= 6:
        return True
    return False


def _extract_concepts(text: str, limit: int = 50) -> List[str]:
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
            if re.search(r"\b(page|slide)\s*\d", key):
                continue
            seen.add(key)
            concepts.append(term)
            if len(concepts) >= limit:
                return concepts
    for m in _DEFINITION_RE.finditer(text or ""):
        term = (m.group(1) or "").strip()
        if len(term) >= 3 and term.lower() not in seen:
            seen.add(term.lower())
            concepts.append(term)
    return concepts


def _rewrite_vague_stem(stem: str, concept: str) -> str:
    s = stem.strip().rstrip("?").lower()
    c = concept.strip()
    if "difference" in s:
        return f"What is the difference between {c} and related concepts?"
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
    m = _DEFINITION_RE.search(text)
    if m and m.group(1).strip().lower() == c.lower():
        answer = m.group(2).strip()
    else:
        pattern = re.compile(
            rf"\b{re.escape(c)}\b\s+(?:is|are|refers to|means)\s+([^.\n]{{10,120}})",
            re.I,
        )
        hit = pattern.search(text)
        if not hit:
            return None
        answer = hit.group(1).strip()
    if len(answer) < 8:
        return None
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
        distractors.append(f"Alternative: {c} aspect {len(distractors) + 1}")
    options = [answer] + distractors[:3]
    return {
        "question": f"What is the definition of {c}?",
        "options": options,
        "correctIndex": 0,
    }


def validate_and_improve_questions(
    questions: List[Dict[str, Any]],
    source_text: str,
    material_title: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return questions with vague stems rewritten or replaced; no vague stems remain."""
    if not questions:
        return []

    concepts = _extract_concepts(source_text)
    if material_title:
        title_clean = re.sub(r"\b[A-Z]{2,6}\s*\d{3,4}\b", "", material_title).strip()
        title_clean = re.sub(r"\b(File|Moodle)\b", "", title_clean, flags=re.I).strip()
        if title_clean and title_clean.lower() not in {c.lower() for c in concepts}:
            concepts.insert(0, title_clean)

    improved: List[Dict[str, Any]] = []
    used_concepts: Set[str] = set()
    concept_idx = 0

    for i, q in enumerate(questions):
        question = str(q.get("question") or "").strip()
        options = list(q.get("options") or [])
        correct_idx = int(q.get("correctIndex") or 0)

        vague = is_vague_question(question, material_title) or _options_too_generic(options)

        if vague:
            concept = None
            while concept_idx < len(concepts):
                candidate = concepts[concept_idx]
                concept_idx += 1
                if candidate.lower() not in used_concepts:
                    concept = candidate
                    break
            if concept:
                new_q = _build_concept_question(concept, source_text, used_concepts)
                if new_q and not is_vague_question(new_q["question"], material_title):
                    used_concepts.add(concept.lower())
                    new_q["id"] = q.get("id") or f"q{i + 1}"
                    improved.append(new_q)
                    continue
                question = _rewrite_vague_stem(question, concept)
                used_concepts.add(concept.lower())

        if is_vague_question(question, material_title) and concepts:
            concept = concepts[min(i, len(concepts) - 1)]
            question = _rewrite_vague_stem(question, concept)

        if is_vague_question(question, material_title):
            continue

        if len(options) >= 2 and 0 <= correct_idx < len(options):
            improved.append(
                {
                    "id": q.get("id") or f"q{i + 1}",
                    "question": question,
                    "options": options,
                    "correctIndex": correct_idx,
                }
            )

    for j, item in enumerate(improved):
        item["id"] = f"q{j + 1}"

    return improved

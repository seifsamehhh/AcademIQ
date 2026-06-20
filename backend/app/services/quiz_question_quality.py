"""
Validate and repair vague quiz question stems so every question names a concept.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

QUIZ_GENERATION_GUIDANCE = (
    "Generate university-level MCQs from the selected material only. "
    "Every question must mention a specific concept from the selected material. "
    "Do not use the file name as the concept. "
    "Do not ask vague questions. "
    "Every answer option must be a complete, grammatically correct phrase or sentence. "
    "Return only valid MCQs."
)

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
_BROKEN_OPTION_END_RE = re.compile(
    r"\b(the|about|by|of|a|an|to|in|for|with|and|or|as|on|at|from|approx)\s*\.?\s*$",
    re.I,
)
_BROKEN_OPTION_PHRASE_RE = re.compile(
    r"(?i)practically it refers to|described by An\b|it refers to described|"
    r"for human perception refers to|solution is an use|repeat until goal refers to found|"
    r"\bNNNJ is a So\b|refers to found"
)
_FILENAME_CONCEPT_RE = re.compile(
    r"(?i)\.(pdf|pptx?|ppsx)|_|lecture\s*\d+|lab\s*\d+|test\s+notes|algorithm\s+steps"
)
_VAGUE_TITLE_CONCEPT_RE = re.compile(
    r"(?i)^what\s+is\s+(summary|algorithm\s+steps(?:\s+for\s+search)?|test\s+notes)\s*\??$"
)
_VAGUE_PURPOSE_RE = re.compile(
    r"(?i)^what\s+is\s+(?:the\s+)?purpose\s*\??\s*$"
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
        "genghis",
        "summary",
        "algorithm",
        "steps",
        "notes",
        "test",
        "search",
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


def is_broken_option(option: str) -> bool:
    """True when an MCQ option is a fragment or unreadable."""
    o = (option or "").strip()
    if len(o) < 12:
        return True
    if _GENERIC_OPTION_RE.match(o):
        return True
    if _BROKEN_OPTION_END_RE.search(o):
        return True
    if _BROKEN_OPTION_PHRASE_RE.search(o):
        return True
    words = o.split()
    if len(words) < 3:
        return True
    if o.endswith("...") and len(o) < 40:
        return True
    if re.search(r"(?i)\brefers to\s*$", o):
        return True
    if re.search(r"(?i)^\w+ is a So\b", o):
        return True
    return False


def is_grammatically_broken_question(question: str) -> bool:
    q = (question or "").strip()
    if len(q.split()) < 5:
        return True
    if not q.endswith("?"):
        return True
    if not re.match(r"^(What|Which|How|Why|When|In what|According to)", q, re.I):
        return True
    if re.search(r"\?\s*\?", q):
        return True
    return False


def uses_filename_as_concept(question: str, material_title: Optional[str] = None) -> bool:
    q = (question or "").strip()
    if _VAGUE_TITLE_CONCEPT_RE.match(q):
        return True
    m = re.match(r"^what\s+(?:is|are)\s+(?:the\s+)?(.+?)\s*\??\s*$", q, re.I)
    if not m:
        return False
    concept = m.group(1).strip()
    if _FILENAME_CONCEPT_RE.search(concept):
        return True
    if material_title and concept.lower() == clean_title_token(material_title).lower():
        return True
    if len(concept.split()) <= 2 and concept.lower() in _GENERIC_WORDS:
        return True
    return False


def clean_title_token(title: str) -> str:
    t = re.sub(r"\b[A-Z]{2,6}\s*\d{3,4}\b", "", title or "")
    t = re.sub(r"\b(File|Moodle|Copy|Lab|Lecture)\b", "", t, flags=re.I)
    t = re.sub(r"\.(pdf|pptx?|ppsx)\b", "", t, flags=re.I)
    return t.strip()


def is_question_valid(
    question: str,
    options: List[str],
    source_text: str,
    material_title: Optional[str],
    keywords: List[str],
) -> bool:
    if is_vague_question(question, material_title):
        return False
    if uses_filename_as_concept(question, material_title):
        return False
    if is_grammatically_broken_question(question):
        return False
    if _VAGUE_PURPOSE_RE.match(question or ""):
        return False
    if not question_mentions_topic(question, material_title, keywords):
        return False
    if not _options_valid(options):
        return False
    return True


def _extract_keywords(
    source_text: str,
    material_title: Optional[str],
) -> List[str]:
    keywords: List[str] = []
    seen: Set[str] = set()
    if material_title:
        title_clean = re.sub(r"\b[A-Z]{2,6}\s*\d{3,4}\b", "", material_title)
        title_clean = re.sub(r"\b(File|Moodle|Copy)\b", "", title_clean, flags=re.I)
        for part in re.split(r"[-–—:]+", title_clean):
            part = part.strip()
            if len(part) >= 4 and part.lower() not in seen:
                seen.add(part.lower())
                keywords.append(part)
    for concept in _extract_concepts(source_text, 30):
        if concept.lower() not in seen:
            seen.add(concept.lower())
            keywords.append(concept)
    return keywords


def question_mentions_topic(
    question: str,
    material_title: Optional[str],
    keywords: List[str],
) -> bool:
    """True when the stem references material title or extracted keywords."""
    q_lower = (question or "").lower()
    if len(q_lower.split()) >= 10:
        return True
    for kw in keywords[:25]:
        token = kw.strip().lower()
        if len(token) >= 4 and token in q_lower:
            return True
    if material_title:
        for token in re.findall(r"[a-z]{4,}", material_title.lower()):
            if token not in _GENERIC_WORDS and token in q_lower:
                return True
    return False


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
    if _VAGUE_PURPOSE_RE.match(q):
        return True
    if uses_filename_as_concept(q, material_title):
        return True
    if _VAGUE_TITLE_CONCEPT_RE.match(q):
        return True
    if re.match(r"^what\s+are\s+\w+\s*\??\s*$", q, re.I) and " of " not in q.lower():
        word = re.sub(r"^what\s+are\s+|\s*\??\s*$", "", q, flags=re.I).strip()
        if len(word.split()) <= 2:
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
            if key in _GENERIC_WORDS or _FILENAME_CONCEPT_RE.search(term):
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


def _options_valid(options: List[str]) -> bool:
    if len(options) < 4:
        return False
    return all(not is_broken_option(o) for o in options)


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
    if len(answer) < 8 or is_broken_option(answer):
        return None
    if len(answer) > 100:
        answer = answer[:97].rsplit(" ", 1)[0] + "…"
    distractors: List[str] = []
    for other in _extract_concepts(text, 20):
        if other.lower() != c.lower() and len(other) > 3:
            snippet = other[:80]
            if (
                snippet not in distractors
                and snippet != answer
                and not is_broken_option(snippet)
            ):
                distractors.append(snippet)
        if len(distractors) >= 3:
            break
    while len(distractors) < 3:
        filler = f"A related concept distinct from {c}"
        if not is_broken_option(filler):
            distractors.append(filler)
        else:
            distractors.append(f"Alternative aspect of {c}")
    options = [answer] + distractors[:3]
    if not _options_valid(options):
        return None
    question = f"What is the definition of {c}?"
    if uses_filename_as_concept(question) or is_vague_question(question):
        return None
    return {
        "question": question,
        "options": options,
        "correctIndex": 0,
    }


def _fill_valid_questions_from_concepts(
    source_text: str,
    material_title: Optional[str],
    needed: int,
    used: Set[str],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    keywords = _extract_keywords(source_text, material_title)
    for concept in _extract_concepts(source_text, 40):
        if concept.lower() in used:
            continue
        built = _build_concept_question(concept, source_text, used)
        if not built:
            continue
        if not is_question_valid(
            built["question"],
            built["options"],
            source_text,
            material_title,
            keywords,
        ):
            continue
        used.add(concept.lower())
        out.append(built)
        if len(out) >= needed:
            break
    return out


def validate_and_improve_questions(
    questions: List[Dict[str, Any]],
    source_text: str,
    material_title: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return only valid MCQs; drop bad questions rather than returning them."""
    keywords = _extract_keywords(source_text, material_title)
    if not questions:
        return _fill_valid_questions_from_concepts(source_text, material_title, 5, set())

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

        vague = (
            is_vague_question(question, material_title)
            or uses_filename_as_concept(question, material_title)
            or is_grammatically_broken_question(question)
            or _options_too_generic(options)
            or not _options_valid(options)
            or not question_mentions_topic(question, material_title, keywords)
        )

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
                if new_q and is_question_valid(
                    new_q["question"],
                    new_q["options"],
                    source_text,
                    material_title,
                    keywords,
                ):
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
        if uses_filename_as_concept(question, material_title):
            continue
        if is_grammatically_broken_question(question):
            continue

        if not _options_valid(options):
            concept = concepts[min(i, len(concepts) - 1)] if concepts else None
            if concept:
                rebuilt = _build_concept_question(concept, source_text, used_concepts)
                if rebuilt:
                    rebuilt["id"] = q.get("id") or f"q{i + 1}"
                    improved.append(rebuilt)
            continue

        if len(options) >= 4 and 0 <= correct_idx < len(options):
            if is_question_valid(question, options[:4], source_text, material_title, keywords):
                improved.append(
                    {
                        "id": q.get("id") or f"q{i + 1}",
                        "question": question,
                        "options": options[:4],
                        "correctIndex": correct_idx,
                    }
                )

    if len(improved) < len(questions):
        extra = _fill_valid_questions_from_concepts(
            source_text,
            material_title,
            max(len(questions) - len(improved), 0),
            used_concepts,
        )
        improved.extend(extra)

    for j, item in enumerate(improved):
        item["id"] = f"q{j + 1}"

    return improved

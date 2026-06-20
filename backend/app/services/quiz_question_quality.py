"""
Validate and repair vague quiz question stems so every question names a concept.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

QUIZ_GENERATION_GUIDANCE = (
    "Generate university-level multiple-choice questions from the selected course material only.\n\n"
    "Rules:\n"
    "1. Every question must mention a specific concept from the material.\n"
    "2. Do not use the file name as the tested concept.\n"
    "3. Do not ask vague questions like: What is the definition? What is Summary? "
    "What is the purpose? What are Genghis? What is Algorithm steps for search?\n"
    "4. Each question must be grammatically correct.\n"
    "5. Each answer option must be complete and readable.\n"
    "6. No broken fragments.\n"
    "7. The correct answer must be directly supported by the selected content.\n"
    "8. Distractors must be plausible but wrong.\n"
    "9. Return JSON only."
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
    r"\b(the|about|by|of|a|an|to|in|for|with|and|or|as|on|at|from|approx|include|refers to)\s*\.?\s*$",
    re.I,
)
_TECH_TERM_RE = re.compile(r"^[A-Z]{2,10}$")
_BROKEN_OPTION_PHRASE_RE = re.compile(
    r"(?i)practically it refers to|described by An\b|it refers to described|"
    r"for human perception refers to|solution is an use|repeat until goal refers to found|"
    r"\bNNNJ is a So\b|refers to found|refers to natural|refers to given by|"
    r"refers to to |refers to very |refers to specifically|refers to filtered|"
    r"^pattern it\b|sent to a feature"
)
_VAGUE_CONCEPT_RE = re.compile(
    r"(?i)^(the|a|an)\s+(features?|information|output|input|value|result|data)$"
)
_SHOUTY_STEM_RE = re.compile(r"\b[A-Z]{3,}(?:\s+[A-Z]{3,}){2,}")
_BAD_STEM_RE = re.compile(
    r"(?i)^what\s+is\s+(change|make|select|number of|task of)\b|"
    r"^what\s+is\s+information from\b"
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
    r"\b([A-Za-z][A-Za-z0-9 /&\-]{2,50})\s+"
    r"(?:is|are|refers to|means|used to|helps|defined as|consists of|includes)\s+"
    r"([^.\n]{8,120})",
    re.I,
)


def clean_option_text(option: str) -> str:
    """Normalize an MCQ option into a complete readable sentence."""
    o = re.sub(r"[\uf000-\uf8ff\ufffd•▪]", " ", (option or ""))
    o = re.sub(r"\s+", " ", o).strip()
    if not o:
        return ""
    o = o.rstrip(",;:")
    if o and o[0].islower():
        o = o[0].upper() + o[1:]
    if o and not o.endswith((".", "!", "?")):
        o += "."
    if len(o) > 120:
        o = o[:117].rsplit(" ", 1)[0] + "."
    return o


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
    if len(words) < 4 and not _TECH_TERM_RE.match(o):
        return True
    if o.endswith("...") and len(o) < 40:
        return True
    if re.search(r"(?i)\brefers to\s*$", o):
        return True
    if re.search(r"(?i)^\w+ is a So\b", o):
        return True
    if re.search(r"(?i)(?:\[Page\s*\d|Page\s*\d+\])|course outline|\d{1,2}/\d{1,2}/\d{4}|learning and adaptation", o):
        return True
    if re.search(r"[\uf000-\uf8ff\ufffd]", o):
        return True
    if re.search(r"(?i)^(passed|referred|called)\s+to\b", o):
        return True
    if re.search(r"(?i)make decisions about patterns", o):
        return True
    if re.search(r"(?i)postprocessing:|image algebra|visual example", o):
        return True
    if re.search(r"\d\.\s*$", o) and len(words) <= 6:
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
    if _SHOUTY_STEM_RE.search(q.replace("?", "")):
        return True
    if _BAD_STEM_RE.search(q):
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


def option_contains_weird_terms(option: str, source_text: str) -> bool:
    """True when an option contains long tokens absent from the source material."""
    src_lower = (source_text or "").lower()
    for token in re.findall(r"[A-Za-z]{7,}", option or ""):
        low = token.lower()
        if low in _GENERIC_WORDS:
            continue
        if low not in src_lower and token not in source_text:
            return True
    return False


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
    for opt in options:
        if option_contains_weird_terms(opt, source_text):
            return False
    return True


def repair_and_select_questions(
    questions: List[Dict[str, Any]],
    source_text: str,
    material_title: Optional[str] = None,
    target: int = 5,
) -> List[Dict[str, Any]]:
    """Validate, repair, fallback-fill, and return the best MCQs (up to target)."""
    min_good = min(3, target)
    improved = validate_and_improve_questions(questions, source_text, material_title)
    selected = improved[:target]

    if len(selected) >= min_good:
        for j, item in enumerate(selected):
            item["id"] = f"q{j + 1}"
        return selected[:target]

    from app.services.quiz_gen_fallback import generate_deterministic_fallback

    fallback = generate_deterministic_fallback(source_text, material_title, target)
    if fallback:
        merged = selected + fallback
        improved2 = validate_and_improve_questions(merged, source_text, material_title)
        if len(improved2) > len(selected):
            selected = improved2[:target]

    if len(selected) < min_good and len((source_text or "").strip()) > 1000:
        relaxed = generate_deterministic_fallback(
            source_text, material_title, target, relax_validation=True,
        )
        if relaxed:
            selected = relaxed[:target]

    for j, item in enumerate(selected):
        item["id"] = f"q{j + 1}"
    return selected[:target]


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
    if re.match(r"^what\s+are\s+(main|key|other|general)\s+", q, re.I):
        return True
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", q)
    skip = _GENERIC_WORDS | frozenset(
        {"what", "which", "how", "why", "when", "the", "are", "is", "does", "do"}
    )
    substantive = [t for t in tokens if t.lower() not in skip]
    if len(substantive) < 1 and len(q.split()) <= 6:
        return True
    concept_m = re.search(
        r"(?i)(?:best describes|definition of|role of|main idea of)\s+(.+?)\??\s*$",
        q,
    )
    if concept_m:
        concept = concept_m.group(1).strip()
        if _VAGUE_CONCEPT_RE.match(concept):
            return True
        if re.search(r"which the|category\s+to which|lies\??\s*$", concept, re.I):
            return True
        if concept.lower().startswith("change pixel"):
            return True
        if len(concept.split()) == 1 and concept.lower() in {
            "length", "classifier", "features", "feature", "length",
        }:
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


def _extract_clean_sentences(text: str, limit: int = 30) -> List[str]:
    out: List[str] = []
    seen: Set[str] = set()
    for m in re.finditer(r"[A-Za-z][^.!?]{25,200}[.!?]", text or ""):
        s = clean_option_text(re.sub(r"\s+", " ", m.group(0)).strip())
        if is_broken_option(s):
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= limit:
            break
    return out


def _build_concept_question(
    concept: str,
    text: str,
    used: Set[str],
) -> Optional[Dict[str, Any]]:
    c = concept.strip()
    if not c or c.lower() in used:
        return None
    if re.search(r"\bit\b", c, re.I) and len(c.split()) <= 3:
        return None
    if _SHOUTY_STEM_RE.search(c):
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
        answer = answer[:97].rsplit(" ", 1)[0] + "."
    answer = clean_option_text(answer)
    sentences = _extract_clean_sentences(text)
    distractors: List[str] = []
    for s in sentences:
        if s.lower() == answer.lower() or c.lower() in s.lower()[:20]:
            continue
        if s not in distractors:
            distractors.append(s)
        if len(distractors) >= 3:
            break
    for other in _extract_concepts(text, 20):
        if other.lower() != c.lower() and len(other) > 3:
            for s in sentences:
                if other.lower() in s.lower() and s not in distractors:
                    distractors.append(s)
                    break
        if len(distractors) >= 3:
            break
    while len(distractors) < 3:
        filler = f"A related concept distinct from {c}"
        if not is_broken_option(filler):
            distractors.append(filler)
        else:
            distractors.append(f"Alternative aspect of {c}")
    options = [clean_option_text(answer)] + [
        clean_option_text(d) for d in distractors[:3]
    ]
    if not _options_valid(options):
        return None
    question = f"Which statement best describes {c}?"
    if uses_filename_as_concept(question) or is_vague_question(question):
        question = f"What is the role of {c} in this material?"
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


def _post_filter_acceptable(
    questions: List[Dict[str, Any]],
    source_text: str,
    material_title: Optional[str],
) -> List[Dict[str, Any]]:
    keywords = _extract_keywords(source_text, material_title)
    out: List[Dict[str, Any]] = []
    for q in questions:
        opts = [clean_option_text(o) for o in q.get("options") or []]
        stem = str(q.get("question") or "").strip()
        if not is_question_valid(stem, opts, source_text, material_title, keywords):
            continue
        out.append(
            {
                "id": q.get("id"),
                "question": stem,
                "options": opts[:4],
                "correctIndex": int(q.get("correctIndex") or 0),
            }
        )
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
                if rebuilt and is_question_valid(
                    rebuilt["question"],
                    rebuilt["options"],
                    source_text,
                    material_title,
                    keywords,
                ):
                    rebuilt["id"] = q.get("id") or f"q{i + 1}"
                    improved.append(rebuilt)
            continue

        if len(options) >= 4 and 0 <= correct_idx < len(options):
            cleaned_opts = [clean_option_text(o) for o in options[:4]]
            if is_question_valid(
                question, cleaned_opts, source_text, material_title, keywords,
            ):
                improved.append(
                    {
                        "id": q.get("id") or f"q{i + 1}",
                        "question": question,
                        "options": cleaned_opts,
                        "correctIndex": min(correct_idx, 3),
                    }
                )

    improved = _post_filter_acceptable(improved, source_text, material_title)

    if len(improved) < max(3, min(5, len(questions) or 5)):
        extra = _fill_valid_questions_from_concepts(
            source_text,
            material_title,
            max(5 - len(improved), 0),
            used_concepts,
        )
        improved.extend(_post_filter_acceptable(extra, source_text, material_title))

    if len(improved) < 3 and len((source_text or "").strip()) > 1000:
        from app.services.quiz_gen_fallback import generate_deterministic_fallback

        fallback = generate_deterministic_fallback(
            source_text, material_title, 5, relax_validation=True,
        )
        for fb in fallback:
            if len(improved) >= 5:
                break
            filtered = _post_filter_acceptable([fb], source_text, material_title)
            if filtered:
                improved.append(filtered[0])

    for j, item in enumerate(improved):
        item["id"] = f"q{j + 1}"

    return improved[:5]

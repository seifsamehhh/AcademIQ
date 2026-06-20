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
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

_MIN_DEFINITION_LEN = 20
_MAX_DEFINITION_LEN = 160
_MAX_OPTION_LEN = 120   # hard cap on every answer option including sentence-fragment distractors
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
    re.compile(
        r"\b([A-Z][A-Za-z0-9]+(?:\s+[A-Za-z0-9]+){0,5})\s+(?:is )?defined as\s+([^.\n]+?)\.",
        re.IGNORECASE | re.MULTILINE,
    ),
    re.compile(
        r"\b([A-Z][A-Za-z0-9]+(?:\s+[A-Za-z0-9]+){0,5})\s+(?:can be described as|is known as|is called)\s+([^.\n]+?)\.",
        re.IGNORECASE | re.MULTILINE,
    ),
]

_COLON_PATTERN = re.compile(
    r"(?:^|\n)\s*([A-Z][A-Za-z0-9][A-Za-z0-9 /&\-]{1,48}?)\s*:\s+([^.\n]{20,160})\.",
    re.MULTILINE,
)

# "Concept (qualifier) is a/an/the definition."  — parenthetical between concept and "is"
_PAREN_SKIP_PATTERN = re.compile(
    r"\b([A-Z][A-Za-z0-9]+(?:\s+[A-Za-z0-9]+){0,5})\s+\([^)]{0,80}\)\s+is\s+(?:a|an|the)?\s*([^.\n]{15,200})\.",
    re.MULTILINE,
)

# "Concept (ABBREV) is a definition."  — also extracts ABBREV as concept
_ABBREV_IS_PATTERN = re.compile(
    r"\b([A-Z][A-Za-z][A-Za-z0-9\s/&\-]{1,45}?)\s+\(\s*([A-Z][A-Z0-9]{1,7})\s*\)\s+is\s+(?:a|an|the)?\s*([^.\n]{15,200})\.",
    re.MULTILINE,
)

# "What is X? / What are X?" on one line; answer is next non-empty line(s)
_QA_LINE_RE = re.compile(
    r"^[Ww]hat\s+(?:is|are)\s+(?:a\s+|an\s+|the\s+)?([A-Za-z][A-Za-z0-9\s/&()\-]{2,60}?)\s*\??\s*$",
)

_SLIDE_TITLE_RE = re.compile(r"^[A-Z][A-Za-z0-9][\w\s/&\-]{2,55}$")

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
    # Generic document structure terms
    "for example", "for instance", "in summary", "introduction", "summary",
    "note", "hint", "warning", "important", "overview", "objective",
    "objectives", "agenda", "contents", "outline", "index", "table of contents",
    "conclusion", "results", "discussion", "references", "bibliography",
    "appendix", "acknowledgements", "abstract", "preface",
    # Demo/test artifacts
    "programming lecture", "database lecture", "seeded demo material",
    "academiq test content",
    # Pronouns and deictic words that leak as concepts
    "it", "its", "this", "that", "these", "those", "they", "their", "there",
    "its output", "its input", "its result", "its value", "its purpose",
    "this process", "this method", "this technique", "this approach",
    "that is", "that means",
    # Vague single-word subjects that lack educational specificity
    "output", "input", "result", "value", "process", "method", "approach",
    "step", "stage", "phase", "part", "section", "type", "form", "kind",
    "example", "case", "item", "element", "component", "feature", "aspect",
    "function", "operation", "action", "task", "activity", "event",
    # Navigation / UI noise
    "what", "click", "see", "refer", "go", "open", "close", "next", "back",
    "continue", "return", "submit", "select",
}

# Pronouns and question words that must NEVER start a concept phrase
_CONCEPT_BANNED_PREFIXES = (
    "it ", "its ", "this ", "that ", "these ", "those ", "they ",
    "their ", "there ", "what ", "which ", "when ", "where ", "who ",
    "how ", "why ", "a ", "an ", "the ",
)

# Patterns that indicate slide/course headers or noise — not valid distractors
_SENTENCE_SKIP_RE = re.compile(
    r"^[A-Z]{2,6}\d+[-/]\w+"           # course codes: CSC399-SWE412
    r"|^\d+\s+of\s+\d+"                 # slide numbers: "3 of 24"
    r"|^(?:slide|page|chapter|unit|lab|part)\s*\d"  # "Slide 3"
    r"|^https?://"                       # URLs
    r"|^\w+\.(com|org|edu|io)\b"         # domain lines
    r"|@"                                # contains email @ symbol
    r"|^\s*(?:contents?|what\?|index|outline)\s*$",  # ToC noise
    re.IGNORECASE,
)


def _extract_material_sentences(
    text: str,
    min_words: int = 5,
    max_chars: int = 130,
) -> List[str]:
    """
    Extract meaningful sentence fragments from the material text to use as
    content-grounded fallback distractors.

    All returned strings come from the SAME material — no generic placeholders.
    Filters out course codes, slide headers, and navigation noise.
    """
    blob = re.sub(r"\s+", " ", text.strip())
    raw_sentences = re.split(r"(?<=[.!?])\s+", blob)
    result: List[str] = []
    seen: Set[str] = set()
    for s in raw_sentences:
        s = s.strip()
        # Skip course codes, slide numbers, and navigation headers
        if _SENTENCE_SKIP_RE.match(s):
            continue
        words = s.split()
        if len(words) < min_words:
            continue
        if len(s) > max_chars:
            # Trim to word boundary within _MAX_OPTION_LEN
            trimmed = ""
            for w in words:
                candidate = (trimmed + " " + w).strip()
                if len(candidate) <= _MAX_OPTION_LEN:
                    trimmed = candidate
                else:
                    break
            s = trimmed or " ".join(words[:18])
        # Skip lines that are mostly numbers/symbols/single words
        if re.match(r"^[\d\s\W]+$", s):
            continue
        # Skip if >40% of characters are uppercase (likely a heading/acronym block)
        upper_ratio = sum(1 for c in s if c.isupper()) / max(len(s), 1)
        if upper_ratio > 0.4:
            continue
        # Skip if sentence contains PDF artifact characters (private-use or geometric
        # separators like ◊ ◆ ● that appear as section dividers in extracted PDFs)
        if re.search(r"[\uf000-\uf8ff\ufffd\u25a0-\u25ff]", s):
            continue
        # Skip document-title patterns: "Subject — Topic (context) Type"
        # (em/en dash + parenthetical = almost always a header, not a sentence)
        if re.search(r"[\u2013\u2014]", s) and re.search(r"\(.*\)", s):
            continue
        option = _format_option(s)
        if not option or len(option) < 20:
            continue
        key = _option_key(option)
        if key in seen:
            continue
        seen.add(key)
        result.append(option)
    return result


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
    lower = concept.lower().strip()

    # Reject exact matches and substring noise
    if lower in _INVALID_CONCEPTS:
        return False

    # Reject concepts starting with pronouns/deictic/question/article words
    if any(lower.startswith(prefix) for prefix in _CONCEPT_BANNED_PREFIXES):
        return False

    words = concept.split()
    if len(words) > 5 or len(words) < 1:
        return False

    # Reject if any word is a known invalid concept (catches "Its output" where "Its" alone is bad)
    if words[0].lower() in _INVALID_CONCEPTS:
        return False

    if any(bad in lower for bad in ("introduction", "summary", "lecture", "seeded", "demo material")):
        return False

    # Reject duplicate-word concepts like "flow flow"
    if len(words) >= 2 and words[-1].lower() == words[0].lower():
        return False

    if re.search(r"\sA\s+[A-Z]", concept):
        return False

    # Reject "X and Y" compound concepts (too vague)
    if " and " in lower and len(words) > 3:
        return False

    if len(words) >= 2 and concept.lower().count(words[0].lower()) > 1:
        return False

    # Must contain at least one alphabetic word with ≥3 letters
    if not any(re.match(r"[A-Za-z]{3,}", w) for w in words):
        return False

    return True


def _valid_definition(defn: str) -> bool:
    core = defn.rstrip(".")
    if len(core) < _MIN_DEFINITION_LEN or len(core) > _MAX_DEFINITION_LEN:
        return False
    if len(core.split()) < 5:
        return False
    return True


def _normalize_source_text(text: str) -> str:
    from app.services.quiz_material_eligibility import normalize_quiz_text

    return _strip_section_headers(normalize_quiz_text(text))


def _structure_normalize(text: str) -> str:
    """Clean noise chars but preserve newlines for structural (line-aware) extraction."""
    cleaned = text or ""
    cleaned = cleaned.replace("\x00", " ")
    cleaned = re.sub(r"[\uf000-\uf8ff]", " ", cleaned)
    cleaned = re.sub(r"[\u25a0-\u25ff\u2022\u2023\u2043]", " ", cleaned)
    # Merge hyphenated line breaks: "two-\n-dimensional" → "two-dimensional"
    cleaned = re.sub(r"-\n[ \t]*-?[ \t]*", "", cleaned)
    cleaned = re.sub(r"\n[ \t]*-\n[ \t]*", "", cleaned)
    # Normalise per-line whitespace, drop blank lines
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in cleaned.splitlines()]
    return "\n".join(l for l in lines if l)


_ARTIFACT_RE = re.compile(r"[\uf000-\uf8ff\ufffd\u25a0-\u25ff]")


def _add_pair(
    pairs: List[Tuple[str, str]],
    seen: set[str],
    concept_raw: str,
    defn_raw: str,
) -> None:
    from app.services.quiz_question_quality import is_teachable_concept

    concept = _normalize_concept(concept_raw)
    definition = _normalize_definition(defn_raw)
    if _ARTIFACT_RE.search(concept) or _ARTIFACT_RE.search(definition):
        return
    key = concept.lower()
    if not is_teachable_concept(concept) or not _valid_definition(definition):
        return
    if key in seen:
        return
    seen.add(key)
    pairs.append((concept, definition))


def _extract_colon_pairs(text: str, seen: set[str], pairs: List[Tuple[str, str]]) -> None:
    for concept_raw, defn_raw in _COLON_PATTERN.findall(text):
        concept = _normalize_concept(concept_raw)
        if len(concept.split()) <= 2 and len(defn_raw.split()) >= 8:
            _add_pair(pairs, seen, concept_raw, defn_raw)


def _extract_paren_skip(text: str, seen: set[str], pairs: List[Tuple[str, str]]) -> None:
    """Extract 'X (qualifier) is a Y' definitions skipping the parenthetical."""
    for m in _PAREN_SKIP_PATTERN.finditer(text):
        _add_pair(pairs, seen, m.group(1), m.group(2))


def _extract_abbrev_is(text: str, seen: set[str], pairs: List[Tuple[str, str]]) -> None:
    """Extract 'Full Name (ABB) is a Y' — adds both the abbreviation and full name."""
    for m in _ABBREV_IS_PATTERN.finditer(text):
        full_name = m.group(1).strip()
        abbrev = m.group(2).strip()
        definition = m.group(3).strip()
        _add_pair(pairs, seen, abbrev, f"{full_name}: {definition}")
        _add_pair(pairs, seen, full_name, definition)


def _extract_qa_adjacent(text: str, seen: set[str], pairs: List[Tuple[str, str]]) -> None:
    """
    Extract 'What is X?  \\n  Answer sentence(s)' patterns from line-structured text.
    Works with slide PDFs that present Q&A on consecutive lines.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    skip_tokens = {"=", "http", "@", "www."}
    for i, line in enumerate(lines[:-1]):
        m = _QA_LINE_RE.match(line)
        if not m:
            continue
        # Strip leading article from captured concept
        concept_raw = re.sub(r"^(?:a|an|the)\s+", "", m.group(1).strip(), flags=re.IGNORECASE)
        # Collect next 1-3 non-empty lines as the answer
        answer_lines: list[str] = []
        for j in range(i + 1, min(i + 4, len(lines))):
            next_l = lines[j]
            if any(tok in next_l.lower() for tok in skip_tokens):
                break
            # Stop if we hit another question
            if _QA_LINE_RE.match(next_l):
                break
            answer_lines.append(next_l)
            # Stop after a complete sentence
            if next_l.rstrip().endswith((".", "!", "?")):
                break
        definition = " ".join(answer_lines)
        if len(definition.split()) < 5:
            continue
        _add_pair(pairs, seen, concept_raw, definition)


def _extract_slide_pairs(text: str, seen: set[str], pairs: List[Tuple[str, str]]) -> None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for index, line in enumerate(lines[:-1]):
        next_line = lines[index + 1]
        if not _SLIDE_TITLE_RE.match(line):
            continue
        if len(next_line.split()) < 8:
            continue
        if len(next_line) > 220:
            continue
        _add_pair(pairs, seen, line, next_line)


def extract_definitions(text: str) -> List[Tuple[str, str]]:
    """Pull teachable concept/definition pairs — no slide headings."""
    seen: set[str] = set()
    pairs: List[Tuple[str, str]] = []

    structured = _strip_section_headers(_structure_normalize(text))
    _extract_qa_adjacent(structured, seen, pairs)

    source = _normalize_source_text(text)
    blob = re.sub(r"\s+", " ", source)
    _extract_paren_skip(blob, seen, pairs)
    _extract_abbrev_is(blob, seen, pairs)

    sentences = re.split(r"(?<=[.!?])\s+", blob)
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
                _add_pair(pairs, seen, concept_raw, defn_raw)

    best: dict[str, tuple[str, str]] = {}
    for concept, definition in pairs:
        key = concept.lower().strip()
        if key not in best or len(definition) > len(best[key][1]):
            best[key] = (concept, definition)
    ranked = list(best.values())
    ranked.sort(key=lambda p: -len(p[1]))
    return ranked


def _definition_option(concept: str, definition: str) -> str:
    """Definition body as option — question stem names the concept."""
    body = definition.strip().rstrip(".")
    body = re.sub(r"^(a|an|the)\s+", "", body, flags=re.IGNORECASE)
    return _format_option(body)


def _question_prompt(concept: str, index: int = 0) -> str:
    from app.services.quiz_question_quality import stem_template_for_concept

    return stem_template_for_concept(concept, index)


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
    material_sentences: Optional[List[str]] = None,
    source_text: Optional[str] = None,
) -> List[str]:
    """Same-topic wrong answers — not definitions of other concepts."""
    from app.services.quiz_question_quality import (
        pick_same_topic_distractors,
        rival_concept_names,
    )

    rivals = rival_concept_names(pool, concept)
    used = set(used_global)
    used.add(correct.lower())
    return pick_same_topic_distractors(
        concept,
        correct,
        source_text or "",
        rivals,
        used,
        material_sentences=material_sentences,
        n=n,
    )


def _build_question(
    idx: int,
    concept: str,
    definition: str,
    pool: List[Tuple[str, str]],
    used_global: Set[str],
    material_sentences: Optional[List[str]] = None,
    source_text: Optional[str] = None,
) -> Dict[str, Any] | None:
    correct = _definition_option(concept, definition)
    if not correct:
        return None

    distractors = _pick_distractors(
        concept, correct, pool, used_global, n=3,
        material_sentences=material_sentences,
        source_text=source_text,
    )
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
        "question": _question_prompt(concept, idx - 1),
        "options": options,
        "correctIndex": correct_idx,
    }


def generate_lightweight(text: str, num_questions: int = 8) -> List[Dict[str, Any]]:
    """
    Build MCQs from ranked teachable definition pairs in the material.
    """
    from app.services.quiz_material_eligibility import prepare_quiz_generation_text
    from app.services.quiz_question_quality import (
        build_mcq_from_teachable_pair,
        extract_teachable_pairs,
        final_repair_mcq_options,
        mcq_options_final_sane,
    )

    prepared = prepare_quiz_generation_text(text)
    if not prepared:
        logger.warning("Lightweight quiz gen: empty text")
        return []

    pairs = extract_teachable_pairs(prepared, limit=num_questions + 8)
    logger.info("Lightweight quiz gen: %d teachable pairs", len(pairs))

    if len(pairs) < _MIN_QUESTIONS:
        logger.warning("Lightweight quiz gen: insufficient teachable pairs (%d)", len(pairs))
        return []

    material_sentences = _extract_material_sentences(re.sub(r"\s+", " ", prepared))
    target = max(_MIN_QUESTIONS, min(num_questions, len(pairs)))
    questions: List[Dict[str, Any]] = []

    for i, (concept, definition) in enumerate(pairs):
        if len(questions) >= target:
            break
        built = build_mcq_from_teachable_pair(
            concept, definition, prepared, pairs, i,
        )
        if not built:
            continue
        built = final_repair_mcq_options(built, prepared, teachable_pairs=pairs)
        if not mcq_options_final_sane(built):
            continue
        built["id"] = f"q{len(questions) + 1}"
        questions.append(built)

    logger.info("Lightweight quiz gen: produced %d questions", len(questions))
    return questions if len(questions) >= _MIN_QUESTIONS else []

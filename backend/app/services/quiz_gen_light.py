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
    concept = _normalize_concept(concept_raw)
    definition = _normalize_definition(defn_raw)
    # Reject pairs that contain PDF-extraction artifact characters
    if _ARTIFACT_RE.search(concept) or _ARTIFACT_RE.search(definition):
        return
    key = concept.lower()
    if not _valid_concept(concept) or not _valid_definition(definition):
        return
    if key in seen:
        return
    seen.add(key)
    pairs.append((concept, definition))


def _extract_colon_pairs(text: str, seen: set[str], pairs: List[Tuple[str, str]]) -> None:
    for concept_raw, defn_raw in _COLON_PATTERN.findall(text):
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
    """Pull concept/definition pairs from lecture-style prose and slide PDFs."""
    seen: set[str] = set()
    pairs: List[Tuple[str, str]] = []

    # ── Line-aware extractions (use original line structure) ──────────────────
    structured = _strip_section_headers(_structure_normalize(text))
    _extract_qa_adjacent(structured, seen, pairs)       # "What is X?\n Answer"
    _extract_colon_pairs(structured, seen, pairs)        # "Heading: description."
    _extract_slide_pairs(structured, seen, pairs)        # "Title\n long sentence"

    # ── Blob extractions (use fully normalised text) ──────────────────────────
    source = _normalize_source_text(text)
    blob = re.sub(r"\s+", " ", source)
    _extract_paren_skip(blob, seen, pairs)               # "X (qual) is a Y."
    _extract_abbrev_is(blob, seen, pairs)                # "Name (ABB) is a Y."

    normalized = blob
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
                _add_pair(pairs, seen, concept_raw, defn_raw)

    # Deduplicate by concept: if the same concept was extracted multiple times
    # (different phrasings), keep the longest definition to avoid near-duplicate
    # options appearing in the same question.
    best: dict[str, tuple[str, str]] = {}
    for concept, definition in pairs:
        key = concept.lower().strip()
        if key not in best or len(definition) > len(best[key][1]):
            best[key] = (concept, definition)
    return list(best.values())


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
    material_sentences: Optional[List[str]] = None,
) -> List[str]:
    """
    Build distinct wrong answers grounded entirely in the same material.

    Priority:
      1. Definitions from OTHER pairs in the same material.
      2. Sentence fragments extracted from the same material text.

    No generic/hardcoded distractors — every option is grounded in the
    selected material's own content so questions stay domain-relevant
    (electronics, hardware, biology, etc. — whatever the material covers).
    """
    correct_key = _option_key(correct)
    candidates: List[str] = []

    # Primary: other concept definitions from the same material
    for other_concept, other_def in pool:
        if other_concept.lower() == concept.lower():
            continue
        option = _definition_option(other_concept, other_def)
        # Hard-cap option length (applies after _format_option already trimmed)
        if len(option) > _MAX_OPTION_LEN:
            option = _format_option(option, max_len=_MAX_OPTION_LEN)
        key = _option_key(option)
        if key == correct_key or key in used_global or option in candidates:
            continue
        candidates.append(option)

    # Fallback: sentence fragments from the same material (content-grounded)
    if len(candidates) < n and material_sentences:
        concept_lower = concept.lower()
        # Track which concept names are already represented in candidates so we
        # don't add a sentence fragment about the same concept as an existing option.
        _concept_prefix_re = re.compile(
            r"^([A-Za-z][A-Za-z\s]{2,40}?)\s+(?:refers to|is a|is an|is the|are)\b",
            re.IGNORECASE,
        )
        covered: Set[str] = set()
        for cand in candidates:
            m = _concept_prefix_re.match(cand)
            if m:
                covered.add(m.group(1).lower().strip())

        for fragment in material_sentences:
            if len(candidates) >= n:
                break
            key = _option_key(fragment)
            if key == correct_key or fragment in candidates:
                continue
            # Skip fragments about the same concept as the question
            if fragment.lower().startswith(concept_lower):
                continue
            # Skip fragments whose concept is already represented by a candidate
            m = _concept_prefix_re.match(fragment)
            if m and m.group(1).lower().strip() in covered:
                continue
            candidates.append(fragment)
            # Track this newly added fragment's concept
            if m:
                covered.add(m.group(1).lower().strip())

    return candidates[:n]


def _build_question(
    idx: int,
    concept: str,
    definition: str,
    pool: List[Tuple[str, str]],
    used_global: Set[str],
    material_sentences: Optional[List[str]] = None,
) -> Dict[str, Any] | None:
    correct = _definition_option(concept, definition)
    if not correct:
        return None

    distractors = _pick_distractors(concept, correct, pool, used_global, n=3,
                                    material_sentences=material_sentences)
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
    Build MCQ questions from content_text using definition extraction.

    All distractors are drawn from the SAME material text — either from other
    extracted definition pairs or from sentence fragments in the same content.
    No hardcoded or generic distractors are used.
    """
    from app.services.quiz_material_eligibility import prepare_quiz_generation_text

    prepared = prepare_quiz_generation_text(text)
    if not prepared:
        logger.warning("Lightweight quiz gen: empty text")
        return []

    pairs = extract_definitions(prepared)
    logger.info("Lightweight quiz gen: extracted %d definition pairs", len(pairs))

    if len(pairs) < 3:
        logger.warning("Lightweight quiz gen: insufficient definitions (%d)", len(pairs))
        return []

    # Extract sentence fragments from the same material for fallback distractors
    material_sentences = _extract_material_sentences(re.sub(r"\s+", " ", prepared))
    logger.debug("Lightweight quiz gen: %d material sentence fragments", len(material_sentences))

    target = max(_MIN_QUESTIONS, min(num_questions, len(pairs)))
    questions: List[Dict[str, Any]] = []
    used_global: Set[str] = set()

    for concept, definition in pairs:
        if len(questions) >= target:
            break
        q = _build_question(len(questions) + 1, concept, definition, pairs,
                            used_global, material_sentences=material_sentences)
        if q:
            questions.append(q)

    logger.info("Lightweight quiz gen: produced %d questions", len(questions))
    return questions if len(questions) >= _MIN_QUESTIONS else []

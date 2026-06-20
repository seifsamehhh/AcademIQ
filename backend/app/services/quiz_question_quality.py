"""
Validate and repair vague quiz question stems so every question names a concept.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

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
    r"(?:\b(the|about|by|of|a|an|to|in|for|with|and|or|as|on|at|from|approx|include|refers to)\s*\.?\s*$"
    r"|[,:\{\(]\s*$)",
    re.I,
)
_TECH_TERM_RE = re.compile(r"^[A-Z]{2,10}$")
_BROKEN_OPTION_PHRASE_RE = re.compile(
    r"(?i)practically it refers to|described by An\b|it refers to described|"
    r"for human perception refers to|solution is an use|repeat until goal refers to found|"
    r"\bNNNJ is a So\b|refers to found|refers to natural|refers to given by|"
    r"refers to to |refers to very |refers to specifically|refers to filtered|"
    r"reasons for doing this include refers to|^pattern it\b|sent to a feature|"
    r"make decisions about patterns"
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
_WEAK_SINGLE_CONCEPTS = frozenset(
    {
        "length", "classifier", "features", "feature", "what", "which", "how",
        "why", "when", "agent", "agents", "pattern", "patterns", "data", "class",
        "classes", "model", "models", "input", "output", "algorithm", "method",
        "methods", "system", "systems", "process", "training", "testing",
        "learning", "concept", "category", "object", "vector", "vectors", "image",
        "images", "pixel", "pixels", "set", "sets", "type", "types", "function",
        "functions", "network", "networks", "node", "nodes", "tree", "trees",
        "rule", "rules", "terminology", "lightness", "width", "information",
        "trade", "label", "task", "they", "it", "we", "itself", "result",
    }
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
_CONCEPT_FROM_STEM_RE = re.compile(
    r"(?i)(?:best describes|purpose of|main purpose of|role of|main idea of|main goal of|"
    r"definition of|correctly explains|difference between|important in|role does)\s+(.+?)\??\s*$"
)
_ROLE_PLAY_RE = re.compile(r"(?i)what role does\s+(.+?)\s+play in")
_FILE_NOISE_RE = re.compile(
    r"(?i)\b(?:swe\d+|csc\d+|csc\s*\d+|file|moodle|copy)\b|\.(?:pdf|pptx?|ppsx|docx?)\b"
)
_COPY_NUM_RE = re.compile(r"\s*\(\d+\)\s*")
_DIGIT_PREFIX_RE = re.compile(r"^\d{1,2}\s+")
_MATERIAL_TITLE_OPTION_RE = re.compile(
    r"(?i)(?:\blecture\s*\d|\blab\s*\d|test\s+import\s+definition|import\s+definition|"
    r"ready\s+for\s+quiz|selected\s+material|\.pdf\b|\.pptx\b|\.ppsx\b|\bfile\b|\bmoodle\b)"
)
_MATERIAL_TITLE_PREFIX_RE = re.compile(
    r"(?i)^(?:lecture|lab)\s*\d+\s*[—–\-]\s*"
    r"(?:test\s+import\s+definition|import\s+definition)?\s*:\s*"
)
_IMPORT_DEF_PREFIX_RE = re.compile(
    r"(?i)^(?:test\s+import\s+definition|import\s+definition)\s*:\s*"
)
_MERGED_CAMEL_RE = re.compile(r"([a-z])([A-Z])")
_OPTION_BLACKLIST_RE = re.compile(
    r"(?i)(?:which of the following|suppose that|why\?|sample input|sample output|"
    r"input\s*/?\s*output|input output|operation\s*\?|origi|points\s*\)|\bexercise\b|"
    r"given table|shown in the following|resize 2nd image|nnnj|njnj|"
    r"test import definition|\.pdf\b|\.pptx\b|\.ppsx\b|\bslide\b|\[slide|lab\s*#|"
    r"iff\s*\.|does not end\s*,|states\s*\{|sample input/output|\bquestion\b|"
    r"\bex\d*\s*:|^ex\d|page\s*\d+|lab overview|computer vision tasks|"
    r"sort,\s*square|moving window transform|depends on non|"
    r"set the pixel value|midpoint value|variance of pixels)"
)
_SLIDE_MARKER_RE = re.compile(
    r"(?i)\[?\s*slide\s*\d+\s*\]?|lab\s*#\s*\d+|page\s*\d+"
)
_BROKEN_PREFIX_RE = re.compile(
    r"(?i)^(?:points\s*\)|question:|exercise:|sample input/output|"
    r"ex\d*\s*:|process:|page\s*\d+\s*)"
)
_HEADING_OPTION_RE = re.compile(
    r"(?i)^(?:non\s*-?\s*linear filters|global he|local he|original image|"
    r"origin\s*x\s*y|process)\s*[:]?\s*"
)
_MATH_JUNK_RE = re.compile(
    r"[=∑∏√−𝑫𝑮𝒙𝒚𝐆]|==\s*\w|\)f\(|tan−|tan\s*−|partial derivative|"
    r"direction of this vector|simplified as:|third colum|\bmag\b|"
    r"for practical reasons this can be|1st derivative|2nd derivative|"
    r"the formula for|main applications:"
)
_FORMULA_HEADING_RE = re.compile(
    r"(?i)–\s*(line|example)\s*–|hough transform.*example|"
    r"derivative\s*–\s*second derivative|smoothing filters main"
)
_FRAGMENT_START_RE = re.compile(r"(?i)^(en by|ction|roximating|edg)\b")
_GENERIC_SAFE_DISTRACTORS = [
    "It improves the visual quality or interpretability of the input data.",
    "It helps transform raw data into a more useful representation.",
    "It supports analysis by highlighting meaningful patterns in the data.",
    "It is used to prepare information for later processing steps.",
]
_CONCEPT_GENERIC_DISTRACTORS = [
    "It mainly describes a general preprocessing step rather than the selected concept.",
    "It focuses on changing the input format without addressing the main concept.",
    "It represents a different technique from the one described in the question.",
    "It is related to the topic but does not correctly explain the selected concept.",
]
MIN_OPTION_WORDS = 6
MAX_OPTION_WORDS = 35
MIN_QUIZ_RETURN = 3
MAX_FALLBACK_FILL = 5
RICH_CONTENT_CHARS = 1000


def normalize_merged_words(text: str) -> str:
    """Light OCR merge fix — LuminosityGray -> Luminosity Gray, etc."""
    s = (text or "").strip()
    if not s:
        return ""
    s = _MERGED_CAMEL_RE.sub(r"\1 \2", s)
    for old, new in (
        ("LuminosityGray", "Luminosity Gray"),
        ("GrayScale", "Gray Scale"),
        ("NonLinear", "Non-Linear"),
        ("InputOutput", "Input Output"),
    ):
        s = re.sub(re.escape(old), new, s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip()


def _rewrite_known_broken_patterns(option: str) -> str:
    """Rewrite common ugly OCR/slide fragments into clean answer sentences."""
    o = (option or "").strip()
    low = o.lower()
    if "thermostat" in low and ("reactive" in low or "states" in low or "environment" in low):
        return (
            "A thermostat can be modeled as a reactive agent that chooses actions "
            "based on the current state of its environment."
        )
    if "image classification" in low and "single label" in low:
        return "Image classification predicts a single label for the entire image."
    if "behaviorally equivalent" in low:
        return (
            "Two agents are behaviorally equivalent when they produce the same "
            "actions in the same states."
        )
    if "what is inside this image" in low or "model only answers" in low:
        return "The model predicts the category of objects present in the image."
    if "does not end" in low and "environment" in low:
        return (
            "In general, agents continue interacting with their environment over time."
        )
    return o


def sanitize_option_text(raw: str) -> str:
    """Strip slide markers, broken prefixes, and dangling symbols from an option."""
    o = re.sub(r"[\uf000-\uf8ff\ufffd•▪…]", " ", (raw or ""))
    o = re.sub(r"\s+", " ", o).strip()
    if not o:
        return ""
    o = o.replace("?", ".")
    o = _SLIDE_MARKER_RE.sub(" ", o)
    o = _BROKEN_PREFIX_RE.sub("", o)
    o = _HEADING_OPTION_RE.sub("", o)
    o = re.sub(r"(?i)\bex\d*\s*:", " ", o)
    o = re.sub(r"(?i)sort,\s*square[^.]*\)\s*", " ", o)
    o = re.sub(r"\(\s*[a-z]\s*\.?\s*$", "", o)
    o = re.sub(r"[\{\}\[\]]", " ", o)
    o = re.sub(r'"{2,}|\'{2,}', '"', o)
    o = re.sub(r"\.{2,}", ".", o)
    o = re.sub(r",\s*,", ",", o)
    o = re.sub(r"\s+-\s+", "-", o)
    o = re.sub(r"(?i)\bnon\s+-\s*linear", "non-linear", o)
    o = _rewrite_known_broken_patterns(o)
    embedded_q = re.search(r"(?i)\bwhat is\b", o)
    if embedded_q and embedded_q.start() > 0:
        suffix = o[embedded_q.start():].strip()
        if len(suffix.split()) >= MIN_OPTION_WORDS:
            o = suffix
        else:
            prefix = o[:embedded_q.start()].strip()
            if len(prefix.split()) >= MIN_OPTION_WORDS:
                o = prefix
    o = re.sub(r"(?i)\s*–\s*\(cont\.[^.]*\.?\s*$", "", o).strip()
    o = re.sub(r"(?i)\s+smooth(ing)?\s+filters\s+smooth(ing)?\s+filters.*$", "", o).strip()
    if _SLIDE_MARKER_RE.search(o) or re.search(r"(?i)\bslide\b", o):
        colon = re.search(r":\s*(.+)$", o)
        if colon and len(colon.group(1).split()) >= MIN_OPTION_WORDS:
            o = colon.group(1).strip()
    label_colon = re.match(r"^[^:]{3,80}:\s*(.+)$", o)
    if label_colon and len(label_colon.group(1).split()) >= MIN_OPTION_WORDS:
        prefix = o[:label_colon.start(1)].lower()
        if any(
            k in prefix
            for k in ("slide", "agent", "classification", "lab", "overview", "pattern")
        ):
            o = label_colon.group(1).strip()
    o = _rewrite_known_broken_patterns(o)
    o = normalize_merged_words(o)
    o = re.sub(r"\s+", " ", o).strip()
    o = o.rstrip(",;:{([ ")
    return o


def option_needs_replacement(
    option: str,
    material_title: Optional[str] = None,
) -> bool:
    """True when an option should be swapped (never fails the whole quiz)."""
    o = sanitize_option_text(option)
    o = clean_option_text(o) if o else ""
    if not o or len(o) < 12:
        return True
    if "?" in o:
        return True
    if _OPTION_BLACKLIST_RE.search(o):
        return True
    if _SLIDE_MARKER_RE.search(o) or re.search(r"(?i)\bslide\b", o):
        return True
    if is_material_title_option(o, material_title):
        return True
    if is_broken_option(o):
        return True
    return False


def clean_option_text(option: str) -> str:
    """Normalize an MCQ option — statements only, never questions."""
    o = sanitize_option_text(option)
    if not o:
        return ""
    o = o.rstrip(",;:")
    if o and o[0].islower():
        o = o[0].upper() + o[1:]
    words = o.split()
    if len(words) > MAX_OPTION_WORDS:
        o = " ".join(words[:MAX_OPTION_WORDS]).rstrip(",;:")
    if o and not o.endswith((".", "!")):
        o += "."
    if len(o) > 120:
        o = o[:117].rsplit(" ", 1)[0] + "."
    return o


def is_material_title_option(
    option: str,
    material_title: Optional[str] = None,
) -> bool:
    """True when an option looks like a file/material title, not an answer."""
    o = (option or "").strip()
    if not o:
        return True
    if _MATERIAL_TITLE_OPTION_RE.search(o):
        return True
    if re.match(r"(?i)^lecture\s*\d+\s*[—–\-]", o):
        return True
    if re.match(r"(?i)^lab\s*\d+\s*[—–\-]", o):
        return True
    if material_title:
        title_clean = clean_title_token(material_title).lower()
        if title_clean and len(title_clean) >= 8 and title_clean in o.lower():
            return True
    return False


def strip_material_title_from_option(option: str) -> str:
    """Remove lecture/lab/test-import/slide prefixes; keep answer body only."""
    o = sanitize_option_text(option)
    m = _MATERIAL_TITLE_PREFIX_RE.match(o)
    if m:
        o = o[m.end() :]
    m2 = _IMPORT_DEF_PREFIX_RE.match(o)
    if m2:
        o = o[m2.end() :]
    return clean_option_text(o)


def _generic_concept_distractor(concept: str, used: Set[str]) -> str:
    for d in _CONCEPT_GENERIC_DISTRACTORS:
        if d.lower() not in used:
            return d
    return _generic_safe_distractor(used)


def _unique_distractor_for_slot(slot: int, used: Set[str]) -> str:
    """Pick a distinct generic distractor for option slot 0-3."""
    pool = _CONCEPT_GENERIC_DISTRACTORS + _GENERIC_SAFE_DISTRACTORS
    candidate = pool[slot % len(pool)]
    if candidate.lower() not in used:
        return candidate
    for j in range(1, len(pool)):
        candidate = pool[(slot + j) % len(pool)]
        if candidate.lower() not in used:
            return candidate
    suffixes = (" in this context.", " for this topic.", " in the material.", " here.")
    base = pool[slot % len(pool)].rstrip(".")
    for suffix in suffixes:
        candidate = base + suffix
        if candidate.lower() not in used:
            return candidate
    return f"It does not correctly explain the concept in option {slot + 1}."


def _generic_safe_distractor(used: Set[str]) -> str:
    return _unique_distractor_for_slot(0, used)


def _pick_replacement_option(
    source_text: str,
    used: Set[str],
    material_title: Optional[str] = None,
    concept: Optional[str] = None,
    global_used: Optional[Set[str]] = None,
) -> str:
    combined_used = set(used)
    if global_used:
        combined_used.update(global_used)
    for s in extract_educational_sentences(source_text, limit=60):
        candidate = strip_material_title_from_option(s)
        if not candidate or candidate.lower() in combined_used:
            continue
        if option_needs_replacement(candidate, material_title):
            continue
        return candidate
    for s in _extract_clean_sentences(source_text, limit=30):
        candidate = strip_material_title_from_option(s)
        if not candidate or candidate.lower() in combined_used:
            continue
        if option_needs_replacement(candidate, material_title):
            continue
        return candidate
    if concept:
        return _generic_concept_distractor(concept, combined_used)
    return _generic_safe_distractor(combined_used)


def sanitize_quiz_options(
    options: List[str],
    correct_index: int,
    source_text: str,
    material_title: Optional[str] = None,
    question: Optional[str] = None,
    global_used: Optional[Set[str]] = None,
) -> Tuple[List[str], int]:
    """Clean options; replace bad choices without failing the quiz."""
    concept = extract_concept_from_stem(question or "")
    used: Set[str] = set()
    if global_used:
        used.update(global_used)
    cleaned: List[str] = []
    correct_idx = max(0, min(int(correct_index or 0), max(0, len(options) - 1)))
    correct_raw = options[correct_idx] if options else ""

    for i, opt in enumerate(options):
        o = strip_material_title_from_option(opt)
        if option_needs_replacement(o, material_title):
            o = _pick_replacement_option(
                source_text, used, material_title, concept, global_used,
            )
        if o.lower() in used:
            o = _unique_distractor_for_slot(i, used | (global_used or set()))
        used.add(o.lower())
        cleaned.append(o)

    if not cleaned:
        cleaned = [
            _pick_replacement_option(
                source_text, set(), material_title, concept, global_used,
            )
        ]

    correct_clean = strip_material_title_from_option(correct_raw)
    if (
        option_needs_replacement(correct_clean, material_title)
        or correct_clean.lower() not in {x.lower() for x in cleaned}
    ):
        replacement = _pick_replacement_option(
            source_text,
            {x.lower() for x in cleaned},
            material_title,
            concept,
            global_used,
        )
        if correct_idx < len(cleaned):
            cleaned[correct_idx] = replacement
        else:
            cleaned[0] = replacement
            correct_idx = 0

    while len(cleaned) < 4:
        extra = _pick_replacement_option(
            source_text,
            {x.lower() for x in cleaned},
            material_title,
            concept,
            global_used,
        )
        if extra.lower() in {x.lower() for x in cleaned}:
            extra = _generic_safe_distractor(
                {x.lower() for x in cleaned} | (global_used or set()),
            )
        cleaned.append(extra)

    # Ensure four unique options
    seen_opts: Set[str] = set()
    unique: List[str] = []
    for slot, o in enumerate(cleaned[:4]):
        if o.lower() in seen_opts:
            o = _pick_replacement_option(
                source_text,
                seen_opts | (global_used or set()),
                material_title,
                concept,
                global_used,
            )
        if o.lower() in seen_opts:
            o = _unique_distractor_for_slot(slot, seen_opts | (global_used or set()))
        seen_opts.add(o.lower())
        unique.append(o)
    cleaned = unique

    return cleaned[:4], correct_idx


def is_broken_option(option: str) -> bool:
    """True when an MCQ option is a fragment or unreadable."""
    o = (option or "").strip()
    if "?" in o:
        return True
    if _SLIDE_MARKER_RE.search(o) or re.search(r"(?i)\bslide\b|\[slide", o):
        return True
    if re.search(r"(?i)lab overview|computer vision tasks\s+\d", o):
        return True
    if re.search(r"(?i)\bex\d*\s*:|sort,\s*square|set the pixel value|midpoint value", o):
        return True
    if re.search(r"(?i)depends on non|moving window transform|variance of pixels", o):
        return True
    if re.search(r"(?i)^(?:global he|local he|origin\s*x\s*y|original image)\b", o):
        return True
    if _MATH_JUNK_RE.search(o) or _FRAGMENT_START_RE.search(o):
        return True
    if _FORMULA_HEADING_RE.search(o):
        return True
    if re.search(r"(?i)^can cause some strange", o):
        return True
    if re.search(r"(?i)\bwhat is\b", o) and not re.match(r"(?i)^what is\b", o):
        return True
    if re.search(r"(?i)\(cont\.|–\s*\(cont|smooth(ing)?\s+filters\s+smooth", o):
        return True
    if re.search(r"==\d|iiz\s*r\b|mask size|→|𝐺|𝑅|𝑖", o):
        return True
    if re.search(
        r"(?i)sharpen filter|spatial filtering|local hist equalization|"
        r"sharpening.*edge filters|linear-averaging filter|weighted mean",
        o,
    ):
        return True
    if re.search(r"(?i)model only answers", o):
        return True
    if re.search(r"^\w+\s*\([^)]{3,40}\)[A-Z]", o):
        return True
    if len(o) < 12:
        return True
    words = o.split()
    if _GENERIC_OPTION_RE.match(o):
        return True
    if _BROKEN_OPTION_END_RE.search(o):
        return True
    if _BROKEN_OPTION_PHRASE_RE.search(o):
        return True
    if len(words) < MIN_OPTION_WORDS and not _TECH_TERM_RE.match(o):
        return True
    if len(words) > MAX_OPTION_WORDS:
        return True
    sym = len(re.findall(r"[^\w\s]", o))
    if sym > max(6, len(words)):
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
    if is_material_title_option(o):
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
    concept = extract_concept_from_stem(question)
    if is_weak_concept(concept):
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


def normalize_concept_key(concept: str) -> str:
    c = re.sub(r"^the\s+", "", (concept or "").lower().strip())
    return re.sub(r"\s+", " ", c)


def extract_concept_from_stem(question: str) -> str:
    q = (question or "").strip()
    m = _CONCEPT_FROM_STEM_RE.search(q)
    if m:
        return normalize_concept_key(m.group(1).strip())
    m_role = _ROLE_PLAY_RE.search(q)
    if m_role:
        return normalize_concept_key(m_role.group(1).strip())
    m2 = re.match(r"^what\s+(?:is|are)\s+(?:the\s+)?(.+?)\s*\??\s*$", q, re.I)
    if m2:
        return normalize_concept_key(m2.group(1).strip())
    tokens = [
        t.lower()
        for t in re.findall(r"[A-Za-z][A-Za-z0-9\-]{3,}", q)
        if t.lower() not in _GENERIC_WORDS
    ]
    return normalize_concept_key(" ".join(tokens[:3]))


def normalize_stem(stem: str) -> str:
    s = re.sub(r"\s+", " ", (stem or "").lower().strip().rstrip("?"))
    return re.sub(r"[^\w\s]", "", s)


def _question_signature(q: Dict[str, Any]) -> Tuple[str, str, str]:
    stem = normalize_stem(str(q.get("question") or ""))
    concept = extract_concept_from_stem(str(q.get("question") or ""))
    opts = q.get("options") or []
    idx = int(q.get("correctIndex") or 0)
    correct = ""
    if opts and 0 <= idx < len(opts):
        correct = normalize_stem(str(opts[idx]))
    return concept, stem[:70], correct[:70]


def _score_question(
    q: Dict[str, Any],
    source_text: str,
    material_title: Optional[str],
) -> int:
    stem = str(q.get("question") or "")
    opts = [clean_option_text(o) for o in q.get("options") or []]
    keywords = _extract_keywords(source_text, material_title)
    score = 0
    if is_question_valid(stem, opts, source_text, material_title, keywords):
        score += 1000
    score += len(stem.split()) * 5
    concept = extract_concept_from_stem(stem)
    if concept:
        score += min(len(concept.split()) * 25, 75)
    if is_weak_concept(concept):
        score -= 800
    if re.search(r"(?i)which statement best describes", stem):
        score += 50
    if re.search(r"(?i)what is the (main purpose|purpose|role)", stem):
        score += 40
    if re.search(r"(?i)which of the following", stem):
        score -= 200
    return score


def deduplicate_questions(
    questions: List[Dict[str, Any]],
    source_text: str,
    material_title: Optional[str],
) -> List[Dict[str, Any]]:
    best_by_concept: Dict[str, Dict[str, Any]] = {}
    best_score: Dict[str, int] = {}
    seen_stems: Set[str] = set()
    out: List[Dict[str, Any]] = []

    for q in questions:
        concept, stem_key, _ = _question_signature(q)
        if not concept or len(concept) < 2:
            concept = stem_key[:40]
        if stem_key in seen_stems:
            continue
        score = _score_question(q, source_text, material_title)
        prev = best_by_concept.get(concept)
        if prev is not None and best_score.get(concept, 0) >= score:
            continue
        if prev is not None:
            out = [x for x in out if extract_concept_from_stem(str(x.get("question") or "")) != concept]
        best_by_concept[concept] = q
        best_score[concept] = score
        seen_stems.add(stem_key)
        out.append(q)

    return out


def extract_educational_sentences(text: str, limit: int = 40) -> List[str]:
    """Clean sentences from selected material (8–35 words, no OCR noise)."""
    out: List[str] = []
    seen: Set[str] = set()
    noise = re.compile(
        r"(?i)(?:\[Page\s*\d|Page\s*\d+\])|postprocessing:|image algebra|"
        r"visual example|course outline|\d{1,2}/\d{1,2}/\d{4}|"
        r"\bex\d*\s*:|sort,\s*square|set the pixel value|depends on non|"
        r"moving window transform|lab overview|computer vision tasks|"
        r"partial derivative|direction of this vector|simplified as:|"
        r"for practical reasons this can be|third colum"
    )
    for m in re.finditer(r"[A-Za-z][^.!?]{15,280}[.!?]", text or ""):
        raw = re.sub(r"\s+", " ", m.group(0)).strip()
        words = raw.split()
        if len(words) < 8 or len(words) > 35:
            continue
        if noise.search(raw) or _MATH_JUNK_RE.search(raw):
            continue
        s = clean_option_text(raw)
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


def clean_concept_label(raw: str) -> str:
    """Strip file/OCR prefixes from a concept label."""
    c = normalize_merged_words((raw or "").strip())
    c = _FILE_NOISE_RE.sub(" ", c)
    c = _COPY_NUM_RE.sub(" ", c)
    c = _DIGIT_PREFIX_RE.sub("", c)
    c = re.sub(r"[_|]+", " ", c)
    c = re.sub(r"\s+", " ", c).strip()
    if not c:
        return ""
    if c.isupper() and 1 <= len(c.split()) <= 4:
        c = c.title()
    c = c[:55].strip()
    if is_weak_concept(c):
        return ""
    return c


def is_weak_concept(concept: str) -> bool:
    """True when a stem concept is too generic, OCR-noisy, or truncated."""
    c = re.sub(r"\s+", " ", (concept or "").strip())
    if not c or len(c) < 3:
        return True
    low = c.lower()
    if low in _WEAK_SINGLE_CONCEPTS:
        return True
    words = low.split()
    if len(words) == 1:
        return words[0] in _WEAK_SINGLE_CONCEPTS
    if len(words) <= 2 and all(
        w in _WEAK_SINGLE_CONCEPTS or w in {"the", "a", "an"} for w in words
    ):
        return True
    if re.search(
        r"category to which|object belon|which a given|play in|recogntit|"
        r"pattern recognition algorithm$|information from a single|"
        r"^(number of|task of|example of|extractor whose|a typical|summary some|weak notions)|"
        r"summary summary|image\s+\d+\s+image|change pixel|dealing with image",
        low,
    ):
        return True
    if low.endswith(" that") or "whose purpose" in low:
        return True
    if low.startswith("itself from") or "from one machine" in low:
        return True
    if re.search(r"operatio\s+n|result image|origi\s*nx|smoothed image thresholded|"
                 r"look-up table for|in others the|rationality but what|current square", low):
        return True
    if re.match(r"(?i)(suck|but what)", low):
        return True
    if len(re.findall(r"\b[A-Z][a-z]{2,}", c)) >= 4:
        return True
    if _SHOUTY_STEM_RE.search(c) and len(words) >= 3:
        return True
    if len(words) > 7:
        return True
    if words[0] in {"what", "which", "how", "why", "when", "the"} and len(words) <= 3:
        return True
    last = words[-1]
    if len(last) <= 5 and re.search(r"(lon|rec|tit)$", last):
        return True
    return False


def clean_question_stem(question: str, material_title: Optional[str] = None) -> str:
    q = (question or "").strip()
    m = _CONCEPT_FROM_STEM_RE.search(q)
    if m:
        cleaned = clean_concept_label(m.group(1))
        if cleaned:
            q = q[:m.start(1)] + cleaned + q[m.end(1):]
    topic_m = re.search(r"(?i)in\s+(.+?)\??\s*$", q)
    if topic_m:
        topic = clean_concept_label(topic_m.group(1))
        if topic:
            q = q[:topic_m.start(1)] + topic + q[topic_m.end(1):]
    return q


def light_cleanup_question(
    question: str,
    source_text: str,
    material_title: Optional[str] = None,
) -> str:
    """Non-blocking stem cleanup; rewrite only when clearly vague."""
    q = normalize_merged_words((question or "").strip())
    q = _FILE_NOISE_RE.sub(" ", q)
    q = re.sub(r"(?i)^lecture\s*\d+\s*[—–\-]\s*", "", q).strip()
    q = clean_question_stem(q, material_title)
    if q and not q.endswith("?"):
        q = q.rstrip(".") + "?"
    vague = (
        is_vague_question(q, material_title)
        or uses_filename_as_concept(q, material_title)
        or is_grammatically_broken_question(q)
    )
    if vague:
        for candidate in _extract_concepts(source_text, 20):
            c = clean_concept_label(candidate)
            if c and not is_weak_concept(c):
                q = f"Which statement best describes {c}?"
                break
        else:
            topic = clean_concept_label(clean_title_token(material_title or ""))
            if topic and not is_weak_concept(topic):
                q = f"Which statement best describes {topic}?"
    return q or "Which statement best describes this topic?"


def mcq_options_final_sane(
    item: Dict[str, Any],
    material_title: Optional[str] = None,
) -> bool:
    opts = list(item.get("options") or [])
    if len(opts) != 4:
        return False
    if len({o.lower() for o in opts}) != 4:
        return False
    idx = int(item.get("correctIndex") or 0)
    if not (0 <= idx < 4):
        return False
    for o in opts:
        if "?" in o or option_needs_replacement(o, material_title):
            return False
    return True


def final_repair_mcq_options(
    item: Dict[str, Any],
    source_text: str,
    material_title: Optional[str] = None,
    global_used: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """Run option sanitizer twice; replace any option that still fails checks."""
    question = str(item.get("question") or "")
    for _ in range(2):
        opts, idx = sanitize_quiz_options(
            list(item.get("options") or []),
            int(item.get("correctIndex") or 0),
            source_text,
            material_title,
            question=question,
            global_used=global_used,
        )
        opts = [o.replace("?", ".") for o in opts]
        item["options"] = opts[:4]
        item["correctIndex"] = max(0, min(idx, len(item["options"]) - 1))
        seen_opts: Set[str] = set()
        for slot, opt in enumerate(item["options"]):
            if opt.lower() in seen_opts:
                replacement = _unique_distractor_for_slot(
                    slot, seen_opts | (global_used or set()),
                )
                item["options"][slot] = replacement
            seen_opts.add(item["options"][slot].lower())
        if mcq_options_final_sane(item, material_title):
            break
    return item


def final_repair_mcq(
    item: Dict[str, Any],
    source_text: str,
    material_title: Optional[str] = None,
    global_used: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """Final MCQ option pass; swap entire MCQ only if options stay ugly."""
    item = final_repair_mcq_options(item, source_text, material_title, global_used)
    if mcq_options_final_sane(item, material_title):
        return item
    from app.services.quiz_gen_fallback import generate_deterministic_fallback

    fb = generate_deterministic_fallback(source_text, material_title, 1)
    if fb:
        replacement = light_cleanup_mcq(
            dict(fb[0]), source_text, material_title, global_used,
        )
        replacement = final_repair_mcq_options(
            replacement, source_text, material_title, global_used,
        )
        if mcq_options_final_sane(replacement, material_title):
            return replacement
    return final_repair_mcq_options(item, source_text, material_title, global_used)


def light_cleanup_mcq(
    item: Dict[str, Any],
    source_text: str,
    material_title: Optional[str] = None,
    global_used: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """Clean one MCQ in place — never drop it."""
    item["question"] = light_cleanup_question(
        str(item.get("question") or ""), source_text, material_title,
    )
    raw_opts = list(item.get("options") or [])
    if not raw_opts:
        raw_opts = [
            _pick_replacement_option(
                source_text, set(), material_title, None, global_used,
            )
        ]
    opts, idx = sanitize_quiz_options(
        raw_opts,
        int(item.get("correctIndex") or 0),
        source_text,
        material_title,
        question=item["question"],
        global_used=global_used,
    )
    item["options"] = [o.replace("?", ".") for o in opts[:4]]
    item["correctIndex"] = max(0, min(idx, len(item["options"]) - 1))
    item = final_repair_mcq_options(item, source_text, material_title, global_used)
    if global_used is not None:
        global_used.update(o.lower() for o in item["options"])
    return item


def _accept_drafts(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep draft MCQs with minimal structure — do not apply strict validation."""
    out: List[Dict[str, Any]] = []
    for q in questions or []:
        stem = str(q.get("question") or "").strip()
        opts = [str(o) for o in (q.get("options") or []) if str(o).strip()]
        if not stem and not opts:
            continue
        out.append(
            {
                "id": q.get("id"),
                "question": stem or "Which statement best describes this topic?",
                "options": opts if opts else ["See the selected course material."],
                "correctIndex": int(q.get("correctIndex") or 0),
            }
        )
    return out


def emergency_quiz_fill(
    source_text: str,
    material_title: Optional[str] = None,
    target: int = 5,
) -> List[Dict[str, Any]]:
    """Last-resort fill so rich materials never return an empty quiz."""
    from app.services.quiz_gen_fallback import generate_deterministic_fallback

    fb = generate_deterministic_fallback(source_text, material_title, target + 2)
    global_used: Set[str] = set()
    out: List[Dict[str, Any]] = []
    for item in _accept_drafts(fb):
        out.append(light_cleanup_mcq(item, source_text, material_title, global_used))
    return out[:target]


def log_quiz_generation_stats(
    material_title: Optional[str],
    content_length: int,
    ai_attempted: bool,
    ai_time_seconds: float,
    valid_ai_count: int,
    fallback_count: int,
    final_count: int,
) -> None:
    logger.info(
        "Quiz stats title=%s content_len=%d ai_attempted=%s ai_time_seconds=%.2f "
        "valid_ai_count=%d fallback_count=%d final_count=%d",
        (material_title or "")[:80],
        content_length,
        ai_attempted,
        ai_time_seconds,
        valid_ai_count,
        fallback_count,
        final_count,
    )


def finalize_quiz_fast(
    questions: List[Dict[str, Any]],
    source_text: str,
    material_title: Optional[str] = None,
    target: int = 5,
    deadline: Optional[float] = None,
    fallback_text: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], int, int]:
    """Non-blocking finalize: clean every draft, fill to target, never return empty for rich text."""
    import time

    fb_source = (fallback_text or source_text or "").strip()
    validate_text = fb_source if len(fb_source) >= len((source_text or "").strip()) else source_text
    content_len = len((source_text or "").strip())
    min_target = target if content_len > RICH_CONTENT_CHARS else min(MIN_QUIZ_RETURN, target)

    pool = _accept_drafts(questions)
    valid_primary = len(pool)
    if pool:
        pool = deduplicate_questions(pool, validate_text, material_title)

    fallback_added = 0
    from app.services.quiz_gen_fallback import generate_deterministic_fallback

    if (deadline is None or time.monotonic() < deadline - 0.5):
        fb = generate_deterministic_fallback(fb_source, material_title, target + 4)
        before = len(pool)
        pool = deduplicate_questions(_accept_drafts(fb) + pool, validate_text, material_title)
        fallback_added = max(0, len(pool) - before)

    fill_attempts = 0
    while (
        len(pool) < min_target
        and fill_attempts < MAX_FALLBACK_FILL
        and (deadline is None or time.monotonic() < deadline - 0.3)
    ):
        fill_attempts += 1
        need = min(min_target - len(pool) + 2, 4)
        fb = generate_deterministic_fallback(fb_source, material_title, need)
        before = len(pool)
        pool = deduplicate_questions(_accept_drafts(fb) + pool, validate_text, material_title)
        fallback_added += max(0, len(pool) - before)

    global_used: Set[str] = set()
    cleaned: List[Dict[str, Any]] = []
    for item in pool:
        cleaned.append(light_cleanup_mcq(item, validate_text, material_title, global_used))
    pool = deduplicate_questions(cleaned, validate_text, material_title)
    pool = pool[:target]

    if len(pool) < min_target and content_len > RICH_CONTENT_CHARS:
        extra = emergency_quiz_fill(validate_text, material_title, min_target)
        for item in extra:
            if len(pool) >= min_target:
                break
            item = light_cleanup_mcq(item, validate_text, material_title, global_used)
            merged = deduplicate_questions(pool + [item], validate_text, material_title)
            if len(merged) > len(pool):
                pool = merged
                fallback_added += 1

    pool = pool[:target]
    repaired: List[Dict[str, Any]] = []
    repair_used: Set[str] = set(global_used) if global_used else set()
    for item in pool:
        repaired.append(
            final_repair_mcq(item, validate_text, material_title, repair_used),
        )
        repair_used.update(o.lower() for o in repaired[-1].get("options") or [])
    pool = repaired[:target]

    for j, item in enumerate(pool):
        item["id"] = f"q{j + 1}"

    return pool, valid_primary, fallback_added


def repair_and_select_questions(
    questions: List[Dict[str, Any]],
    source_text: str,
    material_title: Optional[str] = None,
    target: int = 5,
) -> List[Dict[str, Any]]:
    final, _, _ = finalize_quiz_fast(questions, source_text, material_title, target=target)
    return final


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
    concept_m = _CONCEPT_FROM_STEM_RE.search(q) or _ROLE_PLAY_RE.search(q)
    if concept_m:
        concept = clean_concept_label(concept_m.group(1).strip())
        if not concept or len(concept) < 3:
            return True
        if _VAGUE_CONCEPT_RE.match(concept):
            return True
        if re.search(r"category\s+to which|which the|belon$|lies\??\s*$", concept, re.I):
            return True
        if concept.lower() in {"what", "which", "how", "why", "when"}:
            return True
        if concept.lower().startswith("change pixel"):
            return True
        if len(concept.split()) == 1 and concept.lower() in _GENERIC_WORDS:
            return True
    if re.match(r"(?i)which statement best describes what\??\s*$", q):
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
        raw = re.sub(r"\s+", " ", m.group(0)).strip()
        if _MATH_JUNK_RE.search(raw) or _FRAGMENT_START_RE.search(raw):
            continue
        s = clean_option_text(raw)
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

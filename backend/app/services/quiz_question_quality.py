"""
Validate and repair vague quiz question stems so every question names a concept.
"""

from __future__ import annotations

import hashlib
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
    r"\b(the|about|by|of|a|an|to|in|for|with|and|or|as|on|at|from|approx|include|refers to|"
    r"iff|that|histories)\s*\.?\s*$",
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
    r"^what\s+is\s+information from\b|"
    r"purpose of if\b|describes if\b|explains if\b|"
    r"purpose of walk\b|describes walk\b|"
    r"whose goal\b|next can be\b|geography of the\b|"
    r"purpose of the environment\b|describes the environment\b"
)
_ARABIC_SCRIPT_RE = re.compile(r"[\u0600-\u06FF]")
_OCR_SPLIT_CAPS_RE = re.compile(r"(?<![A-Za-z])[B-HJ-Z]\s+[a-z]{2,}")
_JUNK_OPTION_CONTENT_RE = re.compile(
    r"(?i)\beg\b|american heritage|i can relax|concrete architectures|"
    r"perlocution|steve opens the window|users\)|"
    r"information filtering agent key|different types of intelligent|"
    r"histories that\.?$|behaviorally equivalent iff|to all environments|"
    r"deduction rules that govern|thatea\s*=|example\s*x\d|\bx\d\s+\d|"
    r"key characteristics of intelligent agents|one that acts or has the power|"
    r"general definitions of agent|logic based agents it|"
    r"cardmembers maximize their rewards|partially observable\s*,\s*internal state|"
    r"^:\s*the deduction|chatbots are primarily designed for sharing"
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
_ALLOWED_COMPOUND_CONCEPTS = frozenset(
    {
        "training set", "test set", "feature vector", "intelligent agent",
        "multi agent system", "multi-agent system", "utility based agent",
        "utility-based agent", "goal based agent", "goal-based agent",
        "learning agent", "reactive agent", "deliberative agent",
        "simple reflex agent", "model based reflex agent",
        "model-based reflex agent", "information filtering agent",
        "partially observable environment", "fully observable environment",
        "belief desire intention", "belief-desire-intention",
        "naive bayes", "bayes theorem", "edge detection", "image segmentation",
        "image enhancement", "histogram equalization", "spatial filtering",
        "pattern recognition", "supervised learning", "unsupervised learning",
        "feature extraction", "decision theory", "bayesian classification",
        "conditional independence", "maximum likelihood", "laplacian operator",
        "sobel operator", "hough transform",
    }
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
        "and", "or", "but", "direction", "magnitude", "detector", "vector",
        "walk", "iff", "geography", "users", "next",
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
    r"\bquestion\b|for example|e\.g\.|example of|model only answers|what is inside this image|"
    r"chapter\s+\d|pattern classification,\s*chapter|encoder-decoder architecture)"
)
_GENERIC_SAFE_DISTRACTORS = [
    "It improves the visual quality or interpretability of the input data.",
    "It helps transform raw data into a more useful representation.",
    "It supports analysis by highlighting meaningful patterns in the data.",
    "It is used to prepare information for later processing steps.",
]
_CONCEPT_GENERIC_DISTRACTORS = [
    "It describes preprocessing, not the concept asked about.",
    "It changes input format but not the main idea.",
    "It is a different technique from the one in the question.",
    "It is related to the topic but does not explain this concept.",
]
_EXAMPLE_ONLY_WORDS = frozenset(
    {
        "cat", "cats", "dog", "dogs", "mouse", "bird", "apple", "car", "tree",
        "fish", "horse", "banana", "orange", "john", "mary", "bob", "alice",
        "image", "images", "picture", "photo", "figure", "fig", "table",
    }
)
_EXAMPLE_PHRASE_RE = re.compile(
    r"(?i)(?:for example|for instance|e\.g\.|such as|example of|sample input|"
    r"sample output|consider a|suppose that|imagine a)"
)
_HEADING_SHAPE_RE = re.compile(
    r"(?i)^(original image|replicate edge|global he|local he|origin\s*x\s*y|"
    r"slide\s*\d|page\s*\d|lab\s*#|computer vision tasks|smoothing filters$|"
    r"sharpening filters$|^process$|^filters$|lab overview|visual example|"
    r"edge filters$|results of)"
)
_SLIDE_MARKER_RE = re.compile(r"(?i)\[?\s*slide\s*\d+\s*\]?|lab\s*#\s*\d+|page\s*\d+")
_TABLE_ROW_OPTION_RE = re.compile(
    r"(?i)\|"
    r"|chapter\s+\d+\s+\d+"
    r"|chapter\s+\d+\s+classification"
    r"|pattern classification,\s*chapter"
    r"|model only answers"
    r"|what is inside this image"
    r"|u-net\s*\|"
    r"|seg\s*net\s*\|"
    r"|deep\s*lab"
    r"|res\s*net\s*\|"
    r"|mobile\s*net\s*\|"
    r"|efficient\s*net\s*\|"
    r"|convolutional network\s+u-net"
    r"|encoder-decoder architecture"
    r"|very famous in medical imaging"
)
_BROKEN_OPTION_START_RE = re.compile(
    r"(?i)^(parated|ification|y\s+convolutional|e\s+res\s|separated and)"
)
_INCOMPLETE_OPTION_END_RE = re.compile(
    r"(?i)(?:\bthe main\s*\.?\s*$|\bthe main\s*$|\|\s*\w+\s*\.?\s*$|"
    r"\bhigh\s*\.?\s*$|\bfeature\s*\.?\s*$|\bpattern\s*\.?\s*$)"
)
_CROSS_CONCEPT_OPTION_RE = re.compile(
    r"(?i)^[A-Za-z][\w\s/&\-]{2,45}\s+(?:is|are|refers to|means)\s+"
)
_PRIORITY_TEACHABLE_TERMS = [
    "pattern recognition", "supervised learning", "unsupervised learning",
    "classification", "regression", "feature extraction", "training set",
    "test set", "decision theory", "feature vector", "edge detection",
    "image segmentation", "image enhancement", "histogram equalization",
    "naive bayes", "bayes theorem", "intelligent agent", "multi-agent system",
    "swarm intelligence", "prior probability", "posterior probability",
    "likelihood", "bayesian classification", "conditional independence",
    "maximum likelihood", "spatial filtering", "convolution", "gradient",
    "laplacian operator", "sobel operator", "hough transform",
    "sensors", "actuators", "utility-based agent", "reactive agent",
    "deliberative agent", "learning agent", "information filtering agent",
    "goal-based agent", "model-based reflex agent", "simple reflex agent",
    "partially observable environment", "fully observable environment",
    "belief-desire-intention", "chatbot",
]
_EXTRA_GENERIC_DISTRACTORS = [
    "It confuses training data with test data in machine learning.",
    "It describes hardware wiring instead of the software concept.",
    "It applies only to unsupervised learning, not this topic.",
    "It is about image display settings, not agent reasoning.",
    "It mixes up classification and regression tasks.",
    "It refers to user interface design, not artificial intelligence.",
    "It describes a database query, not an intelligent agent behavior.",
    "It is a networking protocol detail, not a learning algorithm.",
    "It explains file storage, not how agents perceive an environment.",
    "It describes sorting arrays, not pattern recognition methods.",
]
MIN_OPTION_WORDS = 6
MAX_OPTION_WORDS = 35
MIN_QUIZ_RETURN = 3
MAX_FALLBACK_FILL = 5
RICH_CONTENT_CHARS = 1000


def is_heading_concept(concept: str) -> bool:
    c = (concept or "").strip()
    if not c:
        return True
    if _HEADING_SHAPE_RE.search(c):
        return True
    if _SLIDE_MARKER_RE.search(c):
        return True
    if re.search(r"(?i)\b(page|slide)\s*\d", c):
        return True
    words = c.split()
    if len(words) <= 4 and c.isupper():
        return True
    upper_ratio = sum(1 for ch in c if ch.isupper()) / max(len(c), 1)
    if upper_ratio > 0.55 and len(words) <= 5:
        return True
    return False


def is_example_only_concept(concept: str) -> bool:
    low = (concept or "").strip().lower()
    if not low:
        return True
    if low in _EXAMPLE_ONLY_WORDS:
        return True
    if _EXAMPLE_PHRASE_RE.search(low):
        return True
    words = low.split()
    if len(words) == 1 and words[0] in _EXAMPLE_ONLY_WORDS:
        return True
    if re.match(r"(?i)^image\s+\d+$", low):
        return True
    return False


def is_duplicate_label_concept(concept: str) -> bool:
    """OCR/slide labels like 'Direction The direction of this vector'."""
    c = (concept or "").strip()
    if not c:
        return True
    if re.match(r"(?i)^(\w+)\s+the\s+\1\b", c):
        return True
    words = c.lower().split()
    if len(words) >= 3 and words[0] == words[2] and words[1] == "the":
        return True
    if len(words) >= 2 and words[0] == words[-1]:
        return True
    if re.match(r"(?i)^(direction|magnitude|vector|detector|laplacian)\s+the\b", c):
        return True
    if re.match(r"(?i)^(hence|gaps|one|filtered|given)\b", c):
        return True
    if re.search(r"\ban image\s*$", c):
        return True
    if re.search(r"\bone and\b", c):
        return True
    if re.search(r"(?i)operators an image", c):
        return True
    return False


def is_slide_fragment_concept(concept: str) -> bool:
    """Slide/OCR fragments that should never become question stems."""
    c = (concept or "").strip()
    if not c:
        return True
    low = c.lower()
    if re.match(r"(?i)^if\s+(the\s+)?", low):
        return True
    if re.search(r"(?i)whose goal|next can be|geography of the", low):
        return True
    if re.match(r"(?i)^next\b", low):
        return True
    if re.search(r"(?i)\biff\s*$", low):
        return True
    if ")" in c and "(" not in c:
        return True
    if re.search(r"(?i)perlocution|american heritage|concrete architectures", low):
        return True
    if re.search(r"(?i)types of intelligent$|^intelligent$", low):
        return True
    if re.match(r"(?i)^(the\s+)?environment$", low):
        return True
    return False


def clean_teachable_answer(raw: str, concept: str = "") -> str:
    """Normalize a material-backed answer line for MCQ options."""
    a = clean_option_text(raw)
    a = re.sub(r"^[A-Za-z]+[\)]\s*", "", a)
    a = re.sub(r"^The\s+[A-Za-z]+\s+of\s+f\s*\([^)]+\)\s*", "", a, flags=re.I)
    a = re.sub(r"\s+", " ", a).strip()
    if a and not a.endswith((".", "!")):
        a += "."
    return a


def is_broken_definition_answer(answer: str) -> bool:
    a = (answer or "").strip()
    if not a or is_broken_option(a):
        return True
    if re.search(r"…|\bi\.\s*$|\+\s*ve", a):
        return True
    if re.search(r"(?i)\bex\d*\s*:|sort,\s*square|set the pixel value", a):
        return True
    if re.search(r"(?i)process:|moving window|\[ convolution", a):
        return True
    if re.search(r"f\s*\(|\(x,\s*y\)|\\frac|coordinates\s*\(", a):
        return True
    if re.search(r"(?i)edge\s*-\s*based point", a):
        return True
    if is_table_or_slide_junk_option(a):
        return True
    if re.search(r"\d\s*-\s*[A-Za-z]", a):
        return True
    if re.match(r"(?i)^tal\s+steps", a):
        return True
    words = a.split()
    if re.match(r"(?i)^implementing\s+1st derivative", a) and len(words) < 12:
        return True
    if len(words) < MIN_OPTION_WORDS:
        return True
    if words[0].lower() in {"too", "hence", "given", "filtered", "bridged"} and len(words) < 10:
        return True
    if _JUNK_OPTION_CONTENT_RE.search(a):
        return True
    if _ARABIC_SCRIPT_RE.search(a):
        return True
    return False


def is_teachable_concept(concept: str) -> bool:
    c = clean_concept_label(concept)
    if not c or is_weak_concept(c):
        return False
    if is_slide_fragment_concept(c):
        return False
    if is_heading_concept(c):
        return False
    if is_example_only_concept(c):
        return False
    if is_duplicate_label_concept(c):
        return False
    if len(c.split()) == 1 and c.lower() in _GENERIC_WORDS:
        return False
    return True


def stem_template_for_concept(concept: str, index: int = 0) -> str:
    c = clean_concept_label(concept) or concept
    templates = [
        f"Which statement best describes {c}?",
        f"What is the main purpose of {c}?",
        f"Which option correctly explains {c}?",
    ]
    return templates[index % len(templates)]


def extract_teachable_pairs(text: str, limit: int = 25) -> List[Tuple[str, str]]:
    """Definition-backed (concept, answer) pairs — no headings or examples."""
    from app.services.quiz_gen_light import extract_definitions

    ranked: List[Tuple[int, str, str]] = []
    seen: Set[str] = set()
    low = (text or "").lower()

    for term in _PRIORITY_TEACHABLE_TERMS:
        if term not in low or not is_teachable_concept(term):
            continue
        label = term.title() if term != "naive bayes" else "Naive Bayes"
        answer: Optional[str] = None
        pattern = re.compile(
            rf"\b{re.escape(term)}\b\s+"
            r"(?:is|are|refers to|means|used to|helps|defined as|consists of|includes)\s+"
            r"([^.\n]{12,140})\.?",
            re.I,
        )
        hit = pattern.search(text or "")
        if hit:
            answer = clean_option_text(hit.group(1).strip())
        if not answer or is_broken_definition_answer(answer):
            for m in re.finditer(r"[A-Za-z][^.!?]{25,220}[.!?]", text or ""):
                sent = re.sub(r"\s+", " ", m.group(0)).strip()
                if not re.search(
                    rf"(?i)(?:^|\b){re.escape(term)}\b\s+(?:is|are|means|refers to|used to)",
                    sent,
                ):
                    continue
                if re.search(r"f\s*\(|\(x,\s*y\)", sent):
                    continue
                candidate = clean_teachable_answer(sent, label)
                if not is_broken_definition_answer(candidate):
                    answer = candidate
                    break
        if not answer or is_broken_definition_answer(answer):
            continue
        key = normalize_concept_key(term)
        if key in seen:
            continue
        seen.add(key)
        score = len(answer.split()) + 20
        ranked.append((score, label, answer))

    for concept, definition in extract_definitions(text):
        answer = clean_option_text(definition)
        if is_broken_definition_answer(answer):
            continue
        if not is_teachable_concept(concept):
            continue
        key = normalize_concept_key(concept)
        if key in seen:
            continue
        seen.add(key)
        score = len(answer.split()) + min(len(concept.split()) * 3, 12)
        ranked.append((score, concept, answer))

    if len(ranked) < 3:
        for m in _DEFINITION_RE.finditer(text or ""):
            concept = clean_concept_label((m.group(1) or "").strip())
            answer = clean_option_text((m.group(2) or "").strip())
            if is_broken_definition_answer(answer) or not is_teachable_concept(concept):
                continue
            key = normalize_concept_key(concept)
            if key in seen:
                continue
            seen.add(key)
            score = len(answer.split())
            ranked.append((score, concept, answer))

    ranked.sort(key=lambda x: -x[0])
    pairs = [(c, a) for _, c, a in ranked[:limit]]

    if len(pairs) < min(limit, 5):
        pairs = _mine_thin_content_pairs(text, pairs, limit)

    return pairs[:limit]


def _mine_thin_content_pairs(
    text: str,
    existing: List[Tuple[str, str]],
    limit: int,
) -> List[Tuple[str, str]]:
    """Extra pair mining for shorter lecture slides (e.g. intelligent agents)."""
    seen = {normalize_concept_key(c) for c, _ in existing}
    ranked: List[Tuple[int, str, str]] = []
    for concept, answer in existing:
        ranked.append((len(answer.split()), concept, answer))

    for term in (
        "sensors", "actuators", "utility-based agent", "reactive agent",
        "deliberative agent", "learning agent", "goal-based agent",
        "model-based reflex agent", "simple reflex agent", "chatbot",
        "partially observable", "fully observable", "multi-agent system",
    ):
        if term not in (text or "").lower():
            continue
        label = term.title() if "agent" not in term else term.replace("-", "-").title()
        if term == "utility-based agent":
            label = "Utility-Based Agent"
        elif term == "goal-based agent":
            label = "Goal-Based Agent"
        elif term == "model-based reflex agent":
            label = "Model-Based Reflex Agent"
        elif term == "simple reflex agent":
            label = "Simple Reflex Agent"
        elif term == "learning agent":
            label = "Learning Agent"
        elif term == "multi-agent system":
            label = "Multi-Agent System"
        key = normalize_concept_key(term)
        if key in seen or not is_teachable_concept(label):
            continue
        for m in re.finditer(
            rf"\b{re.escape(term)}\b[^.!?]{{0,80}}[.!?]",
            text or "",
            re.I,
        ):
            sent = clean_teachable_answer(m.group(0), label)
            if not re.search(
                rf"(?i)(?:^|\b){re.escape(term)}\b\s+(?:is|are|means|refers to|used to)",
                sent,
            ):
                continue
            if is_broken_definition_answer(sent):
                continue
            seen.add(key)
            ranked.append((len(sent.split()) + 8, label, sent))
            break

    for sent in extract_educational_sentences(text, limit=40):
        m = re.match(
            r"^([A-Za-z][^.!?]{2,45}?)\s+"
            r"(?:is|are|means|refers to|used to|helps|defined as)\s+(.+)$",
            sent,
            re.I,
        )
        if not m:
            continue
        concept = clean_concept_label(m.group(1).strip())
        answer = clean_teachable_answer(m.group(2).strip(), concept)
        if not is_teachable_concept(concept) or is_broken_definition_answer(answer):
            continue
        key = normalize_concept_key(concept)
        if key in seen:
            continue
        seen.add(key)
        ranked.append((len(answer.split()), concept, answer))

    ranked.sort(key=lambda x: -x[0])
    return [(c, a) for _, c, a in ranked[:limit]]


def rival_concept_names(pairs: List[Tuple[str, str]], exclude: str) -> List[str]:
    ex = normalize_concept_key(exclude)
    out: List[str] = []
    for concept, _ in pairs:
        if normalize_concept_key(concept) != ex:
            out.append(concept)
    return out


def option_names_other_concept(option: str, rival_concepts: List[str]) -> bool:
    o = (option or "").lower()
    for name in rival_concepts:
        n = name.lower().strip()
        if len(n) < 4:
            continue
        if re.search(rf"(?i)\b{re.escape(n)}\b", o):
            if _CROSS_CONCEPT_OPTION_RE.match(option or ""):
                return True
            if o.startswith(n):
                return True
    return False


def _unique_distractor_for_slot(slot: int, used: Set[str]) -> str:
    pool = _CONCEPT_GENERIC_DISTRACTORS + _EXTRA_GENERIC_DISTRACTORS + _GENERIC_SAFE_DISTRACTORS
    candidate = pool[slot % len(pool)]
    if candidate.lower() not in used:
        return candidate
    for j in range(1, len(pool)):
        candidate = pool[(slot + j) % len(pool)]
        if candidate.lower() not in used:
            return candidate
    return f"It does not correctly explain the concept in option {slot + 1}."


def pick_same_topic_distractors(
    concept: str,
    correct: str,
    source_text: str,
    rival_concepts: List[str],
    used: Set[str],
    material_sentences: Optional[List[str]] = None,
    n: int = 3,
) -> List[str]:
    """Wrong options — material sentences first, then varied generics (not repeated junk)."""
    correct_key = correct.lower().strip()
    out: List[str] = []

    sentences = material_sentences or extract_educational_sentences(source_text, limit=40)
    for s in sentences:
        if len(out) >= n:
            break
        o = strip_material_title_from_option(s)
        if not o or o.lower() in used or o.lower() == correct_key:
            continue
        if option_needs_replacement(o):
            continue
        if option_names_other_concept(o, rival_concepts):
            continue
        if concept.lower() in o.lower()[:40]:
            continue
        out.append(o)
        used.add(o.lower())

    generic_pool = _CONCEPT_GENERIC_DISTRACTORS + _EXTRA_GENERIC_DISTRACTORS + _GENERIC_SAFE_DISTRACTORS
    for d in generic_pool:
        if len(out) >= n:
            break
        if d.lower() not in used and d.lower() != correct_key:
            out.append(d)
            used.add(d.lower())

    slot = 0
    while len(out) < n and slot < 16:
        d = _unique_distractor_for_slot(slot, used)
        if d.lower() not in used and d.lower() != correct_key:
            out.append(d)
            used.add(d.lower())
        slot += 1
    return out[:n]


def normalize_merged_words(text: str) -> str:
    """Light OCR merge fix — LuminosityGray -> Luminosity Gray; S ensors -> Sensors."""
    s = (text or "").strip()
    if not s:
        return ""
    s = re.sub(r"(?<![A-Za-z])([B-HJ-Z])\s+([a-z]{2,})", r"\1\2", s)
    s = _MERGED_CAMEL_RE.sub(r"\1 \2", s)
    for old, new in (
        ("LuminosityGray", "Luminosity Gray"),
        ("GrayScale", "Gray Scale"),
        ("NonLinear", "Non-Linear"),
        ("InputOutput", "Input Output"),
    ):
        s = re.sub(re.escape(old), new, s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip()


def option_needs_replacement(
    option: str,
    material_title: Optional[str] = None,
) -> bool:
    """True when an option should be swapped (never fails the whole quiz)."""
    o = (option or "").strip()
    if not o or len(o) < 8:
        return True
    if "?" in o:
        return True
    if _ARABIC_SCRIPT_RE.search(o):
        return True
    if _OCR_SPLIT_CAPS_RE.search(o):
        return True
    if _JUNK_OPTION_CONTENT_RE.search(o):
        return True
    if _OPTION_BLACKLIST_RE.search(o):
        return True
    if is_material_title_option(o, material_title):
        return True
    if is_table_or_slide_junk_option(o):
        return True
    if is_broken_option(o):
        return True
    return False


def is_table_or_slide_junk_option(option: str) -> bool:
    """Slide tables, chapter headers, model catalogues, meta-AI lines."""
    o = (option or "").strip()
    if not o:
        return True
    if "|" in o:
        return True
    if _TABLE_ROW_OPTION_RE.search(o):
        return True
    if _BROKEN_OPTION_START_RE.search(o):
        return True
    if _INCOMPLETE_OPTION_END_RE.search(o):
        return True
    if re.search(r"(?i)select the length of the fish", o):
        return True
    if re.search(r"(?i)should not overlap pattern", o):
        return True
    pipe_segments = [p.strip() for p in o.split("|") if p.strip()]
    if len(pipe_segments) >= 2:
        return True
    return False


def rewrite_known_bad_option(option: str) -> str:
    """Rewrite common ugly OCR/meta fragments into clean answer lines."""
    o = (option or "").strip()
    low = o.lower()
    if "model only answers" in low or "what is inside this image" in low:
        return "The model predicts the category of objects present in the image."
    return o


def clean_option_text(option: str) -> str:
    """Normalize an MCQ option — statements only, never questions."""
    o = rewrite_known_bad_option(option)
    o = re.sub(r"[\uf000-\uf8ff\ufffd\u2022\u25aa\"'\u201c\u201d]", " ", o)
    o = re.sub(r"\s+", " ", o).strip()
    if not o:
        return ""
    o = o.replace("?", ".")
    o = normalize_merged_words(o)
    if _ARABIC_SCRIPT_RE.search(o) or _JUNK_OPTION_CONTENT_RE.search(o):
        return ""
    if _OCR_SPLIT_CAPS_RE.search(o):
        o = re.sub(r"(?<![A-Za-z])([B-HJ-Z])\s+([a-z]{2,})", r"\1\2", o)
    o = re.sub(r"^A([a-z])", r"A \1", o)
    o = o.rstrip(",;:")
    if o and o[0].islower():
        o = o[0].upper() + o[1:]
    words = o.split()
    if len(words) > 35:
        o = " ".join(words[:35]).rstrip(",;:")
    if o and not o.endswith((".", "!")):
        o += "."
    if len(o) > 120:
        cut = o[:117].rsplit(" ", 1)[0]
        if len(cut.split()) >= MIN_OPTION_WORDS:
            o = cut.rstrip(".,;:") + "."
        else:
            o = o[:117].rstrip(".,;:") + "."
    if is_table_or_slide_junk_option(o):
        return ""
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
    """Remove lecture/lab/test-import title prefixes; keep answer body only."""
    o = (option or "").strip()
    m = _MATERIAL_TITLE_PREFIX_RE.match(o)
    if m:
        o = o[m.end() :]
    m2 = _IMPORT_DEF_PREFIX_RE.match(o)
    if m2:
        o = o[m2.end() :]
    return clean_option_text(o)


def _generic_safe_distractor(used: Set[str]) -> str:
    return _unique_distractor_for_slot(0, used)


def sanitize_quiz_options(
    options: List[str],
    correct_index: int,
    source_text: str,
    material_title: Optional[str] = None,
    global_used: Optional[Set[str]] = None,
    rival_concepts: Optional[List[str]] = None,
) -> Tuple[List[str], int]:
    """Clean options; replace bad choices without failing the quiz."""
    used: Set[str] = set()
    cleaned: List[str] = []
    correct_idx = max(0, min(int(correct_index or 0), max(0, len(options) - 1)))
    correct_raw = options[correct_idx] if options else ""
    rivals = rival_concepts or []

    for slot, opt in enumerate(options):
        o = strip_material_title_from_option(clean_option_text(opt))
        if option_needs_replacement(o, material_title) or option_names_other_concept(o, rivals):
            o = _pick_replacement_option(source_text, used, material_title, rivals)
        if o.lower() in used:
            o = _unique_distractor_for_slot(slot, used)
        used.add(o.lower())
        cleaned.append(o)

    if not cleaned:
        cleaned = [_pick_replacement_option(source_text, set(), material_title, rivals)]

    correct_clean = strip_material_title_from_option(clean_option_text(correct_raw))
    if option_needs_replacement(correct_clean, material_title) or option_names_other_concept(
        correct_clean, rivals,
    ):
        replacement = _pick_replacement_option(
            source_text, {x.lower() for x in cleaned}, material_title, rivals,
        )
        if correct_idx < len(cleaned):
            cleaned[correct_idx] = replacement
        else:
            cleaned[0] = replacement
            correct_idx = 0
    elif correct_clean.lower() not in {x.lower() for x in cleaned}:
        if correct_idx < len(cleaned):
            cleaned[correct_idx] = correct_clean

    while len(cleaned) < 4:
        extra = _unique_distractor_for_slot(len(cleaned), {x.lower() for x in cleaned} | used)
        cleaned.append(extra)

    seen_opts: Set[str] = set()
    unique: List[str] = []
    for slot, o in enumerate(cleaned[:4]):
        if o.lower() in seen_opts:
            o = _unique_distractor_for_slot(slot, seen_opts | used)
        seen_opts.add(o.lower())
        unique.append(o)

    return unique[:4], correct_idx


def _pick_replacement_option(
    source_text: str,
    used: Set[str],
    material_title: Optional[str] = None,
    rival_concepts: Optional[List[str]] = None,
) -> str:
    rivals = rival_concepts or []
    for s in extract_educational_sentences(source_text, limit=60):
        candidate = strip_material_title_from_option(s)
        if not candidate or candidate.lower() in used:
            continue
        if option_needs_replacement(candidate, material_title):
            continue
        if option_names_other_concept(candidate, rivals):
            continue
        return candidate
    for s in _extract_clean_sentences(source_text, limit=30):
        candidate = strip_material_title_from_option(s)
        if not candidate or candidate.lower() in used:
            continue
        if option_needs_replacement(candidate, material_title):
            continue
        if option_names_other_concept(candidate, rivals):
            continue
        return candidate
    return _unique_distractor_for_slot(0, used)


def is_broken_option(option: str) -> bool:
    """True when an MCQ option is a fragment or unreadable."""
    o = (option or "").strip()
    if "?" in o:
        return True
    if _SLIDE_MARKER_RE.search(o) or re.search(r"(?i)\bslide\b", o):
        return True
    if _EXAMPLE_PHRASE_RE.search(o):
        return True
    if len(o) < 12:
        return True
    if _GENERIC_OPTION_RE.match(o):
        return True
    if _BROKEN_OPTION_END_RE.search(o):
        return True
    if _BROKEN_OPTION_PHRASE_RE.search(o):
        return True
    words = o.split()
    if len(words) < MIN_OPTION_WORDS and not _TECH_TERM_RE.match(o):
        return True
    if len(words) > MAX_OPTION_WORDS:
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
    if re.search(r"(?i)depends on non|non\s*-?\s*linear filters|\(e\.\s*$", o):
        return True
    if re.search(r"(?i)process:|moving window|\[ convolution|response=", o):
        return True
    if is_material_title_option(o):
        return True
    if is_table_or_slide_junk_option(o):
        return True
    if re.search(r"\d\.\s*$", o) and len(words) <= 6:
        return True
    if _ARABIC_SCRIPT_RE.search(o):
        return True
    if _OCR_SPLIT_CAPS_RE.search(o):
        return True
    if _JUNK_OPTION_CONTENT_RE.search(o):
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
    concept = extract_concept_from_stem(q)
    if not concept or not is_teachable_concept(concept):
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
        r"chapter\s+\d|pattern classification,\s*chapter|\|"
        r"|model only answers|u-net|seg\s*net|res\s*net|mobile\s*net"
    )
    for m in re.finditer(r"[A-Za-z][^.!?]{15,280}[.!?]", text or ""):
        raw = re.sub(r"\s+", " ", m.group(0)).strip()
        if is_table_or_slide_junk_option(raw):
            continue
        words = raw.split()
        if len(words) < 8 or len(words) > 35:
            continue
        if noise.search(raw) or _EXAMPLE_PHRASE_RE.search(raw):
            continue
        if re.search(r"(?i)\bex\d*\s*:|sort,\s*square|set the pixel value", raw):
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
        if low not in _ALLOWED_COMPOUND_CONCEPTS:
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
    if is_slide_fragment_concept(c):
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
        for concept, _ in extract_teachable_pairs(source_text, 25):
            if is_teachable_concept(concept):
                q = stem_template_for_concept(concept, 0)
                break
        else:
            topic = clean_concept_label(clean_title_token(material_title or ""))
            if topic and is_teachable_concept(topic):
                q = stem_template_for_concept(topic, 0)
    concept_in_stem = extract_concept_from_stem(q)
    if not is_teachable_concept(concept_in_stem):
        for concept, _ in extract_teachable_pairs(source_text, 25):
            q = stem_template_for_concept(concept, 0)
            break
    return q or "Which statement best describes this topic?"


def mcq_options_final_sane(item: Dict[str, Any], material_title: Optional[str] = None) -> bool:
    opts = list(item.get("options") or [])
    if len(opts) != 4 or len({o.lower() for o in opts}) != 4:
        return False
    idx = int(item.get("correctIndex") or 0)
    if not (0 <= idx < 4):
        return False
    for o in opts:
        if "?" in o or option_needs_replacement(o, material_title):
            return False
        if is_table_or_slide_junk_option(o):
            return False
    stem = str(item.get("question") or "")
    if is_grammatically_broken_question(stem):
        return False
    concept = extract_concept_from_stem(stem)
    if not is_teachable_concept(concept):
        return False
    return True


def final_repair_mcq_options(
    item: Dict[str, Any],
    source_text: str,
    material_title: Optional[str] = None,
    global_used: Optional[Set[str]] = None,
    teachable_pairs: Optional[List[Tuple[str, str]]] = None,
) -> Dict[str, Any]:
    pairs = teachable_pairs or extract_teachable_pairs(source_text, 30)
    concept = extract_concept_from_stem(str(item.get("question") or ""))
    rivals = rival_concept_names(pairs, concept) if concept else [
        c for c, _ in pairs
    ]
    for _ in range(2):
        opts, idx = sanitize_quiz_options(
            list(item.get("options") or []),
            int(item.get("correctIndex") or 0),
            source_text,
            material_title,
            global_used=global_used,
            rival_concepts=rivals,
        )
        item["options"] = [o.replace("?", ".") for o in opts[:4]]
        item["correctIndex"] = max(0, min(idx, len(item["options"]) - 1))
        seen: Set[str] = set()
        for slot, opt in enumerate(item["options"]):
            if opt.lower() in seen:
                item["options"][slot] = _unique_distractor_for_slot(
                    slot, seen | (global_used or set()),
                )
            seen.add(item["options"][slot].lower())
        if mcq_options_final_sane(item, material_title):
            break
    return item


def final_repair_mcq(
    item: Dict[str, Any],
    source_text: str,
    material_title: Optional[str] = None,
    global_used: Optional[Set[str]] = None,
    teachable_pairs: Optional[List[Tuple[str, str]]] = None,
    template_idx: int = 0,
    used_concepts: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    pairs = teachable_pairs or extract_teachable_pairs(source_text, 30)
    item = final_repair_mcq_options(item, source_text, material_title, global_used, pairs)
    if mcq_options_final_sane(item, material_title):
        return item
    skip = used_concepts or set()
    for concept, answer in pairs:
        key = normalize_concept_key(concept)
        if key in skip:
            continue
        built = build_mcq_from_teachable_pair(
            concept, answer, source_text, pairs, template_idx, material_title,
        )
        if not built:
            continue
        replacement = final_repair_mcq_options(
            built, source_text, material_title, global_used, pairs,
        )
        if mcq_options_final_sane(replacement, material_title):
            return replacement
    return final_repair_mcq_options(item, source_text, material_title, global_used, pairs)


def build_mcq_from_teachable_pair(
    concept: str,
    answer: str,
    source_text: str,
    teachable_pairs: List[Tuple[str, str]],
    template_idx: int,
    material_title: Optional[str] = None,
    global_used: Optional[Set[str]] = None,
) -> Optional[Dict[str, Any]]:
    if not is_teachable_concept(concept) or is_broken_definition_answer(answer):
        return None
    rivals = rival_concept_names(teachable_pairs, concept)
    correct = clean_teachable_answer(answer, concept)
    if not correct or is_broken_option(correct):
        return None
    used: Set[str] = {correct.lower()}
    if global_used:
        used.update(global_used)
    distractors = pick_same_topic_distractors(
        concept, correct, source_text, rivals, used, n=3,
    )
    if len(distractors) < 3:
        return None
    return {
        "question": stem_template_for_concept(concept, template_idx),
        "options": [correct] + distractors[:3],
        "correctIndex": 0,
    }


def _shuffle_mcq_options(options: List[str], correct_index: int, salt: str) -> Tuple[List[str], int]:
    correct = options[correct_index]
    seed = int(hashlib.md5(salt.encode()).hexdigest(), 16)
    ordered = list(options)
    for i in range(len(ordered) - 1, 0, -1):
        j = seed % (i + 1)
        seed //= (i + 1)
        ordered[i], ordered[j] = ordered[j], ordered[i]
    return ordered, ordered.index(correct)


def light_cleanup_mcq(
    item: Dict[str, Any],
    source_text: str,
    material_title: Optional[str] = None,
    global_used: Optional[Set[str]] = None,
    teachable_pairs: Optional[List[Tuple[str, str]]] = None,
) -> Dict[str, Any]:
    """Clean one MCQ in place — never drop it."""
    pairs = teachable_pairs or extract_teachable_pairs(source_text, 30)
    item["question"] = light_cleanup_question(
        str(item.get("question") or ""), source_text, material_title,
    )
    concept = extract_concept_from_stem(item["question"])
    rivals = rival_concept_names(pairs, concept) if concept else [c for c, _ in pairs]
    raw_opts = list(item.get("options") or [])
    if not raw_opts:
        raw_opts = [_pick_replacement_option(source_text, set(), material_title, rivals)]
    opts, idx = sanitize_quiz_options(
        raw_opts,
        int(item.get("correctIndex") or 0),
        source_text,
        material_title,
        global_used=global_used,
        rival_concepts=rivals,
    )
    item["options"] = [o.replace("?", ".") for o in opts[:4]]
    item["correctIndex"] = max(0, min(idx, len(item["options"]) - 1))
    item = final_repair_mcq_options(item, source_text, material_title, global_used, pairs)
    shuffled, idx = _shuffle_mcq_options(
        item["options"], int(item.get("correctIndex") or 0), str(item.get("question") or ""),
    )
    item["options"] = shuffled
    item["correctIndex"] = idx
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


def _build_sane_mcqs_from_pairs(
    teachable_pairs: List[Tuple[str, str]],
    source_text: str,
    material_title: Optional[str],
    target: int,
    global_used: Optional[Set[str]] = None,
    used_concepts: Optional[Set[str]] = None,
    start_template_idx: int = 0,
) -> List[Dict[str, Any]]:
    """Build MCQs only from teachable pairs that pass final sanity gates."""
    pool: List[Dict[str, Any]] = []
    used = used_concepts or set()
    gused = global_used or set()
    for i, (concept, answer) in enumerate(teachable_pairs):
        if len(pool) >= target:
            break
        key = normalize_concept_key(concept)
        if key in used:
            continue
        built = build_mcq_from_teachable_pair(
            concept, answer, source_text, teachable_pairs,
            start_template_idx + len(pool), material_title, gused,
        )
        if not built:
            continue
        item = light_cleanup_mcq(
            built, source_text, material_title, gused, teachable_pairs,
        )
        item = final_repair_mcq(
            item, source_text, material_title, gused, teachable_pairs,
            template_idx=start_template_idx + len(pool), used_concepts=used,
        )
        if not mcq_options_final_sane(item, material_title):
            continue
        pool.append(item)
        used.add(key)
    return pool


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

    valid_primary = len(_accept_drafts(questions))
    teachable_pairs = extract_teachable_pairs(validate_text, 50)
    global_used: Set[str] = set()
    used_concepts: Set[str] = set()
    fallback_added = 0

    pool = _build_sane_mcqs_from_pairs(
        teachable_pairs, validate_text, material_title, target,
        global_used, used_concepts,
    )

    from app.services.quiz_gen_fallback import generate_deterministic_fallback

    if (
        len(pool) < min_target
        and (deadline is None or time.monotonic() < deadline - 0.5)
    ):
        fb_pairs = extract_teachable_pairs(fb_source, 50)
        if len(fb_pairs) > len(teachable_pairs):
            teachable_pairs = fb_pairs
        more = _build_sane_mcqs_from_pairs(
            teachable_pairs, validate_text, material_title,
            min_target - len(pool), global_used, used_concepts,
            start_template_idx=len(pool),
        )
        if more:
            pool = deduplicate_questions(pool + more, validate_text, material_title)
            fallback_added += len(more)

    fill_attempts = 0
    while (
        len(pool) < min_target
        and fill_attempts < MAX_FALLBACK_FILL
        and (deadline is None or time.monotonic() < deadline - 0.3)
    ):
        fill_attempts += 1
        need = min(min_target - len(pool) + 2, 6)
        fb = generate_deterministic_fallback(fb_source, material_title, need)
        for draft in _accept_drafts(fb):
            if len(pool) >= min_target:
                break
            item = light_cleanup_mcq(
                draft, validate_text, material_title, global_used, teachable_pairs,
            )
            item = final_repair_mcq(
                item, validate_text, material_title, global_used,
                teachable_pairs, template_idx=len(pool), used_concepts=used_concepts,
            )
            if not mcq_options_final_sane(item, material_title):
                continue
            merged = deduplicate_questions(pool + [item], validate_text, material_title)
            if len(merged) > len(pool):
                pool = merged
                concept = extract_concept_from_stem(str(item.get("question") or ""))
                if concept:
                    used_concepts.add(normalize_concept_key(concept))
                fallback_added += 1

    if len(pool) < min_target and content_len > RICH_CONTENT_CHARS:
        for item in emergency_quiz_fill(validate_text, material_title, min_target):
            if len(pool) >= min_target:
                break
            item = light_cleanup_mcq(
                item, validate_text, material_title, global_used, teachable_pairs,
            )
            item = final_repair_mcq(
                item, validate_text, material_title, global_used,
                teachable_pairs, template_idx=len(pool), used_concepts=used_concepts,
            )
            if not mcq_options_final_sane(item, material_title):
                continue
            merged = deduplicate_questions(pool + [item], validate_text, material_title)
            if len(merged) > len(pool):
                pool = merged
                fallback_added += 1

    pool = [
        item for item in pool[:target]
        if mcq_options_final_sane(item, material_title)
    ]

    while len(pool) < min_target and teachable_pairs:
        if deadline is not None and time.monotonic() >= deadline - 0.2:
            break
        more = _build_sane_mcqs_from_pairs(
            teachable_pairs, validate_text, material_title,
            min_target - len(pool), global_used, used_concepts,
            start_template_idx=len(pool),
        )
        if not more:
            teachable_pairs = teachable_pairs[1:]
            continue
        pool = deduplicate_questions(pool + more, validate_text, material_title)
        fallback_added += len(more)
        if len(pool) >= min_target:
            break

    pool = [
        item for item in pool[:target]
        if mcq_options_final_sane(item, material_title)
    ]

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
    """Definition-backed concepts only — no slide headings."""
    concepts: List[str] = []
    seen: Set[str] = set()
    for concept, _ in extract_teachable_pairs(text, limit):
        key = concept.lower()
        if key not in seen:
            seen.add(key)
            concepts.append(concept)
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

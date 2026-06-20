"""
Validate, deduplicate, repair, and finalize MCQ quiz output.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

QUIZ_GENERATION_GUIDANCE = (
    "You are creating a university-level MCQ quiz from one selected course material only.\n"
    "Return exactly 5 high-quality MCQs unless the content is insufficient.\n"
    "Every question must mention a specific concept from the material.\n"
    "Do not ask vague questions.\n"
    "Do not use the file name as a concept.\n"
    "Do not copy broken OCR fragments.\n"
    "Every answer option must be complete, readable, and grammatically correct.\n"
    "The correct answer must be directly supported by the material.\n"
    "Distractors must be plausible but wrong.\n"
    "Do not repeat concepts.\n"
    "Return JSON only."
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
    r"reasons for doing this include refers to|^pattern it\b|sent to a feature|"
    r"make decisions about patterns"
)
_VAGUE_CONCEPT_RE = re.compile(
    r"(?i)^(the|a|an)\s+(features?|information|output|input|value|result|data|length|classifier)$"
)
_SHOUTY_STEM_RE = re.compile(r"\b[A-Z]{3,}(?:\s+[A-Z]{3,}){2,}")
_BAD_STEM_RE = re.compile(
    r"(?i)^what\s+is\s+(change|make|select|number of|task of)\b|"
    r"^what\s+is\s+information from\b"
)
_FILENAME_CONCEPT_RE = re.compile(
    r"(?i)\.(pdf|pptx?|ppsx)|_|lecture\s*\d+|lab\s*\d+|test\s+notes|algorithm\s+steps|"
    r"swe\d+|csc\d+|^\d{2}\s+lecture"
)
_VAGUE_TITLE_CONCEPT_RE = re.compile(
    r"(?i)^what\s+is\s+(summary|algorithm\s+steps(?:\s+for\s+search)?|test\s+notes)\s*\??$"
)
_VAGUE_PURPOSE_RE = re.compile(
    r"(?i)^what\s+is\s+(?:the\s+)?purpose\s*\??\s*$"
)
_GENERIC_OPTION_RE = re.compile(
    r"^(none of the above|all of the above|not applicable|n/?a|true|false|yes|no|other)\s*$",
    re.I,
)
_CONCEPT_FROM_STEM_RE = re.compile(
    r"(?i)(?:best describes|purpose of|role of|main idea of|main goal of|definition of|"
    r"correctly explains|difference between)\s+(.+?)\??\s*$"
)
_GENERIC_WORDS = frozenset(
    {
        "definition", "purpose", "advantage", "advantages", "disadvantage",
        "disadvantages", "type", "types", "role", "function", "difference",
        "used", "meaning", "genghis", "summary", "algorithm", "steps",
        "notes", "test", "search", "length", "classifier", "features",
        "feature", "material", "topic", "concept",
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
_OCR_NOISE_RE = re.compile(
    r"(?i)(?:\[Page\s*\d|Page\s*\d+\])|postprocessing:|image algebra|"
    r"visual example|course outline|\d{1,2}/\d{1,2}/\d{4}|learning and adaptation"
)
_GARBAGE_CONCEPT_RE = re.compile(
    r"(?i)^(pattern it|main applications?|njnj|work only if|reasons for doing this include|"
    r"algorithm steps for search|sobel operators an image|basics of image segmentation segmentation|"
    r"highlight transitions in intensities|warping means that points|ai tool whose goal|"
    r"agent|category to which|given object belongs|^what\??$)"
)
_EMAIL_RE = re.compile(r"@|\.edu\b|miuegypt", re.I)
_REPEAT_CHAR_RE = re.compile(r"(.)\1{4,}")


def clean_option_text(option: str) -> str:
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
    if len(words) > 35:
        return True
    if o.endswith("...") and len(o) < 40:
        return True
    if re.search(r"(?i)\brefers to\s*$", o):
        return True
    if _OCR_NOISE_RE.search(o):
        return True
    if _EMAIL_RE.search(o):
        return True
    if re.search(r"[\uf000-\uf8ff\ufffd]", o):
        return True
    if re.search(r"(?i)^(passed|referred|called)\s+to\b", o):
        return True
    if _REPEAT_CHAR_RE.search(o):
        return True
    if re.search(r"\d\.\s*$", o) and len(words) <= 6:
        return True
    return False


def is_grammatically_broken_question(question: str) -> bool:
    q = (question or "").strip()
    if _EMAIL_RE.search(q):
        return True
    if re.search(r"(?i)associated with.*@", q):
        return True
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
    if re.match(r"^which of the following is true\s*\??\s*$", q, re.I):
        return True
    return False


def uses_filename_as_concept(question: str, material_title: Optional[str] = None) -> bool:
    q = (question or "").strip()
    if _VAGUE_TITLE_CONCEPT_RE.match(q):
        return True
    m = re.match(r"^what\s+(?:is|are)\s+(?:the\s+)?(.+?)\s*\??\s*$", q, re.I)
    if m:
        concept = m.group(1).strip()
        if _FILENAME_CONCEPT_RE.search(concept):
            return True
        if material_title and concept.lower() == clean_title_token(material_title).lower():
            return True
        if len(concept.split()) <= 2 and concept.lower() in _GENERIC_WORDS:
            return True
    cm = _CONCEPT_FROM_STEM_RE.search(q)
    if cm:
        concept = cm.group(1).strip()
        if _FILENAME_CONCEPT_RE.search(concept):
            return True
        if re.search(r"(?i)in this material\s*$", concept):
            return True
        if _VAGUE_CONCEPT_RE.match(concept):
            return True
    return False


def clean_title_token(title: str) -> str:
    t = re.sub(r"\b[A-Z]{2,6}\s*\d{3,4}\b", "", title or "")
    t = re.sub(r"\b(File|Moodle|Copy|Lab|Lecture)\b", "", t, flags=re.I)
    t = re.sub(r"\.(pdf|pptx?|ppsx)\b", "", t, flags=re.I)
    return t.strip()


def option_contains_weird_terms(option: str, source_text: str) -> bool:
    src_lower = (source_text or "").lower()
    for token in re.findall(r"[A-Za-z]{7,}", option or ""):
        low = token.lower()
        if low in _GENERIC_WORDS:
            continue
        if low not in src_lower and token not in source_text:
            return True
    return False


def normalize_concept_key(concept: str) -> str:
    c = re.sub(r"^the\s+", "", (concept or "").lower().strip())
    return re.sub(r"\s+", " ", c)


def extract_concept_from_stem(question: str) -> str:
    q = (question or "").strip()
    m = _CONCEPT_FROM_STEM_RE.search(q)
    if m:
        return normalize_concept_key(m.group(1).strip())
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
    s = re.sub(r"[^\w\s]", "", s)
    return s


def _question_signature(q: Dict[str, Any]) -> Tuple[str, str, str]:
    stem = normalize_stem(str(q.get("question") or ""))
    concept = extract_concept_from_stem(str(q.get("question") or ""))
    opts = q.get("options") or []
    idx = int(q.get("correctIndex") or 0)
    correct = ""
    if opts and 0 <= idx < len(opts):
        correct = normalize_stem(str(opts[idx]))
    return concept, stem[:70], correct[:70]


def _score_question(q: Dict[str, Any], source_text: str, material_title: Optional[str]) -> int:
    stem = str(q.get("question") or "")
    opts = [clean_option_text(o) for o in q.get("options") or []]
    score = 0
    keywords = _extract_keywords(source_text, material_title)
    if is_question_valid(stem, opts, source_text, material_title, keywords):
        score += 1000
    score += len(stem.split()) * 5
    score += sum(len(o.split()) for o in opts)
    if re.search(r"(?i)which statement best describes", stem):
        score += 50
    if re.search(r"(?i)what is the (purpose|role|main goal)", stem):
        score += 40
    if re.search(r"(?i)which of the following", stem):
        score -= 200
    if re.search(r"\bCLASSIFICATION\b", stem):
        score -= 30
    return score


def deduplicate_questions(
    questions: List[Dict[str, Any]],
    source_text: str,
    material_title: Optional[str],
) -> List[Dict[str, Any]]:
    """Remove duplicate and near-duplicate MCQs; keep the higher-quality one."""
    best_by_concept: Dict[str, Dict[str, Any]] = {}
    best_score: Dict[str, int] = {}
    seen_stems: Set[str] = set()
    seen_correct: Set[str] = set()
    out: List[Dict[str, Any]] = []

    for q in questions:
        concept, stem_key, correct_key = _question_signature(q)
        if not concept or len(concept) < 3:
            concept = stem_key[:40]

        if stem_key in seen_stems:
            continue
        if correct_key and correct_key in seen_correct and concept in best_by_concept:
            continue

        score = _score_question(q, source_text, material_title)
        prev = best_by_concept.get(concept)
        if prev is not None:
            prev_score = best_score.get(concept, 0)
            if score <= prev_score:
                continue
            out = [x for x in out if extract_concept_from_stem(str(x.get("question") or "")) != concept]

        best_by_concept[concept] = q
        best_score[concept] = score
        seen_stems.add(stem_key)
        if correct_key:
            seen_correct.add(correct_key)
        out.append(q)

    return out


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


def is_vague_question(question: str, material_title: Optional[str] = None) -> bool:
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
    concept_m = _CONCEPT_FROM_STEM_RE.search(q)
    if concept_m:
        concept = concept_m.group(1).strip()
        if _VAGUE_CONCEPT_RE.match(concept):
            return True
        if _GARBAGE_CONCEPT_RE.match(concept):
            return True
        if _EMAIL_RE.search(concept):
            return True
        if re.match(r"^[A-Z]{3,6}$", concept) and concept.lower() not in {
            "svm", "knn", "dna", "ocr", "gpu",
        }:
            return True
        if re.search(r"which the|category\s+to which|lies\??\s*$", concept, re.I):
            return True
        if concept.lower().startswith("change pixel"):
            return True
        if len(concept.split()) == 1 and concept.lower() in _GENERIC_WORDS:
            return True
    if re.match(r"^which of the following", q, re.I):
        if not concept_m or _GARBAGE_CONCEPT_RE.search(concept_m.group(1)):
            return True
    return False


def _extract_keywords(source_text: str, material_title: Optional[str]) -> List[str]:
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
    q_lower = (question or "").lower()
    if len(q_lower.split()) >= 8:
        return True
    for kw in keywords[:30]:
        token = kw.strip().lower()
        if len(token) >= 4 and token in q_lower:
            return True
    if material_title:
        for token in re.findall(r"[a-z]{4,}", material_title.lower()):
            if token not in _GENERIC_WORDS and token in q_lower:
                return True
    return False


def _extract_concepts(text: str, limit: int = 50) -> List[str]:
    concepts: List[str] = []
    seen: Set[str] = set()
    priority = [
        "pattern recognition", "supervised learning", "unsupervised learning",
        "classification", "regression", "feature extraction", "training set",
        "test set", "decision theory", "feature vector", "edge detection",
        "image segmentation", "image enhancement", "naive bayes",
        "intelligent agent", "multi-agent system", "riverpod",
    ]
    low = (text or "").lower()
    for term in priority:
        if term in low and term not in seen:
            seen.add(term)
            concepts.append(term)
    for pattern in (_CONCEPT_FROM_TEXT_RE, _HEADING_RE):
        for m in pattern.finditer(text or ""):
            term = (m.group(1) or "").strip()
            if len(term) < 3 or len(term) > 60:
                continue
            key = term.lower()
            if key in seen or key in _GENERIC_WORDS or _FILENAME_CONCEPT_RE.search(term):
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


def extract_educational_sentences(text: str, limit: int = 40) -> List[str]:
    """Clean sentences from selected material only (8–35 words, no OCR noise)."""
    out: List[str] = []
    seen: Set[str] = set()
    for m in re.finditer(r"[A-Za-z][^.!?]{15,280}[.!?]", text or ""):
        raw = re.sub(r"\s+", " ", m.group(0)).strip()
        words = raw.split()
        if len(words) < 8 or len(words) > 35:
            continue
        s = clean_option_text(raw)
        if is_broken_option(s):
            continue
        if _OCR_NOISE_RE.search(s):
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= limit:
            break
    return out


def _options_valid(options: List[str]) -> bool:
    if len(options) != 4:
        return False
    return all(not is_broken_option(o) for o in options)


def _repair_options(
    options: List[str],
    correct_idx: int,
    sentence_pool: List[str],
) -> Optional[List[str]]:
    if len(options) < 4:
        return None
    cleaned = [clean_option_text(o) for o in options[:4]]
    idx = min(correct_idx, 3)
    correct = cleaned[idx]
    repaired: List[str] = []
    used: Set[str] = {correct.lower()}
    repaired.append(correct)

    for o in cleaned:
        if o.lower() not in used and not is_broken_option(o):
            repaired.append(o)
            used.add(o.lower())
        if len(repaired) >= 4:
            break

    for s in sentence_pool:
        if len(repaired) >= 4:
            break
        if s.lower() not in used and not is_broken_option(s):
            repaired.append(s)
            used.add(s.lower())

    if len(repaired) < 4:
        return None
    return repaired[:4]


def _build_concept_question(
    concept: str,
    text: str,
    used: Set[str],
    sentence_pool: List[str],
) -> Optional[Dict[str, Any]]:
    c = concept.strip()
    if not c or c.lower() in used or c.lower() in _GENERIC_WORDS:
        return None
    if c.lower() in {"what", "which", "how", "why", "when"}:
        return None
    if c.lower() in {"what", "which", "how", "why", "when"}:
        return None
    if re.search(r"\bit\b", c, re.I) and len(c.split()) <= 3:
        return None
    if _SHOUTY_STEM_RE.search(c) or _FILENAME_CONCEPT_RE.search(c):
        return None

    answer = None
    pattern = re.compile(
        rf"\b{re.escape(c)}\b\s+"
        r"(?:is|are|refers to|means|used to|helps|defined as|consists of|includes)\s+"
        r"([^.\n]{10,120})",
        re.I,
    )
    hit = pattern.search(text)
    if hit:
        answer = clean_option_text(hit.group(1).strip())
    if not answer or is_broken_option(answer):
        for s in sentence_pool:
            if c.lower() in s.lower():
                answer = s
                break
    if not answer or is_broken_option(answer):
        return None

    distractors: List[str] = []
    for s in sentence_pool:
        if s.lower() == answer.lower():
            continue
        if c.lower() in s.lower()[:25]:
            continue
        distractors.append(s)
        if len(distractors) >= 8:
            break

    stems = [
        f"Which statement best describes {c}?",
        f"What is the purpose of {c}?",
        f"What is the role of {c}?",
    ]
    question = next(
        (
            s
            for s in stems
            if not is_vague_question(s) and not uses_filename_as_concept(s)
        ),
        None,
    )
    if not question:
        return None

    options = _repair_options([answer] + distractors[:3], 0, sentence_pool)
    if not options:
        return None

    return {"question": question, "options": options, "correctIndex": 0}


def _fill_valid_questions_from_concepts(
    source_text: str,
    material_title: Optional[str],
    needed: int,
    used: Set[str],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    keywords = _extract_keywords(source_text, material_title)
    pool = extract_educational_sentences(source_text)
    for concept in _extract_concepts(source_text, 50):
        if concept.lower() in used:
            continue
        built = _build_concept_question(concept, source_text, used, pool)
        if not built:
            continue
        if not is_question_valid(
            built["question"], built["options"], source_text, material_title, keywords,
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
    pool = extract_educational_sentences(source_text)
    out: List[Dict[str, Any]] = []
    for q in questions:
        stem = str(q.get("question") or "").strip()
        idx = int(q.get("correctIndex") or 0)
        raw_opts = q.get("options") or []
        repaired = _repair_options(raw_opts, idx, pool)
        if not repaired:
            continue
        correct_idx = 0
        if 0 <= idx < len(raw_opts):
            orig_correct = clean_option_text(raw_opts[idx]).lower()
            for i, o in enumerate(repaired):
                if o.lower() == orig_correct:
                    correct_idx = i
                    break
        if not is_question_valid(stem, repaired, source_text, material_title, keywords):
            continue
        out.append(
            {
                "question": stem,
                "options": repaired,
                "correctIndex": correct_idx,
            }
        )
    return out


def validate_and_improve_questions(
    questions: List[Dict[str, Any]],
    source_text: str,
    material_title: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if not questions:
        return _fill_valid_questions_from_concepts(source_text, material_title, 5, set())

    keywords = _extract_keywords(source_text, material_title)
    pool = extract_educational_sentences(source_text)
    concepts = _extract_concepts(source_text)
    improved: List[Dict[str, Any]] = []
    used_concepts: Set[str] = set()

    for i, q in enumerate(questions):
        question = str(q.get("question") or "").strip()
        options = list(q.get("options") or [])
        correct_idx = int(q.get("correctIndex") or 0)

        repaired_opts = _repair_options(options, correct_idx, pool)
        if not repaired_opts:
            concept = concepts[i % len(concepts)] if concepts else None
            if concept:
                rebuilt = _build_concept_question(concept, source_text, used_concepts, pool)
                if rebuilt and is_question_valid(
                    rebuilt["question"], rebuilt["options"], source_text, material_title, keywords,
                ):
                    used_concepts.add(concept.lower())
                    improved.append(rebuilt)
            continue

        new_idx = correct_idx
        if repaired_opts:
            orig = clean_option_text(options[correct_idx] if correct_idx < len(options) else "")
            for j, o in enumerate(repaired_opts):
                if o.lower() == orig.lower():
                    new_idx = j
                    break

        if is_question_valid(question, repaired_opts, source_text, material_title, keywords):
            improved.append(
                {
                    "question": question,
                    "options": repaired_opts,
                    "correctIndex": new_idx,
                }
            )

    return _post_filter_acceptable(improved, source_text, material_title)


def _fill_to_target(
    pool: List[Dict[str, Any]],
    source_text: str,
    material_title: Optional[str],
    target: int,
) -> List[Dict[str, Any]]:
    used: Set[str] = set()
    for q in pool:
        used.add(extract_concept_from_stem(str(q.get("question") or "")))

    while len(pool) < target:
        before_len = len(pool)
        needed = target - len(pool)
        extra = _fill_valid_questions_from_concepts(
            source_text, material_title, needed + 2, used,
        )
        if not extra:
            from app.services.quiz_gen_fallback import generate_deterministic_fallback

            fb = generate_deterministic_fallback(
                source_text, material_title, needed + 2,
            )
            extra = _post_filter_acceptable(fb, source_text, material_title)
        if not extra:
            break
        for q in extra:
            concept = extract_concept_from_stem(str(q.get("question") or ""))
            if concept in used:
                continue
            pool.append(q)
            used.add(concept)
            if len(pool) >= target:
                break
        if len(pool) == before_len:
            break

    return pool


def log_quiz_generation_stats(
    material_title: Optional[str],
    content_length: int,
    ai_generated: int,
    valid_after_validation: int,
    after_dedupe: int,
    fallback_added: int,
    final_count: int,
    rejected_summary: Dict[str, int],
) -> None:
    logger.info(
        "Quiz finalize title=%s content_len=%d ai_generated=%d valid=%d deduped=%d "
        "fallback_added=%d final=%d rejected=%s",
        (material_title or "")[:80],
        content_length,
        ai_generated,
        valid_after_validation,
        after_dedupe,
        fallback_added,
        final_count,
        rejected_summary,
    )


def finalize_quiz_questions(
    questions: List[Dict[str, Any]],
    source_text: str,
    material_title: Optional[str] = None,
    target: int = 5,
) -> List[Dict[str, Any]]:
    """Validate, dedupe, repair, expand to target, and return demo-quality MCQs."""
    content_len = len((source_text or "").strip())
    min_target = target if content_len > 1000 else min(3, target)
    ai_count = len(questions)

    pool = validate_and_improve_questions(questions, source_text, material_title)
    valid_count = len(pool)

    pool = deduplicate_questions(pool, source_text, material_title)
    deduped_count = len(pool)

    before_fill = len(pool)
    pool = _fill_to_target(pool, source_text, material_title, min_target)
    fallback_added = max(0, len(pool) - before_fill)

    pool = deduplicate_questions(pool, source_text, material_title)
    pool = _post_filter_acceptable(pool, source_text, material_title)

    if len(pool) < min_target and content_len > 1000:
        for attempt in range(3):
            if len(pool) >= min_target:
                break
            from app.services.quiz_gen_fallback import generate_deterministic_fallback

            fb = generate_deterministic_fallback(
                source_text, material_title, min_target + attempt + 4,
            )
            fb = _post_filter_acceptable(fb, source_text, material_title)
            pool = deduplicate_questions(pool + fb, source_text, material_title)
            pool = _post_filter_acceptable(pool, source_text, material_title)
            pool = _fill_to_target(pool, source_text, material_title, min_target)
            fallback_added += len(pool) - deduped_count

    for j, item in enumerate(pool[:target]):
        item["id"] = f"q{j + 1}"

    final = pool[:target]
    log_quiz_generation_stats(
        material_title,
        content_len,
        ai_count,
        valid_count,
        deduped_count,
        fallback_added,
        len(final),
        {"short_pool": max(0, min_target - len(final))},
    )
    return final


def repair_and_select_questions(
    questions: List[Dict[str, Any]],
    source_text: str,
    material_title: Optional[str] = None,
    target: int = 5,
) -> List[Dict[str, Any]]:
    return finalize_quiz_questions(questions, source_text, material_title, target=target)

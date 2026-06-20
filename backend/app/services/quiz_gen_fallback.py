"""
Fast deterministic MCQ fallback — template-based, selected material only.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from app.services.quiz_question_quality import (
    clean_concept_label,
    clean_option_text,
    deduplicate_questions,
    extract_concept_from_stem,
    extract_educational_sentences,
    is_broken_option,
    is_question_valid,
    is_vague_question,
    is_weak_concept,
    normalize_concept_key,
    uses_filename_as_concept,
    _extract_keywords,
    _SHOUTY_STEM_RE,
)

_HEADING_RE = re.compile(
    r"(?:^|\n)\s*([A-Z][A-Za-z0-9][\w\s/&\-]{3,55})\s*$",
    re.MULTILINE,
)
_DEF_RE = re.compile(
    r"\b([A-Za-z][A-Za-z0-9 /&\-]{3,50})\s+"
    r"(?:is|are|refers to|means|used to|helps|defined as|consists of|includes)\s+"
    r"([^.\n]{12,140})\.?",
    re.I,
)
_SKIP_HEADING = re.compile(
    r"(?i)^(summary|introduction|contents|outline|references|agenda|objectives)$"
)

_PRIORITY_TERMS = [
    "pattern recognition", "supervised learning", "unsupervised learning",
    "classification", "regression", "feature extraction", "training set",
    "test set", "decision theory", "feature vector", "edge detection",
    "image segmentation", "image enhancement", "naive bayes", "bayes theorem",
    "intelligent agent", "multi-agent system", "swarm intelligence",
    "riverpod", "flutter", "state management", "prior probability",
    "posterior probability", "likelihood", "bayesian classification",
    "conditional independence", "maximum likelihood",
]


def _topic_label(material_title: Optional[str], text: Optional[str] = None) -> str:
    low = (text or "").lower()
    for term in _PRIORITY_TERMS:
        if term in low:
            return term.title() if term != "naive bayes" else "Naive Bayes"
    if material_title:
        t = re.sub(r"\b[A-Z]{2,6}\s*\d{3,4}\b", "", material_title)
        t = re.sub(r"\b(File|Moodle|Copy|Lecture)\b", "", t, flags=re.I).strip()
        t = re.sub(r"^\d{1,2}\s+", "", t)
        t = re.sub(r"(?i)lecture\s*\d+\s*", "", t).strip()
        t = clean_concept_label(t)
        if t and not is_weak_concept(t):
            return t[:50]
    return "this topic"


def _stem_templates(concept: str, topic: str, index: int) -> str:
    c = clean_concept_label(concept) or concept
    templates = [
        f"Which statement best describes {c}?",
        f"What is the main purpose of {c}?",
        f"What role does {c} play in {topic}?",
        f"Which option correctly explains {c}?",
        f"Why is {c} important in {topic}?",
    ]
    return templates[index % len(templates)]


def _is_good_concept(term: str) -> bool:
    t = clean_concept_label(term)
    if not t or is_weak_concept(t):
        return False
    if _SHOUTY_STEM_RE.search(t) and len(t.split()) >= 3:
        return False
    if re.match(r"(?i)^(what|which|how|why|when)\b", t):
        return False
    if "?" in t or " if its " in t.lower():
        return False
    if re.search(r"(?i)image\s*\d|resize$|types of spatial", t):
        return False
    return True


def _extract_concepts(text: str, limit: int = 20) -> List[str]:
    concepts: List[str] = []
    seen: Set[str] = set()
    low = (text or "").lower()
    for term in _PRIORITY_TERMS:
        if term in low and _is_good_concept(term):
            key = normalize_concept_key(term)
            if key not in seen:
                seen.add(key)
                concepts.append(term)
    for m in _HEADING_RE.finditer(text or ""):
        term = clean_concept_label((m.group(1) or "").strip())
        if not _is_good_concept(term) or _SKIP_HEADING.match(term):
            continue
        key = normalize_concept_key(term)
        if key not in seen:
            seen.add(key)
            concepts.append(term)
    for m in _DEF_RE.finditer(text or ""):
        term = clean_concept_label((m.group(1) or "").strip())
        key = normalize_concept_key(term)
        if _is_good_concept(term) and key not in seen:
            seen.add(key)
            concepts.append(term)
    return concepts[:limit]


def _definition_pairs(text: str, limit: int = 15) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    seen: Set[str] = set()
    for m in _DEF_RE.finditer(text or ""):
        concept = clean_concept_label((m.group(1) or "").strip())
        answer = clean_option_text((m.group(2) or "").strip())
        key = normalize_concept_key(concept)
        if not _is_good_concept(concept) or key in seen or is_broken_option(answer):
            continue
        seen.add(key)
        pairs.append((concept, answer))
        if len(pairs) >= limit:
            break
    return pairs


def _answer_for_concept(
    concept: str,
    text: str,
    sentences: List[str],
) -> Optional[str]:
    pattern = re.compile(
        rf"\b{re.escape(concept)}\b\s+"
        r"(?:is|are|refers to|means|used to|helps|defined as|consists of|includes)\s+"
        r"([^.\n]{12,140})\.?",
        re.I,
    )
    hit = pattern.search(text)
    if hit:
        ans = clean_option_text(hit.group(1).strip())
        if ans and not is_broken_option(ans):
            return ans
    concept_low = concept.lower()
    for s in sentences:
        if concept_low in s.lower():
            return s
    words = [w for w in concept_low.split() if len(w) > 3]
    for s in sentences:
        if len(words) >= 2 and sum(1 for w in words if w in s.lower()) >= 2:
            return s
    if len(words) == 1:
        for s in sentences:
            if words[0] in s.lower():
                return s
    for m in re.finditer(r"[A-Za-z][^.!?]{15,280}[.!?]", text or ""):
        raw = re.sub(r"\s+", " ", m.group(0)).strip()
        if concept_low not in raw.lower():
            continue
        words_n = raw.split()
        if len(words_n) < 8 or len(words_n) > 35:
            continue
        s = clean_option_text(raw)
        if s and not is_broken_option(s):
            return s
    return None


def _build_mcq(
    concept: str,
    answer: str,
    distractors: List[str],
    template_idx: int,
    source_text: str,
    material_title: Optional[str],
    topic: str,
) -> Optional[Dict[str, Any]]:
    c = clean_concept_label(concept)
    if not c or is_weak_concept(c):
        return None
    question = _stem_templates(c, topic, template_idx)
    if is_vague_question(question, material_title) or uses_filename_as_concept(
        question, material_title,
    ):
        return None

    correct = clean_option_text(answer)
    if not correct or is_broken_option(correct):
        return None

    options: List[str] = [correct]
    used: Set[str] = {correct.lower()}
    c_low = c.lower()
    for d in distractors:
        o = clean_option_text(d)
        if not o or o.lower() in used or is_broken_option(o):
            continue
        if c_low not in o.lower()[:30]:
            options.append(o)
            used.add(o.lower())
        if len(options) >= 4:
            break
    for d in distractors:
        if len(options) >= 4:
            break
        o = clean_option_text(d)
        if o and o.lower() not in used and not is_broken_option(o):
            options.append(o)
            used.add(o.lower())

    if len(options) < 4:
        extra = extract_educational_sentences(source_text, limit=80)
        for d in extra:
            o = clean_option_text(d)
            if o and o.lower() not in used and not is_broken_option(o):
                options.append(o)
                used.add(o.lower())
            if len(options) >= 4:
                break

    if len(options) < 4:
        return None

    keywords = _extract_keywords(source_text, material_title)
    if not is_question_valid(question, options[:4], source_text, material_title, keywords):
        return None

    return {
        "question": question,
        "options": options[:4],
        "correctIndex": 0,
    }


def generate_deterministic_fallback(
    text: str,
    material_title: Optional[str] = None,
    num_questions: int = 5,
    relax_validation: bool = False,
) -> List[Dict[str, Any]]:
    """Fast template-based MCQs from clean sentences in the selected text only."""
    if not text or not text.strip():
        return []

    sentences = extract_educational_sentences(text, limit=50)
    topic = _topic_label(material_title, text)
    used: Set[str] = set()
    out: List[Dict[str, Any]] = []
    template_idx = 0

    for concept in _extract_concepts(text):
        key = normalize_concept_key(concept)
        if key in used:
            continue
        answer = _answer_for_concept(concept, text, sentences)
        if not answer:
            for c2, a2 in _definition_pairs(text):
                if normalize_concept_key(c2) == key:
                    answer = a2
                    break
        if not answer:
            continue
        distractors = [s for s in sentences if s.lower() != answer.lower()]
        built: Optional[Dict[str, Any]] = None
        for try_idx in range(5):
            q = _build_mcq(
                concept, answer, distractors, template_idx + try_idx,
                text, material_title, topic,
            )
            if q:
                built = q
                template_idx += try_idx + 1
                break
        if not built:
            continue
        used.add(extract_concept_from_stem(built["question"]) or key)
        out.append(built)
        if len(out) >= num_questions:
            break

    for concept, answer in _definition_pairs(text):
        key = normalize_concept_key(concept)
        if key in used:
            continue
        distractors = [s for s in sentences if s.lower() != answer.lower()]
        built = None
        for try_idx in range(5):
            q = _build_mcq(
                concept, answer, distractors, template_idx + try_idx,
                text, material_title, topic,
            )
            if q:
                built = q
                template_idx += try_idx + 1
                break
        if not built:
            continue
        used.add(extract_concept_from_stem(built["question"]) or key)
        out.append(built)
        if len(out) >= num_questions:
            break

    out = deduplicate_questions(out, text, material_title)
    return out[:num_questions]

"""
Deterministic MCQ fallback from headings and clean sentences in selected material only.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from app.services.quiz_question_quality import (
    clean_option_text,
    deduplicate_questions,
    extract_concept_from_stem,
    extract_educational_sentences,
    is_broken_option,
    is_question_valid,
    is_vague_question,
    normalize_concept_key,
    uses_filename_as_concept,
    _extract_keywords,
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


def _definition_pairs(text: str, limit: int = 25) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    seen: Set[str] = set()
    for m in _DEF_RE.finditer(text or ""):
        concept = (m.group(1) or "").strip()
        answer = clean_option_text((m.group(2) or "").strip())
        key = concept.lower()
        if key in seen or len(concept) < 4:
            continue
        if is_broken_option(answer):
            continue
        seen.add(key)
        pairs.append((concept, answer))
        if len(pairs) >= limit:
            break
    return pairs

_PRIORITY_TERMS = [
    "pattern recognition",
    "supervised learning",
    "unsupervised learning",
    "classification",
    "regression",
    "feature extraction",
    "training set",
    "test set",
    "decision theory",
    "feature vector",
    "edge detection",
    "image segmentation",
    "image enhancement",
    "sobel operator",
    "laplacian",
    "naive bayes",
    "intelligent agent",
    "multi-agent system",
    "swarm intelligence",
    "riverpod",
    "flutter",
    "state management",
]


def _extract_concepts(text: str, limit: int = 30) -> List[str]:
    concepts: List[str] = []
    seen: Set[str] = set()
    low = (text or "").lower()
    for term in _PRIORITY_TERMS:
        if term in low and term not in seen:
            seen.add(term)
            concepts.append(term)
    for m in _HEADING_RE.finditer(text or ""):
        term = (m.group(1) or "").strip()
        if len(term) < 4 or len(term) > 55 or _SKIP_HEADING.match(term):
            continue
        if re.search(r"\b(page|slide|file|moodle)\b", term, re.I):
            continue
        key = term.lower()
        if key in seen:
            continue
        seen.add(key)
        concepts.append(term)
    for m in _DEF_RE.finditer(text or ""):
        term = (m.group(1) or "").strip()
        if len(term) >= 4 and term.lower() not in seen:
            seen.add(term.lower())
            concepts.append(term)
    return concepts[:limit]


def _short_material_label(material_title: Optional[str]) -> str:
    if not material_title:
        return "this topic"
    t = re.sub(r"\b[A-Z]{2,6}\s*\d{3,4}\b", "", material_title)
    t = re.sub(r"\b(File|Moodle|Copy)\b", "", t, flags=re.I).strip()
    t = re.sub(r"\b\d+\s+", "", t).strip()
    return t[:50] if t else "this topic"


def _answer_for_concept(
    concept: str,
    text: str,
    sentences: List[str],
) -> Optional[str]:
    pattern = re.compile(
        rf"\b{re.escape(concept)}\b\s+"
        r"(?:is|are|refers to|means|used to|helps|defined as|consists of|includes)\s+"
        r"([^.\n]{12,140})\.",
        re.I,
    )
    hit = pattern.search(text)
    if hit:
        ans = clean_option_text(hit.group(1).strip())
        if ans and not is_broken_option(ans):
            return ans
    for s in sentences:
        if concept.lower() in s.lower():
            return s
    return None


def _stem_templates(concept: str, topic: str) -> List[str]:
    c = concept if not concept.isupper() else concept.title()
    return [
        f"Which statement best describes {c}?",
        f"What is the purpose of {c}?",
        f"What is the role of {c} in {topic}?",
        f"Which option correctly explains {c}?",
        f"What is the main goal of {c}?",
    ]


def _build_question(
    concept: str,
    answer: str,
    distractors: List[str],
    source_text: str,
    material_title: Optional[str],
) -> Optional[Dict[str, Any]]:
    topic = _short_material_label(material_title)
    question = None
    for stem in _stem_templates(concept, topic):
        if not is_vague_question(stem, material_title) and not uses_filename_as_concept(
            stem, material_title
        ):
            question = stem
            break
    if not question:
        return None

    correct = clean_option_text(answer)
    if not correct or is_broken_option(correct):
        return None

    options: List[str] = [correct]
    used: Set[str] = {correct.lower()}
    for d in distractors:
        cleaned = clean_option_text(d)
        if cleaned and cleaned.lower() not in used and not is_broken_option(cleaned):
            options.append(cleaned)
            used.add(cleaned.lower())
        if len(options) >= 4:
            break

    while len(options) < 4 and distractors:
        filler = clean_option_text(distractors[len(options) % len(distractors)])
        if filler and filler.lower() not in used and not is_broken_option(filler):
            options.append(filler)
            used.add(filler.lower())

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
    """Build MCQs from clean educational sentences in the selected text only."""
    if not text or not text.strip():
        return []

    sentences = extract_educational_sentences(text)
    used_concepts: Set[str] = set()
    used_distractors: Set[str] = set()
    out: List[Dict[str, Any]] = []

    for concept, answer in _definition_pairs(text, limit=num_questions + 8):
        if normalize_concept_key(concept) in used_concepts:
            continue
        distractors = [
            s for s in sentences
            if s.lower() != answer.lower() and s.lower() not in used_distractors
        ]
        q = _build_question(concept, answer, distractors, text, material_title)
        if not q:
            continue
        concept_key = extract_concept_from_stem(q["question"])
        if concept_key in used_concepts:
            continue
        for opt in q["options"][1:]:
            used_distractors.add(opt.lower())
        used_concepts.add(concept_key)
        out.append(q)
        if len(out) >= num_questions:
            break

    concepts = _extract_concepts(text)
    for concept in concepts:
        if concept.lower() in used_concepts:
            continue
        answer = _answer_for_concept(concept, text, sentences)
        if not answer:
            continue
        distractors = [
            s for s in sentences
            if s.lower() != answer.lower() and s.lower() not in used_distractors
        ]
        q = _build_question(concept, answer, distractors, text, material_title)
        if not q and relax_validation:
            q = _build_question(concept, answer, distractors, text, material_title)
        if not q:
            continue
        concept_key = extract_concept_from_stem(q["question"])
        if concept_key in used_concepts:
            continue
        for opt in q["options"][1:]:
            used_distractors.add(opt.lower())
        used_concepts.add(concept_key or concept.lower())
        out.append(q)
        if len(out) >= num_questions:
            break

    out = deduplicate_questions(out, text, material_title)

    if len(out) < num_questions:
        loose = extract_educational_sentences(text)
        low = (text or "").lower()
        for term in _PRIORITY_TERMS:
            if term not in low:
                continue
            key = normalize_concept_key(term)
            if key in used_concepts:
                continue
            answer = None
            for s in loose:
                if term in s.lower():
                    answer = s
                    break
            if not answer:
                continue
            distractors = [
                s for s in loose
                if s.lower() != answer.lower() and s.lower() not in used_distractors
            ]
            q = _build_question(term, answer, distractors, text, material_title)
            if not q:
                continue
            ck = extract_concept_from_stem(q["question"])
            if ck in used_concepts:
                continue
            used_concepts.add(ck)
            out.append(q)
            if len(out) >= num_questions:
                break

    out = deduplicate_questions(out, text, material_title)
    return out[:num_questions]

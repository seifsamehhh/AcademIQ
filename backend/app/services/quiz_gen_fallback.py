"""
Deterministic MCQ fallback from headings and clean sentences in selected material only.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

from app.services.quiz_question_quality import (
    clean_option_text,
    is_broken_option,
    is_question_valid,
    is_vague_question,
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
    r"([^.\n]{12,140})\.",
    re.I,
)
_SENTENCE_RE = re.compile(r"[A-Za-z][^.!?]{25,220}[.!?]")
_SKIP_HEADING = re.compile(
    r"(?i)^(summary|introduction|contents|outline|references|agenda|objectives)$"
)


def _clean_sentences(text: str) -> List[str]:
    out: List[str] = []
    seen: Set[str] = set()
    for m in _SENTENCE_RE.finditer(text or ""):
        s = clean_option_text(re.sub(r"\s+", " ", m.group(0)).strip())
        if len(s) < 25 or len(s) > 220:
            continue
        if is_broken_option(s):
            continue
        if re.search(r"(?i)(?:\[Page\s*\d|Page\s*\d+\])|postprocessing:|image algebra|visual example", s):
            continue
        if re.search(r"\d\.\s*$", s) and len(s.split()) <= 6:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def _extract_concepts(text: str, limit: int = 24) -> List[str]:
    concepts: List[str] = []
    seen: Set[str] = set()
    priority = [
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
        "sobel operator",
        "laplacian",
    ]
    low = (text or "").lower()
    for term in priority:
        if term in low and term not in seen:
            seen.add(term)
            concepts.append(term)
    for m in _HEADING_RE.finditer(text or ""):
        term = (m.group(1) or "").strip()
        if len(term) < 4 or len(term) > 55:
            continue
        if _SKIP_HEADING.match(term):
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
        return "this material"
    t = re.sub(r"\b[A-Z]{2,6}\s*\d{3,4}\b", "", material_title)
    t = re.sub(r"\b(File|Moodle|Copy)\b", "", t, flags=re.I).strip()
    return t[:60] if t else "this material"


def _answer_for_concept(concept: str, text: str, sentences: List[str]) -> Optional[str]:
    dm = _DEF_RE.search(text)
    if dm and dm.group(1).strip().lower() == concept.lower():
        ans = clean_option_text(dm.group(2).strip())
        if ans and not is_broken_option(ans):
            return ans
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


def _build_question(
    concept: str,
    answer: str,
    distractors: List[str],
    source_text: str,
    material_title: Optional[str],
    relax_validation: bool = False,
) -> Optional[Dict[str, Any]]:
    label = _short_material_label(material_title)
    stems = [
        f"Which statement best describes {concept}?",
        f"What is the main idea of {concept} in {label}?",
    ]
    question = None
    for stem in stems:
        if not is_vague_question(stem, material_title) and not uses_filename_as_concept(
            stem, material_title
        ):
            question = stem
            break
    if not question:
        return None

    options: List[str] = []
    correct = clean_option_text(answer)
    if correct and not is_broken_option(correct):
        options.append(correct)
    for d in distractors:
        cleaned = clean_option_text(d)
        if cleaned and cleaned not in options and not is_broken_option(cleaned):
            options.append(cleaned)
        if len(options) >= 4:
            break
    while len(options) < 4 and distractors:
        filler = clean_option_text(distractors[len(options) % len(distractors)])
        if filler and filler not in options:
            options.append(filler)
    if len(options) < 4:
        return None

    if relax_validation:
        return {
            "question": question,
            "options": options[:4],
            "correctIndex": 0,
        }

    keywords = _extract_keywords(source_text, material_title)
    if is_question_valid(question, options[:4], source_text, material_title, keywords):
        return {
            "question": question,
            "options": options[:4],
            "correctIndex": 0,
        }
    return None


def generate_deterministic_fallback(
    text: str,
    material_title: Optional[str] = None,
    num_questions: int = 5,
    relax_validation: bool = False,
) -> List[Dict[str, Any]]:
    """Build MCQs from headings and definition sentences in the selected text only."""
    if not text or not text.strip():
        return []

    sentences = _clean_sentences(text)
    concepts = _extract_concepts(text)
    if not concepts and sentences:
        concepts = ["pattern recognition", "supervised learning", "classification"]

    used: Set[str] = set()
    used_distractors: Set[str] = set()
    out: List[Dict[str, Any]] = []
    keywords = _extract_keywords(text, material_title)

    for concept in concepts:
        if concept.lower() in used:
            continue
        answer = _answer_for_concept(concept, text, sentences)
        if not answer:
            continue
        distractors = [
            s for s in sentences
            if s != answer and s.lower() not in used_distractors
        ]
        q = _build_question(
            concept, answer, distractors, text, material_title, relax_validation=relax_validation
        )
        if not q:
            continue
        if not relax_validation and not is_question_valid(
            q["question"],
            q["options"],
            text,
            material_title,
            keywords,
        ):
            continue
        for opt in q.get("options") or []:
            if opt != q["options"][0]:
                used_distractors.add(opt.lower())
        used.add(concept.lower())
        q["id"] = f"q{len(out) + 1}"
        out.append(q)
        if len(out) >= num_questions:
            break

    if len(out) < num_questions and len(sentences) >= 4:
        for i, sent in enumerate(sentences):
            if len(out) >= num_questions:
                break
            concept_match = re.match(r"^([A-Za-z][\w\s/&\-]{3,40}?)\s+(?:is|are)\b", sent, re.I)
            concept = concept_match.group(1).strip() if concept_match else f"topic {len(out) + 1}"
            if concept.lower() in used:
                continue
            others = [s for j, s in enumerate(sentences) if j != i][:6]
            q = _build_question(
                concept, sent, others, text, material_title, relax_validation=relax_validation
            )
            if not q:
                continue
            if not relax_validation and not is_question_valid(
                q["question"],
                q["options"],
                text,
                material_title,
                keywords,
            ):
                continue
            used.add(concept.lower())
            q["id"] = f"q{len(out) + 1}"
            out.append(q)

    return out[:num_questions]

"""
Deterministic MCQ fallback from headings and clean sentences in selected material.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

from app.services.quiz_question_quality import (
    clean_option_text,
    is_broken_option,
    is_vague_question,
    uses_filename_as_concept,
)

_HEADING_RE = re.compile(
    r"(?:^|\n)\s*([A-Z][A-Za-z0-9][\w\s/&\-]{3,55})\s*$",
    re.MULTILINE,
)
_DEF_RE = re.compile(
    r"\b([A-Za-z][A-Za-z0-9 /&\-]{3,50})\s+"
    r"(?:is|are|refers to|means|used to|helps|defined as)\s+"
    r"([^.\n]{12,140})\.",
    re.I,
)
_SENTENCE_RE = re.compile(r"[A-Za-z][^.!?]{25,220}[.!?]")


def _clean_sentences(text: str) -> List[str]:
    out: List[str] = []
    seen: Set[str] = set()
    for m in _SENTENCE_RE.finditer(text or ""):
        s = re.sub(r"\s+", " ", m.group(0)).strip()
        if len(s) < 25 or len(s) > 220:
            continue
        if is_broken_option(s):
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def _extract_concepts(text: str, limit: int = 20) -> List[str]:
    concepts: List[str] = []
    seen: Set[str] = set()
    for pattern in (_HEADING_RE,):
        for m in pattern.finditer(text or ""):
            term = (m.group(1) or "").strip()
            if len(term) < 4 or len(term) > 55:
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


def _build_question(
    concept: str,
    answer: str,
    distractors: List[str],
    material_title: Optional[str],
) -> Optional[Dict[str, Any]]:
    label = _short_material_label(material_title)
    question = f"What is the main idea of {concept} in {label}?"
    if is_vague_question(question) or uses_filename_as_concept(question):
        question = f"Which statement best describes {concept}?"
    if is_vague_question(question) or uses_filename_as_concept(question):
        return None

    options = [clean_option_text(answer)]
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
    return {
        "question": question,
        "options": options[:4],
        "correctIndex": 0,
    }


def generate_deterministic_fallback(
    text: str,
    material_title: Optional[str] = None,
    num_questions: int = 5,
) -> List[Dict[str, Any]]:
    sentences = _clean_sentences(text)
    concepts = _extract_concepts(text)
    if not concepts and sentences:
        concepts = ["the main topic"]
    used: Set[str] = set()
    out: List[Dict[str, Any]] = []

    for concept in concepts:
        if concept.lower() in used:
            continue
        answer = None
        dm = _DEF_RE.search(text)
        if dm and dm.group(1).strip().lower() == concept.lower():
            answer = dm.group(2).strip()
        if not answer:
            for s in sentences:
                if concept.lower() in s.lower():
                    answer = s
                    break
        if not answer and sentences:
            answer = sentences[len(out) % len(sentences)]
        if not answer:
            continue
        distractors = [s for s in sentences if s != answer][:6]
        q = _build_question(concept, answer, distractors, material_title)
        if not q:
            continue
        used.add(concept.lower())
        q["id"] = f"q{len(out) + 1}"
        out.append(q)
        if len(out) >= num_questions:
            break

    if len(out) < num_questions and len(sentences) >= 4:
        for i, sent in enumerate(sentences[:num_questions * 2]):
            if len(out) >= num_questions:
                break
            others = [s for j, s in enumerate(sentences) if j != i][:3]
            q = _build_question(f"concept {len(out) + 1}", sent, others, material_title)
            if q:
                q["id"] = f"q{len(out) + 1}"
                out.append(q)

    return out[:num_questions]

"""
Fast deterministic MCQ fallback — teachable concepts only, selected material only.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

from app.services.quiz_question_quality import (
    build_mcq_from_teachable_pair,
    clean_option_text,
    deduplicate_questions,
    extract_concept_from_stem,
    extract_educational_sentences,
    extract_teachable_pairs,
    final_repair_mcq_options,
    is_broken_option,
    is_teachable_concept,
    mcq_options_final_sane,
    normalize_concept_key,
    stem_template_for_concept,
)


def _is_good_concept(term: str) -> bool:
    return is_teachable_concept(term)


def generate_deterministic_fallback(
    text: str,
    material_title: Optional[str] = None,
    num_questions: int = 5,
    relax_validation: bool = False,
) -> List[Dict[str, Any]]:
    """MCQs from ranked teachable definition pairs — no headings or examples."""
    if not text or not text.strip():
        return []

    pairs = extract_teachable_pairs(text, limit=num_questions + 15)
    if not pairs:
        return []

    used: Set[str] = set()
    out: List[Dict[str, Any]] = []

    for template_idx, (concept, answer) in enumerate(pairs):
        key = normalize_concept_key(concept)
        if key in used:
            continue
        built = build_mcq_from_teachable_pair(
            concept, answer, text, pairs, template_idx, material_title,
        )
        if not built:
            continue
        built = final_repair_mcq_options(built, text, material_title, teachable_pairs=pairs)
        if not mcq_options_final_sane(built, material_title):
            continue
        used.add(extract_concept_from_stem(built["question"]) or key)
        out.append(built)
        if len(out) >= num_questions:
            break

    out = deduplicate_questions(out, text, material_title)
    return out[:num_questions]

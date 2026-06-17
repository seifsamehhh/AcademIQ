# backend/app/routes/student_data.py
"""
Student-facing data endpoints consumed by the Next.js frontend
(front-end/src/lib/api.ts). All are scoped to the authenticated student via
JWT Bearer tokens or legacy session cookies (get_current_user), and read the
real normalized MongoDB collections.

Paths intentionally have NO /api prefix to match the frontend's api.ts calls
(/courses, /dashboard, /courses/{id}/performance, ...).
"""

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.models.user import ROLE_ADMIN
from app.repositories import material_repository
from app.services import quiz_gen, student_data
from app.services.student_data import (
    MIN_QUIZ_CONTENT_CHARS,
    MIN_EDUCATIONAL_REPROCESS_CHARS,
    _classify_non_quiz_material,
    _is_educational_material,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Student data"])

# ── Context-relevance helpers ─────────────────────────────────────────────────

_CTX_STOP: Set[str] = {
    "the", "a", "an", "and", "or", "of", "to", "in", "is", "at", "by",
    "for", "with", "on", "as", "this", "that", "from", "are", "was",
    "were", "be", "been", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might",
    # generic material-name words — not discriminative
    "lecture", "lab", "notes", "slides", "file", "material", "chapter",
    "handout", "tutorial", "worksheet", "revision", "review",
}


def _tok(text: str) -> Set[str]:
    """Lowercase, strip punctuation, return significant word set."""
    words = re.sub(r"[^a-z0-9\s]", " ", (text or "").lower()).split()
    return {w for w in words if len(w) > 2 and w not in _CTX_STOP}


def _extract_num(title: str) -> Optional[int]:
    """Return the first integer in a title string (e.g. 'Lecture 3' → 3)."""
    m = re.search(r"\b(\d+)\b", title or "")
    return int(m.group(1)) if m else None


def _type_tag(title: str) -> Optional[str]:
    t = (title or "").lower()
    if "lecture" in t:
        return "lecture"
    if re.search(r"\blab\b", t):
        return "lab"
    if any(w in t for w in ("revision", "review", "summary")):
        return "revision"
    if any(w in t for w in ("notes", "handout", "tutorial", "slides")):
        return "notes"
    return None


def _relevance_score(
    sel_title: str,
    sel_snippet: str,
    ctx_doc: Dict[str, Any],
) -> float:
    """
    Score 0.0–1.0 how relevant a context document is to the selected material.

    Signals (weighted):
      1. Title Jaccard overlap (0.40)
      2. Number proximity — adjacent lectures = related topics (0.25)
      3. Keyword overlap between selected text snippet and ctx text (0.25)
      4. Same material type bonus (0.10)
    """
    ctx_title = ctx_doc.get("title") or ""
    ctx_snippet = (ctx_doc.get("content_text") or "")[:400]

    sel_tw = _tok(sel_title)
    ctx_tw = _tok(ctx_title)

    score = 0.0

    # 1. Title Jaccard
    if sel_tw and ctx_tw:
        score += len(sel_tw & ctx_tw) / len(sel_tw | ctx_tw) * 0.40

    # 2. Number proximity
    sel_n = _extract_num(sel_title)
    ctx_n = _extract_num(ctx_title)
    if sel_n is not None and ctx_n is not None:
        d = abs(sel_n - ctx_n)
        score += 0.25 if d <= 1 else 0.15 if d == 2 else 0.07 if d <= 4 else 0.0

    # 3. Keyword overlap with selected content snippet
    sw = _tok(sel_snippet)
    cw = _tok(ctx_snippet)
    if sw and cw:
        score += min(len(sw & cw) / max(len(sw), 1), 1.0) * 0.25

    # 4. Same material type
    if _type_tag(sel_title) and _type_tag(sel_title) == _type_tag(ctx_title):
        score += 0.10

    return min(score, 1.0)


def _build_fallback_context_text(
    sel_title: str,
    sel_text: str,
    edu_candidates: List[Dict[str, Any]],
    lecture_num: int,
    max_ctx: int = 3,
    ctx_cap: int = 10_000,
) -> Tuple[str, List[str], List[str], str]:
    """
    Build the combined text for a course-context fallback quiz generation.
    Returns (combined_text, ctx_ids, ctx_titles, selection_reason).

    Diversification strategy — prevents adjacent weak lectures (Lecture 1,
    Lecture 2, Lecture 3) from all producing the same quiz:

    1. Rank all candidates by relevance to the selected material.
    2. Apply a lecture-number rotation within the top candidates so that each
       lecture number naturally picks from a slightly different position in the
       ranked list.  Lecture 1 → starts at index 1, Lecture 2 → index 2, etc.
    3. For each selected context material, extract a DIFFERENT WINDOW of its
       text based on the lecture number:
         window_start = (lecture_num * 700) % max(1, full_len - 2800)
       Lecture 1 and Lecture 2 using the same context material will therefore
       see different paragraphs and different extracted concepts → different Q.
    4. Repeat the selected material's own text twice when it is short (<1 000
       chars) so its concepts get higher "density" in the generator's input,
       making the output more topic-grounded.
    """
    if not edu_candidates:
        return "", [], [], "no_candidates"

    scored: List[Tuple[Dict[str, Any], float]] = [
        (doc, _relevance_score(sel_title, sel_text[:400], doc))
        for doc in edu_candidates
    ]
    scored.sort(key=lambda x: x[1], reverse=True)

    # ── Rotation within the candidate pool ───────────────────────────────────
    n = len(scored)
    high_rel = [(d, s) for d, s in scored if s >= 0.20]
    low_rel  = [(d, s) for d, s in scored if s < 0.20]

    if len(high_rel) >= max_ctx:
        # Rotate within high-relevance tier by lecture number
        offset = lecture_num % len(high_rel)
        ordered = [high_rel[(i + offset) % len(high_rel)] for i in range(len(high_rel))]
    elif high_rel:
        # Some high-rel + fill from low-rel with rotation
        offset = lecture_num % max(1, len(low_rel))
        low_rotated = [low_rel[(i + offset) % len(low_rel)] for i in range(len(low_rel))]
        ordered = high_rel + low_rotated
    else:
        offset = lecture_num % max(1, n)
        ordered = [scored[(i + offset) % n] for i in range(n)]

    selected_docs = [doc for doc, _ in ordered[:max_ctx]]

    # ── Build combined text ───────────────────────────────────────────────────
    parts: List[str] = []

    # Topic anchor – helps rule-based generators tag this as the focal topic
    if sel_title:
        parts.append(
            f"{sel_title}\n{sel_title}\n{sel_title}"
        )

    # Selected material text (boost: repeat if short to raise concept density)
    if sel_text:
        header = sel_title or "Selected Material"
        parts.append(f"# {header}\n{sel_text}")
        if len(sel_text) < 1_000:
            parts.append(f"# {header} (continued)\n{sel_text}")

    # Context materials with lecture-number windowing
    ctx_ids: List[str] = []
    ctx_titles: List[str] = []
    total_ctx = 0
    window_size = 2_800

    for doc in selected_docs:
        if total_ctx >= ctx_cap:
            break
        full_text = (doc.get("content_text") or "").strip()
        if not full_text:
            continue

        ctx_title = doc.get("title") or "Course material"
        full_len = len(full_text)

        # Different lecture numbers access different windows of the same material
        if full_len > window_size:
            w_start = (lecture_num * 700) % max(1, full_len - window_size)
            ctx_text = full_text[w_start: w_start + window_size]
            if len(ctx_text) < 400:  # edge case: window too close to end
                ctx_text = full_text[:window_size]
        else:
            ctx_text = full_text

        remaining = ctx_cap - total_ctx
        if len(ctx_text) > remaining:
            ctx_text = ctx_text[:remaining]

        parts.append(f"# {ctx_title}\n{ctx_text}")
        ctx_ids.append(str(doc.get("material_id") or ""))
        ctx_titles.append(ctx_title)
        total_ctx += len(ctx_text)

    combined = "\n\n".join(parts)
    reason = (
        f"lecture_num={lecture_num} offset={lecture_num % max(1, n)} "
        f"window_start={lecture_num * 700} "
        f"context=[{', '.join(ctx_titles)}]"
    )
    return combined, ctx_ids, ctx_titles, reason


def _groundedness_check(
    questions: List[Dict[str, Any]],
    title_kws: Set[str],
) -> bool:
    """
    Return True if at least one generated question references a keyword
    from the selected material title.  Generic fallback questions that
    mention no topic from the title fail this check.
    """
    if not title_kws or not questions:
        return True
    meaningful = {k for k in title_kws if len(k) > 3}
    if not meaningful:
        return True
    for q in questions:
        body = (q.get("question", "") + " " + " ".join(q.get("options", []))).lower()
        if any(kw in body for kw in meaningful):
            return True
    return False


def _student_id_from_user(user: Dict[str, Any]) -> str | None:
    sid = user.get("student_id")
    return str(sid).strip() if sid else None


@router.get("/courses")
def list_courses(user: Dict[str, Any] = Depends(get_current_user)):
    return student_data.get_courses(str(user["_id"]), user.get("student_id"))


@router.get("/dashboard")
def dashboard(user: Dict[str, Any] = Depends(get_current_user)):
    return student_data.get_dashboard(user)


@router.get("/courses/{course_id}/performance")
def performance(course_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    return student_data.get_performance(
        str(user["_id"]),
        course_id,
        _student_id_from_user(user),
    )


@router.get("/courses/{course_id}/insights")
def insights(course_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    return student_data.get_insights(
        str(user["_id"]),
        course_id,
        _student_id_from_user(user),
    )


@router.get("/debug/feature-vectors/{student_id}/{course_id}")
def debug_feature_vectors(
    student_id: str,
    course_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Demo-safe debug: inspect whether a feature vector exists for student/course.
    Students may only query their own student_id; admins may query any demo student.
    """
    caller_student_id = _student_id_from_user(user)
    is_admin = user.get("role") == ROLE_ADMIN
    if not is_admin and caller_student_id != student_id:
        raise HTTPException(status_code=403, detail="Cannot inspect another student's features")

    from app.repositories import user_repository

    target_user = user_repository.find_by_student_id(student_id)
    if not target_user:
        raise HTTPException(status_code=404, detail=f"Student not found: {student_id}")

    return student_data.debug_feature_vector(
        str(target_user["_id"]),
        student_id,
        course_id,
    )


@router.get("/courses/{course_id}/materials")
def materials(course_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    # Materials are course-scoped (shared), filtered by enrolled course name when needed.
    return student_data.get_materials(course_id, str(user["_id"]))


@router.post("/courses/{course_id}/quiz")
def generate_quiz(
    course_id: str,
    body: Dict[str, Any],
    _user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Generate a quiz from selected materials' stored content_text.

    Two modes:
      selected_material_only   — selected material has enough content on its own.
      course_context_fallback  — selected material is educational but too sparse;
                                 supplemented with other ready educational materials
                                 from the same course.  Never uses content from a
                                 different course or non-educational files.
    """
    material_ids: List[str] = body.get("materialIds", []) or []
    if not material_ids:
        raise HTTPException(status_code=400, detail="materialIds required")

    # ── 1. Fetch selected-material text ───────────────────────────────────────
    text, mat_meta = material_repository.get_content_with_meta(course_id, material_ids)
    selected_text = (text or "").strip()
    content_chars = len(selected_text)

    # Primary title used for topic-anchoring and relevance scoring
    primary_title: str = (
        (mat_meta[0].get("title") or "") if mat_meta else ""
    )
    selected_titles = [m.get("title") for m in mat_meta]
    selected_is_educational = all(
        _is_educational_material(m.get("title") or "", "")
        or not _classify_non_quiz_material(m.get("title") or "", "")[0]
        for m in mat_meta
    )

    logger.info(
        "Quiz request course=%s materials=%s content_chars=%d",
        course_id, material_ids, content_chars,
    )

    # ── 2. First attempt: generate from selected material alone ───────────────
    questions: List[Dict[str, Any]] = []
    engine = "no_text"
    generator_mode = "selected_material_only"
    context_material_ids: List[str] = []
    context_material_titles: List[str] = []
    context_reason: str | None = None
    context_selection_reason: str | None = None
    duplicate_guard_triggered = False

    if content_chars >= MIN_QUIZ_CONTENT_CHARS:
        questions, engine = quiz_gen.generate_questions(selected_text, num_questions=5)

    # ── 3. Course-context fallback ────────────────────────────────────────────
    # Triggered when selected material produced 0 questions AND it is educational.
    #
    # Key principle: context is RANKED BY RELEVANCE to the selected material,
    # not just grabbed by content length.  This ensures Lecture 1 and Lecture 2
    # use different context documents and thus produce different questions.
    #
    # Safeguards:
    #   - Same course only
    #   - Max 3 context materials (not 5 generic ones)
    #   - Selected material title injected as a "Topic Focus" anchor
    #   - Duplicate guard: checks that at least one question references a
    #     keyword from the selected material title
    if not questions and selected_is_educational:
        # Fetch all ready educational candidates (up to 20 for ranking)
        all_ctx_docs = material_repository.get_ready_context_materials(
            course_id,
            exclude_ids=material_ids,
            min_chars=MIN_QUIZ_CONTENT_CHARS,
        )

        # Remove non-educational documents
        edu_candidates: List[Dict[str, Any]] = [
            doc for doc in all_ctx_docs
            if not _classify_non_quiz_material(
                doc.get("title") or "", (doc.get("file_type") or "").lower()
            )[0]
        ]

        if edu_candidates:
            # Use lecture number for deterministic but per-lecture diversification
            sel_num = _extract_num(primary_title) or 0

            # Build diversified combined text:
            #   - Rotates candidate selection by lecture number
            #   - Takes lecture-number-specific windows of context text
            #   - Repeats selected text when short for concept density
            combined_text, context_material_ids, context_material_titles, ctx_sel_reason = (
                _build_fallback_context_text(
                    sel_title=primary_title,
                    sel_text=selected_text,
                    edu_candidates=edu_candidates,
                    lecture_num=sel_num,
                    max_ctx=3,
                    ctx_cap=10_000,
                )
            )
            context_selection_reason = ctx_sel_reason

            if combined_text.strip():
                ctx_questions, ctx_engine = quiz_gen.generate_questions(
                    combined_text, num_questions=5
                )
                if ctx_questions:
                    # Duplicate guard: verify questions reference keywords from
                    # the selected material's title (prevents generic fallback Q)
                    title_kws = _tok(primary_title)
                    grounded = _groundedness_check(ctx_questions, title_kws)
                    if not grounded:
                        duplicate_guard_triggered = True
                        logger.warning(
                            "Fallback questions not grounded in '%s' — "
                            "retrying with stronger title anchor (lecture_num=%d)",
                            primary_title, sel_num,
                        )
                        # Retry: prepend a more forceful anchor and try a
                        # slightly different window (shift +1 lecture step)
                        strong_anchor = (
                            f"{primary_title}\n{primary_title}\n{primary_title}\n\n"
                        )
                        retry_text = strong_anchor + combined_text
                        retry_qs, retry_engine = quiz_gen.generate_questions(
                            retry_text, num_questions=5
                        )
                        if retry_qs:
                            ctx_questions = retry_qs
                            ctx_engine = retry_engine

                    questions = ctx_questions
                    engine = ctx_engine
                    generator_mode = "course_context_fallback"
                    context_reason = (
                        f"Selected material '{primary_title}' had only {content_chars} chars; "
                        f"supplemented with {len(context_material_ids)} related educational "
                        f"material(s) from the same course (lecture_num={sel_num})."
                    )
                    logger.info(
                        "Context fallback succeeded: course=%s selected=%s "
                        "context=%s questions=%d grounded=%s lecture_num=%d",
                        course_id, material_ids, context_material_ids,
                        len(questions), not duplicate_guard_triggered, sel_num,
                    )

    # ── 4. Final error gates ──────────────────────────────────────────────────
    if not questions:
        if not content_chars:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "missing_content_text",
                    "message": (
                        "Selected materials have no extracted text. "
                        "Use the Chrome extension → 'Upload materials for quiz' on "
                        "the Moodle course page first."
                    ),
                    "material_ids": material_ids,
                },
            )

        if not context_material_ids and content_chars < MIN_QUIZ_CONTENT_CHARS:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "content_too_short_no_context",
                    "message": (
                        f"The selected material has only {content_chars} characters of "
                        f"extracted text (need at least {MIN_QUIZ_CONTENT_CHARS}), and no "
                        "other ready educational materials exist in this course to provide "
                        "context. Re-upload a text-based PDF or PPTX via the Chrome extension."
                    ),
                    "content_chars": content_chars,
                    "min_required": MIN_QUIZ_CONTENT_CHARS,
                    "material_ids": material_ids,
                },
            )

        raise HTTPException(
            status_code=422,
            detail={
                "error": "quiz_generation_failed",
                "message": (
                    f"Could not generate quiz questions from '{primary_title or 'selected material'}' "
                    f"({content_chars} chars) even with course-context support. "
                    "The content may be image-only, too fragmented, or have no teachable "
                    "concepts. Try re-uploading a text-based PDF or selecting a different material."
                ),
                "content_chars": content_chars,
                "engine": engine,
                "generator_mode": generator_mode,
                "context_materials_tried": len(context_material_ids),
                "material_ids": material_ids,
            },
        )

    # ── 5. Success response ───────────────────────────────────────────────────
    debug: Dict[str, Any] = {
        "generator_mode": generator_mode,
        "selected_material_id": material_ids[0] if len(material_ids) == 1 else material_ids,
        "selected_material_title": primary_title,
        "selected_material_ids": material_ids,
        "selected_material_titles": selected_titles,
        "selected_material_content_length": content_chars,
        "content_text_length_per_material": {
            m["material_id"]: m["raw_chars"] for m in mat_meta
        },
        "question_count": len(questions),
        "engine": engine,
        "duplicate_guard_triggered": duplicate_guard_triggered,
    }
    if generator_mode == "course_context_fallback":
        debug["context_material_ids_used"] = context_material_ids
        debug["context_material_titles_used"] = context_material_titles
        debug["context_selection_reason"] = context_selection_reason
        debug["reason"] = context_reason

    return {
        "courseId": course_id,
        "materialIds": material_ids,
        "questions": questions,
        "engine": engine,
        "generatorMode": generator_mode,
        "debug": debug,
    }

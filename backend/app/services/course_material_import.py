"""
Import local course material files into MongoDB for Quiz Generation.

Reads files from backend/import_materials/{course_id}/ and updates canonical
course_materials rows (match existing Moodle rows or create new educational rows).
"""

from __future__ import annotations

import hashlib
import html as html_lib
import io
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.models.material import build_material_doc
from app.repositories import material_repository
from app.services.material_cache import (
    build_extracted_content_fields,
    compute_content_hash,
    content_text_length,
    enrich_kind_fields,
    is_extraction_cache_hit,
)
from app.services.material_quiz_display import (
    classify_material_kind,
    classify_non_quiz_material,
    extract_material_number,
    is_educational_material,
)
from app.services.material_quiz_upload import (
    _allocate_material_id,
    _compute_stable_material_key,
    _derive_readiness_from_probe,
    _find_canonical_learning_row,
    _normalize_incoming_material_item,
    _normalize_title,
    _stable_hash_material_id,
    _title_word_overlap,
)
from app.services.material_text_extract import extract_text_from_bytes

SUPPORTED_EXTENSIONS = frozenset(
    {".pdf", ".pptx", ".ppsx", ".docx", ".txt", ".html", ".htm", ".zip"}
)

COURSE_NAMES: Dict[str, str] = {
    "666": "AAI — Advanced Artificial Intelligence - 26S",
    "808": "DIA — Designing Intelligent Agents - 26S",
    "478": "KRA — Knowledge Representation and Reasoning - 26S",
    "670": "ML — Machine Learning - 26S",
    "462": "MDP — Mobile Device Programming - 26S",
}

CONTENT_SOURCE = "course_material_import"
SOURCE_NOTE = "Content imported from provided course material file."

_TOPIC_KEYWORDS = (
    "frames",
    "knowledge representation",
    "svm",
    "mlp",
    "backpropagation",
    "back propagation",
    "neural network",
    "decision tree",
    "bayes",
    "clustering",
    "regression",
    "gradient",
    "perceptron",
    "cnn",
    "rnn",
    "lstm",
    "transformer",
    "embedding",
    "ontology",
    "logic",
    "reasoning",
    "agent",
    "mobile",
    "android",
    "ios",
    "kotlin",
    "swift",
)

_PART_RE = re.compile(r"(?i)\bpart\s*#?\s*(\d+)\b")
_LNUM_RE = re.compile(r"(?i)\b(?:l|lec)\s*#?\s*(\d+)\b")


@dataclass
class ImportFileResult:
    path: str
    action: str  # imported | updated | merged | skipped | failed | duplicate
    match_strategy: Optional[str] = None
    material_id: Optional[str] = None
    title: Optional[str] = None
    quiz_status: Optional[str] = None
    content_chars: int = 0
    error: Optional[str] = None


@dataclass
class ImportRunSummary:
    course_id: str
    email: str
    folder: str
    files_seen: int = 0
    imported_count: int = 0
    updated_count: int = 0
    merged_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    created_count: int = 0
    matched_count: int = 0
    duplicate_count: int = 0
    results: List[ImportFileResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "course_id": self.course_id,
            "email": self.email,
            "folder": self.folder,
            "files_seen": self.files_seen,
            "imported_count": self.imported_count,
            "updated_count": self.updated_count,
            "merged_count": self.merged_count,
            "skipped_count": self.skipped_count,
            "failed_count": self.failed_count,
            "created_count": self.created_count,
            "matched_count": self.matched_count,
            "duplicate_count": self.duplicate_count,
            "results": [
                {
                    "path": r.path,
                    "action": r.action,
                    "match_strategy": r.match_strategy,
                    "material_id": r.material_id,
                    "title": r.title,
                    "quiz_status": r.quiz_status,
                    "content_chars": r.content_chars,
                    "error": r.error,
                }
                for r in self.results
            ],
        }


def _extension(path: Path) -> str:
    return path.suffix.lower()


def _file_type_from_ext(ext: str) -> str:
    ext = ext.lower().lstrip(".")
    if ext in ("htm", "html"):
        return "html"
    if ext == "ppsx":
        return "pptx"
    return ext


def _title_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    stem = re.sub(r"[_\-]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    return stem or "Untitled Material"


def _classify_from_filename(filename: str) -> Tuple[str, str, Optional[int]]:
    """Derive display title, material_kind, material_number from filename."""
    title = _title_from_filename(filename)
    ft = _file_type_from_ext(_extension(Path(filename)))
    is_non_quiz, _ = classify_non_quiz_material(title, ft)
    kind = classify_material_kind(title, ft, is_non_quiz)
    number = extract_material_number(title, kind)

    # Topic / notes heuristics when kind is generic
    lower = title.lower()
    if kind in ("other_educational", "notes") or number == 9999:
        if re.search(r"(?i)\brevision|final\s+revision|review\b", lower):
            kind = "revision"
            number = extract_material_number(title, kind)
        elif any(kw in lower for kw in _TOPIC_KEYWORDS):
            kind = "notes"
            number = extract_material_number(title, kind)

    if number == 9999:
        m = _LNUM_RE.search(title)
        if m:
            kind = "lecture"
            number = int(m.group(1))

    return title, kind, number if number != 9999 else None


def extract_pdf_text_with_pages(data: bytes) -> str:
    import PyPDF2

    try:
        reader = PyPDF2.PdfReader(io.BytesIO(data))
        pages: List[str] = []
        for idx, page in enumerate(reader.pages, 1):
            try:
                text = (page.extract_text() or "").strip()
            except Exception:
                text = ""
            if text:
                pages.append(f"[Page {idx}]\n{text}")
        return "\n\n".join(pages)
    except Exception:
        return ""


def extract_html_text(data: bytes) -> str:
    raw = data.decode("utf-8", errors="ignore")
    # Strip script/style blocks
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?is)<br\s*/?>", "\n", raw)
    raw = re.sub(r"(?is)</p\s*>", "\n\n", raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = html_lib.unescape(raw)
    raw = re.sub(r"[ \t]+", " ", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()


def extract_file_bytes(
    data: bytes,
    filename: str,
    file_type: str,
) -> Tuple[str, Optional[str]]:
    ext = _extension(Path(filename))
    if ext == ".pdf":
        text = extract_pdf_text_with_pages(data)
        return text, None if text else "empty_pdf"
    if ext in (".html", ".htm"):
        text = extract_html_text(data)
        return text, None if text else "empty_html"
    if ext == ".zip":
        return "", "zip_container"
    return extract_text_from_bytes(data, file_type=file_type, filename=filename)


def _iter_supported_files(folder: Path) -> List[Path]:
    files: List[Path] = []
    if not folder.is_dir():
        return files
    for path in sorted(folder.rglob("*")):
        if not path.is_file():
            continue
        if _extension(path) in SUPPORTED_EXTENSIONS:
            files.append(path)
    return files


def _expand_zip_paths(zip_path: Path, temp_dir: Path) -> List[Tuple[Path, str]]:
    """Extract zip and return (path, virtual_name) for supported inner files."""
    out: List[Tuple[Path, str]] = []
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(temp_dir)
    except Exception:
        return out
    for inner in sorted(temp_dir.rglob("*")):
        if not inner.is_file():
            continue
        if _extension(inner) not in SUPPORTED_EXTENSIONS or _extension(inner) == ".zip":
            continue
        rel = f"{zip_path.name}/{inner.relative_to(temp_dir).as_posix()}"
        out.append((inner, rel))
    return out


def _find_by_title_similarity(
    course_id: str,
    title: str,
    file_type: str,
    min_overlap: float = 0.55,
) -> Optional[Tuple[Dict[str, Any], str]]:
    norm = _normalize_title(title)
    best: Optional[Dict[str, Any]] = None
    best_score = 0.0
    for doc in material_repository.list_by_course(course_id):
        dt = str(doc.get("title") or "")
        dft = str(doc.get("file_type") or "")
        if not is_educational_material(dt, dft):
            continue
        is_non, _ = classify_non_quiz_material(dt, dft)
        if is_non:
            continue
        score = _title_word_overlap(norm, _normalize_title(dt))
        if score > best_score:
            best_score = score
            best = doc
    if best and best_score >= min_overlap:
        return best, f"title_similarity:{best_score:.2f}"
    return None


def _find_match(
    course_id: str,
    title: str,
    file_type: str,
    material_kind: str,
    material_number: Optional[int],
) -> Tuple[Optional[Dict[str, Any]], str]:
    # 1. kind + number
    if material_number is not None and material_kind not in ("other_moodle_item", "other_educational"):
        canonical = _find_canonical_learning_row(course_id, title, file_type)
        if canonical:
            return canonical, "canonical_learning_row"
        for doc in material_repository.list_by_course(course_id):
            dk = doc.get("material_kind")
            if not dk:
                dt = str(doc.get("title") or "")
                dft = str(doc.get("file_type") or "")
                d_non, _ = classify_non_quiz_material(dt, dft)
                dk = classify_material_kind(dt, dft, d_non)
            dn = doc.get("material_number")
            if dn is None:
                dn = extract_material_number(str(doc.get("title") or ""), dk)
                if dn == 9999:
                    dn = None
            base_kind = material_kind.replace("_link", "")
            doc_base = str(dk).replace("_link", "")
            if doc_base == base_kind and dn == material_number:
                return doc, "material_kind_number"

    # 2. title similarity
    sim = _find_by_title_similarity(course_id, title, file_type)
    if sim:
        return sim[0], sim[1]

    # 3. filename keywords in title
    norm_title = _normalize_title(title)
    for doc in material_repository.list_by_course(course_id):
        dt = str(doc.get("title") or "")
        if norm_title and norm_title == _normalize_title(dt):
            return doc, "normalized_title_exact"

    # 4. stable key / allocate
    norm = _normalize_incoming_material_item(
        {
            "title": title,
            "file_type": file_type,
            "url": None,
            "source_url": None,
            "resolved_url": None,
            "material_id": "",
            "id": "",
        }
    )
    mid, existing, strategy = _allocate_material_id(course_id, norm, {})
    if existing:
        return existing, strategy

    return None, "new"


def _should_skip_import(
    doc: Optional[Dict[str, Any]],
    new_hash: Optional[str],
    force: bool,
) -> bool:
    if force or not doc:
        return False
    if doc.get("content_source") == CONTENT_SOURCE:
        if new_hash and doc.get("content_hash") == new_hash and content_text_length(doc) > 0:
            return True
    if is_extraction_cache_hit(doc, force=False):
        if new_hash and doc.get("content_hash") == new_hash:
            return True
    return False


def _merge_content(existing_text: str, new_text: str, filename: str) -> str:
    existing = (existing_text or "").strip()
    chunk = (new_text or "").strip()
    if not chunk:
        return existing
    if not existing:
        return chunk
    marker = f"--- Imported: {filename} ---"
    if chunk in existing:
        return existing
    return f"{existing}\n\n{marker}\n\n{chunk}"


def _persist_import(
    course_id: str,
    course_name: str,
    doc: Optional[Dict[str, Any]],
    match_strategy: str,
    title: str,
    file_type: str,
    material_kind: str,
    material_number: Optional[int],
    original_filename: str,
    text: str,
    force: bool,
) -> Tuple[Optional[Dict[str, Any]], str, bool]:
    """Return (doc, action, created)."""
    now = datetime.utcnow()
    stripped = (text or "").strip()
    new_hash = compute_content_hash(stripped)

    if doc and _should_skip_import(doc, new_hash, force):
        return doc, "skipped", False

    merged = False
    if doc and match_strategy != "new" and content_text_length(doc) > 0:
        combined = _merge_content(doc.get("content_text") or "", stripped, original_filename)
        if combined != stripped:
            stripped = combined
            merged = True
            new_hash = compute_content_hash(stripped)

    probe = _derive_readiness_from_probe(stripped, file_type)
    content_fields = build_extracted_content_fields(stripped, probe)
    kind_fields = enrich_kind_fields(title, file_type)
    if material_kind and material_kind != "other_moodle_item":
        kind_fields["material_kind"] = material_kind
    if material_number is not None:
        kind_fields["material_number"] = material_number

    import_fields: Dict[str, Any] = {
        **content_fields,
        **kind_fields,
        "content_source": CONTENT_SOURCE,
        "source_note": SOURCE_NOTE,
        "original_filename": original_filename,
        "imported_at": now,
        "file_type": file_type,
        "title": title,
        "course_name": course_name,
        "metadata_only": False,
        "category": material_kind if material_kind not in ("other_educational", "notes") else "lecture",
    }

    if doc:
        oid = str(doc.get("_id") or "")
        material_repository.update_by_object_id(oid, import_fields)
        updated = material_repository.get_by_object_id(oid)
        action = "merged" if merged else "updated"
        return updated, action, False

    # Create new canonical row
    norm = _normalize_incoming_material_item(
        {
            "title": title,
            "file_type": file_type,
            "url": f"import://{course_id}/{original_filename}",
            "source_url": f"import://{course_id}/{original_filename}",
            "resolved_url": None,
            "material_id": "",
            "id": "",
        }
    )
    material_id, _, _ = _allocate_material_id(course_id, norm, {})
    if not material_id:
        material_id = _stable_hash_material_id(
            "import", f"{course_id}|{original_filename.lower()}"
        )
    stable_key = _compute_stable_material_key(course_id, norm)

    base = build_material_doc(
        {
            "title": title,
            "file_type": file_type,
            "url": f"import://{course_id}/{original_filename}",
            "course_id": course_id,
            "material_id": material_id,
        },
        course_id,
        course_name,
    )
    if not base:
        base = {
            "course_id": course_id,
            "course_name": course_name,
            "material_id": material_id,
            "title": title,
            "file_type": file_type,
        }

    full_doc = {
        **base,
        **import_fields,
        "stable_material_key": stable_key,
        "semantic_tags": [material_kind if material_kind != "other_moodle_item" else "lecture"],
    }
    material_repository.upsert(full_doc)
    created = material_repository.get(course_id, material_id)
    return created, "created", True


def import_file_path(
    course_id: str,
    course_name: str,
    file_path: Path,
    display_name: str,
    force: bool = False,
) -> ImportFileResult:
    rel = display_name
    try:
        data = file_path.read_bytes()
    except Exception as exc:
        return ImportFileResult(
            path=rel,
            action="failed",
            error=f"read_failed:{exc}",
        )

    title, material_kind, material_number = _classify_from_filename(display_name)
    file_type = _file_type_from_ext(_extension(file_path))

    if not is_educational_material(title, file_type):
        is_non, _ = classify_non_quiz_material(title, file_type)
        if is_non or material_kind == "other_moodle_item":
            return ImportFileResult(
                path=rel,
                action="skipped",
                title=title,
                error="non_educational",
            )

    text, err = extract_file_bytes(data, display_name, file_type)
    if err == "zip_container":
        return ImportFileResult(path=rel, action="skipped", error="zip_use_expand")

    if err or not (text or "").strip():
        return ImportFileResult(
            path=rel,
            action="failed",
            title=title,
            error=err or "empty_extraction",
        )

    doc, strategy = _find_match(
        course_id, title, file_type, material_kind, material_number
    )

    updated_doc, action, created = _persist_import(
        course_id,
        course_name,
        doc,
        strategy,
        title,
        file_type,
        material_kind,
        material_number,
        display_name,
        text,
        force,
    )

    quiz_status = None
    chars = 0
    mid = None
    if updated_doc:
        quiz_status = str(updated_doc.get("quiz_status") or "")
        chars = content_text_length(updated_doc)
        mid = str(updated_doc.get("material_id") or "")

    if action == "skipped":
        return ImportFileResult(
            path=rel,
            action="skipped",
            match_strategy=strategy,
            material_id=mid,
            title=title,
            quiz_status=quiz_status,
            content_chars=chars,
        )

    return ImportFileResult(
        path=rel,
        action=action,
        match_strategy=strategy if doc else "new",
        material_id=mid,
        title=title,
        quiz_status=quiz_status,
        content_chars=chars,
    )


def import_course_folder(
    email: str,
    course_id: str,
    folder: Path,
    force: bool = False,
) -> ImportRunSummary:
    course_id = str(course_id).strip()
    course_name = COURSE_NAMES.get(course_id, f"Course {course_id}")
    summary = ImportRunSummary(
        course_id=course_id,
        email=email,
        folder=str(folder),
    )

    if not folder.is_dir():
        summary.results.append(
            ImportFileResult(path=str(folder), action="failed", error="folder_not_found")
        )
        return summary

    work_items: List[Tuple[Path, str]] = []
    temp_dirs: List[Path] = []

    for path in _iter_supported_files(folder):
        if _extension(path) == ".zip":
            temp_dir = Path(tempfile.mkdtemp(prefix="academiq_import_"))
            temp_dirs.append(temp_dir)
            work_items.extend(_expand_zip_paths(path, temp_dir))
        else:
            work_items.append((path, path.name))

    summary.files_seen = len(work_items)

    for file_path, display_name in work_items:
        result = import_file_path(
            course_id, course_name, file_path, display_name, force=force
        )
        summary.results.append(result)

        if result.action in ("created", "updated", "merged"):
            summary.imported_count += 1
            if result.action == "created":
                summary.created_count += 1
            elif result.action == "updated":
                summary.updated_count += 1
            elif result.action == "merged":
                summary.merged_count += 1
            if result.match_strategy and result.match_strategy != "new":
                summary.matched_count += 1
        elif result.action == "skipped":
            summary.skipped_count += 1
            if result.error == "non_educational":
                pass
            elif result.match_strategy:
                summary.matched_count += 1
        elif result.action == "failed":
            summary.failed_count += 1
        elif result.action == "duplicate":
            summary.duplicate_count += 1

    for td in temp_dirs:
        shutil.rmtree(td, ignore_errors=True)

    return summary


def import_all_courses(
    email: str,
    import_root: Path,
    force: bool = False,
) -> List[ImportRunSummary]:
    summaries: List[ImportRunSummary] = []
    if not import_root.is_dir():
        return summaries
    for child in sorted(import_root.iterdir()):
        if child.is_dir() and child.name.isdigit():
            summaries.append(
                import_course_folder(email, child.name, child, force=force)
            )
    return summaries

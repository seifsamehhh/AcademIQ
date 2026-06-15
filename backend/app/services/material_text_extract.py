"""
Extract plain text from uploaded learning-material bytes for quiz generation.
"""

from __future__ import annotations

import io
import zipfile
import xml.etree.ElementTree as ET
from typing import Optional, Tuple


def extract_pdf_text(data: bytes) -> str:
    import PyPDF2

    reader = PyPDF2.PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def extract_pptx_text(data: bytes) -> str:
    from pptx import Presentation

    presentation = Presentation(io.BytesIO(data))
    chunks = []
    for slide in presentation.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text:
                chunks.append(shape.text)
    return "\n".join(chunks)


def extract_docx_text(data: bytes) -> str:
    try:
        import docx  # python-docx

        document = docx.Document(io.BytesIO(data))
        return "\n".join(p.text for p in document.paragraphs if p.text)
    except ImportError:
        # Minimal fallback: read word/document.xml from the docx zip.
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            xml = zf.read("word/document.xml")
        root = ET.fromstring(xml)
        texts = []
        for node in root.iter():
            if node.tag.endswith("}t") and node.text:
                texts.append(node.text)
        return " ".join(texts)


def _guess_kind(file_type: str, filename: str, content_type: str = "") -> str:
    ft = (file_type or "").lower().strip()
    if ft in {"pdf", "pptx", "ppt", "docx", "doc", "txt", "text"}:
        return ft
    name = (filename or "").lower()
    for ext in ("pdf", "pptx", "ppt", "docx", "doc", "txt"):
        if name.endswith(f".{ext}"):
            return ext
    ctype = (content_type or "").lower()
    if "pdf" in ctype:
        return "pdf"
    if "presentation" in ctype or "powerpoint" in ctype:
        return "pptx"
    if "word" in ctype:
        return "docx"
    if "text/plain" in ctype:
        return "txt"
    return ft or "unknown"


def extract_text_from_bytes(
    data: bytes,
    *,
    file_type: str = "",
    filename: str = "",
    content_type: str = "",
) -> Tuple[str, Optional[str]]:
    """
    Return (extracted_text, error_message).

    error_message is set when extraction fails or the file type is unsupported.
    """
    if not data:
        return "", "empty_file"

    kind = _guess_kind(file_type, filename, content_type)
    try:
        if kind == "pdf":
            return extract_pdf_text(data), None
        if kind in {"txt", "text"}:
            return data.decode("utf-8", errors="ignore"), None
        if kind in {"pptx", "ppt"}:
            return extract_pptx_text(data), None
        if kind in {"docx", "doc"}:
            return extract_docx_text(data), None
        return "", f"unsupported_file_type:{kind or 'unknown'}"
    except Exception as exc:
        return "", f"extraction_failed:{exc}"

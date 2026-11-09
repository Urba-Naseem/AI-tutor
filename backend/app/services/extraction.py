"""US-1.1 - Turn uploaded documents into text for the AI.

PDFs are read first with the fast text reader (pypdfium2): well under a second, where Docling's layout and table
models took several minutes per PDF on a CPU. The AI reads CLO tables fine from plain text. Docling is still used
when the fast text looks poor (e.g. a scanned or image-only PDF) and for DOCX, PPTX and HTML. Plain text and
Markdown are read directly. Upload validation also lives here.
"""
from __future__ import annotations

import io
import re
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException

from ..config import get_settings

ALLOWED = {
    ".pdf": (b"%PDF",),
    ".docx": (b"PK\x03\x04",),
    ".pptx": (b"PK\x03\x04",),
    ".html": None,
    ".htm": None,
    ".md": None,
    ".txt": None,
}
MIME = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".html": "text/html", ".htm": "text/html", ".md": "text/markdown", ".txt": "text/plain",
}


def validate_upload(filename: str, data: bytes) -> str:
    """Return the file extension or raise 422 with a clear reason."""
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(422, f"Unsupported file type '{ext or 'none'}'. Allowed: {', '.join(sorted(ALLOWED))}")
    if not data:
        raise HTTPException(422, "The file is empty")
    limit = get_settings().max_upload_mb * 1024 * 1024
    if len(data) > limit:
        raise HTTPException(413, f"File too large (max {get_settings().max_upload_mb} MB)")
    magic = ALLOWED[ext]
    if magic and not any(data.startswith(m) for m in magic):
        raise HTTPException(422, f"File content does not match its '{ext}' extension")
    if magic is None:
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(422, "Text files must be UTF-8 encoded")
    return ext


@lru_cache
def _converter():
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    opts = PdfPipelineOptions()
    opts.do_ocr = False  # curriculum PDFs are text-based; OCR is slow on CPU
    opts.do_table_structure = True
    return DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)})


def docling_available() -> bool:
    try:
        import docling  # noqa: F401

        return True
    except ImportError:
        return False


RX_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f￾￿]")
MIN_CHARS_PER_PAGE = 200  # below this a PDF is probably scanned images: let Docling try


def _drop_running_lines(pages: list[str]) -> list[str]:
    """Remove running headers / footers: the first or last two lines of a page when they recur (numbers ignored)
    at the edge of most pages (60%+). Only page edges are looked at, and a mere 3 repeats is not enough: a table row
    such as "Cognitive, L3 - Applying PLO 4 35%" can end several pages and must be kept."""
    if len(pages) < 3:
        return pages
    norm = lambda s: re.sub(r"\d+", "#", s.strip())  # noqa: E731
    edges = []
    for p in pages:
        ls = [x for x in p.split("\n") if x.strip()]
        edges.append({norm(x) for x in ls[:2] + ls[-2:]})
    from collections import Counter

    need = max(3, int(0.6 * len(pages) + 0.999))
    common = {n for n, k in Counter(n for e in edges for n in e).items() if k >= need}
    out = []
    for p in pages:
        ls = p.split("\n")
        idx = [i for i, x in enumerate(ls) if x.strip()]
        edge_i = set(idx[:2] + idx[-2:])
        out.append("\n".join(x for i, x in enumerate(ls) if not (i in edge_i and norm(x) in common)))
    return out


def fast_pdf_text(data: bytes) -> str | None:
    """Text of a text-based PDF in well under a second, page by page; None if it looks scanned or unreadable."""
    try:
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(data)
        pages = [pdf[i].get_textpage().get_text_range() for i in range(len(pdf))]
    except Exception:
        return None
    pages = [RX_CONTROL.sub("", p.replace("\r\n", "\n").replace("\r", "\n")) for p in pages]
    pages = _drop_running_lines(pages)
    text = "\n\n".join(pages)
    # a table cell that wraps right after a dash ("Affective, L2 -" / "Responding", "Week 1 -" / "Basics") continues
    # on the next line: join it back (a word hyphen has no space before it, so "multi-\nlevel" is left alone)
    text = re.sub(r"(\S)[ \t]+[�–—-][ \t]*\n[ \t]*(?=[A-Za-z])", r"\1 – ", text)
    letters = sum(ch.isalpha() for ch in text)
    if not pages or len(text.strip()) < MIN_CHARS_PER_PAGE * len(pages) or letters < 0.5 * len(text.strip()):
        return None
    return text


def extract_markdown(filename: str, data: bytes) -> tuple[str, str]:
    """Returns (markdown, engine)."""
    ext = Path(filename).suffix.lower()
    if ext in (".md", ".txt"):
        return data.decode("utf-8"), "plain-text"
    if ext == ".pdf" and (text := fast_pdf_text(data)):
        return text, "pdf-text"
    if not docling_available():
        raise HTTPException(500, "Docling is not installed (pip install -r requirements-docling.txt)")
    from docling.datamodel.base_models import DocumentStream

    try:
        result = _converter().convert(DocumentStream(name=filename, stream=io.BytesIO(data)))
        md = result.document.export_to_markdown()
    except Exception as e:
        raise HTTPException(422, f"Could not extract text from the document: {str(e)[:200]}")
    return md, "docling"

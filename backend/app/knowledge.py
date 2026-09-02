from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from docx import Document
from pypdf import PdfReader


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    text: str
    method: str
    needs_ocr: bool


@dataclass(frozen=True)
class Chunk:
    ordinal: int
    text: str
    page_start: int
    page_end: int
    content_hash: str
    extraction_method: str


class OcrEngine(Protocol):
    def recognize_pdf_page(self, pdf_path: Path, page_number: int) -> str: ...


def normalize_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def looks_corrupted(text: str) -> bool:
    if len(text.strip()) < 40:
        return True
    control_chars = sum(1 for char in text if ord(char) < 32 and char not in "\n\r\t")
    replacement_like = sum(text.count(char) for char in ("�", "Ӌ", "δ", "൭", "Ҩ"))
    return control_chars > 3 or replacement_like / max(len(text), 1) > 0.01


def extract_pdf_pages(pdf_path: str | Path, ocr: OcrEngine | None = None) -> list[ExtractedPage]:
    path = Path(pdf_path)
    reader = PdfReader(path)
    pages: list[ExtractedPage] = []
    for index, page in enumerate(reader.pages, start=1):
        extracted = normalize_text(page.extract_text() or "")
        needs_ocr = looks_corrupted(extracted)
        method = "pdf_text"
        if needs_ocr and ocr is not None:
            extracted = normalize_text(ocr.recognize_pdf_page(path, index))
            needs_ocr = looks_corrupted(extracted)
            method = "ocr"
        pages.append(ExtractedPage(index, extracted, method, needs_ocr))
    return pages


def chunk_pages(pages: Iterable[ExtractedPage], target_chars: int = 1200) -> list[Chunk]:
    chunks: list[Chunk] = []
    buffer: list[str] = []
    start_page: int | None = None
    end_page: int | None = None
    methods: set[str] = set()

    def flush() -> None:
        nonlocal buffer, start_page, end_page, methods
        text = normalize_text("\n".join(buffer))
        if text and start_page is not None and end_page is not None:
            chunks.append(
                Chunk(
                    ordinal=len(chunks),
                    text=text,
                    page_start=start_page,
                    page_end=end_page,
                    content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    extraction_method="+".join(sorted(methods)),
                )
            )
        buffer, start_page, end_page, methods = [], None, None, set()

    for page in pages:
        if page.needs_ocr or not page.text:
            flush()
            continue
        paragraphs = [item.strip() for item in re.split(r"\n\s*\n", page.text) if item.strip()]
        for paragraph in paragraphs:
            if buffer and sum(len(item) for item in buffer) + len(paragraph) > target_chars:
                flush()
            start_page = start_page or page.page_number
            end_page = page.page_number
            methods.add(page.method)
            buffer.append(paragraph)
    flush()
    return chunks


def extract_docx_paragraphs(docx_path: str | Path) -> list[ExtractedPage]:
    """Represent DOCX paragraphs as locatable blocks using paragraph ordinals."""
    document = Document(Path(docx_path))
    pages: list[ExtractedPage] = []
    for index, paragraph in enumerate(document.paragraphs, start=1):
        text = normalize_text(paragraph.text)
        if text:
            pages.append(ExtractedPage(index, text, "docx_paragraph", False))
    return pages

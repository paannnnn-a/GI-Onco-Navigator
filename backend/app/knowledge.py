from __future__ import annotations

import hashlib
import re
import statistics
import unicodedata
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


@dataclass(frozen=True)
class TranscriptCue:
    start_seconds: int
    end_seconds: int
    text: str


@dataclass(frozen=True)
class TranscriptChunk:
    ordinal: int
    text: str
    start_seconds: int
    end_seconds: int
    content_hash: str


class OcrEngine(Protocol):
    def recognize_pdf_page(self, pdf_path: Path, page_number: int) -> str: ...


def _is_expected_letter(char: str) -> bool:
    codepoint = ord(char)
    return (
        char.isascii()
        or 0x3400 <= codepoint <= 0x9FFF  # CJK ideographs
        or 0xF900 <= codepoint <= 0xFAFF  # CJK compatibility ideographs
        or 0x0370 <= codepoint <= 0x03FF  # Greek symbols used in scientific text
    )


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
    letters = [char for char in text if unicodedata.category(char).startswith("L")]
    unexpected_letters = sum(not _is_expected_letter(char) for char in letters)
    unexpected_ratio = unexpected_letters / max(len(letters), 1)
    return (
        control_chars > 3
        or replacement_like / max(len(text), 1) > 0.01
        or (len(letters) >= 20 and unexpected_ratio > 0.03)
    )


def audit_pdf(pdf_path: str | Path) -> dict[str, object]:
    """Return non-content PDF extraction metrics safe to store in source metadata."""
    path = Path(pdf_path)
    pages = extract_pdf_pages(path)
    character_counts = [len(page.text) for page in pages]
    pages_needing_ocr = [page.page_number for page in pages if page.needs_ocr]
    return {
        "filename": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "size_bytes": path.stat().st_size,
        "pages": len(pages),
        "text_characters": sum(character_counts),
        "median_characters_per_page": (
            int(statistics.median(character_counts)) if character_counts else 0
        ),
        "readable_text_pages": len(pages) - len(pages_needing_ocr),
        "pages_needing_ocr_count": len(pages_needing_ocr),
        "pages_needing_ocr": pages_needing_ocr,
    }


def extract_pdf_pages(pdf_path: str | Path, ocr: OcrEngine | None = None) -> list[ExtractedPage]:
    path = Path(pdf_path)
    reader = PdfReader(path)
    pages: list[ExtractedPage] = []
    for index, page in enumerate(reader.pages, start=1):
        extracted = normalize_text(page.extract_text() or "")
        needs_ocr = looks_corrupted(extracted)
        pages.append(ExtractedPage(index, extracted, "pdf_text", needs_ocr))
    if ocr is not None:
        pending = [page.page_number for page in pages if page.needs_ocr]
        batch_method = getattr(ocr, "recognize_pdf_pages", None)
        if callable(batch_method):
            recognized = batch_method(path, pending)
        else:
            recognized = {number: ocr.recognize_pdf_page(path, number) for number in pending}
        pages = [
            ExtractedPage(
                page.page_number,
                normalize_text(recognized.get(page.page_number, "")),
                "ocr",
                looks_corrupted(normalize_text(recognized.get(page.page_number, ""))),
            )
            if page.needs_ocr
            else page
            for page in pages
        ]
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


def _timestamp_seconds(value: str) -> int:
    parts = value.strip().replace(",", ".").split(":")
    if len(parts) == 2:
        hours, minutes, seconds = 0, int(parts[0]), float(parts[1])
    elif len(parts) == 3:
        hours, minutes, seconds = int(parts[0]), int(parts[1]), float(parts[2])
    else:
        raise ValueError(f"invalid subtitle timestamp: {value}")
    return round(hours * 3600 + minutes * 60 + seconds)


def extract_transcript_cues(path: str | Path) -> list[TranscriptCue]:
    """Parse SRT or WebVTT; subtitle content is data, never application instructions."""
    raw = Path(path).read_text(encoding="utf-8-sig")
    blocks = re.split(r"\r?\n\s*\r?\n", raw.strip())
    cues: list[TranscriptCue] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines or lines[0].upper().startswith("WEBVTT"):
            continue
        timing_index = next((index for index, line in enumerate(lines) if "-->" in line), None)
        if timing_index is None:
            continue
        start_raw, end_raw = (item.strip().split()[0] for item in lines[timing_index].split("-->", 1))
        text = normalize_text(" ".join(re.sub(r"<[^>]+>", "", line) for line in lines[timing_index + 1 :]))
        if text:
            cues.append(TranscriptCue(_timestamp_seconds(start_raw), _timestamp_seconds(end_raw), text))
    return cues


def chunk_transcript(cues: Iterable[TranscriptCue], target_chars: int = 800) -> list[TranscriptChunk]:
    chunks: list[TranscriptChunk] = []
    buffer: list[TranscriptCue] = []

    def flush() -> None:
        nonlocal buffer
        if not buffer:
            return
        text = normalize_text(" ".join(item.text for item in buffer))
        chunks.append(
            TranscriptChunk(
                ordinal=len(chunks), text=text, start_seconds=buffer[0].start_seconds,
                end_seconds=buffer[-1].end_seconds,
                content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            )
        )
        buffer = []

    for cue in cues:
        if buffer and sum(len(item.text) for item in buffer) + len(cue.text) > target_chars:
            flush()
        buffer.append(cue)
    flush()
    return chunks

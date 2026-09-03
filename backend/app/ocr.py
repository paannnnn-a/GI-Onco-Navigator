from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path


class RapidOcrEngine:
    """Optional, fully local Chinese OCR adapter for scanned PDFs."""

    def __init__(self, zoom: float = 2.5) -> None:
        try:
            import pymupdf as fitz
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as exc:
            raise RuntimeError(
                "OCR dependencies are missing; install the project with `pip install -e .[ocr]`"
            ) from exc
        self._fitz = fitz
        self._engine = RapidOCR()
        self.zoom = zoom

    def recognize_pdf_page(self, pdf_path: Path, page_number: int) -> str:
        return self.recognize_pdf_pages(pdf_path, [page_number]).get(page_number, "")

    def recognize_pdf_pages(
        self, pdf_path: Path, page_numbers: Iterable[int]
    ) -> dict[int, str]:
        requested = list(page_numbers)
        if any(page_number < 1 for page_number in requested):
            raise ValueError("page_number is one-based")
        recognized: dict[int, str] = {}
        document = self._fitz.open(pdf_path)
        try:
            for page_number in requested:
                page = document.load_page(page_number - 1)
                matrix = self._fitz.Matrix(self.zoom, self.zoom)
                pixmap = page.get_pixmap(matrix=matrix, alpha=False)
                result, _ = self._engine(pixmap.tobytes("png"))
                recognized[page_number] = (
                    "\n".join(str(line[1]) for line in result if len(line) >= 2)
                    if result
                    else ""
                )
        finally:
            document.close()
        return recognized

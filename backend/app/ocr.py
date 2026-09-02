from __future__ import annotations

from pathlib import Path


class RapidOcrEngine:
    """Optional, fully local Chinese OCR adapter for scanned PDFs."""

    def __init__(self, zoom: float = 2.5) -> None:
        try:
            import fitz
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as exc:
            raise RuntimeError(
                "OCR dependencies are missing; install the project with `pip install -e .[ocr]`"
            ) from exc
        self._fitz = fitz
        self._engine = RapidOCR()
        self.zoom = zoom

    def recognize_pdf_page(self, pdf_path: Path, page_number: int) -> str:
        if page_number < 1:
            raise ValueError("page_number is one-based")
        document = self._fitz.open(pdf_path)
        try:
            page = document.load_page(page_number - 1)
            matrix = self._fitz.Matrix(self.zoom, self.zoom)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            result, _ = self._engine(pixmap.tobytes("png"))
        finally:
            document.close()
        if not result:
            return ""
        return "\n".join(str(line[1]) for line in result if len(line) >= 2)

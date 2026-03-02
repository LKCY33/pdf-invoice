from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz  # pymupdf
from paddleocr import PaddleOCR


@dataclass
class OcrResult:
    pages: int
    text: str


_OCR: PaddleOCR | None = None


def _get_ocr() -> PaddleOCR:
    global _OCR
    if _OCR is None:
        # Chinese simplified by default; keep it lightweight.
        _OCR = PaddleOCR(use_angle_cls=True, lang="ch")
    return _OCR


def ocr_pdf(pdf_path: Path, max_pages: int = 2, dpi: int = 300) -> OcrResult:
    doc = fitz.open(pdf_path)
    try:
        n_pages = doc.page_count
        limit = min(n_pages, max_pages)
        ocr = _get_ocr()
        parts: list[str] = []
        for i in range(limit):
            page = doc.load_page(i)
            mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img_bytes = pix.tobytes("png")

            res = ocr.ocr(img_bytes, cls=True)
            # res format: list[list[ [box], (text, score) ]]
            for line in res[0] if res else []:
                if not line or len(line) < 2:
                    continue
                txt, score = line[1]
                if txt:
                    parts.append(txt)
        return OcrResult(pages=n_pages, text="\n".join(parts))
    finally:
        doc.close()

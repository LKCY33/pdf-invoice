from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz  # pymupdf


@dataclass
class TextExtraction:
    pages: int
    text: str


def extract_text_pymupdf(pdf_path: Path, max_pages: int | None = None) -> TextExtraction:
    doc = fitz.open(pdf_path)
    try:
        n_pages = doc.page_count
        limit = n_pages if max_pages is None else min(n_pages, max_pages)
        parts: list[str] = []
        for i in range(limit):
            page = doc.load_page(i)
            parts.append(page.get_text("text"))
        return TextExtraction(pages=n_pages, text="\n\n".join(parts))
    finally:
        doc.close()

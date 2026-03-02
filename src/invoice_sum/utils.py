from __future__ import annotations

import hashlib
from decimal import Decimal, InvalidOperation
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_decimal(s: str) -> Decimal:
    # Accept common formats like "1,234.56" and "￥123.45".
    cleaned = (
        s.replace(",", "")
        .replace("￥", "")
        .replace("¥", "")
        .replace("RMB", "")
        .replace("CNY", "")
        .strip()
    )
    try:
        return Decimal(cleaned)
    except InvalidOperation as e:
        raise ValueError(f"invalid decimal: {s!r}") from e

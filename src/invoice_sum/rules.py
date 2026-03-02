from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from .utils import parse_decimal


_AMOUNT_RE = re.compile(r"(?P<num>\d{1,3}(?:,\d{3})*(?:\.\d{2})|\d+(?:\.\d{2}))")

# Ordered from strongest signal -> weakest.
_KEY_PATTERNS = [
    r"价税合计\s*\(小写\)",
    r"价税合计",
    r"合计金额",
    r"应付金额",
    r"合计\s*\(小写\)",
    r"总计",
    r"合计",
]


@dataclass
class ExtractedAmount:
    amount: str
    confidence: float
    evidence: str


def _find_amount_near(text: str, key_re: re.Pattern[str], window: int = 120) -> list[ExtractedAmount]:
    out: list[ExtractedAmount] = []
    for m in key_re.finditer(text):
        start = max(0, m.start() - window)
        end = min(len(text), m.end() + window)
        snippet = text[start:end]
        for am in _AMOUNT_RE.finditer(snippet):
            raw = am.group("num")
            try:
                d: Decimal = parse_decimal(raw)
            except ValueError:
                continue
            if d < 0:
                continue
            out.append(
                ExtractedAmount(
                    amount=str(d),
                    confidence=0.85,
                    evidence=snippet.strip().replace("\n", " ")[:240],
                )
            )
    return out


def extract_total_amount(text: str) -> Optional[ExtractedAmount]:
    # Normalize whitespace.
    t = re.sub(r"[\t\r\f\v]+", " ", text)

    candidates: list[ExtractedAmount] = []
    for kp in _KEY_PATTERNS:
        key_re = re.compile(kp)
        hits = _find_amount_near(t, key_re)
        if hits:
            # Earlier keys are more reliable.
            bump = 0.1 * max(0, 3 - _KEY_PATTERNS.index(kp))
            for h in hits:
                h.confidence = min(0.99, h.confidence + bump)
            candidates.extend(hits)
            break

    if not candidates:
        return None

    # Choose the max amount as heuristic if multiple are present.
    def _as_decimal(s: str) -> Decimal:
        return parse_decimal(s)

    best = max(candidates, key=lambda c: _as_decimal(c.amount))
    return best

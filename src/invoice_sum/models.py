from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


DocType = Literal["text", "scan"]
Method = Literal["text_rule", "ocr_rule", "llm_fallback", "failed"]


class InvoiceFields(BaseModel):
    total_amount: Optional[str] = None
    currency: Optional[str] = None
    invoice_no: Optional[str] = None
    date: Optional[str] = None


class ResultRecord(BaseModel):
    ts: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    file: str
    sha256: str
    pages: int
    doc_type: DocType
    attempt: int
    method: Method
    fields: InvoiceFields = Field(default_factory=InvoiceFields)
    confidence: float = 0.0
    evidence: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

import requests


@dataclass
class LlmExtraction:
    total_amount: Optional[str]
    currency: Optional[str]
    confidence: float
    evidence: list[str]


SYSTEM_PROMPT = """You extract the final total amount from an invoice.
Return ONLY valid JSON, no markdown, no extra text.
Schema:
{
  \"total_amount\": string|null,  // decimal number like 1234.56
  \"currency\": string|null,      // e.g. CNY
  \"confidence\": number,         // 0..1
  \"evidence\": string[]          // up to 3 short snippets
}
Rules:
- total_amount MUST be the final payable total (e.g. 价税合计/合计金额/总计), not tax-only.
- If unsure, set total_amount=null and confidence<=0.4.
"""


def llm_enabled() -> bool:
    return os.getenv("INVOICE_SUM_LLM", "off").lower() in {"1", "true", "on", "yes"}


def extract_with_llm(text: str) -> LlmExtraction:
    base_url = os.environ["OPENAI_BASE_URL"].rstrip("/")
    api_key = os.environ["OPENAI_API_KEY"]
    model = os.getenv("OPENAI_MODEL", "gpt-5.2")

    url = f"{base_url}/responses"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "text", "text": SYSTEM_PROMPT}],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Extract the final total amount from this invoice text:\n\n" + text[:20000],
                    }
                ],
            },
        ],
        "max_output_tokens": 300,
    }

    r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
    r.raise_for_status()
    data = r.json()

    # Try to locate the first text output.
    out_text = None
    for item in data.get("output", []) or []:
        for c in item.get("content", []) or []:
            if c.get("type") == "output_text" and c.get("text"):
                out_text = c["text"]
                break
        if out_text:
            break

    if not out_text:
        return LlmExtraction(total_amount=None, currency=None, confidence=0.0, evidence=["no output_text"])

    try:
        obj = json.loads(out_text)
    except json.JSONDecodeError:
        return LlmExtraction(total_amount=None, currency=None, confidence=0.0, evidence=["invalid json"])

    total_amount = obj.get("total_amount")
    currency = obj.get("currency")
    confidence = float(obj.get("confidence") or 0.0)
    evidence = obj.get("evidence") or []
    if not isinstance(evidence, list):
        evidence = []
    evidence = [str(x) for x in evidence][:3]

    return LlmExtraction(
        total_amount=str(total_amount) if total_amount is not None else None,
        currency=str(currency) if currency is not None else None,
        confidence=max(0.0, min(1.0, confidence)),
        evidence=evidence,
    )

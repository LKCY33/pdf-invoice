from __future__ import annotations

import argparse
import csv
import os
from decimal import Decimal
from pathlib import Path

from .dotenv import load_dotenv
from .extract_text import extract_text_pymupdf
from .io import append_jsonl, load_jsonl
from .llm import extract_with_llm, llm_enabled
from .models import InvoiceFields, ResultRecord
from .ocr import ocr_pdf
from .rules import extract_total_amount
from .utils import parse_decimal, sha256_file


def _bool(s: str) -> bool:
    return s.lower() in {"1", "true", "yes", "on"}


def main() -> int:
    ap = argparse.ArgumentParser(prog="invoice-sum")
    ap.add_argument("--dir", required=True, help="Directory containing PDF invoices")
    ap.add_argument("--out", default="out", help="Output directory")
    ap.add_argument("--llm", choices=["on", "off"], default=None, help="Enable LLM fallback")
    ap.add_argument("--retry-failed", action="store_true", help="Retry previously failed PDFs")
    ap.add_argument("--reprocess", action="store_true", help="Reprocess all PDFs")
    ap.add_argument("--max-ocr-pages", type=int, default=None, help="Max pages to OCR (default from env)")

    args = ap.parse_args()

    repo_root = Path.cwd()
    load_dotenv(repo_root / ".env")

    if args.llm is not None:
        os.environ["INVOICE_SUM_LLM"] = args.llm

    out_dir = Path(args.out)
    results_path = out_dir / "results.jsonl"
    out_dir.mkdir(parents=True, exist_ok=True)

    existing = list(load_jsonl(results_path))
    latest_by_sha: dict[str, dict] = {}
    for rec in existing:
        sha = rec.get("sha256")
        if not sha:
            continue
        prev = latest_by_sha.get(sha)
        if prev is None or int(rec.get("attempt") or 0) >= int(prev.get("attempt") or 0):
            latest_by_sha[sha] = rec

    pdf_dir = Path(args.dir)
    pdfs = sorted([p for p in pdf_dir.rglob("*.pdf") if p.is_file()])

    max_ocr_pages = args.max_ocr_pages
    if max_ocr_pages is None:
        try:
            max_ocr_pages = int(os.getenv("INVOICE_SUM_MAX_OCR_PAGES", "2"))
        except ValueError:
            max_ocr_pages = 2

    for pdf in pdfs:
        sha = sha256_file(pdf)
        prev = latest_by_sha.get(sha)

        if not args.reprocess and prev is not None:
            if prev.get("method") != "failed" and prev.get("fields", {}).get("total_amount"):
                continue
            if prev.get("method") == "failed" and not args.retry_failed:
                continue

        attempt = int(prev.get("attempt") or 0) + 1 if prev else 1

        # Step 1: classify by text density.
        try:
            te = extract_text_pymupdf(pdf, max_pages=2)
            text = te.text
            pages = te.pages
        except Exception as e:
            rec = ResultRecord(
                file=str(pdf),
                sha256=sha,
                pages=0,
                doc_type="scan",
                attempt=attempt,
                method="failed",
                fields=InvoiceFields(),
                confidence=0.0,
                evidence=[],
                errors=[f"text extract failed: {e}"]
            )
            append_jsonl(results_path, rec)
            latest_by_sha[sha] = rec.model_dump()
            continue

        # Heuristic: if we have a decent amount of text, treat as text PDF.
        doc_type = "text" if len(text.strip()) >= 200 else "scan"

        try:
            if doc_type == "text":
                hit = extract_total_amount(text)
                if hit:
                    rec = ResultRecord(
                        file=str(pdf),
                        sha256=sha,
                        pages=pages,
                        doc_type="text",
                        attempt=attempt,
                        method="text_rule",
                        fields=InvoiceFields(total_amount=hit.amount, currency="CNY"),
                        confidence=hit.confidence,
                        evidence=[hit.evidence],
                        errors=[],
                    )
                    append_jsonl(results_path, rec)
                    latest_by_sha[sha] = rec.model_dump()
                    continue

            # OCR path
            ocr = ocr_pdf(pdf, max_pages=max_ocr_pages)
            hit = extract_total_amount(ocr.text)
            if hit:
                rec = ResultRecord(
                    file=str(pdf),
                    sha256=sha,
                    pages=ocr.pages,
                    doc_type="scan",
                    attempt=attempt,
                    method="ocr_rule",
                    fields=InvoiceFields(total_amount=hit.amount, currency="CNY"),
                    confidence=hit.confidence,
                    evidence=[hit.evidence],
                    errors=[],
                )
                append_jsonl(results_path, rec)
                latest_by_sha[sha] = rec.model_dump()
                continue

            # LLM fallback
            if llm_enabled():
                llm = extract_with_llm(ocr.text if ocr.text.strip() else text)
                if llm.total_amount is not None:
                    # Validate decimal.
                    _ = parse_decimal(llm.total_amount)
                rec = ResultRecord(
                    file=str(pdf),
                    sha256=sha,
                    pages=ocr.pages,
                    doc_type=doc_type,
                    attempt=attempt,
                    method="llm_fallback" if llm.total_amount else "failed",
                    fields=InvoiceFields(total_amount=llm.total_amount, currency=llm.currency or "CNY"),
                    confidence=llm.confidence,
                    evidence=llm.evidence,
                    errors=[] if llm.total_amount else ["llm could not extract total_amount"],
                )
                append_jsonl(results_path, rec)
                latest_by_sha[sha] = rec.model_dump()
                continue

            rec = ResultRecord(
                file=str(pdf),
                sha256=sha,
                pages=pages,
                doc_type=doc_type,
                attempt=attempt,
                method="failed",
                fields=InvoiceFields(),
                confidence=0.0,
                evidence=[],
                errors=["no extraction method succeeded"],
            )
            append_jsonl(results_path, rec)
            latest_by_sha[sha] = rec.model_dump()

        except Exception as e:
            rec = ResultRecord(
                file=str(pdf),
                sha256=sha,
                pages=pages,
                doc_type=doc_type,
                attempt=attempt,
                method="failed",
                fields=InvoiceFields(),
                confidence=0.0,
                evidence=[],
                errors=[f"processing failed: {e}"],
            )
            append_jsonl(results_path, rec)
            latest_by_sha[sha] = rec.model_dump()

    # Aggregate latest successful.
    latest_success: list[dict] = []
    for sha, rec in latest_by_sha.items():
        fields = rec.get("fields") or {}
        amt = fields.get("total_amount")
        if amt:
            try:
                parse_decimal(amt)
            except Exception:
                continue
            latest_success.append(rec)

    # Summaries by currency.
    totals: dict[str, Decimal] = {}
    for rec in latest_success:
        fields = rec.get("fields") or {}
        cur = (fields.get("currency") or "CNY").upper()
        amt = parse_decimal(fields["total_amount"])
        totals[cur] = totals.get(cur, Decimal("0")) + amt

    # Write CSV
    csv_path = out_dir / "invoices.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["file", "sha256", "method", "doc_type", "total_amount", "currency", "confidence"],
        )
        w.writeheader()
        for rec in sorted(latest_success, key=lambda r: r.get("file", "")):
            fields = rec.get("fields") or {}
            w.writerow(
                {
                    "file": rec.get("file"),
                    "sha256": rec.get("sha256"),
                    "method": rec.get("method"),
                    "doc_type": rec.get("doc_type"),
                    "total_amount": fields.get("total_amount"),
                    "currency": (fields.get("currency") or "CNY").upper(),
                    "confidence": rec.get("confidence"),
                }
            )

    # Write summary.json
    summary_path = out_dir / "summary.json"
    failed = [r for r in latest_by_sha.values() if r.get("method") == "failed"]
    import json

    summary = {
        "files_total": len(pdfs),
        "files_success": len(latest_success),
        "files_failed": len(failed),
        "totals": {k: str(v) for k, v in totals.items()},
        "failed": [{"file": r.get("file"), "sha256": r.get("sha256"), "errors": r.get("errors")} for r in failed],
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

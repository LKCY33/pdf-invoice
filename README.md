# invoice-sum

Lightweight CLI to extract invoice totals from a directory of PDFs and compute sums.

Approach:
- Prefer text extraction from PDF when available.
- Fallback to OCR for scanned PDFs.
- Optional LLM-based extraction as the last resort.
- Persist results as JSONL; compute totals using code (`decimal.Decimal`).

## Quick start

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

python -m invoice_sum --dir /path/to/invoices --out out --llm off
```

## Output

- `out/results.jsonl`: one JSON per processed PDF (append-only)
- `out/invoices.csv`: latest successful extraction per file
- `out/summary.json`: totals + stats

## Status

MVP scaffold.

# invoice-sum

Lightweight CLI to extract invoice totals from a directory of PDFs and compute sums.

Approach:
- Prefer text extraction from PDF when available.
- Fallback to OCR for scanned PDFs.
- Optional LLM-based extraction as the last resort.
- Persist results as JSONL; compute totals using code (`decimal.Decimal`).

## Setup

1) Create a virtualenv and install deps

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

2) Configure LLM fallback (optional)

- Copy `.env.template` to `.env`
- Fill in `OPENAI_API_KEY`

```bash
cp .env.template .env
$EDITOR .env
```

Notes:
- `.env` is ignored by git (safe to keep keys locally).
- If you don't want LLM fallback, keep `INVOICE_SUM_LLM=off`.

## Run

```bash
python -m invoice_sum --dir /path/to/invoices --out out
```

Enable LLM fallback explicitly:

```bash
python -m invoice_sum --dir /path/to/invoices --out out --llm on
```

## Output

- `out/results.jsonl`: one JSON per processed PDF (append-only)
- `out/invoices.csv`: latest successful extraction per file
- `out/summary.json`: totals + stats

## Status

MVP scaffold.

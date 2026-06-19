# OCR-Scanned PDFs — Quality Scoring

PDF quality assessment for the book pipeline. Not all PDFs with >500 chars are good
text — pre-19th-century documents often have OCR layers with millions of chars but
degraded text (long-s → f, garbled headers, mixed Latin/Gothic scripts).

## 3-Tier Quality Check

```
pymupdf char count per PDF
  │
  ├── < 500 chars → SCANNED (pure images) → queue for OCR, do NOT ticket
  │
  ├── 500+ chars → quality_score(sample=16 pages)
  │     ├── score < 80 → DEGRADED OCR → queue for fresh OCR, do NOT ticket
  │     └── score ≥ 80 → GOOD TEXT → ticket for normal processing
  │
  └── .epub/.mobi/.azw3 → always ticket (extractable, no OCR needed)
```

## quality_score() Function

Samples 16 pages evenly distributed across the PDF. For each page:
- Extract text with pymupdf
- Score based on: ratio of printable chars, common OCR error patterns
  (long-s→f, rn→m, cl→d), character n-gram frequency vs expected language
- Returns 0-100, where ≥80 = good enough for direct processing

Threshold determined empirically from the Fomenko/Nosovskiy PDFs where
500K+ chars existed but text was heavily degraded (long-s substitutions,
garbled chapter headers). Score dropped below 80 despite high char count.

## OCR Pipeline

When a PDF is queued for OCR:
- marker-pdf: 8+ GB RAM baseline (5 models, ~6.7 GB loaded)
- Server: 11 GB RAM → 1 page per invocation only (79s per page)
- 626-page book ≈ 12h estimated
- Strategy: chain OCR ticket AFTER all digital book tickets (--parent)
- Lighter alternatives: Tesseract (~200 MB), EasyOCR (~2-3 GB)

## Queue File

Scanned/degraded PDFs → `/root/.hermes/queues/ocr_books.txt`
Process when OCR-capable infra is available (≥16 GB RAM or external API).

## Related

- `books-extraction.md` — Full book pipeline
- `detection-model.md` — Complete detection + pre-flight model
- SKILL.md — "PDF pre-flight: 3-tier quality check mandatory"

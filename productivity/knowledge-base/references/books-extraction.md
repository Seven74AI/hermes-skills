# Book Extraction for Knowledge Base

Extract, summarize, and fact-check books (ePub, PDF) into structured Obsidian notes.

**This reference is the authoritative book extraction pipeline.** It absorbed the standalone `book-extraction` skill (2026-07-05 consolidation). Load `knowledge-base` skill; this reference provides the book-specific pipeline.

## Prerequisites

- `ebooklib` + `beautifulsoup4` — for ePub
- `pymupdf` — for PDF
- `obsidian` skill — for vault operations
- `knowledge-base` skill — for template and categories

## Triggers

- User sends an `.epub`, `.pdf`, or `.mobi` file (Telegram blocks `.epub` — user must rename to `.zip` or send via scp)
- User provides a path to a book file on the server
- Remote PDF URL (use `web_extract` first, fall back to local download + pymupdf)

### MOBI format

MOBI files are handled like ePubs: text-based, no pre-flight needed, ticket directly. If `ebooklib` can't parse a MOBI, convert to ePub first with Calibre:

```bash
ebook-convert input.mobi /tmp/output.epub
```

Then follow the ePub extraction pipeline.

## Delegation rule — when to route through Planner

**Do NOT process books inline when ANY of these are true:**

| Condition | Why |
|-----------|-----|
| Massive document | 1000+ pages / 40MB+ PDF — extraction alone can timeout, reading burns 20+ turns |
| Multi-book batch | 3+ books in one archive — NEVER process inline. Create one kanban ticket per book directly (see Batch Book Dispatch below). |
| Huge single book | 150K+ words — would exhaust iteration budget on read_file calls alone. Route to Planner. |
| User says "donne ça au planner" | Explicit delegation request — respect it immediately |
| User says "make a planner ticket" | Same — create the ticket, don't process inline |

### Batch Book Dispatch — multi-book archives

When the user drops a Mega link, zip, or directory containing 3+ books:

1. Download and extract the archive
2. **Pre-flight — OCR quality check on all PDFs (3 tiers).** ePubs and MOBIs are always text-based and skip this step. Run the batch script:

   ```bash
   python3 scripts/pdf_preflight.py /tmp/mega_books/
   ```

   This runs Tier 1 (binary scan detection) + Tier 2 (quality scoring) on every PDF in the directory and prints a summary grouped by verdict: CLEAN (≥80, ticket), DEGRADED (60-79, queue), BAD (<60, queue), SCANNED (0 chars, queue). See `references/ocr-scanned-pdfs.md` for the full scoring methodology and the long-s trap.

   **⛔ NEVER write a DIY scoring function.** Always use `scripts/pdf_preflight.py` — it contains the canonical `quality_score_pdf()` with the authoritative LONG_S_WORDS dictionary and scoring formula (`100 − long_s×0.5 − garbled_pages×5`). A DIY function WILL produce different (usually wrong) scores and the user WILL catch it.

   **Readability spot-check.** After scoring, for each CLEAN PDF sample-read 3 pages: beginning (page ~5, skip copyright/TOC), middle (~page_count//2), and end (~last-5 pages). Read ~500 chars from each via pymupdf. Verify the text is semantically coherent — a PDF can score 100/100 and still be garbage (wrong-language OCR, DRM'd text, watermarked pages, actual gibberish that happens to have valid words). Flag and discuss any PDF that looks unreadable BEFORE creating tickets. The user expects this visual confirmation.

3. **For CLEAN PDFs + all ePubs + all MOBIs:** Create **one ticket per book** on `knowledge-base` board with `--assignee researcher`, `--skill knowledge-base`, `--max-runtime 3600`. No `--parent` chaining. Use `execute_code` with `subprocess.run()` to batch-create tickets (never `$(cat /tmp/body.txt)` in shell).

   For temp files, use safe indexed names: `/tmp/ticket_body_{idx:04d}.txt`
   Template: knowledge-base skill `templates/kanban-ticket-template.md` → Book ticket body template

4. **For DEGRADED, BAD, or SCANNED PDFs:** Do NOT create a kanban ticket. Instead:
   - Upload the PDF to MinIO: `mc cp <file> minio/knowledge-base/books/<slug>.pdf`
   - Append to the OCR queue: `echo "title | author | pages | reason (score X/100 or fully scanned) | minio://<slug>.pdf" >> /root/.hermes/queues/ocr_books.txt`
   - Tell the user it's queued
   - marker-pdf's ~8 GB model load will OOM-loop kanban workers on 11 GB servers

5. Sync skills after: `bash /root/.hermes/skills/productivity/knowledge-base/scripts/sync-to-profiles.sh`

## Pipeline

### Step 1: Get the file

**If sent via Telegram as .zip (ePub renamed):**

Single book:
```bash
cp "/root/.hermes/cache/documents/doc_"*"_"*".zip" /tmp/book.zip
cd /tmp && unzip -o book.zip -d book_extract
EPUB=$(find /tmp/book_extract -name "*.epub" -not -path "*/__MACOSX/*" | head -1)
```

**If sent via scp or already on server:** Use path directly.

### Step 2: Extract text

#### ePub (ebooklib)

```bash
python3 -c "
from ebooklib import epub
from bs4 import BeautifulSoup

book = epub.read_epub('PATH_TO_EPUB')
from ebooklib import ITEM_DOCUMENT
items = list(book.get_items_of_type(ITEM_DOCUMENT))

all_text = []
for i, item in enumerate(items):
    soup = BeautifulSoup(item.get_body_content(), 'html.parser')
    text = soup.get_text(separator='\n')
    chars = len(text.strip())
    if chars > 100:
        all_text.append((i, chars, text.strip()))

all_text.sort(key=lambda x: -x[1])

with open('/tmp/book_full.txt', 'w') as f:
    for idx, chars, text in all_text:
        f.write(f'\n\n=== CHAPTER {idx} ===\n\n')
        f.write(text)

total = sum(c for _, c, _ in all_text)
print(f'Chapters: {len(all_text)}, Total: {total:,} chars (~{total//5:,} words)')
"
```

#### PDF (pymupdf) — text extraction + quality check

**First, run the full 3-tier quality check** (see `references/ocr-scanned-pdfs.md`):

```bash
# Tier 1: binary check
python3 -c "
import pymupdf
doc = pymupdf.open('PATH_TO_PDF')
total = sum(len(doc[i].get_text().strip()) for i in range(doc.page_count))
print(f'{doc.page_count} pages, {total} chars')
"
```

If `total < 500` chars → **SCANNED.** Queue for OCR, do NOT create a ticket.

If `total ≥ 500` chars → **run Tier 2 quality scoring** from `references/ocr-scanned-pdfs.md`. Score < 80 = degraded OCR → queue for fresh OCR. Score ≥ 80 = clean text → proceed.

```
python3 -c "
import pymupdf
doc = pymupdf.open('PATH_TO_PDF')
text = ''
for page in doc:
    text += page.get_text() + '\n'
with open('/tmp/book_full.txt', 'w') as f:
    f.write(text)
print(f'Saved: {len(text):,} chars')
"
```

#### Scanned PDF — marker-pdf with `--page_range` chunking

**marker-pdf loads ~8 GB of models at startup regardless of page count.** Even 1 page needs 8 GB. On 11 GB servers, only single-page batches are safe.

```bash
for page in $(seq 0 625); do
  marker_single --page_range "${page}-${page}" \
    --output_dir /tmp/ocr_chunks/chunk_${page} \
    --output_format markdown --disable_image_extraction \
    --disable_multiprocessing \
    /tmp/books_batch/scanned_book.pdf
done

for f in /tmp/ocr_chunks/chunk_*/scanned_book/*.md; do cat "$f"; echo; done > /tmp/book_full.txt
```

### Step 3: Read the ENTIRE book — NOT just samples

**⚠️ CRITICAL: Sampling 3-5 chapters produces garbage summaries.** A 100K-word book requires reading ~2,000-3,000 lines of extracted text across multiple `read_file` passes. Plan for 5-10 read_file calls.

**Reading strategy:**
1. **First pass — structure discovery:** Read first 300 lines of the largest chapter.
2. **Systematic read-through:** Read in 200-300 line chunks through ALL chapters.
3. **End of book:** Always read the last 300-500 lines — author bios, glossaries, appendices live there.
4. **Batch reads:** Use multiple parallel `read_file` calls.

**Extract from every section:** main claims, clinical cases, evidence cited, author credentials, controversial positions, treatment protocols, diagnostic methods.

### Step 4: Research and verify

- `web_search` for the author's credentials and reputation
- `web_search` for key claims
- Cross-reference with existing knowledge base notes

### Step 5: Create the note

Use the `knowledge-base` template. Save to `Knowledge base/`. See `templates/book-note-template.md`.

**Size target:** A proper book note is 15,000-25,000 characters. Under 5,000 chars = you haven't read enough.

### Step 6: Push to Git

```bash
cd "$OBSIDIAN_VAULT_PATH" && git add -A && git commit -m "add: <slug> — <author> (book)" && git push
```

## Pitfalls

- **DIY quality scoring — always use the canonical algorithm.** The `references/ocr-scanned-pdfs.md` reference contains the canonical LONG_S_WORDS dictionary and scoring formula. Never write your own.
- **Batch book tickets — same-topic misidentification.** Include a unique content fingerprint in each ticket body (distinctive first-sentence quote, unique chapter title, dedication text). Verify note frontmatter `source` matches the assigned book before pushing.
- **Telegram blocks .epub** — tell user to rename to .zip or use scp.
- **The long-s trap — degraded OCR that passes binary checks.** 17th-18th century PDFs often have an OCR text layer (millions of chars) but quality is terrible. Always run Tier 2 quality scoring.
- **PDFs can be scanned images OR degraded OCR** — two distinct failure modes. Tier 1 catches scanned, Tier 2 catches degraded.
- **French books often have accented characters in filenames** — use wildcard glob or `find` instead of exact paths.
- **SAMPLING IS NOT ENOUGH.** Read EVERY chapter. Budget 5-10 read_file calls.
- **The end of the book is the most valuable part** — NEVER skip the last 500 lines.
- **Don't save the full text to the vault** — it's too large. Save to `/tmp/`.
- **Batch your read_file calls** — use multiple parallel `read_file` calls in one turn.
- **marker-pdf OOM on scanned PDFs** — Do NOT create kanban tickets for scanned PDFs. Use single-page `--page_range` batches.
- **Incomplete chapter in existing KB note → re-extract only that chapter.** See `references/targeted-chapter-extraction.md` for the full pattern.
- **Confidence calibration** — a single book by one author is at most ⚠️ plausible unless claims are independently verified.

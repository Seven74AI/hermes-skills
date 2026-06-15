# Book Extraction — ePub & PDF

Pipeline for processing books into the knowledge base. Books are 50-150K words — never read the full text in context. Read chapter by chapter, extract key claims, synthesize.

## Supported formats

| Format | Tool | Install |
|--------|------|---------|
| ePub | `ebooklib` + `beautifulsoup4` | `pip install ebooklib beautifulsoup4` |
| PDF (text) | `pymupdf` | `pip install pymupdf` |
| PDF (scanned/OCR) | `marker-pdf` | `pip install marker-pdf` (~5GB) |

## Receiving books via Mega archive

When the user sends a Mega.nz link to a zip archive of books:

### Step A: Download the archive

**Primary method — megadl (megatools).** No Python dependency, works on all versions:

```bash
mkdir -p /tmp/book_archives
megadl "https://mega.nz/file/FILE_ID#FILE_KEY" --path /tmp/book_archives/batch_<YYYYMMDD>.zip
```

Check file was written: `ls -la /tmp/book_archives/batch_<YYYYMMDD>.zip`

**Fallback — mega.py** (broken on Python ≥3.12 — `asyncio.coroutine` removed):

```python
from mega import Mega
import shutil

m = Mega()
f = m.download_url('https://mega.nz/file/FILE_ID#FILE_KEY')
shutil.move(f, '/tmp/book_archives/batch_<YYYYMMDD>.zip')
```

### Step B: Extract to a CLEAN directory

**Always use a fresh, empty directory.** Never extract into a pre-existing directory — it may contain stale books from a prior session, and you will misreport them as new.

```bash
rm -rf /tmp/books_extracted
mkdir -p /tmp/books_extracted
unzip /tmp/books_archive_<batch>.zip -d /tmp/books_extracted
```

### Step C: Identify books

List only the book files (ePub, PDF, MOBI, AZW3) and present them to the user for confirmation before creating tickets:

```bash
find /tmp/books_extracted -type f \( -iname "*.epub" -o -iname "*.pdf" -o -iname "*.mobi" -o -iname "*.azw3" \) | sort
```

Keep the files in `/tmp/books_extracted/` — workers will access them from there. Each ticket body references the full path.

## ePub pipeline

### Step 0: Use unique temp paths

**CRITICAL: Multiple book workers run in parallel. NEVER use `/tmp/book.epub` — use a unique path to avoid race conditions.**

```bash
SLUG="<book-slug>"
BOOK_EPUB="/tmp/book_${SLUG}.epub"
BOOK_TXT="/tmp/book_${SLUG}_full.txt"
```

### Step 1: User sends the file

Telegram blocks `.epub` — user must rename to `.zip` before uploading, or use `scp`.

```bash
unzip -o /tmp/book.zip -d /tmp/book_output
```

### Step 2: Extract full text

```python
from ebooklib import epub
from bs4 import BeautifulSoup
import os

# Use unique paths — multiple book workers run in parallel!
BOOK_EPUB = os.environ.get('BOOK_EPUB', '/tmp/book_<slug>.epub')
BOOK_TXT = os.environ.get('BOOK_TXT', '/tmp/book_<slug>_full.txt')

book = epub.read_epub(BOOK_EPUB)

items = list(book.get_items_of_type(9))  # ITEM_DOCUMENT
all_text = []
total_chars = 0

for i, item in enumerate(items):
    soup = BeautifulSoup(item.get_content(), 'html.parser')
    text = soup.get_text(separator='\n').strip()
    chars = len(text)
    total_chars += chars
    all_text.append((i, chars, text))

# Sort by size (biggest = main content chapters)
all_text.sort(key=lambda x: -x[1])

# Save full text for reference — PRESERVE CHAPTER ORDER, don't sort by size
# Keep the size-sorted list for analysis but save in original order
# Use unique path (BOOK_TXT), not /tmp/book_full.txt — parallel workers will overwrite!
with open(BOOK_TXT, 'w') as f:
    for i, item in enumerate(items):
        soup = BeautifulSoup(item.get_content(), 'html.parser')
        text = soup.get_text(separator='\n').strip()
        chars = len(text)
        if chars > 100:
            f.write(f'\n\n=== CHAPTER {i} ({chars:,} chars) ===\n\n{text}')

# Also print chapter sizes sorted for quick analysis
sorted_chapters = sorted(all_text, key=lambda x: -x[1])
print(f'\nChapter sizes (sorted):')
for idx, chars, text in sorted_chapters[:10]:
    preview = text[:80].replace('\n', ' ')
    print(f'  Ch.{idx}: {chars:,} chars — {preview}...')

# Metadata
title = book.get_metadata('DC', 'title')
author = book.get_metadata('DC', 'creator')
print(f'Title: {title[0][0] if title else "?"}')
print(f'Author: {author[0][0] if author else "?"}')
print(f'Total: {total_chars:,} chars (~{total_chars//5:,} words)')
print(f'Chapters: {len(items)}')
```

### Step 3: Read EVERY chapter in full — no sampling, no exceptions

**Read the entire book.** Every chapter, every page. No sampling, no "key passages only," no "start with the top 5 by size."

**How:** Use `read_file` with `offset` and `limit` to read the full extracted text (the file at `BOOK_TXT`) in chunks if needed. For short books, read it all in one pass. For long books (100K+ words), read across multiple turns — the user will wait.

**Never sample.** The user has been explicit: "On lit tout pas d'échantillonnage." Sampling means you will miss content, miss quotes, and produce a note that's too shallow. The user will ask you to redo it. Read everything the first time.

**Focus on extracting:**
- The author's own words — direct quotes with chapter numbers
- Claims the author makes (especially controversial or novel ones)
- Statistics, studies cited
- Clinical advice, treatment protocols, patient case studies
- The author's framing: why they wrote the book, what they think they discovered

**Verify coverage:** After reading, confirm you've read every chapter. Count them against the epub metadata.

### Step 4: Create structured note

**Load the template first:** `skill_view(name='knowledge-base', file_path='templates/book-note-template.md')`

Save to `Knowledge base/<slug>.md`. The template defines the required structure. Key sections that MUST be populated:

### Step 5: Upload source to MinIO

**Always upload. Do not skip this step.** The source file (ePub/PDF) and extracted full text must be archived in MinIO so the note can link back to the original.

```bash
# Upload original ebook — use unique path, not /tmp/book.epub!
mc cp "$BOOK_EPUB" "minio/knowledge-base/books/<slug>.epub"

# Upload extracted full text (with chapters preserved)
mc cp "$BOOK_TXT" "minio/knowledge-base/books/<slug>.txt"

# Verify both uploaded
mc ls "minio/knowledge-base/books/<slug>"
```

For PDFs, same pattern: `mc cp /tmp/book.pdf "minio/knowledge-base/books/<slug>.pdf"`

**File naming:** Use the same slug as the note filename (matching what goes in `source_file` frontmatter).

### Step 6: Create structured note

**Load the template first:** `skill_view(name='knowledge-base', file_path='templates/book-note-template.md')`

Save to `Knowledge base/<slug>.md`. The template defines the required structure. **Fill in `source_file` frontmatter** with the MinIO URL of the original ebook:

```yaml
source_file: http://vmi3304846.tail5c02a1.ts.net:9000/knowledge-base/books/<slug>.epub
```

Also mention the archived files in the **Sources** section of the note:
```
- Original file archived: http://vmi3304846.tail5c02a1.ts.net:9000/knowledge-base/books/<slug>.epub
- Full extracted text archived: http://vmi3304846.tail5c02a1.ts.net:9000/knowledge-base/books/<slug>.txt (~XK chars, ~XK words, X chapters)
```

### Step 7: Push to Git

```bash
cd "$OBSIDIAN_VAULT_PATH"
git add -A
git commit -m "add: <slug> — <author> (livre, ~XK mots)"
git push
```

## PDF pipeline

For PDFs, use the `ocr-and-documents` skill. `pymupdf` for text-based PDFs, `marker-pdf` for scanned/OCR. Then follow the same reading and structuring steps as ePub (Step 3-7 above).

### Pre-flight OCR check — scan ALL PDFs BEFORE creating tickets

Before creating any book tickets, scan every PDF in the batch to determine which need OCR. Use `execute_code` to batch-check all PDFs in one turn:

```python
# Efficient batch scan — checks every PDF's extractable text in one pass
from hermes_tools import terminal
import glob

for pdf in sorted(glob.glob("/tmp/books_batch/*.pdf")):
    out = terminal(
        f"python3 -c \"import pymupdf; doc=pymupdf.open('{pdf}'); "
        f"total=sum(len(doc[i].get_text().strip()) for i in range(doc.page_count)); "
        f"print(f'{{doc.page_count}}|{{total}}')\"",
        timeout=60
    )
    name = os.path.basename(pdf)[:80]
    pages, chars = out['output'].strip().split('|')
    needs_ocr = int(chars) < 500
    print(f"{'⚠️ OCR' if needs_ocr else '✓ text'} | {pages}p | {int(chars):,} chars | {name}")
```

PDFs with < 500 chars total across all pages are fully scanned (images only) — they need OCR. PDFs with substantial text can be processed directly with pymupdf.

### Scanned PDF / OCR pipeline

When a PDF is confirmed scanned (pymupdf returns < 500 chars), `marker-pdf` is the OCR tool.

**⚠️ CRITICAL MEMORY CONSTRAINT:** `marker-pdf` loads OCR/detection models that consume **8+ GB RAM at baseline** — regardless of how many pages you process. The models are loaded before page processing begins, so `--page_range` chunks do NOT reduce model memory. `--disable_multiprocessing` also doesn't help significantly.

**Server sizing rule:** marker-pdf needs ≥ 12 GB free RAM to run safely (8 GB models + per-page overhead + OS baseline). On an 11 GB server with ~4 GB baseline usage, marker-pdf WILL OOM-kill the gateway.

**When the server can't run marker-pdf in bulk:**

**Strategy A — Chain after all other tickets.** Chain the OCR ticket after all other books with `--parent` so it runs alone:
```bash
hermes kanban --board knowledge-base create \
  --assignee researcher --skill knowledge-base \
  --max-runtime 7200 \
  --parent <last_non_ocr_ticket_id> \
  --body "..." \
  "KB: <Title> — <Author>"
```

**Strategy B — 1 page per invocation (tested on 11 GB server, works).** marker-pdf loads all models upfront (~8 GB) regardless of page count, but 1 page per invocation stays at ~8 GB RSS and completes in ~70s. Processing 10+ pages at once causes extreme slowdown (20+ min, may never finish) because layout/recognition doesn't scale linearly.

To process a scanned book page-by-page:
```bash
# Process each page individually — slow but safe
for p in $(seq 0 625); do
  marker_single --page_range "$p-$p" \
    --output_dir "/tmp/ocr_pages/page_${p}" \
    --output_format markdown \
    --disable_image_extraction \
    --disable_multiprocessing \
    "/tmp/books_batch/<filename>.pdf"
done
# Then concatenate all markdown files into one text file for note creation
find /tmp/ocr_pages -name "*.md" | sort -V | xargs cat > /tmp/book_full.txt
```

**Strategy C — lighter OCR.** Tesseract (~200 MB), EasyOCR (~2-3 GB). Lower quality but zero OOM risk.

**Strategy D — skip.** For books where even 1-page-per-invocation is impractical (12+ hours for 600+ pages), skip and notify. This book needs ≥ 16 GB RAM or an external API (Google Vision, Azure OCR).

**marker-pdf model inventory (5 models, ~3.3 GB on disk, ~6.7 GB loaded in RAM):**

| Model | Disk | ~RAM (float32) | Role |
|-------|------|----------------|------|
| Layout detection | 1.4 GB | ~2.8 GB | Page structure (columns, paragraphs) |
| Text recognition | 1.4 GB | ~2.8 GB | OCR engine |
| OCR error detection | 262 MB | ~500 MB | Post-OCR correction |
| Table recognition | 202 MB | ~400 MB | Table detection |
| Text detection | 74 MB | ~150 MB | Text region detection |
| **Total** | **3.3 GB** | **~6.7 GB** | |

All 5 models are loaded at startup, before any page is processed. `--page_range` only controls which pages get OCR'd — it does NOT reduce model loading. With processing overhead, peak RSS is ~8 GB regardless of page count.

**marker-pdf options that DON'T reduce memory:**
- `--page_range "0-49"` — limits pages processed but models still load fully
- `--disable_multiprocessing` — prevents forked workers but main process still holds models

**Real OOM case (2026-06-14):** 626-page scanned PDF (Fomenko, 86 MB).
- 100 pages (no mp disable): 10.5 GB RSS → OOM
- 50 pages: 8 GB RSS → OOM (multiprocessing forks)
- 20 pages + `--disable_multiprocessing`: 8.6 GB RSS, manually killed (safe margin)
- 10 pages: 9.7 GB RSS, 20+ min without completing → extreme slowdown (layout/recognition doesn't scale linearly beyond single digits)
- **1 page: 7.9 GB RSS, 73s, exit 0 ✅ — the only viable batch size on 11 GB**
- Server: 11 GB RAM / 9 GB swap. Two OOM kills within 7 minutes before root cause was identified.
- Estimated 1-page-at-a-time cost: ~12h for 626 pages.

## Language rule

**Everything in English.** Template labels, section headers, analysis — all English. Book quotes stay in their original language but all surrounding text is English. Never mix French and English in the same note.

## Minimum quality bar — MUST meet ALL before pushing

**Stop and self-audit before `git push`. If any of these are missing, rework the note.**

1. **Detailed chapter-by-chapter summaries** — every chapter gets a substantive paragraph, not a bullet. This must be the dominant section of the note (longer than Critical Analysis). The reader needs to understand what's in the book.
2. **≥4 direct quotes** from the book in the "Key Claims" section, each preceded by `>`, with chapter number
3. **≥2 fact-checks** via `web_search` — at least one factual verification and one context check (author, reception)
4. **A "Critical Analysis" section** — concise critique, shorter than Chapter Summaries + Key Claims combined. Covers method, facts, what survives
5. **The "Who Is the Author?" section** — 1 paragraph: background, credentials, conflicts of interest
6. **Note ≥ 100 lines** (excluding frontmatter) — chapter summaries alone should push this well past 60 lines
7. **Content > Critique:** If Critical Analysis is the longest section, the note is unbalanced. Fix it before pushing.
8. **Budget 2-3 rounds** — never push v1

## Kanban dispatch

Books go on the **`knowledge-base`** board (never `default`).

**One ticket per book, no chaining** — books are independent work units with different content, authors, and fact-checking needs. Chaining would block unrelated books on each other. Use:

```bash
hermes kanban --board knowledge-base create \
  --assignee researcher \
  --skill knowledge-base \
  --max-runtime 3600 \
  --body "..." \
  "KB: <Book Title> — <Author> (YYYY)"
```

See `references/kanban-ticket-template.md` for the full book ticket body template.

## Pitfalls

- **Don't try to read the whole book in context.** 97K words = ~200K tokens. Read chapter by chapter from the extracted text file.
- **Claims need verification.** Book authors are often polemical and may cite studies loosely. `web_search` the key claims. Fact-checking is mandatory, not optional — also search the author's background and the book's critical reception.
- **ePub chapter ordering is unreliable.** Sort by size to find the actual content chapters (TOC/cover/copyright are tiny).
- **Telegram blocks .epub** — user must rename to .zip before sending.
- **Don't deliver a reception summary as a book note.** The user expects deep notes: direct quotes from the book, chapter-by-chapter claims with citations, fact-checking of key assertions, author credentials and biases, and critical reception. A note that only summarizes what Wikipedia or critics said about the book is insufficient — extract the author's own words from the text. The "Key Claims" section with `>` blockquotes is the heart of the note, not optional.
- **The first version is never good enough.** Budget 2-3 rounds on any book note: v1 = extract quotes, v2 = fact-check + structure, v3 = polish. Never push v1. The user will always ask for a deeper version — skip that step and deliver v2 or v3 directly.
- **Sorting chapters by size loses order.** The extraction code above saves chapters in original epub order. If you wrote code that sorts by size, the resulting file is unreadable as a book — chapters 1-5 end up after chapter 19. Always preserve the epub's chapter sequence in the saved output file. See Step 2 code for the correct pattern.
- **Small chapters are not optional.** Prefaces, introductions, and short concluding chapters often contain the author's thesis statement, methodology, and key definitions. Reading only the "big" chapters is like skipping the introduction and conclusion of a paper — you miss the argument's framing entirely.
- **Same-topic books can be misidentified.** When processing a batch of books on the same subject (e.g., 3 books about psilocybin or urine therapy), workers may load the right file but misidentify its content as a different book in the batch. **Always verify the EPUB metadata (title + author) matches the book you're supposed to process BEFORE writing the note.** If a worker reports "metadata discrepancy — file X contains book Y," re-verify by extracting the EPUB yourself — the worker may be wrong. Real cases: (2026-06-09) Scazzero file was correctly labeled but worker claimed it contained Bhurani's content because both discuss urine therapy. (2026-06-11) Fadiman epub was correctly labeled but worker claimed it contained Khamsehzadeh because both are about psilocybin.
- **Parallel workers + shared /tmp/book.epub = MinIO corruption.** Multiple book tickets run in parallel (no --parent), all with /tmp/book.epub as temp. Worker A downloads book X → Worker B downloads book Y overwriting the file → Worker A uploads book Y as book X. **Fix:** always use unique paths per slug (/tmp/book_<slug>.epub). Enforced in Step 0 and minio-upload.md.
- **Verify MinIO upload integrity immediately.** After mc cp, re-read the epub metadata and confirm it matches the book you just processed. A metadata mismatch means the file was overwritten — block and notify. See references/minio-upload.md for the verification snippet.
- **Extract archives into a clean directory.** Never `unzip -o` into a pre-existing directory like `/tmp/books_extracted` — it may contain books from a prior session. You'll list stale files as new, the user will catch it, and you'll look incompetent. Always `rm -rf /tmp/books_extracted && mkdir -p /tmp/books_extracted` first.

# Book Extraction — ePub & PDF

Pipeline for processing books into the knowledge base. Books are 50-150K words — never read the full text in context. Read chapter by chapter, extract key claims, synthesize.

## Supported formats

| Format | Tool | Install |
|--------|------|---------|
| ePub | `ebooklib` + `beautifulsoup4` | `pip install ebooklib beautifulsoup4` |
| PDF (text) | `pymupdf` | `pip install pymupdf` |
| PDF (scanned/OCR) | `marker-pdf` | `pip install marker-pdf` (~5GB) |

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

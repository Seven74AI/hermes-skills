---
name: book-extraction
description: Extract and summarize books (ePub, PDF) for the Obsidian knowledge base — ebooklib for ePub, pymupdf for PDFs, structured notes with key claims and fact-checking.
version: 2.0.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [books, epub, pdf, extraction, knowledge-base]
    related_skills: [knowledge-base, obsidian, ocr-and-documents]
---

# Book Extraction for Knowledge Base

Extract, summarize, and fact-check books (ePub, PDF) into structured Obsidian notes.

## Prerequisites

- `ebooklib` + `beautifulsoup4` — for ePub
- `pymupdf` — for PDF
- `obsidian` skill — for vault operations
- `knowledge-base` skill — for template and categories

## Triggers

- User sends an `.epub` or `.pdf` file (Telegram blocks `.epub` — user must rename to `.zip` or send via scp)
- User provides a path to a book file on the server
- Remote PDF URL (use `web_extract` first, fall back to local download + pymupdf)

## Pipeline

### Step 1: Get the file

**If sent via Telegram as .zip (ePub renamed):**
```bash
cp "/root/.hermes/cache/documents/doc_"*"_"*".zip" /tmp/book.zip
cd /tmp && unzip -o book.zip -d book_extract
# Find the .epub inside
EPUB=$(find /tmp/book_extract -name "*.epub" | head -1)
```

**If sent via scp or already on server:**
Use path directly.

### Step 2: Extract text

#### ePub (ebooklib)

```bash
python3 -c "
from ebooklib import epub
from bs4 import BeautifulSoup
import os

book = epub.read_epub('PATH_TO_EPUB')
items = list(book.get_items_of_type(9))  # ITEM_DOCUMENT

all_text = []
for i, item in enumerate(items):
    soup = BeautifulSoup(item.get_content(), 'html.parser')
    text = soup.get_text(separator='\n')
    chars = len(text.strip())
    if chars > 100:
        all_text.append((i, chars, text.strip()))

all_text.sort(key=lambda x: -x[1])

# Save full text
with open('/tmp/book_full.txt', 'w') as f:
    for idx, chars, text in all_text:
        f.write(f'\n\n=== CHAPTER {idx} ===\n\n')
        f.write(text)

# Print summary
total = sum(c for _, c, _ in all_text)
print(f'Chapters: {len(all_text)}, Total: {total:,} chars (~{total//5:,} words)')

# Metadata
title = book.get_metadata('DC', 'title')
author = book.get_metadata('DC', 'creator')
print(f'Title: {title[0][0] if title else \"?\"}')
print(f'Author: {author[0][0] if author else \"?\"}')
print(f'Top chapters by size:')
for idx, chars, preview in all_text[:8]:
    print(f'  Ch{idx}: {chars:,} chars — \"{preview[:120]}...\"')
"
```

#### PDF (pymupdf)

```bash
python3 -c "
import pymupdf
doc = pymupdf.open('PATH_TO_PDF')
print(f'Pages: {doc.page_count}')
text = ''
for page in doc:
    text += page.get_text() + '\n'
with open('/tmp/book_full.txt', 'w') as f:
    f.write(text)
print(f'Saved: {len(text):,} chars')
"
```

### Step 3: Read the ENTIRE book — NOT just samples

**⚠️ CRITICAL: Sampling 3-5 chapters produces garbage summaries. The user WILL reject them.** A 100K-word book requires reading ~2,000-3,000 lines of extracted text across multiple `read_file` passes. This is the most important step and the one that takes the most turns. Plan for 5-10 read_file calls.

**Reading strategy for a typical 8,500-line extracted book:**

1. **First pass — structure discovery:** Read first 300 lines of the largest chapter. Identify the book's architecture (chapter names, section headers, style).
2. **Systematic read-through:** Read in 200-300 line chunks, skipping through ALL chapters. Don't skip chapters because they "seem small" — small chapters often contain the author bio, diagnostic tables, or treatment recommendations that are the most valuable content.
3. **End of book:** Always read the last 300-500 lines — this is where author bios, glossaries, appendices, and treatment sections live. Some of the richest content is here.
4. **Batch reads:** Use multiple parallel `read_file` calls to read different sections simultaneously (e.g., offset=1, offset=800, offset=1600, offset=8200 all in one turn).

**Extract from every section:**
1. **Main claims** — what does the author assert? Quote directly.
2. **Clinical cases / stories** — these are the teaching vehicle. List them all.
3. **Evidence cited** — studies, data, statistics. Note which are sourced vs unsourced.
4. **Author credentials** — who is this person? Check bio section at end of book.
5. **Controversial positions** — where does the author diverge from consensus?
6. **Treatment protocols** — drugs, dosages, natural alternatives
7. **Diagnostic methods** — what tests, what markers, what signs

### Step 4: Research and verify

- `web_search` for the author's credentials and reputation
- `web_search` for key claims (cited studies, controversial assertions)
- Cross-reference with existing knowledge base notes

### Step 5: Create the note

Use the `knowledge-base` template. Save to `Knowledge base/`.

**The note MUST cover the ENTIRE book, not a partial summary.** Structure it as:

```markdown
---
topic: [key topics]
date: YYYY-MM-DD
source: Author Name (book)
confidence: verified | plausible | emerging | debunked | untested
tags: [relevant tags]
---

# Book Title

## Résumé
Author credentials + book thesis in 3-4 sentences.

## Structure complète
Table with EVERY chapter listed, not just the big ones.

## [Chapter Group I — Topic]
Detailed content with quotes, cases, mechanisms.

## [Chapter Group II — Topic]
...same for every chapter group...

## Cas cliniques (if applicable)
Numbered list of EVERY clinical case mentioned.

## Diagnostic / Treatment (if applicable)
Full diagnostic methodology, treatment protocols.

## Contexte / Analyse
Author credentials, position in field, tone, strengths, weaknesses.

## Nuances
What's missing, overclaimed, or needs verification. Be specific.

## Fiabilité
Confidence level with reasoning.

## Sources
- Author. *Book Title* (format)
- Full text saved at `/tmp/book_full.txt`
- Verification sources

## Voir aussi
- [[linked notes]]
```

**Size target:** A proper book note is 15,000-25,000 characters. If your note is < 5,000 chars, you haven't read enough of the book.

### Step 6: Push to Git

```bash
cd "$OBSIDIAN_VAULT_PATH" && git add -A && git commit -m "add: <slug> — <author> (book)" && git push
```

## Pitfalls

- **Telegram blocks .epub** — tell user to rename to .zip or use scp.
- **PDFs can be scanned images** — pymupdf won't extract text. Use marker-pdf in that case (see `ocr-and-documents` skill). Check: if extracted text < 500 chars for a 100+ page PDF, it's likely scanned.
- **French books often have accented characters in filenames** — use wildcard glob or `find` instead of exact paths. Shell quoting of French paths with `ô`, `è`, spaces often fails — use `cd` into the directory and glob with `*` instead.
- **SAMPLING IS NOT ENOUGH.** The user will say "je trouve pas le résumé super" if you read < 30% of the book. Read EVERY chapter. Budget 5-10 read_file calls of 200-300 lines each. This is a 97K-word book, not a blog post.
- **The end of the book is the most valuable part** — author bios, treatment chapters, diagnostic tables, and appendices live there. NEVER skip the last 500 lines.
- **Don't save the full text to the vault** — it's too large. Save to `/tmp/` and reference the path in the note if needed.
- **Language rule** — note body matches source language (English → English, French → French). Template section labels (Résumé, Contexte, etc.) stay in French as structural elements.
- **Confidence calibration** — a single book by one author is at most ⚠️ plausible unless claims are independently verified.
- **Batch your read_file calls** — use multiple parallel read_file calls in one turn (e.g., offset=1, offset=800, offset=1600 all at once). Serial reading wastes turns and makes the summary take forever.
# Book Extraction — ePub & PDF

Pipeline for processing books into the knowledge base. Books are 50-150K words — never read the full text in context. Read chapter by chapter, extract key claims, synthesize.

## Supported formats

| Format | Tool | Install |
|--------|------|---------|
| ePub | `ebooklib` + `beautifulsoup4` | `pip install ebooklib beautifulsoup4` |
| PDF (text) | `pymupdf` | `pip install pymupdf` |
| PDF (scanned/OCR) | `marker-pdf` | `pip install marker-pdf` (~5GB) |

## ePub pipeline

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

epub_file = [f for f in os.listdir('/tmp/book_output') if f.endswith('.epub')][0]
book = epub.read_epub(f'/tmp/book_output/{epub_file}')

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

# Save full text for reference
with open('/tmp/book_full.txt', 'w') as f:
    for idx, chars, text in all_text:
        if chars > 100:
            f.write(f'\n\n=== CHAPTER {idx} ===\n\n{text}')

# Metadata
title = book.get_metadata('DC', 'title')
author = book.get_metadata('DC', 'creator')
print(f'Title: {title[0][0] if title else "?"}')
print(f'Author: {author[0][0] if author else "?"}')
print(f'Total: {total_chars:,} chars (~{total_chars//5:,} words)')
print(f'Chapters: {len(items)}')
```

### Step 3: Read key chapters

The main content is in the largest chapters. Start with the top 5 by size. Use `read_file` with offset/limit to sample each chapter (200-500 lines each). Focus on:

- Claims the author makes (especially controversial or novel ones)
- Statistics, studies cited
- Clinical advice, treatment protocols
- Patient case studies

### Step 4: Create structured note

Save to `Connaissances/livres/<slug>.md`. Template:

```markdown
---
topic: [...]
date: YYYY-MM-DD
source: Auteur (livre)
confidence: plausible | verified | emerging
tags: [...]
---

# Titre du livre

## Résumé
2-3 phrases. Thèse centrale du livre.

## Structure
| Chapitre | Contenu |
|----------|---------|
| I | ... |
| II | ... |

## Affirmations principales
### 1. Claim title
> "Direct quote from book"

Analysis and context.

## Contexte / Analyse
Credentials de l'auteur, position dans le débat, ton du livre.

## Nuances
Limitations, biais, absence de sources, ton polémique, etc.

## Fiabilité
Level + justification.

## Sources
- Full text extracted to /tmp/book_full.txt
- Studies cited by the author (verify)

## Voir aussi
- [[note liée]]
```

### Step 5: Push to Git

```bash
cd "$OBSIDIAN_VAULT_PATH"
git add -A
git commit -m "add: <slug> — <author> (livre, ~XK mots)"
git push
```

## PDF pipeline

For PDFs, use the `ocr-and-documents` skill. `pymupdf` for text-based PDFs, `marker-pdf` for scanned/OCR. Then follow the same reading and structuring steps as ePub (Step 3-5 above).

## Language rule

**Never translate content.** Keep the original language of the source. Template section labels (Résumé, L'affirmation, Contexte, Nuances, Fiabilité, Sources, Voir aussi) remain in French as structural labels.

## Pitfalls

- **Don't try to read the whole book in context.** 97K words = ~200K tokens. Read key chapters only.
- **Claims need verification.** Book authors are often polemical and may cite studies loosely. `web_search` the key claims.
- **ePub chapter ordering is unreliable.** Sort by size to find the actual content chapters (TOC/cover/copyright are tiny).
- **Telegram blocks .epub** — user must rename to .zip before sending.

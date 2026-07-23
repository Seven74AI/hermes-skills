# Targeted Chapter Re-extraction

When a KB note already exists for a book but a specific chapter was missed (too thin in the note, not read at all), re-extract JUST that chapter instead of re-processing the whole book.

## Step 1: Get the epub

If the source file is on MinIO, re-download it:
```bash
curl -sL -o /tmp/book.epub "http://MINIO_HOST/knowledge-base/epubs/book.epub"
```

## Step 2: Discover chapter structure

```python
from ebooklib import epub, ITEM_DOCUMENT
from bs4 import BeautifulSoup

book = epub.read_epub('/tmp/book.epub')

# List all chapters with preview
for item in book.get_items_of_type(ITEM_DOCUMENT):
    soup = BeautifulSoup(item.get_body_content(), 'html.parser')
    text = soup.get_text(separator='\n', strip=True)
    print(f"[{item.get_name()}] {text[:150]}")
    print("---")
```

## Step 3: Extract the target chapter

Once you identify the filename (e.g., `c10.xhtml` for Chapter 10):

```python
for item in book.get_items_of_type(ITEM_DOCUMENT):
    if 'c10' in item.get_name():
        soup = BeautifulSoup(item.get_body_content(), 'html.parser')
        text = soup.get_text(separator='\n', strip=True)
        print(text)
```

## Step 4: Patch the existing KB note

Compare the extracted chapter against the existing note. Use `patch` to replace the thin section with the full content. The diff will show exactly what changed.

## Real case

2026-06-14 — Humbert *Les parasites* chapter 10 (Treatment). The original KB note had only 4 drug names. Re-extraction revealed: full posology table (16 rows), 5 unlisted drugs, mechanism of action, pregnancy contraindication, anti-cancer research details, and 8 naturopathic remedies with preparation instructions.

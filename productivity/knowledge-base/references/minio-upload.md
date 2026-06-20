# MinIO Upload for Knowledge Base

Upload source files (ePub, PDF, etc.) to MinIO after extraction.

## Credentials

From researcher profile env:
- `MINIO_ENDPOINT=http://localhost:9000`
- `MINIO_ACCESS_KEY`
- `MINIO_SECRET_KEY`
- `MINIO_BUCKET=knowledge-base`

## Upload

**CRITICAL: Multiple book workers run in parallel. NEVER use `/tmp/book.epub` — use unique paths per slug.**

```bash
source /root/.hermes/profiles/researcher/.env
mc alias set minio http://localhost:9000 "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY"

# Use unique paths — parallel workers will overwrite /tmp/book.epub otherwise!
mc cp "/tmp/book_<slug>.epub" "minio/$MINIO_BUCKET/books/<slug>.epub"
mc cp "/tmp/book_<slug>_full.txt" "minio/$MINIO_BUCKET/books/<slug>.txt"
```

**After every upload, verify integrity immediately:**
```bash
# Verify the epub metadata matches expected title/author
python3 -c "
from ebooklib import epub
book = epub.read_epub('/tmp/book_<slug>.epub')
t = book.get_metadata('DC', 'title')[0][0]
a = book.get_metadata('DC', 'creator')[0][0]
print(f'{t} — {a}')
"
# Should match the book you just processed. If it doesn't, the file was
# overwritten by a parallel worker — stop, block, do not push the note.
```

## Public URL for notes

Once uploaded, the file is accessible at:
```
http://vmi3304846.tail5c02a1.ts.net:9000/knowledge-base/books/<slug>.epub
http://vmi3304846.tail5c02a1.ts.net:9000/knowledge-base/books/<slug>.txt
```

Include this in the note frontmatter:
```yaml
source_files:
  source: http://vmi3304846.tail5c02a1.ts.net:9000/knowledge-base/books/<slug>.epub
  text: http://vmi3304846.tail5c02a1.ts.net:9000/knowledge-base/books/<slug>.txt
```

## Folder mapping

| File type | MinIO path | Frontmatter field |
|-----------|-----------|-------------------|
| Books (ePub/PDF) | `books/<slug>.<ext>` | `source_files.source` |
| Videos (YouTube) | `videos/<slug>.webm` | `source_files.video` |
| Videos (Reels) | `reels/<slug>.mp4` | `source_files.video` |
| Transcripts | `videos/<slug>.json` | `source_files.transcript` |
| Articles/Threads | `articles/<slug>.txt` | `source_files.text` |

All book files (original ePub/PDF + extracted full text) go under `books/` with the same slug.

## Notes

- mc alias is already configured on the server — skip step 1 on first use
- Bucket is set to `download` policy (public read) but only accessible via Tailscale network
- No authentication needed for downloads

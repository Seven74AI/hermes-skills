# Profile HuggingFace Download Caches

## Gap

Step 2j (Profile package manager caches) targets `.npm`, `.cache/pnpm`, `.cache/node-gyp`, `.cache/prisma`, `.cache/node`, `.cache/gh`, `.cache/pip` — but NOT `.cache/huggingface`. HuggingFace is not a package manager, but its download cache can dominate profile storage.

## Impact

Observed 2026-06-16: researcher-videos profile `.cache/huggingface` = 5.96G — the single largest reclaimable item in the cleanup run. Without this step, disk stayed at 74% after completing steps 2a-2q; after manually purging the huggingface cache, usage dropped to 70%.

## Safety

- **These are download caches, NOT installed models.** Installed models live in `/root/.hermes/models/` and are protected by the skill.
- Fully regeneratable on next `huggingface_hub.snapshot_download()` or `from_pretrained()` call.
- Same safety class as Playwright/Puppeteer/Camoufox browser caches (steps 2i/2l/2m).

## Cleanup Script (step 2ja)

```bash
cat > /tmp/cleanup-hf-cache.py << 'PYEOF'
import shutil, os, glob

total = 0
for cache in glob.glob('/root/.hermes/profiles/*/home/.cache/huggingface'):
    if os.path.isdir(cache):
        size = sum(os.path.getsize(os.path.join(dp,f)) for dp,_,files in os.walk(cache) for f in files)
        shutil.rmtree(cache, ignore_errors=True)
        total += size
        print(f'Removed: {cache} ({size/1024/1024:.0f}M)')

print(f'\nTotal: {total/1024/1024:.0f}M')
PYEOF
python3 /tmp/cleanup-hf-cache.py
```

## Recommended insertion point

After step 2j (Profile package manager caches), before step 2k (Profile Trash directories). Also update the escape hatch in Step 1 to list 2ja as a high-impact step.

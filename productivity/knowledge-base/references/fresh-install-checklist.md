# Fresh Install & Migration Checklist

Run after fresh VPS install, OS reinstall, or VM migration. Validates that all knowledge-base
pipeline dependencies and configurations survived the move.

## Quick validation (one-liner)

```bash
/usr/local/lib/hermes-agent/venv/bin/pip list 2>/dev/null | grep -iE "yt-dlp|faster.whisper|pyannote|playwright|mega|ebooklib|pymupdf|marker-pdf|beautifulsoup4" | wc -l
# Expected: 9 packages
```

## Python packages

```bash
/usr/local/lib/hermes-agent/venv/bin/pip install \
  yt-dlp faster-whisper pyannote.audio playwright \
  mega.py ebooklib pymupdf marker-pdf beautifulsoup4
```

**⚠️ Dependency cascade pitfall:** `marker-pdf` downgrades `openai`, `anthropic`, `tenacity`, `Pillow`, `huggingface-hub`. After installing, ALWAYS restore:

```bash
pip install 'openai==2.24.0' 'anthropic==0.87.0' 'tenacity==9.1.4' 'Pillow==12.2.0' 'huggingface-hub==1.16.1' 'tokenizers==0.23.1'
```

**⚠️ pyannote.audio version:** Must use `>=4.0` with torch >=2.5. Pyannote 3.x crashes on `AudioMetaData` / `list_audio_backends` removed in torchaudio 2.5+.
Pin: `pip install 'pyannote.audio>=4.0'`.

**⚠️ pyannote 4.x API change:** `pipeline()` returns `DiarizeOutput`, not `Diarization`.
Use `out.speaker_diarization.itertracks(yield_label=True)` — not `diarization.itertracks()`.

## System packages

```bash
apt-get install -y ffmpeg nodejs gh
```

## Browser automation

```bash
/usr/local/lib/hermes-agent/venv/bin/python -m playwright install chromium
```

## Whisper model

```bash
python3 -c "
from huggingface_hub import snapshot_download
snapshot_download('Systran/faster-whisper-large-v3', cache_dir='/root/.cache/huggingface')
"
```

## Services

```bash
# Firecrawl API
cd /opt/firecrawl && docker compose up -d api

# MinIO (should be running)
systemctl status minio
```

## CLI tools (non-Python)

```bash
# GitHub CLI — fix shadowing by Python 'gh' package
pip uninstall gh -y 2>/dev/null
# xurl (Twitter)
npm install -g @xdevplatform/xurl
```

## Profile dotfiles

Worker profiles have isolated `$HOME`. Copy shared configs:

```bash
for prof in researcher researcher-videos coder reviewer; do
  home="/root/.hermes/profiles/$prof/home"
  mkdir -p "$home/.config/gh" "$home/.xurl"
  cp ~/.config/gh/hosts.yml "$home/.config/gh/"
  cp ~/.gitconfig "$home/.gitconfig"
  cp ~/.xurl/config.json "$home/.xurl/" 2>/dev/null
done
```

## Cookies

- YouTube: `/tmp/yt_cookies.txt`
- Instagram: `/tmp/ig_cookies.txt`
- Instagram cookie MUST contain `sessionid` — validate: `grep -c sessionid /tmp/ig_cookies.txt` >= 1
- User exports from Mac: `scp /tmp/{ig,yt}_cookies.txt root@<tailscale-ip>:/tmp/`

## Whisper model access

Worker profiles use isolated `$HOME` but share the system HF cache at `/root/.cache/huggingface/`.
If a worker can't find the model, symlink:

```bash
ln -s /root/.cache/huggingface /root/.hermes/profiles/researcher-videos/home/.cache/huggingface
```

## Cron jobs to verify

```bash
hermes cron list | grep -iE "block.watchdog|pre.spawn|ci.watchdog|disk|memory|cpu|gateway|kanban.velocity"
```

Missing after migration: Block Watchdog. Recreate:
```bash
hermes cronjob create \
  --name "Kanban Block Watchdog" \
  --schedule "every 5m" \
  --script watchdog-all.py \
  --enabled-toolsets terminal \
  --skills kanban-orchestrator,kanban-worker \
  --deliver origin \
  --prompt "<canonical prompt from kanban-orchestrator skill, references/block-watchdog.md>"
```

## Hardware expectations

This checklist is written for **CPU-only VPS** (6 vCPU AMD EPYC, 8 GB RAM, no GPU).
Performance at this tier:
- pyannote 4.x diarization: ~2-3× realtime, 350% CPU
- faster-whisper large-v3 int8: ~2-3× realtime, 200-300% CPU
- Single-speaker content: skip diarization entirely (saves 30-40 min)
- Machine is at 100% load during diarization — kill crash-looping kanban workers to free CPU

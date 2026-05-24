# What `hermes backup` Does NOT Cover

`hermes backup` archives everything under `~/.hermes/`. During a VPS migration, several critical files live outside this directory and must be backed up separately.

## Root-level dotfiles

These are in `/root/` (or the user's home), not in `~/.hermes/`:

| File | Purpose | Impact if lost |
|------|---------|---------------|
| `/root/.xurl` | Twitter/X OAuth token for xurl CLI | Twitter digest cron jobs fail |
| `/root/.gitconfig` | Git credential helpers (gh CLI) | `git push` fails, PR creation blocked |
| `/root/.config/gh/hosts.yml` | GitHub CLI auth token | `gh pr create`, `gh issue create` fail |
| `/root/.ssh/id_*` | SSH keys for remote access | Can't SSH to other machines |

## System-level configs

| File | Purpose |
|------|---------|
| `/etc/systemd/system/hermes-gateway.service` | Gateway daemon |
| `/etc/systemd/system/hermes-dashboard.service` | Dashboard daemon |
| `/etc/systemd/system/hermes-gateway.service.d/env.conf` | GITHUB_TOKEN for gateway |
| `/etc/systemd/system/minio.service` | MinIO daemon |
| `/etc/default/minio` | MinIO root credentials |

## Storage

| Path | Purpose | Typical size |
|------|---------|-------------|
| `/data/minio/` | All object storage (videos, epubs, PDFs, transcripts) | 7+ GB |
| `/var/lib/docker/volumes/` | Firecrawl + Edgee Lab state | ~200 MB |

## Docker config

| File | Purpose |
|------|---------|
| `/opt/firecrawl/docker-compose.yaml` | Firecrawl stack definition |
| `/opt/firecrawl/.env` | Firecrawl environment (PORT, auth keys) |

## How to back these up

The `vps-migration` skill's `backup-to-macbook.sh` bundles everything NOT covered by `hermes backup` into separate tarballs. See the skill for the full migration playbook.

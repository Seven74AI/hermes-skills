---
name: vps-migration
description: Full VPS migration playbook — backup to MacBook over Tailscale, destroy, rebuild from scratch. Covers Hermes Agent, MinIO, Firecrawl, Docker, systemd units, cron scripts.
---

Complete VPS migration: backup a running VPS to a MacBook over Tailscale, destroy it,
provision a new one, and rebuild everything from scratch.

## Trigger

Use when upgrading a VPS that will be erased (no overlap window).
Not for in-place upgrades or migrations with both VPSes running simultaneously.

## Two scripts

| Phase | Where | Script |
|-------|-------|--------|
| Backup | Old VPS | `scripts/backup-to-macbook.sh <macbook-tailscale-ip> <macbook-username>` |
| Restore | New VPS | `scripts/setup-new-vps.sh <macbook-tailscale-ip> <macbook-username> [tailscale-hostname]` |

Username is **required** — use the macOS short name from `/Users/` (e.g. `marvinlamart`). SSH on macOS does not accept `root`.

## What gets backed up

The backup script creates 4 compressed archives locally on `/tmp/`, then scp's them to the MacBook. This is much faster than rsync'ing thousands of individual files (especially MinIO with 500+ video files).

| Archive | Contents | Typical size |
|---------|----------|-------------|
| `minio.tar.gz` | `/data/minio/` (all buckets + `.minio.sys` metadata) | ~5-6 GB |
| `docker-volumes.tar.gz` | `/var/lib/docker/volumes/` (Firecrawl + Edgee Lab) | ~100 MB |
| `configs.tar.gz` | Systemd units, `/etc/default/minio`, Firecrawl compose+.env, Edgee Lab, cron scripts | ~few KB |
| `hermes-final-backup.zip` | Full `hermes backup` output | ~2 GB |

Total: ~8 GB. MacBook needs >8 GB free space.

## What needs REINSTALLING (not copying)

These do NOT survive a file copy — they must be reinstalled:

| Layer | Why not copy |
|-------|-------------|
| Hermes venv | Python paths, compiled extensions are host-specific |
| Docker engine | System-level daemon, not portable |
| MinIO binary | Can be copied (static binary), but easier to wget |
| Firecrawl repo | Uses `build:` in compose — needs full clone + rebuild |
| Node.js | System package, not portable |
| Tailscale | System service, needs fresh auth |

## Installation sequence on new VPS

Dependency order: later phases depend on earlier ones being up.

1. **Tailscale** — access first, reuse same hostname (remove old node from admin console first)
2. **Docker** — needed by Firecrawl, Edgee
3. **Firecrawl** — clone repo, restore compose + .env, `docker compose build` + `up -d`
4. **MinIO** — install binary, restore data, start service
5. **Edgee Lab** — restore config, build (optional, not needed for Hermes)
6. **Hermes** — clone fork `Seven74AI/hermes-agent`, venv, `hermes import` backup zip
7. **Systemd** — install unit files, enable, start: gateway FIRST, then dashboard

Why gateway before dashboard: the dashboard depends on the gateway being up.

## Tailscale hostname

Reuse the same hostname to keep all Obsidian MinIO links working:

1. Tailscale admin console → Machines → find old node → ... → Remove
2. On new VPS: `tailscale up --hostname=vmi3304846`
3. MagicDNS updates — `vmi3304846.tail5c02a1.ts.net` resolves to new VPS

## Troubleshooting

### Backup script fails: "Cannot reach MacBook via Tailscale"

1. **Check your own Tailscale first**: `tailscale status` — if the VPS shows `offline`, the backup script cannot initiate ANY Tailscale connection. Fix: `tailscale up --accept-routes`, wait 30s, retry.

2. **Check MacBook Tailscale**: `tailscale status | grep macbook` — must show `active`. If `offline`, wake the MacBook or re-auth Tailscale on it.

3. **Wrong IP**: the script needs the MacBook's **Tailscale IPv4** address (e.g. `100.112.19.124`). IPv6 addresses require bracket escaping in SSH/rsync and may not work. Find the correct IPv4: `tailscale status | grep macbook | awk '{print $1}'`.

4. **Node already deleted from admin console**: If you removed the VPS from the Tailscale admin console before running the backup, the VPS loses its identity. Run `tailscale up --accept-routes` to re-auth (gets a temp hostname like `vmi3304846-1`). The backup will work. After the backup, you can reclaim `vmi3304846` on the new VPS:

```bash
# On old VPS (after accidentally deleting node)
tailscale up --accept-routes   # gets temp name, backup works again
./backup-to-macbook.sh <macbook-ip>   # succeeds

# Then destroy old VPS
# On new VPS — old node already deleted, hostname is free
tailscale up --hostname=vmi3304846
```

See `references/tailscale-reconnection-recovery.md` for the full diagnosis and recovery trace from the May 2026 migration session.

## CRITICAL: Tailscale node lifecycle

**DO NOT remove the old VPS node from the Tailscale admin console until AFTER the backup is complete.**

Removing the node kills the VPS's Tailscale connection immediately. The backup script needs Tailscale to rsync to the MacBook. The correct sequence:

1. Run `backup-to-macbook.sh` → data is on MacBook
2. THEN remove old node from Tailscale admin console
3. THEN destroy old VPS
4. Then run `setup-new-vps.sh` on the new VPS (reuses hostname)

If you already deleted the node before backup: see Troubleshooting below.

## Pre-flight checklist

Before running `backup-to-macbook.sh`:
- [ ] **Do NOT delete the old Tailscale node yet** — wait until after backup (see CRITICAL below)
- [ ] **SSH key exists on VPS**: `ls ~/.ssh/id_*.pub` — if missing, generate one: `ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""`
- [ ] **SSH key on MacBook**: copy the VPS public key to the MacBook user's authorized_keys: on the MacBook, `echo "PASTE_KEY_HERE" >> ~/.ssh/authorized_keys`
- [ ] **MacBook username** — pass it as second argument (required, e.g. `./backup-to-macbook.sh 100.112.19.124 marvinlamart`)
- [ ] Verify own Tailscale is online: `tailscale status` — VPS must show `active`
- [ ] MacBook is online via Tailscale: `tailscale status | grep macbook` shows `active`
- [ ] MacBook has SSH enabled (System Settings → General → Sharing → Remote Login)
- [ ] MacBook has >10 GB free disk space (archives are created on VPS then scp'd, freeing temp space after transfer)
- [ ] `hermes backup -o /root/hermes-final-backup.zip` completed (~2 GB)
- [ ] Use the MacBook's **IPv4** Tailscale IP (e.g. `100.112.19.124`), not IPv6 — `tailscale status` shows it
- [ ] `/tmp` has >8 GB free for staging archives (the script creates them there, scps them, then cleans up)

Before running `setup-new-vps.sh`:
- [ ] Old VPS node removed from Tailscale admin console (only now — after backup is confirmed on MacBook)
- [ ] New VPS is provisioned (same OS, minimum 6c/12GB/100GB)
- [ ] SSH access to new VPS works (root or sudo user)
- [ ] MacBook is still online and reachable from new VPS via Tailscale

## Post-migration verification

```bash
# Firecrawl
curl http://localhost:3002/health

# MinIO (local + Tailscale)
curl http://localhost:9000/minio/health/live
curl http://vmi3304846.tail5c02a1.ts.net:9000/minio/health/live

# Hermes gateway
systemctl status hermes-gateway
journalctl -u hermes-gateway -n 20

# Dashboard
curl http://localhost:9119/

# Cron jobs (should show 26+ jobs)
hermes cron list

# Obsidian vault
git clone git@github.com:Seven74AI/obsidian-vault.git ~/Documents/Obsidian\ Vault/

# Test scrape
curl -s http://localhost:3002/v1/scrape -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com"}' | head -c 200
```

## What's NOT covered by `hermes backup`

`hermes backup` only covers `~/.hermes/` (config, state.db, .env, auth, sessions, skills, profiles, cron). It does NOT cover:

| File | What it is | Backup method |
|------|-----------|---------------|
| `/root/.xurl` | Twitter/X OAuth token | `configs.tar.gz` → `root-config/` |
| `/root/.gitconfig` | Git credential helpers (gh CLI) | `configs.tar.gz` → `root-config/` |
| `/root/.config/gh/hosts.yml` | GitHub CLI auth token | `configs.tar.gz` → `root-config/` |
| `/root/.ssh/` | SSH keys (generated for MacBook access) | `configs.tar.gz` → `root-config/` |
| `/etc/systemd/system/*.service` | Hermes + MinIO systemd units | `configs.tar.gz` → `system-config/` |
| `/etc/default/minio` | MinIO root credentials | `configs.tar.gz` → `system-config/` |
| `/opt/firecrawl/docker-compose.yaml` + `.env` | Firecrawl config | `configs.tar.gz` → `system-config/` |
| `/data/minio/` | All object storage data | `minio.tar.gz` |
| `/var/lib/docker/volumes/` | Firecrawl + Edgee Lab state | `docker-volumes.tar.gz` |

Root-level dotfiles (`.xurl`, `.gitconfig`, `.config/gh/`, `.ssh/`) are NOT in `~/.hermes/` and are NOT captured by `hermes backup`. They are bundled into `configs.tar.gz` under a `root-config/` subdirectory and restored to `/root/` on the new VPS.

- **DO NOT delete old Tailscale node before backup** — removing the node from the admin console kills the VPS's Tailscale connection immediately. Backup needs Tailscale to rsync to MacBook. Sequence: backup → delete node → destroy → provision new. If you already deleted it, see `references/tailscale-reconnection-recovery.md` for the `--reset` recovery procedure.
- **SSH key missing on VPS** — the backup script uses SSH to reach the MacBook. If `~/.ssh/id_*.pub` doesn't exist, generate one: `ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""`. Then copy the public key to the MacBook's `~/.ssh/authorized_keys`.
- **SSH defaults to root, macOS rejects it** — the script uses the current VPS user (`root`) for SSH. macOS does not allow root SSH login. Pass the MacBook username as second argument: `./backup-to-macbook.sh 100.112.19.124 marvinlamart`. On the MacBook, add the VPS key to that user's `~/.ssh/authorized_keys`.
- **Hermes backup zip must exist BEFORE running the script** — the script copies `/root/hermes-final-backup.zip` to staging. Run `hermes backup -o /root/hermes-final-backup.zip` first (takes ~7 min, 2 GB). If the zip is missing, the script fails at step 4 — recover by running `hermes backup` directly to `/tmp/vps-backup-staging/` and then scp'ing all 4 files.
- **Staging space in /tmp** — the script creates ~8 GB of tarballs in `/tmp/vps-backup-staging/`. Verify: `df -h /tmp` (needs >8 GB free).
- **venv is not portable** — don't rsync `/usr/local/lib/hermes-agent/venv/`. Recreate: `python3 -m venv venv && pip install -e .`
- **Firecrawl uses `build:` in compose** — needs the full repo clone, not just docker-compose.yml. `docker compose build` takes 5-10 minutes.
- **MinIO `.minio.sys/`** — internal metadata directory inside `/data/minio/`. Must be copied alongside bucket data.
- **Hermes binary not on PATH after `deactivate`** — `pip install -e .` inside a `source activate / deactivate` block leaves `hermes` outside the system PATH. The setup script uses the absolute path: `/usr/local/lib/hermes-agent/venv/bin/hermes import ...`. Never rely on `hermes` being on PATH immediately after venv install.
- **`set -e` kills script on empty glob** — `cp dir/* /dest/` with `set -euo pipefail` fails if the directory is empty. Guard with: `if ls dir/* >/dev/null 2>&1; then cp ...; fi`.
- **Hermes backup zip must exist before running backup script** — the script copies `/root/hermes-final-backup.zip`, it doesn't create it. Run `hermes backup -o /root/hermes-final-backup.zip` first (~7 min). If missing, the zip can be generated directly to the staging dir: `hermes backup -o /tmp/vps-backup-staging/hermes-final-backup.zip` then scp all 4 files.
- **SSH defaults to root user, macOS rejects it** — `ssh <ip>` uses the current VPS user (`root`). macOS SSH does not accept root. Always pass the MacBook short name as second argument. On the MacBook, add the VPS public key to that user's `~/.ssh/authorized_keys`.
- **Firecrawl API container may not restart after stop/start** — the backup script stops Firecrawl for consistent volume backup, then starts it. The API container (`firecrawl-api-1`) may not come back up. Verify with `docker ps`. Not critical since the VPS is about to be destroyed.
- **Hermes gateway fails if Firecrawl is down** — config references `web.backend=firecrawl`. Start Firecrawl before the gateway.
- **GITHUB_TOKEN in gateway env.conf** — `/etc/systemd/system/hermes-gateway.service.d/env.conf` contains it. If missing, gateway starts but GitHub tools fail.
- **Tailscale IP changes** — even with same hostname, the IP (100.x.y.z) is per-node. Avoid hardcoding IPs — use MagicDNS.
- **Docker volume IDs** — anonymous volumes have random names. After restoring `/var/lib/docker/volumes/`, do `docker compose down && docker compose up -d` to let containers find the restored volumes.
- **Edgee Lab Dockerfile** — uses `build:` and may fail with newer Docker versions. It's optional — skip if it fails.
- **Kanban workers interrupted** — any running or blocked tasks on kanban boards will be abruptly terminated when the VPS is destroyed. The gateway won't be running on the new VPS during the install phase, so workers can't self-heal. Check boards before shutdown: `hermes kanban boards` to see active counts, then `hermes kanban --board <slug> list --status running` for details. Tasks in `running` state will show as crashed on the new VPS — re-dispatch them manually or let the block watchdog handle it after the gateway is back up.

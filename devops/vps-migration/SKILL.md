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
| Backup | Old VPS | `scripts/backup-to-macbook.sh <macbook-tailscale-ip>` |
| Restore | New VPS | `scripts/setup-new-vps.sh <macbook-tailscale-ip> [tailscale-hostname]` |

## What gets backed up

| Data | Size | Method |
|------|------|--------|
| MinIO (`/data/minio/`) | ~7 GB | rsync to MacBook |
| Docker volumes | ~200 MB | rsync to MacBook |
| Systemd units + `/etc/default/minio` | ~5 KB | scp to MacBook |
| Firecrawl docker-compose + .env | ~2 KB | scp to MacBook |
| Edgee Lab config | ~few KB | rsync to MacBook |
| Hermes full backup zip | ~2.5 GB | scp to MacBook |
| Hermes cron scripts (`~/.hermes/scripts/`) | ~few KB | rsync to MacBook |

Total: ~10 GB. MacBook needs >10 GB free space.

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

## Pre-flight checklist

Before running `backup-to-macbook.sh`:
- [ ] MacBook is online and reachable via Tailscale
- [ ] MacBook has SSH enabled (System Settings → General → Sharing → Remote Login)
- [ ] MacBook has >10 GB free disk space
- [ ] `hermes backup -o /root/hermes-final-backup.zip` completed (2.5 GB)
- [ ] Tailscale status shows MacBook as connected
- [ ] Kanban boards checked — note any active (running/blocked) tasks that will be interrupted by the shutdown: `hermes kanban boards` then `hermes kanban --board <slug> list --status running` for each board with active counts

Before running `setup-new-vps.sh`:
- [ ] Old VPS node removed from Tailscale admin console
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

## Pitfalls

- **venv is not portable** — don't rsync `/usr/local/lib/hermes-agent/venv/`. Recreate: `python3 -m venv venv && pip install -e .`
- **Firecrawl uses `build:` in compose** — needs the full repo clone, not just docker-compose.yml. `docker compose build` takes 5-10 minutes.
- **MinIO `.minio.sys/`** — internal metadata directory inside `/data/minio/`. Must be copied alongside bucket data.
- **Hermes gateway fails if Firecrawl is down** — config references `web.backend=firecrawl`. Start Firecrawl before the gateway.
- **GITHUB_TOKEN in gateway env.conf** — `/etc/systemd/system/hermes-gateway.service.d/env.conf` contains it. If missing, gateway starts but GitHub tools fail.
- **Tailscale IP changes** — even with same hostname, the IP (100.x.y.z) is per-node. Avoid hardcoding IPs — use MagicDNS.
- **Docker volume IDs** — anonymous volumes have random names. After restoring `/var/lib/docker/volumes/`, do `docker compose down && docker compose up -d` to let containers find the restored volumes.
- **Edgee Lab Dockerfile** — uses `build:` and may fail with newer Docker versions. It's optional — skip if it fails.
- **Kanban workers interrupted** — any running or blocked tasks on kanban boards will be abruptly terminated when the VPS is destroyed. The gateway won't be running on the new VPS during the install phase, so workers can't self-heal. Check boards before shutdown: `hermes kanban boards` to see active counts, then `hermes kanban --board <slug> list --status running` for details. Tasks in `running` state will show as crashed on the new VPS — re-dispatch them manually or let the block watchdog handle it after the gateway is back up.

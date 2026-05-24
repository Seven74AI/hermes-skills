# Pre-Migration Server Discovery

Run these before a VPS migration to build the full inventory of what needs to be backed up or rebuilt.

## 1. Running services

```bash
systemctl list-units --type=service --state=running --no-legend | awk '{print $1}'
```

Note any Hermes, Docker, MinIO, Tailscale, or custom services.

## 2. Docker containers

```bash
docker ps --format '{{.Names}} {{.Image}}'
```

Container data lives under `/var/lib/docker/volumes/`. Decide: backup volumes or rebuild from compose.

## 3. Disk usage

```bash
df -h /
du -sh /data/* 2>/dev/null
```

Find large data directories — MinIO, logs, caches.

## 4. Cron jobs

Use `cronjob(action='list')` from within Hermes. Note which jobs use scripts (need file backup) vs. inline prompts (captured in state.db backup).

## 5. Hermes version and config

```bash
hermes --version
hermes config show 2>/dev/null
```

Note the web backend (firecrawl, ddg, etc.) — it may require Docker rebuild.

## 6. Tailscale

```bash
tailscale status --json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('Self',{}).get('HostName','?'))"
```

New VPS will need a new Tailscale node or re-auth.

## 7. Backup coverage

Check what the Hermes backup cron jobs actually cover:
- `hermes backup` / `hermes backup -q` → config, state, auth, sessions
- External stores (MinIO, Docker volumes, vault uncommitted changes) → NOT covered

## Decision matrix

For each discovered component, decide:

| Component | Backup? | Rebuild? | Notes |
|-----------|---------|----------|-------|
| Hermes state | ✓ (backup cron) | | GitHub repo |
| MinIO data | rsync to bridge | | 7 GB typical |
| Docker volumes | | docker compose up | No state worth saving |
| Obsidian vault | git push | git clone | Check uncommitted |
| System packages | | apt install list | Rarely worth scripting |
| Tailscale | | tailscale up --authkey | New node |

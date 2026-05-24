# VPS Snapshot — May 2026

Exact files discovered during the May 24, 2026 migration prep. Captured so the restore step doesn't need to re-discover them.

## Systemd units

### hermes-dashboard.service
- Path: `/etc/systemd/system/hermes-dashboard.service`
- Exec: `/usr/local/lib/hermes-agent/venv/bin/python3 /usr/local/lib/hermes-agent/venv/bin/hermes dashboard --host 0.0.0.0 --port 9119 --insecure --no-open --skip-build`
- User: root
- Restart: always, RestartSec=5, RestartMaxDelaySec=300
- Environment: HOME=/root, HERMES_HOME=/root/.hermes, PATH includes venv/bin + node_modules/.bin

### hermes-gateway.service
- Path: `/etc/systemd/system/hermes-gateway.service`
- Exec: `/usr/local/lib/hermes-agent/venv/bin/python -m hermes_cli.main gateway run --replace`
- User: root
- Restart: always, RestartForceExitStatus=75
- TimeoutStopSec: 210
- Override: `/etc/systemd/system/hermes-gateway.service.d/env.conf` contains `GITHUB_TOKEN=***`

### minio.service
- Path: `/etc/systemd/system/minio.service`
- Exec: `/usr/local/bin/minio server /data/minio --address ":9000" --console-address ":9001"`
- EnvironmentFile: `/etc/default/minio`
- User: root

## Service credentials

### /etc/default/minio
- MINIO_ROOT_USER=kb-admin
- MINIO_ROOT_PASSWORD=<redacted — captured in backup>

## Docker services

### Firecrawl
- Path: `/opt/firecrawl/`
- Compose: `docker-compose.yaml` (name: firecrawl)
- Port: 3002
- .env: minimal — PORT=3002, HOST=0.0.0.0, USE_DB_AUTHENTICATION=false, BULL_AUTH_KEY=hermes-firecrawl-local
- Containers: api, playwright-service, redis, rabbitmq, nuq-postgres (5 total)
- Volumes: anonymous Docker volumes, ~197 MB total

### Edgee Lab
- Path: `/root/edgee-lab/`
- Compose: `docker-compose.yml`
- Volume: `edgee-lab-config` (named)

## Network

- Tailscale hostname: vmi3304846
- Tailscale IP: 100.98.177.76 (will change on new node)
- MinIO access: private, Tailscale-only, MagicDNS `vmi3304846.tail5c02a1.ts.net:9000`
- Firewall: Tailscale-managed (ts-input/ts-forward chains), UFW inactive

## Hermes

- Version: v0.14.0 (2026.5.16)
- Install path: `/usr/local/lib/hermes-agent/`
- Venv: `/usr/local/lib/hermes-agent/venv/`
- Home: `/root/.hermes/`
- Backup repo: `Seven74AI/hermes-backup` on GitHub
- Profiles: researcher, researcher-videos, coder, reviewer, edgee-planner, hermes-devops, twitter-coder
- 26 cron jobs (watchdogs, digests, backups, kanban)

## Disk layout

| Mount | Total | Used | What |
|-------|-------|------|------|
| / (sda1) | 72 GB | 56 GB | OS + everything |

| Path | Size | Contents |
|------|------|----------|
| /data/minio/knowledge-base/videos/ | 7.0 GB | 512 files — WebM videos + MP3 audio + JSON transcripts |
| /data/minio/knowledge-base/epubs/ | 5.8 MB | 2 files |
| ~/.hermes/state-snapshots/ | 527 MB | 4 snapshots |
| ~/.hermes/sessions/ | 369 MB | Session DB |
| ~/.hermes/state.db | 390 MB | Main state DB |
| /var/lib/docker/volumes/ | 197 MB | Firecrawl + Edgee Lab |

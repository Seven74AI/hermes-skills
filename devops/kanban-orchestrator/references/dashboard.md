# Kanban Dashboard — Web UI Setup

The Kanban dashboard is a web UI served by `hermes dashboard` (top-level, NOT `hermes kanban dashboard`). Port 9119.

## Start

```bash
# First run ever: npm ci + build (takes ~30-60s)
hermes dashboard --host 0.0.0.0 --insecure &

# Subsequent runs: skip build
hermes dashboard --host 0.0.0.0 --insecure --skip-build &
```

`--host 0.0.0.0` is required for Tailscale access. Without it, the dashboard only listens on 127.0.0.1.

`--insecure` is required when binding to non-localhost (it exposes API keys on the network).

## Check status

```bash
hermes dashboard --status
ss -tlnp | grep 9119
```

## Stop

```bash
hermes dashboard --stop
```

## Tailscale URL

Once running with `--host 0.0.0.0`:
```
http://<tailscale-ip>:9119
```

## Pitfalls

- **`hermes kanban dashboard` does NOT exist** — it's `hermes dashboard` (top-level command).
- **First run is slow** — `npm ci` + `npm run build` can take 30-60s. Dashboard isn't reachable until build completes.
- **Port already in use** — stop any existing instance first with `hermes dashboard --stop`.

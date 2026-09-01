# Dashboard Crash-Loop Diagnostic Playbook

Symptom A (port conflict): `hermes-dashboard.service` in `activating (auto-restart)` with restart counter climbing
(>100). Journal shows `[Errno 98] address already in use` on port 9119.

Symptom B (auth gate): same restart loop, but journal shows
`Refusing to bind dashboard to 0.0.0.0 — the auth gate engages on non-loopback binds, but no auth providers are registered.`
and `ss -tlnp | grep 9119` is empty. Caused by `ExecStart` using `--host 0.0.0.0 --insecure` after the auth-gate update.

## Auth-gate fix (Symptom B)

Pick one:
- Password: set `dashboard.basic_auth.username` + `password_hash` in `config.yaml`
  (`python -c "from plugins.dashboard_auth.basic import hash_password; print(hash_password('your-password'))"`).
- OAuth: `hermes dashboard register`.
- Loopback + tunnel: edit the unit to `--host 127.0.0.1` then `systemctl daemon-reload && systemctl restart hermes-dashboard`
  (correct for a "Tailscale-accessible" service reached over SSH/Tailscale).

## Step-by-step diagnosis (port conflict, Symptom A)

```bash
# 1. Confirm the crash loop
systemctl status hermes-dashboard --no-pager | head -10

# 2. Check what's holding the port
ss -tlnp | grep 9119

# 3. Compare the PID to systemd's expected PID
#    If the port-holding PID is OLD and NOT in systemd's cgroup → stale manual process
ps -p <PID> -o pid,lstart,cmd

# 4. Check for zombie children (early warning signal)
ps aux | grep -w Z | grep -v grep
#    Trace zombie parent: ps -o pid,ppid,stat,comm -p <ZOMBIE_PID>
```

## Fix

```bash
kill <STALE_PID>
systemctl restart hermes-dashboard   # or wait for auto-restart (~5 min)
curl -s -o /dev/null -w "%{http_code}" http://localhost:9119/  # verify 200
```

## Prevention

- Never launch `hermes dashboard` manually if a systemd service exists
- If manual launch is needed, disable the service first
- Add a zombie-count watchdog: alert if >3 zombies or any zombie older than 24h
- Add a restart-counter watchdog: alert if any systemd service restarts >100 times without resolution

# Tailscale Reconnection After Accidental Node Deletion

## What happened (2026-05-24)

During VPS migration prep, the old VPS node `vmi3304846` was deleted from the
Tailscale admin console BEFORE the backup script ran. This killed the VPS's
Tailscale identity immediately — the daemon was still running but `Online: false`.

## Recovery steps

```bash
# 1. Force re-auth (generates login URL)
tailscale up --accept-routes --ssh --reset
# Output: "To authenticate, visit: https://login.tailscale.com/a/..."

# 2. Open URL in browser, auth with the tailnet account (sevenai@)

# 3. Verify
tailscale status
# VPS reappears with a NEW IP (100.127.242.119 vs old 100.98.177.76)
# Hostname auto-assigned if old one was deleted (gets temp name or original)
```

## Key takeaways

- **`tailscale up --reset`** is needed when the node was fully deleted (not just
  disconnected). Without `--reset`, it tries to reuse the old identity which no
  longer exists.
- **`tailscale login`** alone may timeout on headless machines — use `tailscale up`
  which outputs the auth URL.
- After re-auth, the VPS may get a different Tailscale IP. SSH hosts checking
  with `StrictHostKeyChecking` will need the new key accepted.
- The MacBook connectivity survives because the MacBook re-discovers the VPS
  via DERP relay once it reconnects.

## Prevention

**Never delete the old Tailscale node before running the backup.** The correct
sequence is: backup → delete node → destroy VPS → provision new.

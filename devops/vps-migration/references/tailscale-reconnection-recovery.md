# Tailscale Reconnection Recovery (May 2026)

## What happened

The VPS node (`vmi3304846`) was removed from the Tailscale admin console BEFORE the backup was complete. This killed the Tailscale connection immediately — ping and SSH to the MacBook (100.112.19.124) both failed with 100% packet loss and "Connection refused".

## Root cause

Removing a node from the admin console revokes its machine key. The `tailscaled` daemon stays `active` but the node shows `Online: False` in `tailscale status --json`. The `tailscale up` command without `--reset` also fails because the existing identity is invalid.

## Recovery procedure

```bash
# 1. Reset Tailscale identity (force re-auth)
tailscale up --accept-routes --ssh --reset

# 2. This prints an auth URL — open it in any browser
#    https://login.tailscale.com/a/<code>

# 3. After authenticating, verify
tailscale status
# Should show active with a temp hostname like vmi3304846-1

# 4. Now the backup script works again
./backup-to-macbook.sh 100.112.19.124 marvinlamart
```

## Side effects

- The VPS gets a new Tailscale IP (changed from 100.98.177.76 to 100.127.242.119)
- The hostname gets a `-1` suffix unless manually renamed in the admin console
- The temporary hostname doesn't matter — the old VPS is about to be destroyed
- On the NEW VPS, `vmi3304846` is already free (node was deleted), so `--hostname=vmi3304846` works

## Prevention

**DO NOT delete the old node from Tailscale admin console until AFTER the backup is confirmed on the MacBook.**

Sequence:
1. Run `backup-to-macbook.sh` → verify files on MacBook
2. THEN delete old node from admin console
3. THEN destroy old VPS
4. Then run `setup-new-vps.sh` on new VPS (reuses `vmi3304846`)

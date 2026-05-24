# Post-Update Recovery After Disk-Full Incident

When `hermes update` runs while the disk is critically full (≥95%), the git
fetch/reset succeeds but several post-update steps fail silently because they
can't write to disk. The gateway also fails to restart with `OSError: [Errno 28]
No space left on device`.

Confirmed 2026-05-23: 72G/72G (100%), 361M free. Git update succeeded (HEAD at
origin/main), but:

- npm install (root) — failed
- npm install (web/) — failed  
- Web UI build (`web/dist/`) — not created
- Stash pop — failed (local changes not restored)
- Gateway restart — crash loop (`activating (auto-restart)`)

## Recovery steps (after disk cleanup drops below ~80%)

Run in order:

```bash
# 1. Pop the stash (local changes preserved during update)
cd /usr/local/lib/hermes-agent && git stash pop

# 2. Reinstall npm dependencies (root + web)
cd /usr/local/lib/hermes-agent && npm install
cd /usr/local/lib/hermes-agent/web && npm install

# 3. Rebuild web UI
cd /usr/local/lib/hermes-agent/web && npm run build

# 4. Restart gateway
systemctl restart hermes-gateway
systemctl is-active hermes-gateway  # should show "active"
```

## Verification

```bash
ls /usr/local/lib/hermes-agent/web/dist/index.html  # should exist
df -h /                                              # should be <80%
systemctl is-active hermes-gateway                   # should be "active"
```

# PNPM Store Deduplication Across Hermes Profiles

## Problem

Each Hermes profile has an isolated `$HOME`, so `pnpm` creates its own content-addressable store at `~/.local/share/pnpm/store`. With multiple profiles using pnpm (coder, reviewer, etc.), the same packages are cached redundantly. Example from 2026-05-24:

| Location | Size |
|---|---|
| `/root/.hermes/profiles/coder/home/.local/share/pnpm` | 4.6G |
| `/root/.hermes/profiles/reviewer/home/.local/share/pnpm` | 2.1G |
| `/root/.local/share/pnpm` (system) | 3.3G |
| **Total wasted** | **6.7G** |

## Solution

Set `PNPM_HOME` in each profile's `.env` to point to the system-level store. pnpm's global store is content-addressable and atomic — safe for concurrent use across processes.

**Verified safe** (pnpm maintainer zkochan, Feb 2026):
> "It is safe to run multiple installs concurrently, which modify the same store. All store related operations are atomic. The store will never be left in a broken state."

Add to each profile's `.env`:
```
PNPM_HOME=/root/.local/share/pnpm
```

Then delete the old isolated stores:
```bash
rm -rf /root/.hermes/profiles/coder/home/.local/share/pnpm
rm -rf /root/.hermes/profiles/reviewer/home/.local/share/pnpm
```

## NOT safe to share

These tools do NOT support concurrent shared use — keep them isolated per profile:

- **rustup** (`RUSTUP_HOME`): Issue rust-lang/rustup#988 open since 2017. No locking, race conditions can corrupt toolchains.
- **cargo builds** (`CARGO_TARGET_DIR`): Issue rust-lang/cargo#16804. Per-target-directory lock serializes builds; race conditions corrupt artifacts. Only safe workaround is per-worktree isolation. The download-only cache (`CARGO_HOME`) is probably fine but the gain is small (~470M).

## Verification

After setting `PNPM_HOME`, verify in a profile session:
```bash
pnpm store path
# Should return: /root/.local/share/pnpm/store/v3
```

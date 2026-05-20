# Shared Config for Worker Profiles

## Problem

Worker profiles have isolated `$HOME` directories (`/root/.hermes/profiles/<name>/home/`). Shared configuration files that live in the host user's home (`~/.xurl`, `~/.gitconfig`, `~/.ssh`) are NOT accessible to worker processes because `$HOME` for the worker points to its profile home, not the host home.

## Symptoms

- `xurl auth status` returns "No apps registered" even though xurl is configured on the host
- `git push` fails with "could not read Username"
- Workers repeatedly ask for OAuth setup that already exists on the host
- Tasks block with "need to configure X" when X is already configured at `/root/`

## Solution

After installing/updating a shared config on the host, copy it to all profiles that need it:

```bash
# Copy .xurl to profiles that need Twitter/X access
for profile in edgee-watcher edgee-reporter edgee-researcher; do
    cp /root/.xurl "/root/.hermes/profiles/$profile/home/.xurl"
    chmod 600 "/root/.hermes/profiles/$profile/home/.xurl"
done

# Copy .gitconfig to profiles that need git push
for profile in music-coder shop-coder startup-coder; do
    cp /root/.gitconfig "/root/.hermes/profiles/$profile/home/.gitconfig"
    chmod 644 "/root/.hermes/profiles/$profile/home/.gitconfig"
done
```

## Impact When Not Done

- **2026-05-18**: edgee-lab T-WATCH task blocked for 15+ runs asking for xurl OAuth setup, while `xurl whoami` worked fine on the host. The Block Watchdog detected it each run but delivered to `local` (file), so the user never knew. Root cause: `~/.xurl` wasn't copied to the `edgee-watcher` profile home.

## Integration with Team Bootstrap

When creating a new project team with `references/team-bootstrap.md`, add a step after profile creation to copy shared configs to the new profile homes. Determine which configs are needed based on the profile's role (watcher → `.xurl`, coder → `.gitconfig`, etc.).

# Profile Home Isolation

Worker profiles each have their own `$HOME` at `/root/.hermes/profiles/<name>/home/`. This means:

- `~/.xurl` in the host home is **not accessible** to workers
- `~/.gitconfig`, `~/.npmrc`, `~/.config/gh/` — same problem
- `~/.hermes/.env` — same problem (profile has its own env)

## Common failures

| Symptom | Root cause | Fix |
|---------|-----------|-----|
| Worker asks for xurl OAuth setup even though `xurl whoami` works on host | `~/.xurl` missing from profile home | `cp /root/.xurl /root/.hermes/profiles/<name>/home/.xurl` |
| Worker can't git push (401) | No git config or token in profile home | Copy `.gitconfig` or use `gh auth` token |
| Worker can't access GitHub API | No GITHUB_TOKEN in profile's `.env` | Set env var in profile config.yaml: `environment: { GITHUB_TOKEN: "..." }` |

## Pattern: copy dotfiles to profiles

After setting up auth on the host (xurl OAuth, gh auth, git config), copy the relevant dotfiles to all profiles that need them:

```bash
# xurl
for p in edgee-watcher edgee-reporter; do
  cp /root/.xurl /root/.hermes/profiles/$p/home/.xurl
done

# gh / git
cp /root/.config/gh/hosts.yml /root/.hermes/profiles/<name>/home/.config/gh/hosts.yml
```

## 2026-05-18 Example

Edgee-lab T-WATCH task cycled 15+ runs asking for xurl OAuth setup. `xurl whoami` worked on the host (`seven_dai74`, OAuth OK), but the `edgee-watcher` profile had no `~/.xurl` in its isolated home. Copying the file unblocked the task immediately.

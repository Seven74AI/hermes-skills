# Dependency Risk Audit — Technique

Use when auditing project dependencies for risky/unmaintained packages.
Applies to npm/pnpm/Yarn projects.

## Quick Audit via npm Registry

```python
import json, urllib.request, time

packages = ["@nichtsam/helmet", "@tusbar/cache-control", ...]

def get_npm_info(pkg):
    url = f"https://registry.npmjs.org/{pkg}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    latest = data.get("dist-tags", {}).get("latest", "?")
    dl_url = f"https://api.npmjs.org/downloads/point/last-week/{pkg}"
    with urllib.request.urlopen(dl_url, timeout=10) as resp:
        dl_data = json.loads(resp.read())
    return {
        "name": pkg,
        "version": latest,
        "weekly": dl_data.get("downloads", 0),
        "maintainers": len(data.get("maintainers", [])),
        "license": data.get("versions", {}).get(latest, {}).get("license", "?"),
        "deprecated": data.get("deprecated", False),
    }
```

## Risk Classification

| Tier | Weekly Downloads | Action |
|------|-----------------|--------|
| 🔴 Critical | < 10,000 | Replace immediately — find alternative |
| 🟡 Concern | 10K – 100K | Review — prefer mainstream alternative if exists |
| 🟢 Safe | 100K – 1M | OK but monitor |
| ✅ Mainstream | > 1M | Safe |

## Red Flags

- **1 maintainer** — bus factor, no redundancy
- **No repository URL** — can't audit source
- **Deprecated** — immediate removal
- **Ancient version** (major version behind in lockfile) — unmaintained
- **@username/package** from unknown org — check org reputation separately

## Example: @nichtsam/helmet → helmet

- `@nichtsam/helmet`: 10K/week, 1 maintainer, wraps standard `helmet` for React Router
- `helmet`: 12M+/week, Express middleware, direct replacement
- Both projects use Express with `@react-router/express` — no need for the wrapper

## Always Check

1. Is the dependency ACTUALLY used in code? (grep imports) — not just in package.json
2. Does the project's framework support the mainstream alternative directly?
3. Is there a lockfile version mismatch? (e.g. v1.0.2 in lockfile, v3.0.1 on npm)

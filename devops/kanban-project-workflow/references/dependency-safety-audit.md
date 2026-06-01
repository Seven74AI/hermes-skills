# Dependency Safety Audit

Audit npm dependencies across project repos for risky packages — single-maintainer, low download count, deprecated, or unmaintained packages. Find safer alternatives.

## When to Use

- User flags a specific package as unsafe (`@nichtsam/helmet`)
- Periodic health check on project dependencies
- After discovering a supply-chain incident or near-miss

## Methodology

### Step 1: Gather all dependencies

```python
import json, subprocess
repos = ["shop", "music-library", "the-swarm"]  # adjust

for repo in repos:
    pkg = json.loads(subprocess.run(
        f"gh api repos/Seven74AI/{repo}/contents/package.json --jq .content | base64 -d",
        shell=True, capture_output=True, text=True
    ).stdout)
    for field in ["dependencies", "devDependencies"]:
        for dep, ver in pkg.get(field, {}).items():
            print(f"[{repo}] {dep}: {ver} ({field})")
```

### Step 2: Check npm registry for each non-major-org package

Skip well-known orgs: `@radix-ui/*`, `@prisma/*`, `@react-router/*`, `@playwright/*`, `@sentry/*`, `@tailwindcss/*`, `@vitejs/*`, `react`, `typescript`, `vite`, `vitest`, `express`, `zod`.

```python
import json, urllib.request, time

def check_pkg(pkg):
    url = f"https://registry.npmjs.org/{pkg}"
    data = json.loads(urllib.request.urlopen(url).read())
    latest = data["dist-tags"]["latest"]
    dl = json.loads(urllib.request.urlopen(
        f"https://api.npmjs.org/downloads/point/last-week/{pkg}"
    ).read())
    return {
        "name": pkg,
        "version": latest,
        "weekly": dl["downloads"],
        "maintainers": len(data.get("maintainers", [])),
        "description": data.get("description", "")[:100],
        "deprecated": "deprecated" in data,
    }
```

### Step 3: Rank by risk

| Risk | Weekly downloads | Action |
|------|-----------------|--------|
| 🔴 Critical | < 10,000 | Replace immediately |
| 🟡 Concerning | 10,000 – 100,000 | Evaluate alternative, replace if better exists |
| 🟢 Acceptable | 100,000 – 1,000,000 | Monitor |
| ✅ Safe | > 1,000,000 | No action |

Additional risk factors:
- **1 maintainer** — bus factor of 1, no succession plan
- **No repository URL** — can't audit source
- **Deprecated** — EOL, security patches stop
- **Multiple major versions behind** — abandoned
- **Unusual org for the domain** (e.g., `@nasa-gcn/remix-seo` in a music library)

### Step 4: Find alternatives

For each risky package, search for the standard/battle-tested alternative:

```python
# Check the obvious alternative
check_pkg("helmet")  # vs @nichtsam/helmet
check_pkg("shadcn")  # vs @sly-cli/sly
```

Prefer packages with:
- > 1M weekly downloads
- ≥ 2 maintainers
- Active repository (recent commits)
- Clear documentation

### Step 5: Create tickets

For each replacement, create a kanban ticket:

```bash
hermes kanban --board <board> create --assignee coder --priority 1 \
  --skill <project> --skill kanban-project-workflow \
  --body "## Replace <old> with <new>

**Risk**: <old> has X weekly downloads, 1 maintainer.
**Alternative**: <new> has Y weekly downloads, Z maintainers.

## Changes needed
- Remove <old> from package.json
- Install <new>
- Update imports in files: <list>
- Verify CI passes (typecheck, lint, vitest, playwright)" \
  "[P1] Replace <old> → <new> (dependency safety)"
```

### Common Replacements (Epic Stack projects)

| Risky | Safe Alternative | Notes |
|-------|-----------------|-------|
| `@nichtsam/helmet` | `helmet` | Express-level. Remove from entry.server.tsx CSP — use helmet's CSP instead. |
| `@tusbar/cache-control` | (remove) | Express handles cache-control. Helmet covers it too. |
| `@sly-cli/sly` (dev) | `npx shadcn@latest add` | Official shadcn CLI, 9× more downloads. |
| `@nasa-gcn/remix-seo` | Manual sitemap/robots | 25 lines of code. No dependency needed. |

### Integration with Global Audit

When running a global health audit (see main SKILL.md), include dependency safety as a standard section. The researcher should run this methodology and report findings alongside CI, codebase, and project health metrics.

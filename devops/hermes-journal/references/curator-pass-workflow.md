# Curator Pass — Manual Workflow & Pitfalls

How to run a manual skill library curation pass (the Weekly Curator cron job `2e1f5c35f5aa` does this automatically every Sunday). Use this when the auto pass needs manual follow-up or when running curator outside cron.

## Workflow

### 1. Backup first

```bash
hermes curator backup
```

### 2. Gather intelligence

```bash
hermes curator status      # stale counts, last run, config
hermes curator usage       # provenance: agent vs bundled vs hub
hermes curator list-archived  # what's already in .archive/
```

**Critical distinction:** `hermes curator usage` shows each skill's **origin** (`agent`, `bundled`, `hub`). Only `agent`-origin skills are manageable by the curator. `skills_list` alone doesn't show provenance — use `usage` for this.

### 3. Identify near-duplicates

Scan `skills_list` for suspicious name clusters. Common patterns to watch for:

- Same concept with different naming: `diagnose` / `diagnosing-bugs` / `systematic-debugging`
- Thin stubs pointing at a real skill: `grill-me` → `grilling`, `grill-with-docs` → `grilling`
- Top-level vs categorized copies: `improve-codebase-architecture` (top-level) vs `software-development/improve-codebase-architecture`

For each candidate pair, load both with `skill_view(name)` and compare structure, phases, and trigger descriptions. Archive the thinner one with `hermes curator archive <name>`.

### 4. Handle symlinked skills (CRITICAL PITFALL)

**Symlinked skills are invisible to the curator for removal.** Skills symlinked from external repos (e.g., `mattpocock-skills`) via `setup-matt-pocock-skills` / `scripts/link-skills.sh`:

- Appear in `skills_list` and load fine via `skill_view`
- `hermes curator archive <name>` creates a copy in `.archive/` but **does NOT remove the symlink**
- The skill remains active because the symlink still resolves
- `hermes curator usage` may or may not list them as agent-created (they're registered in `.usage.json` at symlink creation time)

**Detection:** `ls -la /root/.hermes/skills/<name>` — if it's a symlink (`->`), manual removal is needed.

**Fix after archival:**

```bash
# Verify it's a symlink
ls -la /root/.hermes/skills/<skill-name>

# Remove the symlink (the archived copy is in .archive/)
rm /root/.hermes/skills/<skill-name>

# Verify it's gone from skills_list (may need a new session)
```

**Upstream fix:** The source files in the external repo need to be moved to `deprecated/` so the next `link-skills.sh` run doesn't recreate the symlink.

### 5. Run prune

```bash
# Dry-run first
hermes curator prune --days 90 --dry-run

# Execute if there are candidates
hermes curator prune --days 90
```

Prune only touches agent-created skills idle for >= N days. Bundled and hub skills are never pruned. Skills with `last_activity=never` but origin=`bundled` or `hub` are NOT candidates — they shipped with Hermes and haven't been invoked yet.

### 6. Final curator run

```bash
hermes curator run
```

This picks up any changes (new archives, removed symlinks) and updates the internal tracking state. The report is written to `/root/.hermes/logs/curator/<timestamp>`.

## Known Duplicate Clusters (as of 2026-07-26)

These have been resolved in this environment but may reappear from external repos:

| Cluster | Canonical | Archived/Removed |
|---|---|---|
| Debugging methodology | `diagnose` (v1.1.0, mattpocock) | `systematic-debugging` (archived), `diagnosing-bugs` (symlink removed) |
| Grilling interviews | `grilling` | `grill-me` (thin stub, removed), `grill-with-docs` (thin stub, removed) |
| Architecture improvement | `codebase-design` (vocabulary) | `improve-codebase-architecture` top-level symlink (archived + removed) |

## Pitfalls

- **`hermes curator archive <name>` says "skill not found" for bundled/hub skills.** These are shipped with Hermes and can't be archived. Use `hermes curator usage` to check origin first.

- **Consolidation is OFF by default.** The curator's `--consolidate` flag enables the LLM merge pass. Without it, only deterministic stale/archive operates. Near-duplicate detection must be done manually by loading pairs with `skill_view` and comparing. To enable: `hermes config set curator.consolidate true`.

- **`hermes curator status` "archived" count is misleading.** It shows "0 archived" even when `.archive/` has entries. The count tracks skills archived *this run*, not the total in `.archive/`. Use `hermes curator list-archived` for the authoritative list.

- **Symlinked skills survive archival.** See step 4 above. Always follow `hermes curator archive` with `ls -la` on the skill path to check for symlinks.

- **`hermes curator archive` on ambiguous names.** When two skills share the same name (one top-level, one in a subdirectory like `software-development/`), `hermes curator archive` may refuse with "ambiguous" or silently pick one. Use the full relative path if needed.

- **Upstream churn risk.** Skills from `mattpocock-skills` that were symlinked and then manually removed will **reappear** the next time `setup-matt-pocock-skills` / `scripts/link-skills.sh` runs — unless the source files in `/root/.hermes/mattpocock-skills/skills/` are also moved to `deprecated/`. The curator pass should note which symlinks it removed so the upstream repo can be cleaned.

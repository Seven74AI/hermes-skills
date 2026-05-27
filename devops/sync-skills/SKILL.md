---
name: sync-skills
description: Sync custom skills to the Seven74AI/hermes-skills GitHub repo — script, cron job, and how to add new categories.
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    tags: [devops, skills, sync, github, cron]
---

# Skills Sync to GitHub

Custom-authored skills are synced daily from `~/.hermes/skills/` to the
[Seven74AI/hermes-skills](https://github.com/Seven74AI/hermes-skills) GitHub repo.

**Bundled skills** (those shipped with the hermes-agent fork) are NOT synced by this
pipeline — they live in the fork itself (`Seven74AI/hermes-agent`). This script only
handles skills authored locally.

## What gets synced

Only skills in these custom categories:

- `devops`
- `dogfood`
- `github`
- `mlops`
- `productivity`
- `social-media`
- `software-development`

Within those categories, bundled skills are excluded via a hardcoded `BUNDLED_SKILLS` set
in the script (see below).

**Never synced:** `note-taking/*` and `productivity/knowledge-base` — these live in the
hermes-agent fork, not in hermes-skills.

## Script

**Path:** `/root/.hermes/scripts/sync-skills-to-github.py`

SHA256 comparison — only pushes changed skills. Clones `Seven74AI/hermes-skills` to
`/tmp/hermes-skills-sync/`, copies changed skill directories, commits, and pushes.

## Cron job

**Job ID:** `4eee7fb0b484` — "Daily Skills Sync to GitHub"
**Schedule:** daily at 03:30 Paris time (`30 3 * * *`)
**Script-only:** `no_agent=true` — purely mechanical, no LLM
**Delivery:** `local` (silent unless errors)

```
cronjob(action='list') to inspect
cronjob(action='run', job_id='4eee7fb0b484') to trigger manually
```

## Adding a new custom category

If a new custom category is created under `~/.hermes/skills/` and should be synced:

1. Edit `/root/.hermes/scripts/sync-skills-to-github.py`
2. Add the category name to the `CUSTOM_CATEGORIES` set (line ~22)
3. If the category also exists in bundled hermes-agent skills, add bundled skill paths
   to `BUNDLED_SKILLS` to prevent them from being overwritten
4. Verify with a manual run: `cronjob(action='run', job_id='4eee7fb0b484')`
5. Wait for next daily sync to confirm no errors

## Troubleshooting

**Script fails silently** — check cron last status:
```
cronjob(action='list')  # look for job_id 4eee7fb0b484 last_status
```

**Clone fails** — GITHUB_TOKEN must be set in `~/.hermes/.env`. The script reads it
from there. Verify with `grep GITHUB_TOKEN ~/.hermes/.env`.

**Skill not appearing on GitHub** — check:
- Category is in `CUSTOM_CATEGORIES`
- Skill is NOT in `BUNDLED_SKILLS`
- `SKILL.md` exists in the skill directory

## Memory context

Memory records that `productivity/*` and `note-taking/*` are bundled (synced via
hermes-agent fork, NOT hermes-skills). The `knowledge-base` skill + refs stay
local, not on GitHub.

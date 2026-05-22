# Ghost PR Audit Pattern

When a repo accumulates PRs opened by kanban workers that were never reviewed
or merged, use this researcher pattern to triage them.

## Trigger

- 3+ open PRs on a repo, all from feature branches (feat/t_*, fix/*)
- No reviews, no labels, days old
- The consolidation PR (#198 on shop) may have already absorbed some content

## Researcher Task Template

```
Audit N PRs ouvertes sur <repo> — légitimes ou fantômes ?

Mission: pour chaque PR, vérifier si le code est déjà dans main
(via consolidation), si la PR est encore pertinente, et recommander
close ou merge.
```

## Audit Checklist (per PR)

1. `gh pr view N --repo <repo> --json state,mergeable,reviews,body`
2. Check if the PR's content is already in main (`git log --oneline main | grep -i <keyword>`)
3. Check for duplicates (same feature, different branch versions)
4. Check review status
5. Check mergeability (conflicts?)

## Output Format

```
CLOSE: #N <reason>
KEEP: #N <reason> <action needed>
```

## Real Cases

- **shop** (2026-05-21): 7 PRs audited → 5 closed (obsolete/superseded), 2 kept (#112 i18n, #130 reviewer feedback)
- **the-swarm** (2026-05-21): 3 PRs audited → #34 closed (superseded by #38), #38 and #43 kept
- **music-library** (2026-05-21): PR #1 kept (cleanup sweep, needed rebase for playwright-gate)

## Post-Audit

After researcher completes, create a planner ticket to decompose into actionable
coder/reviewer tickets for the kept PRs.

# CI Fix Template — "0 Flaky, Tout Green"

Recurring task pattern: permanently fix CI so every run is green with zero flaky tests.

## Task Body Template

```
## Objectif

CI shop doit être **100% verte, 0 test flaky, de façon permanente**.

## Mission

1. Auditer l'état actuel de la CI : lancer vitest run && tsc --noEmit && lint && playwright test en local
2. Identifier TOUS les tests flaky (ceux qui passent une fois sur deux)
3. Fixer chaque flaky à la racine (attendre les sélecteurs, mocker le réseau, pas de sleep())
4. Vérifier qu'il n'y a AUCUN || true dans les steps de vérification du workflow CI
5. Ajouter --repeat-each 3 sur Playwright pour détecter les flaky en CI
6. S'assurer que lint + typecheck + vitest + playwright passent 5 fois d'affilée SANS échec
7. Ouvrir une PR, enable auto-merge, créer le ticket reviewer

## Contrainte

**Zéro tolérance.** Après ce ticket, tout fail CI = vrai bug, pas un flaky.
```

## Create Command

```bash
hermes kanban --board <board> create \
  "[P0] Fix CI définitivement — 0 flaky, tout green" \
  --assignee coder \
  --max-runtime 3600 \
  --skill systematic-debugging \
  --skill kanban-project-workflow \
  --skill project-ci \
  --skill long-running-tests \
  --skill github-pr-workflow \
  --skill tdd \
  --body "..."
```

## Why This Repeats

CI rot accumulates over time: flaky tests get ignored, `|| true` sneaks back in after consolidations, Playwright timing issues compound. A dedicated "fix everything" task with a hard constraint (5 consecutive green runs) is the only way to reset the baseline.

## Key Checks

- `grep -r '|| true' .github/workflows/` — any hits on verification steps are bugs
- `--repeat-each 3` on Playwright catches intermittent failures that `--workers=1` alone won't
- Run the full suite 5 times: `for i in $(seq 5); do pnpm test && pnpm typecheck && pnpm lint && pnpm playwright; done`

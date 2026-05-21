# Git push troubleshooting (The Swarm)

## Corrupted object on push

Symptom:
```
fatal: bad object 804ed1ba7d2536e161b50473f9e75982477740e8
error: failed to push some refs to 'https://github.com/Seven74AI/the-swarm.git'
```

Cause: `git commit --amend` after a rebase left a stale parent reference.

Fix:
```bash
git fetch origin && git rebase origin/main && git push origin main
```

Do NOT use `git push --force` — the pre-push hook blocks it and it's dangerous.

## Commits rejected by pre-push hook

Symptom: `✗ Tests failed — push blocked`

Fix: fix the failing tests, `git add -A && git commit --amend --no-edit`, retry push. If amend creates the corrupted-object error above, use the rebase fix instead.

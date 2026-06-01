# Audit Ticket Body Template

Use this structure for ALL researcher audit tickets. The body goes in `--body` when creating the kanban ticket. Sections marked \[REQUIRED\] must be present in every audit ticket; sections marked \[OPTIONAL\] depend on audit type.

## Template

```markdown
## Mission
[REQUIRED] One-paragraph description of what to investigate and why.

## Périmètre
[REQUIRED] Numbered sections, each covering one audit dimension.

### 1. <Dimension name>
- <Specific checks to perform>
- <Data to collect, files to inspect>
- <Tools to use (lighthouse, npm audit, axe-core, etc.)>
- ...

### 2. <Dimension name>
...

## Livrables
[REQUIRED]
1. Rapport complet dans une GitHub Issue — **toujours CRÉER une nouvelle issue**, ne pas juste commenter
   - Commande : `gh issue create --repo Seven74AI/<repo> --title "[AUDIT] <topic>" --body-file /tmp/audit_report.md --label "research-backed"`
   - Le rapport COMPLET doit être dans le body de l'issue, pas juste un lien
2. Tickets kanban pour chaque problème trouvé (P0/P1/P2)
3. Tracker ticket listant tous les findings + sous-tickets

## Contraintes
[REQUIRED]
- Rapport COMPLET dans le body de la GitHub Issue — utiliser `gh issue create`, pas `gh issue comment`
- Template de format : `references/audit-ticket-template.md`
- Sous-tickets avec `--body` ET `--skills <project> --skills kanban-project-workflow`
- [OPTIONAL] Contraintes spécifiques au type d'audit
```

## Post-Completion Checklist
[REQUIRED — every audit ticket body should end with this]
```markdown
- [ ] GitHub Issue CRÉÉE avec le rapport complet comme body (pas juste un commentaire sur une issue existante)
- [ ] Sous-tickets créés pour TOUS les findings P0/P1
- [ ] Tracker ticket créé si 3+ findings
- [ ] Chaque sous-ticket a `--body` et `--skills`
```

## Title Convention
```
[AUDIT] <Project> — <dimension 1>, <dimension 2>, <dimension 3>
```
Example: `[AUDIT] Shop — sécurité, performance, i18n`

## Creation Command Template
```bash
hermes kanban --board <board> create \
  --assignee researcher \
  --priority 2 \
  --skill <project> \
  --skill kanban-project-workflow \
  --body '...' \
  "[AUDIT] <Project> — <dimensions>"
```

## ⛔ Pitfall: Creating GitHub Issue Comment Instead of New Issue

**The researcher MUST create a NEW GitHub Issue with the full report as its body**, not just add a comment to an existing issue. Comments are ephemeral (lost in the noise). The user explicitly requires the full audit result inside a dedicated GitHub issue (2026-05-30).

**Why commenting fails:**
- The report gets buried in the issue thread
- Future agents can't reference it as a standalone work item
- The kanban pipeline doesn't track GitHub comments

**Detection:** If the audit task completes and no new GitHub issue number appears in the summary, the researcher probably commented instead of creating.

**Fix:** Read the researcher's kanban comment, write it to `/tmp/audit_report.md`, then:
```bash
gh issue create --repo Seven74AI/<repo> --title "[AUDIT] <topic>" --body-file /tmp/audit_report.md --label "research-backed"
```
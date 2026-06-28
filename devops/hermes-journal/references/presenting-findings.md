# Presenting Journal Findings to the User

Template and rationale for when the user asks to review journal entries.

## Why this format exists

The user ("Check the last week Hermes journal entries and list me what you think may need my attention") will respond with terse, numbered follow-up questions. The initial report must be structured so each numbered response maps cleanly to one finding.

A verbose report with prose introductions and unexplained jargon forces the user to ask "what is this file?", "what cron are you talking about?", "explain me more" — wasting turns on clarification instead of action.

## Template

```
## 🔴 Critical — Needs action now

### 1. [One-line verdict]
[2-3 sentences max: what, why it matters, how long it's been broken]
- *Journal entries: #X, #Y*

### 2. [One-line verdict]
...

## 🟡 Important — Degraded but not burning

### 4. [One-line verdict]
...

## 🟢 Resolved or stabilizing

- **[Topic]** — what happened, current state
...
```

## Rules

### Verdict first
Every item starts with the conclusion. Not "Upon reviewing the journal, I observed..." but "Backup cron is GONE — 15 days without backup."

### One item = one concern
Don't merge two issues into one item. The user's numbered follow-up "item 3" must map to a single, clean topic.

### Cite journal entries
Each item ends with `- Journal entries: #12, #16` so the user can look at the source. But don't re-summarize the journal entry — the user can read it.

### Explain ALL infrastructure terms
The user does not memorize cron job IDs, tool names, or file paths. Every term that appeared in a journal entry must be explained the first time:
- ❌ "Cron output accumulation — 151 MB with no retention policy"
- ✅ "The output files from every cron job are stored in `/root/.hermes/cron/output/` and have grown to 151 MB with no automatic cleanup"

- ❌ "tirith:pending_approval blocks API calls"
- ✅ "The security scanner (tirith) has a new `pending_approval` mode that blocks legitimate shell commands — even simple `ls` and `cat` — when they run inside a cron job"

### Group by real urgency, not journal labels
The journal has impact labels (🔴 Critical, 🟡 Important, 🟢 Nice to Know) but these reflect the *journal entry's* durability, not the *current* urgency. A "Nice to Know" entry about state.db auto-compaction might actually be a Critical issue because the file didn't shrink. Re-assess urgency based on current state, not the label.

### After presenting — expect the numbered salvo
The user's typical response is 5-7 numbered questions, each 1-2 lines. Answer each directly in order. Don't re-explain the whole context — assume they read your initial report.

### "If yes then no problem"
When the user says "If yes then no problem" or "If yes, then I don't care about X" — they're giving you a decision rule. Apply it immediately. Don't argue, don't add caveats. "Skills are backed up? If yes then no problem about backups." → Verify skills backup, confirm yes, drop the backup concern entirely.

## Example from 2026-06-27 session

User asked: "Check the last week Hermes journal entries and list me what you think may need my attention"

Good initial report structure:
- 7 numbered items across 3 urgency tiers
- Each item: one-line verdict + 1-2 sentences context + journal entry citations
- No preamble

User responded with 7 terse follow-ups:
1. "Are the skills backed up ? If yes then no problem." → Verified GitHub sync, answered yes, dropped backup concern
2. "What is this file ? What's its purpose ?" → Explained state.db (hadn't explained it in initial report)
3. "Check this further" → Investigated SOUL config contradiction
4. "Why we need an agent for this ? Alternative to reduce token consumption?" → Analyzed disk cleanup chain, proposed no_agent alternative
5. "I don't understand. What cron are you taking about ? What's the output ?" → Had used jargon "cron output accumulation" without explaining
6. "Explain me more" → Hadn't explained tirith clearly enough
7. "What skills are missing ?" → Showed the tool-names-as-skills bug

Each question 2-3 was a direct pointer to where the initial report was unclear or incomplete.

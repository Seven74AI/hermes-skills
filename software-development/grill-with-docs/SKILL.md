---
name: grill-with-docs
description: "Grilling session that challenges your plan against the existing domain model, sharpens terminology, and updates documentation (CONTEXT.md, ADRs) inline as decisions crystallise. Use when user wants to stress-test a plan against their project's language and documented decisions."
version: 1.0.0
metadata:
  hermes:
    tags: [grill-with-docs, engineering, matt-pocock]
source: mattpocock/skills
---

<what-to-do>

Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.

Ask the questions one at a time, waiting for feedback on each question before continuing.

**Pitfall — bundling questions:** It is tempting to group related questions together
("four things to decide: A, B, C, D") to move faster. Don't. The user will say
"one by one pls" and you'll lose time backtracking. Even when sub-questions seem
tightly coupled, present them individually. Exception: yes/no confirmations on a
single recommendation can be paired.

**Pitfall — missing option labels:** When a single question has multiple choices,
label them with letters (A, B, C) so the user can answer with a single character
instead of re-typing the full option. "For next question plz provide letters to
each options so I don't need to rewrite the answer every time." This is especially
important on mobile or chat platforms where typing is slow.

If a question can be answered by exploring the codebase, explore the codebase instead.

**Pitfall — CONTEXT.md appends with `patch`:** When adding a new decision to CONTEXT.md,
the `patch` tool with `replace` mode REPLACES `old_string` with `new_string` — it does
NOT append. If you set `old_string` to the last decision line and `new_string` to the
new decision alone, you will erase the last decision. This happened 6+ times in one session.

The correct pattern: set `old_string` to the LAST line of the file (the most recent
decision), and set `new_string` to that same line PLUS the new decision below it,
separated by a newline. Both decisions survive. Verify with `read_file` after every patch.

**Pitfall — presenting choices:** When offering options (A/B/C), always prefix each
with a letter label so the user can reply with a single letter instead of rewriting
the answer. Example: "- **A)** Option one — description\\n- **B)** Option two — description"
single letters — **A)**, **B)**, **C)**. Always include your recommendation with reasoning.
The user can answer with a single letter instead of retyping the option.

**Pitfall — appending to CONTEXT.md with patch:** When adding a new decision, set
`old_string` to the text of the LAST existing decision, and `new_string` to that
same text plus `\n` plus the new decision. Never set `old_string` to the new
decision's text — that will replace (delete) the previous decision. Verify current
state with `read_file` if unsure.

If a question can be answered by exploring the codebase, explore the codebase instead.

**Pitfall — technical jargon:** When the user says "I don't understand" or "explain
it better," do NOT respond with more technical detail or alternative library names.
The user is telling you the abstraction level is wrong. Switch to analogies and
concrete examples — restaurant waiters, signs on doors, people standing in aisles.
Once understanding clicks, return to precise terminology. More jargon = more
confusion, not more clarity.

</what-to-do>

<supporting-info>

## Domain awareness

During codebase exploration, also look for existing documentation:

### File structure

Most repos have a single context:

```
/
├── CONTEXT.md
├── docs/
│   └── adr/
│       ├── 0001-event-sourced-orders.md
│       └── 0002-postgres-for-write-model.md
└── src/
```

If a `CONTEXT-MAP.md` exists at the root, the repo has multiple contexts. The map points to where each one lives:

```
/
├── CONTEXT-MAP.md
├── docs/
│   └── adr/                          ← system-wide decisions
├── src/
│   ├── ordering/
│   │   ├── CONTEXT.md
│   │   └── docs/adr/                 ← context-specific decisions
│   └── billing/
│       ├── CONTEXT.md
│       └── docs/adr/
```

Create files lazily — only when you have something to write. If no `CONTEXT.md` exists, create one when the first term is resolved. If no `docs/adr/` exists, create it when the first ADR is needed.

## During the session

### Challenge against the glossary

When the user uses a term that conflicts with the existing language in `CONTEXT.md`, call it out immediately. "Your glossary defines 'cancellation' as X, but you seem to mean Y — which is it?"

### Sharpen fuzzy language

When the user uses vague or overloaded terms, propose a precise canonical term. "You're saying 'account' — do you mean the Customer or the User? Those are different things."

### Discuss concrete scenarios

When domain relationships are being discussed, stress-test them with specific scenarios. Invent scenarios that probe edge cases and force the user to be precise about the boundaries between concepts.

### Cross-reference with code

When the user states how something works, check whether the code agrees. If you find a contradiction, surface it: "Your code cancels entire Orders, but you just said partial cancellation is possible — which is right?"

### Verify technical claims against documentation

When making claims about what a library, language, or tool can do, verify against the
actual documentation — not memory or assumption. Use Context7 MCP, web_search for
official docs, or read the source code. Never assert "Python does X" or "Flask supports Y"
without checking. The user catches invented claims ("Did you invent any of this?").

**Pitfall — asserting without evidence:** The most damaging pattern is presenting a
technical claim as fact when you haven't checked. Every claim about library behavior
must have a source. When you present findings, separate what you found from what you
propose:

```
Found (in docs/code):   "asyncio.Process.wait() has no timeout parameter"
Proposed (my idea):     "We could use readline() streaming to replace timeouts"
```

This lets the user evaluate the evidence independently from your recommendation.

### Challenge decisions with alternatives

After a decision seems settled, actively search the docs for better alternatives.
Ask: "Is there a different API, pattern, or library that does this better?" The user
will ask this anyway ("challenge what we choose with python docs to see if we had
better alternative"). Be the one to raise it first. Present 2-3 alternatives with
tradeoffs, even if none are better — the act of searching proves the decision is
sound, not lazy.

### Update CONTEXT.md inline

When a term is resolved, update `CONTEXT.md` right there — within the same questioning turn, not
batched for later. Don't wait for the user to ask "are you updating the context as we speak?"
If you answer 4+ questions without a write, you're behind. The document must stay in sync
with the conversation so both parties share a single source of truth.

**Pitfall — deferred updates:** The most common failure mode is answering several questions
in a row, accumulating decisions, then batch-writing CONTEXT.md at the end. This creates a gap
where the user and agent have diverging mental models. The user catches it because they
remember every decision; the agent doesn't notice the drift. Writes should happen every
2-3 resolved questions minimum.

`CONTEXT.md` should be totally devoid of implementation details. Do not treat `CONTEXT.md`
as a spec, a scratch pad, or a repository for implementation decisions. It is a glossary
and nothing else.

**Greenfield projects:** When no domain model exists yet, `CONTEXT.md` starts as an
architecture decisions document — each resolved question becomes a section. As terminology
crystallizes, a Glossary section is added. Once the glossary exists, begin challenging
the user's terms against it. The document evolves from decisions → glossary, not the
other way around. See `references/kb-agent-context-example.md` for a worked example.

### Offer ADRs sparingly

Only offer to create an ADR when all three are true:

1. **Hard to reverse** — the cost of changing your mind later is meaningful
2. **Surprising without context** — a future reader will wonder "why did they do it this way?"
3. **The result of a real trade-off** — there were genuine alternatives and you picked one for specific reasons

If any of the three is missing, skip the ADR. Use the format in [ADR-FORMAT.md](./ADR-FORMAT.md).

</supporting-info>

## Systematic CONTEXT.md vs Code Audit

When the user asks to "review the codebase" or "check implementation against CONTEXT.md", do NOT use conversational grilling. Use the audit methodology:

1. **Extract every verifiable claim** from CONTEXT.md — list them precisely, with line numbers. Do not paraphrase or group.
2. **Verify each claim against actual code** by reading the relevant files — not grepping, not assuming. For each claim, open the file and find the function/line that implements or contradicts it. Mark ✅ or ❌ with the exact line number.
3. **Only report verified findings.** Never claim a drift based on grep alone or on a docstring that may be stale. If you didn't open the file and read the code, don't assert.
4. **Correct yourself when wrong.** If you later find a file that disproves your earlier claim (e.g., `see_also.py` exists but your grep missed it), acknowledge the error explicitly and remove it from the list.

**Pitfall — inventing drift:** The most common failure is reporting a drift based on incomplete evidence (grep didn't find something, a docstring looks wrong). The user catches every unverified claim. Read the file first, then report.

**Pitfall — stale docstrings:** Docstrings can say "Returns: Status string" while the actual code raises `StepError`. Always read the function body, not just the docstring.

## Relationship to `grill-me`

This skill supersedes `grill-me`. The core interviewing loop is identical, but `grill-with-docs` adds domain-model integration: it reads `CONTEXT.md` for the project's glossary, challenges terminology against it, updates it inline as decisions crystallize, and offers ADRs for load-bearing reversals. Prefer `grill-with-docs` for any project that has (or should have) a domain glossary.

## References

- `references/kb-agent-context-example.md` — worked example of a greenfield grilling session producing a full architecture CONTEXT.md
- `references/audit-context-vs-code.md` — systematic codebase audit methodology: claim extraction, file-by-file verification, drift reporting

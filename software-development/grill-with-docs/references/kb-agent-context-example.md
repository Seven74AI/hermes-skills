# Worked Example: KB Agent Architecture (Greenfield)

This is the CONTEXT.md produced during a grilling session that designed a new
knowledge base agent from scratch. No existing domain model existed — the document
evolved from architecture decisions to a glossary over ~20 questions.

## Document structure

```
Architecture Overview (ASCII diagram)
    ↓
Core Decisions (grouped by layer)
    ├── Scope
    ├── Stack
    ├── Ingestion & Routing
    ├── Queue & State Machine
    ├── Consumer Startup & Crash Recovery
    ├── Concurrency
    ├── Error Model
    ├── Pipeline — Mechanical vs LLM
    ├── LLM Interface
    ├── Quality Gates
    ├── See Also
    ├── Visibility
    └── Log Rotation
    ↓
Infrastructure Isolation
Deployment
Book Processing
Testing / Rollout
    ↓
Glossary (terms defined as they crystallized)
    ↓
Remaining Placeholders
```

## Key patterns

### One question at a time
The grilling loop was strictly sequential. Each answer produced either a decision
(locked → write to CONTEXT.md) or a new sub-question. The user's "stop and audit"
requests (reading all KB references, checking for contradictions) were honored
immediately — the grilling paused for them.

### "Fuzzy spots" pass
After the main decision tree was walked (~20 questions), a dedicated pass scanned
for hand-wavy areas: database schema, race conditions, chunking, quality gate
iteration limits, crash recovery, detection priority. 15 fuzzy spots were listed
and resolved one by one.

### Terminology capture
Canonical terms were defined as they emerged:
- "LLM with synthesis-only tools" (not "stateless LLM" — wrong term)
- "PAUSE" (not "skip" — the operator resumes)
- "Orphan process" (subprocess surviving consumer crash)

### Contradiction audit
After the full document was written, a linear scan checked every claim against
every other claim. One contradiction found (SQL table vs Python functions for
content type detection). One ambiguity found (chunk boundary LLM vs synthesis LLM).

### When the skill's own rules don't fit
The skill says "CONTEXT.md is a glossary and nothing else." For greenfield projects,
this is impractical — there are no terms to glossary-ify until decisions exist.
The adaptation: start with decisions, add a glossary as terms crystallize, then
begin challenging against the glossary.

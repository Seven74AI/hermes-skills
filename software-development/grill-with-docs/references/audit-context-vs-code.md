# Systematic CONTEXT.md vs Code Audit

When the user wants to verify that the implementation matches the design document,
use this methodology. It was refined during a kb-agent audit session where the
agent initially invented drifts based on incomplete evidence and was corrected.

## When to use

- User says "review the codebase" or "compare code to CONTEXT.md"
- User asks "liste chaque point du context.md et review l'implémentation point par point"
- User suspects drift between design doc and implementation

## Methodology

### Phase 1: Claim extraction

Read CONTEXT.md completely. Extract every claim that can be verified against code.
Number them. Be precise — quote the exact line, not a paraphrase.

Bad: "LLM should have tools"
Good: "CONTEXT.md lines 210-213: `LLM with synthesis-only tools — read_file, write_file, search_files always.`"

### Phase 2: File-by-file verification

For each claim:
1. Identify which file(s) would implement or contradict it
2. OPEN the file and READ it — do not grep alone
3. Find the exact line that proves or disproves the claim
4. Mark ✅ (aligned) or ❌ (drift) with file:line reference

**Critical pitfall:** A grep that returns nothing is NOT proof of absence. The file may
have been missed because:
- It was created after your file listing
- It lives in an unexpected directory
- Your grep pattern was wrong
- The import happens via a wildcard or dynamic path

Example: `grep -rn 'see_also' agent/pipelines/books.py` returned nothing, but the
file imports `from agent.pipelines.see_also import step_see_also` at line 25.
Always `read_file` the imports section of each pipeline file before concluding.

### Phase 3: Report only verified

Present findings in a table with explicit file:line references:

```
| # | CONTEXT.md | Réalité | Fichier |
|---|-----------|---------|---------|
| 1 | LLM avec tools | LLM reçoit texte dans prompt, pas de tools | llm.py:57-91 |
```

**Never report a drift you haven't verified by reading the actual code.**

### Phase 4: Correct errors

If subsequent reading disproves an earlier claim, remove it immediately.
Do not leave wrong findings in the list because "I already reported them."
The user tracks every claim and will notice uncorrected errors.

## Pitfalls

### Docstrings can lie

A function docstring may say "Returns: Status string" while the actual code
at the bottom raises `StepError(FAIL)`. Always read the function body, not
just the docstring. Docstrings are the most common source of false positives
in drift detection.

### Grep misses dynamic imports

Multiple files may import from `from X import Y` where Y is defined in a
file you didn't list. Always check imports before concluding a feature is
absent.

### Dead code looks alive

A function defined and well-documented may never be called. Check for
callers with grep -rn before marking a feature as "implemented."

Example: `archive_llm_call()` defined in `db.py:296` with full docstring
and schema support. Zero callers in the codebase. Dead code.

### Two implementations of the same concept

Different pipelines may have independent implementations of the same feature
(chunking in web.py vs books.py, minio_upload in every pipeline). This is
code duplication, not drift — but worth noting.

# Updating CONTEXT.md with the Patch Tool

When adding decisions to CONTEXT.md during a grill-with-docs session, the `patch` tool
can silently overwrite previous decisions if used incorrectly.

## The Wrong Pattern (eats decisions)

```
old_string = "6. **Last decision**: ..."
new_string = "7. **New decision**: ..."
```

This **replaces** decision 6 with decision 7. Decision 6 is lost.

## The Correct Pattern (appends)

```
old_string = "6. **Last decision**: ..."
new_string = "6. **Last decision**: ...\n7. **New decision**: ..."
```

This keeps decision 6 AND adds decision 7 after it.

## Or: Append to the Settled Decisions section header

Even better — append to the section boundary:

```
old_string = "## Settled Decisions\n\n"
```

Then include all decisions in `new_string`. But this requires knowing the full list.

## Safest Pattern

Always include the PREVIOUS decision text in the `new_string`, not just the new one.
The `old_string` identifies where to insert; the `new_string` contains both old and new content.

## Verification

After every patch, immediately check the file to confirm no decisions were eaten:
Use a quick verification — count that all expected decision numbers appear consecutively.

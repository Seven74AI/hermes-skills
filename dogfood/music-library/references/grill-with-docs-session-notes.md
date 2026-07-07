# Grill-with-Docs Session Notes

Patterns discovered during the 2026-07-06 audio archiving grill-with-docs session.

## CONTEXT.md Append Pattern

When adding decisions to CONTEXT.md via `patch`, don't replace — append. Use the **last existing decision** as `old_string` and include it in `new_string`:

```
old_string: "N. **Last decision text**"
new_string: "N. **Last decision text**\nN+1. **New decision text**"
```

This avoids the repeated mistake of overwriting the previous decision with the new one.

## User Communication Preferences

- **Letter-labeled options**: When presenting multiple choices, label them A/B/C/D. User prefers replying with a single letter instead of retyping the full answer.
- **One question at a time**: Don't bundle sub-questions. Even tightly-coupled sub-questions should be presented sequentially.
- **Check code, don't assume**: When a question involves how the codebase works, read the actual files rather than guessing.

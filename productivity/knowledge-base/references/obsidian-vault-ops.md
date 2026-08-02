# Obsidian Vault Operations

File-tool-first Obsidian vault work: reading, listing, searching, creating, and editing notes. Originally from the `obsidian` skill, now consolidated under `knowledge-base`.

## Vault path

Use a known or resolved vault path before calling file tools. The vault-path convention is `OBSIDIAN_VAULT_PATH` from `~/.hermes/.env`. If unset, use `~/Documents/Obsidian Vault`.

File tools do not expand shell variables — resolve the vault path first and pass a concrete absolute path. Vault paths may contain spaces; prefer file tools over shell commands.

If the vault path is unknown, `terminal` is acceptable for resolving `OBSIDIAN_VAULT_PATH`. Once the path is known, switch back to file tools.

## Read a note

Use `read_file` with the resolved absolute path. Prefer over `cat` (line numbers + pagination).

## List notes

Use `search_files` with `target: "files"` and the resolved vault path. Prefer over `find` or `ls`.
- List all markdown notes: `pattern: "*.md"` under the vault path.
- List a subfolder: search under that subfolder's absolute path.

## Search

Use `search_files` for both filename and content searches. Prefer over `grep`, `find`, `ls`.
- Filenames: `search_files` with `target: "files"` and filename `pattern`.
- Note contents: `search_files` with `target: "content"`, content regex as `pattern`, and `file_glob: "*.md"`.

## Create a note

Use `write_file` with the resolved absolute path and full markdown content. Prefer over shell heredocs/echo.

## Append to a note

- Read the target note with `read_file`.
- Use `patch` for anchored append when there's stable context.
- Use `write_file` when rewriting the whole note is clearer.
- For simple append with no stable context, `terminal` is acceptable if clearest.

## Targeted edits

Use `patch` for focused note changes with stable context. Prefer over shell text rewriting.

## Wikilinks

Obsidian links notes with `[[Note Name]]` syntax. Use these to link related content.

## Git Sync

For syncing a vault between a server and desktop via GitHub, see `references/git-sync.md` (under the original `obsidian` skill). Covers: repo setup, Obsidian Git plugin config, pitfall checklist.

For cloning an existing vault onto a fresh machine (gh CLI install, PATH shadowing pitfall), see `references/fresh-machine-bootstrap.md`.

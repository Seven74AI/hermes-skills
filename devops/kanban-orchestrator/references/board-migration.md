
# Board Migration — Moving Tasks Between Kanban Boards

When a tenant (e.g. `music-library`) was created on the `default` board instead
of its own board, or when tasks need to move between boards for any reason.

## The problem

There is **no `move` command** between Kanban boards. Each board has its own
SQLite DB with independent task IDs; parent/child links only work within a board.

## The pattern: recreate + archive

```
For each active task on source board:
  1. reclaim  (if running) → resets to ready
  2. unblock  (if blocked) → resets to ready
  3. recreate on target board (title + assignee; skip body for reliability)
  4. archive  on source board
```

## Step-by-step

### 1. Create the target board

```bash
hermes kanban boards create <slug> --name "Display Name"
```

Verify: `hermes kanban boards list`

### 2. List tasks on source board

```bash
hermes kanban --board <source> list --tenant <tenant>
```

### 3. Reclaim running tasks, unblock blocked tasks

**`reclaim` is single-task only** — it accepts exactly one task ID per invocation.
Passing multiple IDs produces `unrecognized arguments`. Loop individually.

**`unblock` and `archive` accept multiple IDs** — batch them for speed.

```bash
# reclaim: one at a time (loop)
hermes kanban --board <source> reclaim <id> --reason 'board migration'

# unblock: batch OK
hermes kanban --board <source> unblock <id1> <id2> <id3> ...

# archive: batch OK
hermes kanban --board <source> archive <id1> <id2> <id3> ...
```

### 4. Recreate on target board + archive on source

```bash
# Create — skip --body for reliability (shell quoting breaks on em dashes, backticks, accents)
hermes kanban --board <target> create "<title>" --assignee "<profile>"

# Archive the original
hermes kanban --board <source> archive <id>
```

### 5. Handle done tasks

Done tasks on the source board can be bulk-archived:
```bash
hermes kanban --board <source> archive <id1> <id2> <id3> ...
```

## CLI pitfalls discovered

### `--board` flag position

The `--board` flag goes **before** the subcommand, not after:
```bash
# CORRECT
hermes kanban --board music-library list

# WRONG — error: unrecognized arguments
hermes kanban list --board music-library
```

### `kanban boards switch` is unreliable for `list`

`hermes kanban boards switch <slug>` may claim success but `kanban list`
still shows the previous board. Always use explicit `--board <slug>` instead
of relying on switch state.

### `archive` has no `--yes` flag

Unlike `hermes profile delete --yes`, the `archive` command has no
confirmation-skip flag — it's non-interactive by default. Just pass task IDs.

### Shell escaping for `--body` is fragile

Task bodies with em dashes (`—`), French accents, backticks, or single
quotes break shell quoting even with `shlex.quote()`. The workaround:
recreate with `--title` and `--assignee` only, skip `--body`. The task
content can be reconstructed from context if needed.

### New board dispatcher claims tasks immediately\n\nWhen you create tasks on a new board, its dispatcher loop claims them\ninstantly. All 40 tasks migrated to `music-library` went from `todo` to\n`running` within seconds — even though the worker profiles were stopped.\n\n**Fix:** Set `kanban.max_spawn` (see main skill doc) **before** bulk-creating\ntasks on a new board. Otherwise, reclaim all tasks after migration to reset\nthem, then unblock in small batches once `max_spawn` is in place.\n\nWithout `max_spawn`: expect a wave of crash/block events as 40+ workers\nOOM the host. Memory example: 40 workers × 120MB RSS = 4.8GB + gateway\n~3.5GB = 8.3GB on an 8GB host → instant OOM kill.

## Parent/child links

Parent/child relationships are board-local and cannot be migrated between
boards. When recreating tasks on a new board, you lose all dependency links.
Re-link them manually after migration if the dependency graph still matters:

```bash
hermes kanban --board <target> link <parent_id> <child_id>
```

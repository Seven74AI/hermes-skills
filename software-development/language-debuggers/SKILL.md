---
name: language-debuggers
description: "Debug Node.js (--inspect, CDP), Python (pdb, debugpy, remote-pdb), and other runtimes — breakpoints, stepping, post-mortem, remote attach."
version: 1.0.0
author: Hermes Agent (curator consolidation)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [debugging, nodejs, python, pdb, debugpy, node-inspect, cdp, breakpoints]
    related_skills: [diagnose, gateway-diagnostics]
---

# Language Debuggers

Debug Node.js and Python runtimes from the terminal — breakpoints, stepping, post-mortem inspection, remote attach. This umbrella covers both languages; use the section matching the runtime.

## When to Use

- A test fails and the traceback/stack trace doesn't reveal why a value is wrong
- You need to step through a function and watch state mutate
- A long-running process (gateway, server, daemon) misbehaves and can't be restarted
- Post-mortem: an exception fired in prod-ish code and you want locals at the crash site
- A subprocess/child process is the actual bug site

**Don't use for:** things `console.log` / `print()` / `logging.debug` solve in under a minute.

---

## Node.js Debugging

Two tools: **`node inspect`** (built-in CLI REPL) for quick poking, and **CDP via `chrome-remote-interface`** for scripted/automated debugging.

### Quick Reference: `node inspect` REPL

Launch paused on first line:

```bash
node inspect path/to/script.js
# or with tsx
node --inspect-brk $(which tsx) path/to/script.ts
```

The `debug>` prompt accepts:

| Command | Action |
|---|---|
| `c` or `cont` | continue |
| `n` or `next` | step over |
| `s` or `step` | step into |
| `o` or `out` | step out |
| `pause` | pause running code |
| `sb('file.js', 42)` | set breakpoint at file.js line 42 |
| `sb(42)` | set breakpoint at line 42 of current file |
| `sb('functionName')` | break when function is called |
| `cb('file.js', 42)` | clear breakpoint |
| `breakpoints` | list all breakpoints |
| `bt` | backtrace (call stack) |
| `list(5)` | show 5 lines of source around current position |
| `watch('expr')` | evaluate expr on every pause |
| `repl` | drop into REPL in current scope (Ctrl+C to exit REPL) |
| `exec expr` | evaluate expression once |
| `restart` | restart script |
| `.exit` | quit debugger |

### Attaching to a Running Node Process

```bash
# Enable inspector on existing process
kill -SIGUSR1 <pid>
# Node prints: Debugger listening on ws://127.0.0.1:9229/<uuid>

# Attach
node inspect -p <pid>
```

### Launch Options

```bash
node --inspect script.js           # listen, keep running
node --inspect-brk script.js       # listen AND pause on first line
node --inspect=0.0.0.0:9230 script.js   # custom host:port

# TypeScript via tsx
node --inspect-brk --import tsx script.ts
```

### Debugging Hermes ui-tui

```bash
cd /home/bb/hermes-agent/ui-tui
npm run build
node --inspect-brk dist/entry.js
# In another terminal:
node inspect -p <node pid>
```

### Programmatic CDP (scripting from terminal)

For automation — set many breakpoints, capture scope state, script a repro. Install `chrome-remote-interface` and write a driver script. Full example at `references/node-cdp-example.js`.

### Node Pitfalls

1. **Wrong line numbers in TS source.** Breakpoints hit emitted JS. Use `node --enable-source-maps` or break in `dist/*.js`.
2. **`--inspect` vs `--inspect-brk`.** Without `-brk`, script races past breakpoints before you attach. Use `--inspect-brk` when setting breakpoints before execution.
3. **Port collisions.** Default 9229. Use `--inspect=0` for random port, read from `/json/list`.
4. **Child processes.** `--inspect` on parent does NOT inspect children. Use `NODE_OPTIONS='--inspect-brk'`.
5. **Running via agent terminal.** Use `terminal(pty=true)` for interactive stepping.
6. **Vitest tests:** Always `--no-file-parallelism` so only one worker exists.

---

## Python Debugging

Three tools, picked by situation:

| Tool | When |
|---|---|
| **`breakpoint()` + pdb** | Local, interactive, simplest |
| **`python -m pdb`** | Launch script under pdb with no source edits |
| **`debugpy` / `remote-pdb`** | Remote / headless / attach to already-running process |

### pdb Quick Reference

Inside any pdb prompt `(Pdb)`:

| Command | Action |
|---|---|
| `n` | next line (step over) |
| `s` | step into |
| `r` | return from current function |
| `c` | continue |
| `unt N` | continue until line N |
| `l` / `ll` | list source / full function |
| `w` | where (stack trace) |
| `u` / `d` | move up/down stack |
| `a` | print args of current function |
| `p expr` / `pp expr` | print / pretty-print expression |
| `display expr` | auto-print expr on every stop |
| `b file:line` | set breakpoint |
| `b func` | break on function entry |
| `tbreak file:line` | one-shot breakpoint |
| `!stmt` | execute arbitrary Python |
| `interact` | drop into full Python REPL (Ctrl+D to exit) |
| `q` | quit |

### Recipe: Local breakpoint

```python
def compute(x, y):
    result = some_helper(x)
    breakpoint()           # drops into pdb here
    return result + y
```

Run normally. Don't forget to remove `breakpoint()` before committing.

### Recipe: Debug a pytest test

```bash
# Drop to pdb on failure (NO xdist!)
python -m pytest tests/path/test.py::test_name --pdb -p no:xdist

# Drop at test START
python -m pytest tests/path/test.py::test_name --trace -p no:xdist
```

**Critical:** pdb does NOT work under pytest-xdist. Always add `-p no:xdist` or `-n 0`.

### Recipe: Post-mortem on exception

```python
import pdb, sys
try:
    run_the_thing()
except Exception:
    pdb.post_mortem(sys.exc_info()[2])
```

### Recipe: Remote debug with remote-pdb (agent-friendly)

```bash
pip install remote-pdb
```

In your code:
```python
from remote_pdb import set_trace
set_trace(host="127.0.0.1", port=4444)   # blocks until connection
```

Then: `nc 127.0.0.1 4444` → full pdb prompt.

### Recipe: Remote debug with debugpy (DAP, IDE-friendly)

```bash
pip install debugpy
```

Launch with debugpy:
```bash
python -m debugpy --listen 127.0.0.1:5678 --wait-for-client your_script.py
```

Or attach to running process:
```bash
python -m debugpy --listen 127.0.0.1:5678 --pid <pid>
```

Connect from VS Code / Cursor with a `launch.json` attach config (see `references/python-debugpy-attach.md`).

### Debugging Hermes Gateway / Workers

For `_SlashWorker` subprocess: use `remote-pdb` with `set_trace()` inside the worker's `exec` path. The worker is persistent across slash commands.

For `tui_gateway`: use `debugpy` + `--wait-for-client` or `remote-pdb` at a handler.

### Python Pitfalls

1. **pdb under pytest-xdist silently does nothing.** Always `-p no:xdist`.
2. **`breakpoint()` in CI / non-TTY hangs.** Never commit it.
3. **`PYTHONBREAKPOINT=0`** disables all `breakpoint()` calls.
4. **`debugpy.listen` needs `wait_for_client()`** or execution races past.
5. **Attach to PID fails on hardened kernels** (`ptrace_scope=1`). Use `sudo echo 0 > /proc/sys/kernel/yama/ptrace_scope`.
6. **Forking / multiprocessing:** pdb does not follow forks. Debug one process at a time.
7. **`scripts/run_tests.sh` strips credentials.** If bug depends on real config, test with raw `pytest`.

## Verification Checklist

After any debug session:
- [ ] First breakpoint actually hits (verify with `w` / `bt`)
- [ ] Source listing shows the right file
- [ ] Post-debug: no stray `breakpoint()` / `set_trace()` in committed code
  ```bash
  rg -n 'breakpoint\(\)|set_trace\(|debugpy\.listen' --type py
  rg -n 'debugger' --type ts --type tsx
  ```

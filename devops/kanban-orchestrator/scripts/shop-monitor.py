#!/usr/bin/env python3
"""Auto-fix Kanban board monitor — logs to /tmp/<board>-monitor.log

Every 2 minutes: scans running/blocked tasks, applies auto-fixes,
and reports progress. Stops when all tasks done.

Auto-fixes applied:
  • max_runtime_seconds NULL → 600s
  • Worker PID dead → reclaim
  • Stale heartbeat >30min + running >1h → reclaim
  • High run count (>5) + stale → rt=600s + reclaim
  • Blocked by timeout/budget/watchdog → unblock + reset failures

Usage:
  python3 scripts/shop-monitor.py <board>
  # Or inline:
  python3 -c "BOARD='shop'; exec(open('scripts/shop-monitor.py').read())"
"""
import sqlite3, time, os, subprocess, sys
from pathlib import Path

BOARD = sys.argv[1] if len(sys.argv) > 1 else 'shop'
LOG = Path(f'/tmp/{BOARD}-monitor.log')
DB = Path(f'/root/.hermes/kanban/boards/{BOARD}/kanban.db')
last_done = 0
last_running = set()

def log_msg(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    with open(LOG, 'a') as f:
        f.write(line + '\n')
    print(line, flush=True)

def run(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=20)
        return r.returncode == 0
    except:
        return False

def status():
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    running = {}
    for r in conn.execute("SELECT id, title FROM tasks WHERE status='running'"):
        running[r['id']] = r['title']
    counts = {}
    for r in conn.execute("SELECT status, COUNT(*) as cnt FROM tasks GROUP BY status"):
        counts[r['status']] = r['cnt']
    total = sum(counts.values())
    resolved = counts.get('done', 0) + counts.get('archived', 0)
    conn.close()
    return running, counts, total, resolved

def health_check():
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    now = time.time()
    fixed = []
    
    rows = conn.execute("""
        SELECT t.id, t.title, t.max_runtime_seconds, t.last_heartbeat_at,
               t.started_at, t.consecutive_failures, t.worker_pid,
               (SELECT COUNT(*) FROM task_runs WHERE task_id = t.id) AS total_runs,
               (SELECT COUNT(*) FROM task_runs WHERE task_id = t.id AND outcome = 'timed_out') AS timeouts,
               (SELECT COUNT(*) FROM task_runs WHERE task_id = t.id AND error LIKE '%budget exhausted%') AS budgets
        FROM tasks t WHERE t.status = 'running'
    """).fetchall()
    
    for r in rows:
        tid = r['id']
        rt = r['max_runtime_seconds'] or 0
        hb = r['last_heartbeat_at'] or 0
        started = r['started_at'] or now
        pid = r['worker_pid']
        age = int((now - started) / 60)
        hb_age = int((now - hb) / 60) if hb else 999
        
        if rt == 0:
            conn.execute("UPDATE tasks SET max_runtime_seconds = 600 WHERE id = ?", (tid,))
            conn.commit()
            log_msg(f"  🔧 {tid}: max_runtime NULL → 600s")
            fixed.append(tid)
        elif pid:
            try:
                os.kill(pid, 0)
            except OSError:
                run(f"hermes kanban --board {BOARD} reclaim {tid}")
                log_msg(f"  🔄 {tid}: PID {pid} mort → reclaimed")
                fixed.append(tid)
        elif age > 60 and hb_age > 30:
            run(f"hermes kanban --board {BOARD} reclaim {tid}")
            log_msg(f"  🔄 {tid}: {age}m old, hb={hb_age}m stale → reclaimed")
            fixed.append(tid)
        elif r['total_runs'] >= 5 and hb_age > 20:
            conn.execute("UPDATE tasks SET max_runtime_seconds = 600 WHERE id = ?", (tid,))
            conn.commit()
            run(f"hermes kanban --board {BOARD} reclaim {tid}")
            log_msg(f"  🔄 {tid}: {r['total_runs']}x runs stale → rt=600s + reclaimed")
            fixed.append(tid)
    
    blocked = conn.execute("SELECT id, last_failure_error FROM tasks WHERE status='blocked'").fetchall()
    for b in blocked:
        err = (b['last_failure_error'] or '').lower()
        if any(kw in err for kw in ['timed_out', 'budget exhausted', 'watchdog auto-block', 'iteration']):
            conn.execute("UPDATE tasks SET max_runtime_seconds=600, consecutive_failures=0 WHERE id=?", (b['id'],))
            conn.commit()
            run(f"hermes kanban --board {BOARD} unblock {b['id']}")
            log_msg(f"  🔓 {b['id']}: auto-unblocked")
            fixed.append(b['id'])
    
    conn.close()
    return fixed

# ── Main ──
with open(LOG, 'w') as f:
    f.write('')

log_msg(f"🛒 {BOARD} monitor START — auto-fix ON")

first = True
while True:
    running, counts, total, resolved = status()
    pct = round(resolved / total * 100) if total else 0
    new_done = counts.get('done', 0) - last_done
    finished = last_running - set(running.keys())
    new_running = set(running.keys()) - last_running
    
    fixed = health_check()
    
    if first:
        log_msg(f"  State: {pct}% ({resolved}/{total}) | R:{len(running)} Ready:{counts.get('ready',0)} Todo:{counts.get('todo',0)} Blocked:{counts.get('blocked',0)}")
        first = False
    else:
        parts = []
        if new_done: parts.append(f"✨ +{new_done}")
        if finished: parts.append(f"✅ {len(finished)} fini")
        if new_running: parts.append(f"▶ {len(new_running)} started")
        if parts:
            log_msg(f"  {pct}% ({resolved}/{total}) | {' | '.join(parts)}")
    
    if len(running) == 0 and counts.get('ready', 0) == 0 and counts.get('todo', 0) == 0 and counts.get('blocked', 0) == 0:
        log_msg(f"🎉 ALL DONE! {resolved}/{total} ({pct}%)")
        break
    
    last_done = counts.get('done', 0)
    last_running = set(running.keys())
    time.sleep(120)

#!/usr/bin/env python3
"""CI Watchdog for <BOARD> — merges green PRs on <FORK>, unblocks linked kanban tasks.

Deploy: hermes cron create --name "<board> CI watchdog" --schedule "every 2m" --script ci-watchdog-<board>.py --no-agent --deliver local
"""
import sqlite3, subprocess, json, re, sys

BOARD = '<board>'      # CHANGE ME
REPO = '<org>/<repo>'  # CHANGE ME — fork repo (e.g. Seven74AI/shop)
DB = f'/root/.hermes/kanban/boards/{BOARD}/kanban.db'

def run_kanban(cmd):
    full = f"hermes kanban --board {BOARD} {cmd}"
    r = subprocess.run(full, shell=True, capture_output=True, text=True, timeout=30)
    return r.returncode == 0, (r.stdout + r.stderr).strip()

def merge_pr(pr_num, strategy='merge'):
    r = subprocess.run(
        ['gh', 'pr', 'merge', str(pr_num), '--repo', REPO, f'--{strategy}', '--delete-branch'],
        capture_output=True, text=True, timeout=20
    )
    out = (r.stdout + r.stderr).lower()
    return 'successfully merged' in out or 'already merged' in out

def check_ci(pr_num):
    pr = subprocess.run(
        ['gh', 'pr', 'view', str(pr_num), '--repo', REPO, '--json', 'headRefName', '--jq', '.headRefName'],
        capture_output=True, text=True, timeout=10
    )
    if pr.returncode != 0: return 'none', None, None
    branch = pr.stdout.strip()
    if not branch: return 'none', None, None
    runs = subprocess.run(
        ['gh', 'run', 'list', '--repo', REPO, '--branch', branch, '--limit', '1',
         '--json', 'status,conclusion,url',
         '--jq', r'.[0] | "\(.status)|\(.conclusion)|\(.url)"'],
        capture_output=True, text=True, timeout=10
    )
    if runs.returncode != 0 or not runs.stdout.strip(): return 'none', None, None
    parts = runs.stdout.strip().split('|')
    if len(parts) < 2: return 'none', None, None
    if parts[0] != 'completed': return 'running', None, parts[2] if len(parts) > 2 else None
    return 'completed', parts[1] or 'none', parts[2] if len(parts) > 2 else None

def find_labeled_prs():
    """Find open PRs with kanban: labels using jq client-side filter.
    gh --label does exact match (not prefix), so we filter in jq instead."""
    try:
        prs = json.loads(subprocess.run(
            ['gh', 'pr', 'list', '--repo', REPO, '--state', 'open',
             '--json', 'number,labels,headRefName',
             '--jq', '[.[] | select(.labels[].name | startswith("kanban:")) | {number, labels: [.labels[].name], headRefName}]'],
            capture_output=True, text=True, timeout=10
        ).stdout)
    except: return {}
    labeled = {}
    for pr in prs:
        for label in pr.get('labels', []):
            if label.startswith('kanban:'):
                labeled[label.split(':', 1)[1]] = (pr['number'], pr['headRefName'])
    return labeled

def find_blocked_tasks(conn):
    """Find tasks awaiting CI — by block event reason, NOT by task status.

    CRITICAL: Do NOT filter on t.status = 'blocked'. Tasks can be promoted to
    'ready' or re-claimed to 'running' by the Kanban Block Watchdog while still
    waiting for CI. Filtering by status misses them and leaves them stuck.

    Instead, find all non-terminal tasks that have ANY block event with
    'awaiting CI' in the reason, regardless of their current status.
    """
    rows = conn.execute("""
        SELECT t.id, te.payload FROM tasks t
        JOIN task_events te ON te.task_id = t.id
        WHERE te.kind = 'blocked'
          AND te.payload LIKE '%awaiting CI%'
          AND t.status NOT IN ('archived', 'completed', 'cancelled', 'done')
        ORDER BY te.id DESC
    """).fetchall()
    seen, result = set(), []
    for tid, payload in rows:
        if tid not in seen:
            seen.add(tid)
            m = re.search(r'kanban:(t_[a-f0-9]+)', payload or '')
            result.append((tid, m.group(1) if m else tid))
    return result

def main():
    conn = sqlite3.connect(DB)
    labeled = find_labeled_prs()
    blocked = find_blocked_tasks(conn)
    work = False
    
    for task_id, label_tid in blocked:
        pr = labeled.get(label_tid) or labeled.get(task_id)
        if not pr: continue
        pr_num, branch = pr
        ci_status, ci_conclusion, ci_url = check_ci(pr_num)
        
        if ci_status == 'running': continue
        
        if ci_status == 'completed' and ci_conclusion == 'success':
            if merge_pr(pr_num):
                conn.execute("DELETE FROM task_comments WHERE task_id = ? AND body LIKE '%github.com%pull%'", (task_id,))
                conn.commit()
                run_kanban(f'comment "{task_id}" "[CI-WATCHDOG] CI passed — PR merged."')
                run_kanban(f'unblock "{task_id}"')
                print(f"  {task_id[:12]} | merged PR #{pr_num}")
                work = True
            else:
                run_kanban(f'comment "{task_id}" "[CI-WATCHDOG] Merge failed — possible conflict."')
                run_kanban(f'unblock "{task_id}"')
                print(f"  {task_id[:12]} | merge FAILED")
                work = True
        elif ci_status == 'completed' and ci_conclusion == 'failure':
            try:
                log_r = subprocess.run(['gh', 'run', 'view', ci_url, '--repo', REPO, '--log-failed'], capture_output=True, text=True, timeout=15)
                err = ((log_r.stderr or log_r.stdout) or "CI failed")[-300:]
            except: err = "CI failed"
            run_kanban(f'comment "{task_id}" "[CI-WATCHDOG] CI failed: {err[:250]}"')
            run_kanban(f'unblock "{task_id}"')
            print(f"  {task_id[:12]} | CI FAILED")
            work = True
    
    conn.close()
    if work: print("Done.")

if __name__ == '__main__':
    main()

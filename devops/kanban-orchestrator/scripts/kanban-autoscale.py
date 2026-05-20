#!/usr/bin/env python3
"""Auto-scale Hermes Kanban profiles based on board load.

Scale-up: clone profiles when ready_tasks > available_profiles * threshold
Scale-down: delete idle clone profiles (no tasks assigned to that specific clone)

Runs as a no_agent cron job. Recommended interval: every 5m.

Deploy:
  hermes cron create "every 5m" --name kanban-autoscale \\
    --no-agent --script kanban-autoscale.py
"""

import subprocess
import json
import re
import sys
import os

MAX_PROFILES_PER_ROLE = 1  # Hard cap: no clones — 1 per role
SCALE_UP_THRESHOLD = 2  # ready > profiles * threshold => clone


def run(cmd, env=None):
    """Run a shell command and return stdout, stderr, returncode."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30,
            env=env or os.environ
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "timeout", 1
    except Exception as e:
        return "", str(e), 1


def base_role(name):
    """Strip -N suffix to get base role name."""
    return re.sub(r'-\d+$', '', name)


def is_clone(name):
    """Check if a profile is a clone (has -N suffix where N is a digit)."""
    return bool(re.search(r'-\d+$', name))


def get_profiles():
    """Parse 'hermes profile list' output to get profile names."""
    stdout, _, rc = run("hermes profile list 2>/dev/null")
    if rc != 0:
        return []

    profiles = []
    for line in stdout.split('\n'):
        line = line.strip()
        # Skip header, separators, empty lines
        if not line or line.startswith('Profile') or '─' in line:
            continue
        # Parse: "  music-coder     deepseek-v4-pro    stopped    ..."
        parts = line.split()
        if parts:
            name = parts[0].lstrip('◆')  # Remove default marker
            if name and '─' not in name:
                profiles.append(name)
    return profiles


def get_boards():
    """Get all kanban board slugs."""
    stdout, _, rc = run("hermes kanban boards list --json 2>/dev/null")
    if rc != 0 or not stdout:
        return ["default"]

    try:
        boards = json.loads(stdout)
        # Filter out archived boards
        return [b["slug"] for b in boards if not b.get("archived", False)]
    except (json.JSONDecodeError, KeyError):
        return ["default"]


def get_tasks_for_board(board_slug):
    """Get all non-archived tasks for a board."""
    env = {**os.environ, "HERMES_KANBAN_BOARD": board_slug}
    stdout, _, rc = run("hermes kanban list --json 2>/dev/null", env=env)
    if rc != 0 or not stdout:
        return []

    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return []


def analyze_and_scale():
    """Main auto-scale logic."""
    profiles = get_profiles()
    if not profiles:
        print("No profiles found, skipping.")
        return

    boards = get_boards()

    # Collect all tasks across all boards
    all_tasks = []
    for board in boards:
        tasks = get_tasks_for_board(board)
        all_tasks.extend(tasks)

    role_ready = {}
    role_running = {}
    role_total = {}

    for task in all_tasks:
        assignee = task.get("assignee", "")
        if not assignee:
            continue
        role = base_role(assignee)
        status = task.get("status", "")

        role_total[role] = role_total.get(role, 0) + 1
        if status == "ready":
            role_ready[role] = role_ready.get(role, 0) + 1
        elif status == "running":
            role_running[role] = role_running.get(role, 0) + 1

    # Count available profiles per role
    role_profiles = {}
    for p in profiles:
        if p == "default":
            continue
        role = base_role(p)
        role_profiles[role] = role_profiles.get(role, 0) + 1

    # === SCALE-UP ===
    for role, current_count in list(role_profiles.items()):
        ready_count = role_ready.get(role, 0)
        running_count = role_running.get(role, 0)

        if ready_count == 0:
            continue

        # Account for running tasks consuming profiles
        effective_available = current_count - running_count
        if effective_available < 0:
            effective_available = 0

        # Need more profiles if ready tasks exceed effective capacity
        needed = (ready_count + SCALE_UP_THRESHOLD - 1) // SCALE_UP_THRESHOLD
        needed = max(needed, current_count)

        if needed > current_count and current_count < MAX_PROFILES_PER_ROLE:
            to_create = min(needed - current_count, MAX_PROFILES_PER_ROLE - current_count)

            # Determine next clone number
            existing_nums = set()
            for p in profiles:
                if base_role(p) == role and is_clone(p):
                    m = re.search(r'-(\d+)$', p)
                    if m:
                        existing_nums.add(int(m.group(1)))

            next_num = 2  # Start from 2 (base profile has no suffix)
            while next_num in existing_nums:
                next_num += 1

            for i in range(to_create):
                clone_name = f"{role}-{next_num + i}"
                print(f"[scale-up] Creating {clone_name} (ready={ready_count}, "
                      f"profiles={current_count}, threshold={SCALE_UP_THRESHOLD})")
                stdout, stderr, rc = run(
                    f"hermes profile create {clone_name} --clone-from {role} 2>&1"
                )
                if rc == 0:
                    print(f"  -> Created {clone_name}")
                    current_count += 1
                else:
                    print(f"  -> Failed: {stderr}")

    # Count tasks per specific assignee (not just per role)
    assignee_total = {}
    for task in all_tasks:
        assignee = task.get("assignee", "")
        if assignee:
            assignee_total[assignee] = assignee_total.get(assignee, 0) + 1

    # === SCALE-DOWN ===
    for p in profiles:
        if p == "default":
            continue
        if not is_clone(p):
            continue

        role = base_role(p)
        profile_task_count = assignee_total.get(p, 0)

        # Only delete if this specific clone has no tasks assigned
        # AND there are other profiles for this role (keep at least 1)
        if profile_task_count == 0 and role_profiles.get(role, 0) > 1:
            print(f"[scale-down] Deleting idle clone {p} (no tasks, "
                  f"{role_profiles[role]} profiles for role '{role}')")
            stdout, stderr, rc = run(
                f"echo '{p}' | hermes profile delete {p} 2>&1"
            )
            if rc == 0:
                print(f"  -> Deleted {p}")
                role_profiles[role] -= 1
            else:
                print(f"  -> Failed: {stderr[:200]}")


if __name__ == "__main__":
    analyze_and_scale()

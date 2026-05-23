#!/usr/bin/env python3
"""Prune state-snapshots, keeping only the N most recent."""
import os, glob, shutil

KEEP = 2
SNAPSHOT_DIR = os.path.expanduser("~/.hermes/state-snapshots")

snapshots = sorted(
    [d for d in glob.glob(os.path.join(SNAPSHOT_DIR, "*/")) if os.path.isdir(d)],
    reverse=True,
)

kept = snapshots[:KEEP]
removed = [s for s in snapshots[KEEP:] if s not in kept]

for snap in removed:
    size = sum(
        os.path.getsize(os.path.join(dp, f))
        for dp, _, files in os.walk(snap)
        for f in files
    )
    shutil.rmtree(snap, ignore_errors=True)
    print(f"Removed: {snap} ({size/1024/1024:.0f}M)")

print(f"Kept {len(kept)}, removed {len(removed)} snapshots.")

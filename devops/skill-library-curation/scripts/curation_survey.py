#!/usr/bin/env python3
"""Curator survey: enumerate skills with provenance, flag near-duplicates, check references.

Symlink-safe — the Matt-Pocock engineering skills are symlinked dirs into
`.hermes/mattpocock-skills/`, which `Path.rglob` misses. This uses
os.walk(followlinks=True) with a visited-set guard against symlink cycles.

Usage: python3 curation_survey.py [--min-sim 0.70]
"""
import os
import re
import sys
import json
from collections import Counter
from itertools import combinations

SKILLS = os.path.expanduser("~/.hermes/skills")
MIN_SIM = 0.70
if "--min-sim" in sys.argv:
    MIN_SIM = float(sys.argv[sys.argv.index("--min-sim") + 1])

STOP = set("""a an and are as at be but by for if in into is it its no not of on or
such that the their then there these they this to was will with your you we i he
she it they our us them me my""".split())


def read_name(text):
    in_fm = False
    for line in text.split("\n"):
        s = line.strip()
        if s == "---":
            if in_fm:
                break
            in_fm = True
            continue
        if in_fm and s.startswith("name:"):
            return s.split(":", 1)[1].strip().strip("\"'")
    return None


def body_tokens(text):
    parts = text.split("---", 2)
    body = parts[2] if len(parts) >= 3 else text
    return [w for w in re.findall(r"[a-z][a-z0-9_\-]{2,}", body.lower()) if w not in STOP]


def load_manifest_names(path):
    if not os.path.exists(path):
        return set()
    names = set()
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and ":" in line:
            names.add(line.split(":", 1)[0].strip())
    return names


def main():
    bundled = load_manifest_names(os.path.join(SKILLS, ".bundled_manifest"))
    hub = set()
    lock = os.path.join(SKILLS, ".hub", "lock.json")
    if os.path.exists(lock):
        data = json.load(open(lock, encoding="utf-8"))
        for k, v in (data.get("installed") or {}).items():
            hub.add(k)
            if isinstance(v, dict) and v.get("install_path"):
                hub.add(os.path.basename(v["install_path"]))

    # Symlink-safe walk with cycle guard.
    info = {}
    visited = set()
    for root, dirs, files in os.walk(SKILLS, followlinks=True):
        rp = os.path.realpath(root)
        if rp in visited:
            dirs[:] = []
            continue
        visited.add(rp)
        if ".archive" in root.split(os.sep) or ".curator_backups" in root.split(os.sep):
            dirs[:] = []
            continue
        if "SKILL.md" in files:
            path = os.path.join(root, "SKILL.md")
            try:
                text = open(path, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            name = read_name(text) or os.path.basename(root)
            origin = "agent"
            if name in bundled:
                origin = "bundled"
            elif name in hub:
                origin = "hub"
            info[name] = dict(origin=origin, path=path, toks=body_tokens(text))

    agent = sorted(n for n, v in info.items() if v["origin"] == "agent")
    print(f"skills: {len(info)} total  (agent={len(agent)} bundled="
          f"{sum(1 for v in info.values() if v['origin']=='bundled')} "
          f"hub={sum(1 for v in info.values() if v['origin']=='hub')})")

    def cosine(a, b):
        ca, cb = Counter(a), Counter(b)
        keys = set(ca) | set(cb)
        dot = sum(ca[k] * cb[k] for k in keys)
        na = sum(v * v for v in ca.values()) ** 0.5
        nb = sum(v * v for v in cb.values()) ** 0.5
        return 0.0 if na == 0 or nb == 0 else dot / (na * nb)

    def jaccard(a, b):
        sa, sb = set(a), set(b)
        return 0.0 if not sa or not sb else len(sa & sb) / len(sa | sb)

    print(f"\n=== AGENT-AGENT near-duplicates (>={MIN_SIM:.0%}) ===")
    found = False
    for a, b in combinations(agent, 2):
        score = max(jaccard(info[a]["toks"], info[b]["toks"]),
                    cosine(info[a]["toks"], info[b]["toks"]))
        if score >= MIN_SIM:
            found = True
            print(f"  {score:.2f}  {a}  <->  {b}")
    if not found:
        print("  (none)")

    # related_skills integrity
    print("\n=== broken related_skills references ===")
    existing = set(info)
    bad = 0
    for n, v in info.items():
        m = re.search(r"related_skills:\s*\[([^\]]*)\]",
                      open(v["path"], encoding="utf-8", errors="replace").read())
        if not m:
            continue
        for r in m.group(1).split(","):
            r = r.strip().strip("'\"")
            if r and r not in existing:
                bad += 1
                print(f"  {n} -> {r} [MISSING]")
    if bad == 0:
        print("  (none)")


if __name__ == "__main__":
    main()

# Operational Infrastructure — Cron Jobs

All cron jobs as of 2026-05-21. See `cronjob(action='list')` for live state.

## Active (24 → 21 active after cleanup)

### Infrastructure (5)
| Job ID | Name | Schedule | Agent? | Notes |
|--------|------|----------|--------|-------|
| `10cb5de254d0` | CI Watchdog (light) | 2m | no_agent | `ci-watchdog-light.py`. Unblocks tasks when kanban-labeled PRs are merged. GitHub auto-merge handles the merge itself. Silent when clean (`deliver: local`). |
| `7ad8ddd5b9c9` | Kanban Block Watchdog | 5m | no_agent | `watchdog-all.py`. Scans ALL boards for blocked tasks + review deadlocks. Delivers to Discord #alert-low. |
| `ceead0ca5089` | Pre-Spawn Health Watchdog | 5m | no_agent | `pre-spawn-watchdog.py`. Validates ready tasks (skills, max_runtime, PR URLs). Notification-only, no auto-fix. |
| `eb1ab33f9bf4` | kanban workspace GC | 15m | no_agent | `kanban-gc-workspaces.py`. Deletes scratch workspaces of done/archived tasks >5min old. Redundant with native `hermes kanban gc` — ⚠️ TO AUDIT. |
| `4eee7fb0b484` | Daily Skills Sync to GitHub | 3:30am | no_agent | `sync-skills-to-github.py`. Pushes custom skills to Seven74AI/hermes-skills. Curated per-profile, not blanket. |

### Monitoring (4)
| `9fbadfbd593e` | Disk Space Watchdog | 10m | no_agent | `disk-watchdog.py`. Alerts Discord #alert-low when disk >80%. |
| `1eed9aea8bfe` | Memory Watchdog | 5m | no_agent | `mem-watchdog.py`. Alerts on high memory pressure. |
| `bfe929afb12e` | CPU Watchdog | 5m | no_agent | `cpu-watchdog.py`. Alerts on sustained high CPU. |
| `b79b6b9ab2db` | Gateway Watchdog | 5m | no_agent | `gateway-watchdog.py`. Checks `systemctl status hermes-gateway`. |

### Content (7)
| `375a7bec3a47` | Twitter Digest Dev/AI | 7am | agent | Delivers to Discord. |
| `c1ec6870ff46` | Twitter Digest Crypto | 7am | agent | Delivers to Discord. |
| `6de540294ee1` | arXiv Daily Digest | 8am | agent | Delivers to Discord. |
| `f6a88cf7a87f` | Polymarket Daily Snapshot | 8am | agent | Delivers to Discord. |
| `f831b59a067f` | Hermes Chronicle Daily Journal | 5am | agent | Delivers to Discord. |
| `adb27516bf29` | HuggingFace Weekly Trending | Mon 9am | agent | Never executed — ⚠️ TO AUDIT. |
| `b4e9989d4d72` | Edgee Lab Daily Report | 9am | agent | **PAUSED** (project inactive). |

### Self-Improvement (4)
| `10798a2ec60c` | nightly-reflector | 1am | agent | Analyzes past 24h sessions. |
| `8c631c426b69` | midday-reflector | 1pm | agent | Same as nightly — ⚠️ TO AUDIT (redundant?). |
| `2e1f5c35f5aa` | weekly-curator | Sun 3am | agent | Curates agent-created skills. |
| `5570e75c5f31` | SOUL Harmonizer | Mon/Thu 9am | agent | Reviews SOUL.md consistency. |

### Other (2)
| `8628d151e230` | hermes-daily-backup | 4am | agent | Backs up Hermes to GitHub. |
| `7776f7e3b0a2` | kanban velocity registry | 3am | no_agent | `kanban-velocity-record.py`. Tracks velocity stats. |
| `4423bee366e6` | Disk Cleanup Agent | 10m | agent | LLM-driven cleanup. ⚠️ TO AUDIT (expensive LLM task). |

## Paused (inactive projects)
| `b4e9989d4d72` | Edgee Lab Daily Report | 9am | Paused 2026-05-21 |
| `cffd88539f6a` | Edgee Lab Strategy Research | 180m | Paused 2026-05-21 |

## ⚠️ To Audit (pending user decision)
| Job ID | Name | Question |
|--------|------|----------|
| `8c631c426b69` | midday-reflector | Redundant with nightly-reflector? |
| `4423bee366e6` | Disk Cleanup Agent | LLM every 10min expensive. Script-only watchdog sufficient? |
| `adb27516bf29` | HuggingFace Weekly | Never executed. Still needed? |
| `eb1ab33f9bf4` | kanban workspace GC | Redundant with native `hermes kanban gc`? |

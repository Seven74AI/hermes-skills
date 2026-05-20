---
name: glance
description: "Glance project configuration — screen sharing tool for AI interaction. Mac first, cross-platform later."
version: 1.0.0
metadata:
  hermes:
    tags: [glance, startup, screen-sharing, ai, desktop, project, kanban]
---

# Glance — Project Configuration

Quick-reference config. Load this skill when working on Glance.

## Concept

**Glance** — Share any screen or window (Mac first, Linux/PC later) with an AI so it can see and interact with it in real-time. Use cases: pair programming, debugging, teaching, automation, accessibility.

## Status (2026-05-19)

MVP code complete — all 6 phases + spike delivered (~15 Swift source files). Blocked on Mac hardware for compilation/testing. Landing page live at https://seven74ai.github.io/glance/.

| Phase | Status | What |
|-------|--------|------|
| 0.1 Spike | ✅ | SCK → Metal → JPEG CLI pipeline |
| 0.2 Landing | ✅ | GitHub Pages + Formspree waitlist |
| 1.1 CaptureEngine | ✅ | SCStream wrapper + permission handling |
| 1.2 Metal | ✅ | GPU-accelerated preprocessing + JPEG encoder |
| 1.3 AI Provider | ✅ | Claude/GPT-4o/Gemini vision clients |
| 1.4 Menu Bar UI | ✅ | NSStatusBar app + overlay + state machine |
| 1.5 Integration | ✅ | Full app bundle wiring all modules |

### Blockers
- 🔴 Never compiled on Mac — all code developed on Linux. Requires M1+ Mac running macOS 14+.
- 🟡 Waitlist not activated (Formspree confirmation pending in AgentMail)
- ✅ CI protocol conformance: fixed (commit 5c242ce)
- ✅ SwiftLint: fixed (PR #1 — trailing commas + line length)

### CI
- `.github/workflows/ci.yml` — SwiftLint + Build & Test on macos-14
- CI failures are tracked as kanban tickets on the `glance` board

## GitHub

`Seven74AI/glance` — fresh repo, no fork upstream.
**Code MUST be pushed to GitHub.** Every coder task MUST end with `git push origin main` before blocking for review.

## Kanban

Board: `glance`
Tenant: `glance`

## Discord

Channel: `#seven-ai`

## Profiles

4 generic profiles: `coder`, `reviewer`, `researcher`, `planner`.

## Development

- Mac first (Swift/Metal/ScreenCaptureKit), cross-platform later
- Real-time screen capture + AI inference pipeline
- Interaction layer: AI can see pixels, OCR, UI element detection, and suggest actions
- No game engine — standard macOS/Linux tooling

## Testing

TDD is mandatory. Load `test-driven-development` skill for every coder task.
CI pipeline required before PR.

## Pipeline

Researcher → Planner → Coder → Reviewer → Done.
Research must complete before planning. Planning before coding.

## Non-Mac Tasks (workable from Linux)

While waiting for Mac hardware, these tasks can be done from the Linux server:

| Type | Example tickets |
|------|----------------|
| **Docs** | README (arch, setup, contribute, stack), API docs, dev onboarding |
| **Landing** | A/B testing, analytics, Formspree activation, more content |
| **CI** | Split SwiftLint/Build into separate jobs, add SPM caching, better test reporting |
| **Lint fixes** | SwiftLint violations (trailing commas, line length) — fixable without compilation |
| **Research** | Linux PipeWire/XDG Portal, Windows Graphics Capture APIs (prepare cross-platform) |
| **Legal** | Privacy policy, terms of service, GDPR compliance draft |
| **Marketing** | README badges, social preview images, demo video storyboard |

## CI Protocol Conformance (CaptureProtocols.swift)

The `CaptureProtocols.swift` file defines testable protocol abstractions for ScreenCaptureKit types. These must match the **real** SCK API signatures on macOS 14+, or CI fails on `macos-14` runners:

| Protocol property | Current (broken) | Should be |
|---|---|---|
| `SCStreamConfigurationProtocol.pixelFormat` | `Int { get set }` | `CFString { get set }` |
| `SCContentFilterProtocol.contentRect` | `CGRect { get set }` | `CGRect { get }` (read-only) |
| `SCContentFilterProtocol.pointPixelScale` | `CGFloat { get set }` | `CGFloat { get }` (read-only) |
| `WindowProtocol.title` | `String { get }` | `String? { get }` (optional) |

**Fix:** Adjust protocol property signatures to match the real SCK types. Use `#if os(macOS)` conditional compilation if abstractions diverge from mocks.

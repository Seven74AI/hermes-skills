# Parallel Zone Exploration Pattern

When a codebase has 3+ distinct architectural zones, a single sequential read is too slow. Split exploration into parallel subagents via `delegate_task` with a `tasks` array.

## When to use

- Codebase with 3+ clearly separable zones (feature modules, utils pipeline, server layer, etc.)
- Each zone has 5+ files to read and analyze
- Zones have minimal cross-zone dependencies (each subagent can work independently)

## How to structure

Each task gets a `context` field with:
- Project path, framework, key conventions
- Domain glossary terms relevant to that zone
- Known pitfalls (circular dependency risks, ADR constraints)
- Specific analysis questions for that zone

Example from a real session (music-library, 3 zones):

```json
{
  "tasks": [
    {
      "goal": "Explore the audio-archive feature module at /tmp/music-library/app/features/audio-archive/. Read ALL 7 source files...",
      "context": "Project: Music Library at /tmp/music-library. Domain glossary at docs/CONTEXT.md. Key terms: ArchiveJob, WorkerState, yt-dlp, Tigris...",
      "toolsets": ["file", "terminal"]
    },
    {
      "goal": "Explore the app/utils/ directory. Focus on the track/playlist processing pipeline...",
      "context": "Project: Music Library at /tmp/music-library. Epic Stack framework. Known pitfall: circular dependency risk between service-playlist → track-batch-processor → playlist-utils...",
      "toolsets": ["file", "terminal"]
    },
    {
      "goal": "Explore the server layer and cross-cutting concerns...",
      "context": "Project: Music Library at /tmp/music-library. ADR-002: Zero cross-boundary imports between app/ and server/ layers...",
      "toolsets": ["file", "terminal"]
    }
  ]
}
```

## What each subagent should return

A structured report per zone:
1. Module-by-module depth assessment (deep → shallow spectrum)
2. Cross-module dependencies (imports, circular risks)
3. Seam quality (hypothetical vs real, single-adapter vs multi-adapter)
4. Shallow module candidates (with deletion-test reasoning)
5. Type-safety gaps (`as any` casts, hand-written types diverging from generated types)

## Synthesis

After all subagents return, the parent agent synthesizes:
- Merge depth spectrums into a single ranked list
- Cross-reference dependencies between zones (was anything missed?)
- Select 5-8 strongest candidates for the HTML report
- Note any cross-zone findings that individual subagents couldn't see

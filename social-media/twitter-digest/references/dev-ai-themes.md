# Dev/AI Theme Keywords & Tagging Configuration

For lists covering web development, AI engineering, agent tools, and TypeScript.

## Theme Keywords (lowercase)

| Theme | Keywords |
|-------|----------|
| Agent UX | agent, agents, agentic, autonomous, orchestrate, delegate, multi-agent, subagent, agent sdk, agent protocol, mcp, tool use, function call, reasoning, planning, workflow, operator, computer use, browser use, handoff, /handoff, sub agent, agent orchestration, coding agent |
| Codex | codex, openai codex, @openai/codex, openai sdk, openai, gpt-5, gpt 5, gpt-4, gpt 4, o3, o4, chatgpt, openai model, deepseek |
| Claude Code | claude code, claude-code, claude.ai, anthropic, sonnet, opus, haiku, claude |
| TypeScript | typescript, ts, type system, types, typed, tsconfig, deno, bun, javascript, js, eslint, prettier, jsx, tsx, react, next.js, nextjs, node.js, nodejs |
| OSS | open source, oss, github, apache, mit license, gpl, open-source, foss, community, repo, repository, pull request, pr, merge, contribute |
| Security | security, vuln, cve, exploit, auth, oauth, jwt, xss, csrf, encrypt, zero trust, supply chain, hack, phish, scam, privacy, leak |
| DevTools | devtools, dev tool, cli, debug, ide, editor, vscode, terminal, tooling, workflow, lint, format, build, bundle, compile, ci/cd, git, docker, kubernetes, nix, flake, shell, bash, json, database |
| AI Engineering | ai, llm, gpt, model, ml, machine learning, deep learning, transformer, embedding, inference, training, fine-tune, fine-tuned, prompt, rag, vector, neural, token, context window, benchmark, eval, sft, rlhf, generation, diffusion, image gen, slop |

## List Authors & Their Domains

Knowing authors helps correct automated tagging mistakes:

| Author | Domain | Default Themes |
|--------|--------|---------------|
| @RhysSullivan | Agent tools (codex, infra, dev UX) | Agent UX, Codex, DevTools |
| @mattpocockuk | TypeScript, Effect, agent skills | TypeScript, Agent UX |
| @kentcdodds | Web dev, agent tools (kody) | Agent UX, TypeScript |
| @kettanaito | OSS, MSW, API mocking | OSS, TypeScript |
| @colinhacks | APIs, security, zod | TypeScript, Security |

## Common Tagging Errors (Dev/AI List)

1. **Meme tweets about code/engineering**: `"junior engineers after submitting their first slop PR"` — keyword match picks up "engineers" → AI Engineering, but it's a DevTools meme about PR workflow. Theme should be DevTools or OSS, signal ⚪ Link/Ref.

2. **Matt Pocock tweets**: Almost everything from @mattpocockuk has a TypeScript lens. `"Pump the classics into my veins"` with a TypeScript screenshot is TypeScript theme, not AI Engineering. His `/grill-me`, `/handoff`, `/grill-with-docs` references are Agent UX.

3. **`/command` references**: Tweets mentioning `/grill-me`, `/handoff`, `/grill-with-docs` are about agent tooling → Agent UX theme.

4. **Apple/iPhone/general tech observations**: `"Remember using websites on the first iPhones?"` with an agent analogy — it's a DevTools/Agent UX observation, not a general AI tweet. The analogy to agents makes it relevant.

5. **Footgun/server/localhost tweets**: `"you don't realize all of the footguns / friction on building an app that runs a server on localhost"` — this is DevTools (infra/security concerns for local dev), not a general Security tweet.

## Date Window

- **Active list (daily):** Today + yesterday (`CUTOFF = today - 1 day`)
- **Weekend/low-activity list:** Today + 2 days back (`CUTOFF = today - 2 days`)
- **After pipeline runs:** 5 pages × 100 tweets typically spans 14+ days; date filtering reduces to ~20-40 tweets

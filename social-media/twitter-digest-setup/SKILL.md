---
name: twitter-digest-setup
description: "Twitter Digest project configuration: Notion DBs, Discord channels, cron schedule, team profiles."
version: 1.0.0
metadata:
  hermes:
    tags: [twitter, digest, notion, discord, cron, reference]
---

# Twitter Digest — Project Configuration

Quick-reference config for the Twitter Digest system. Load this skill when working on the digest pipeline.

## Notion

| Resource | ID |
|----------|-----|
| SevenAI root page | `363511b0706b803dad97fea5109c2aea` |
| Dev/AI DB | `84f93be0` |
| Crypto DB | `ed9b17d1` |
| Journal DB | `1f3c4438` (datasource `d67b533a`) |

v2025-09-03: PATCH `data_source` for props, `title="Name"`.

## Discord

| Channel | ID |
|---------|-----|
| #x-web | `1505632108494852136` |
| #x-crypto | `1505632187435847730` |

## GitHub

`seven74ai.github.io/twitter-digest`

## Twitter/X Lists

| List | ID |
|------|-----|
| Web | `1153202943035879424` |
| Crypto | `1153202845983956995` |

## Cron

| Job | Schedule | Description |
|----|----------|-------------|
| Daily digest | `0 7 Paris` | Main digest |
| Chronicle | Sun 10h | Weekly summary (`f831b59a067f`) |

## Team

| Profile | Role |
|---------|------|
| `twitter-planner` | Plan + decompose |
| `twitter-coder` | Implementation |
| `twitter-reviewer` | Review + merge |

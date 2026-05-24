# Telegram Flood Control — Log Example (2026-05-24)

Real-world flood control event captured during a gateway diagnostic session.

## Log output

```
May 24 15:44:07 vmi3304846 python[1292408]: WARNING gateway.platforms.telegram: [Telegram] Telegram flood control, waiting 65.0s
May 24 15:44:07 vmi3304846 python[1292408]: WARNING gateway.platforms.telegram: [Telegram] Telegram flood control, waiting 65.0s
May 24 15:44:07 vmi3304846 python[1292408]: WARNING gateway.platforms.telegram: [Telegram] Telegram flood control, waiting 65.0s
May 24 15:44:07 vmi3304846 python[1292408]: WARNING gateway.platforms.telegram: [Telegram] Telegram flood control, waiting 65.0s
May 24 15:44:46 vmi3304846 python[1292408]: WARNING gateway.platforms.telegram: [Telegram] Telegram flood control, waiting 27.0s
May 24 15:44:46 vmi3304846 python[1292408]: WARNING gateway.platforms.telegram: [Telegram] Telegram flood control, waiting 26.0s
May 24 15:44:46 vmi3304846 python[1292408]: WARNING gateway.platforms.telegram: [Telegram] Telegram flood control, waiting 26.0s
```

## What happened

- 7 messages triggered flood control simultaneously (4× at 15:44:07, 3× at 15:44:46)
- Initial wait: 65s per message
- Subsequent waits: 27s, 26s, 26s (cooling down)
- Total: ~40 seconds of throttling
- After this: zero Telegram log activity for 3+ hours — user's subsequent messages never reached the gateway, indicating the webhook wasn't delivering them (not a gateway-side queue issue)

## Diagnostic outcome

- Gateway process: healthy (837MB RAM, running since 05:24)
- Telegram API: reachable (HTTP 200 on getMe)
- Dashboard `/api/status`: `telegram.state: connected`, no error
- Root cause: messages not reaching webhook (external to gateway)
- No restart needed

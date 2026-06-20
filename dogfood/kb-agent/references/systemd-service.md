# KB Agent Systemd Service

## Unit file

`/etc/systemd/system/kb-agent.service`:

```ini
[Unit]
Description=KB Agent — Custom Python knowledge base agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/root/kb-agent
ExecStart=/usr/local/lib/hermes-agent/venv/bin/python3 /root/kb-agent/run.py
Restart=on-failure
RestartSteps=10
RestartMaxDelaySec=60
EnvironmentFile=/root/.hermes/.env
Environment=PYTHONUNBUFFERED=1
Environment=PATH=/usr/local/lib/hermes-agent/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
StandardOutput=journal
StandardError=journal
SyslogIdentifier=kb-agent

[Install]
WantedBy=multi-user.target
```

## Deployment

```bash
# Write unit file
cat > /etc/systemd/system/kb-agent.service << 'EOF'
... (content above) ...
EOF

# Enable and start
systemctl daemon-reload
systemctl enable --now kb-agent

# Verify
systemctl status kb-agent
curl -s http://localhost:5000/dashboard | head -5
```

## Pitfalls

- **Use venv Python, not system Python.** `/usr/bin/python3` lacks deps (dotenv, flask, httpx, pyyaml). The Hermes venv at `/usr/local/lib/hermes-agent/venv/bin/python3` has everything. First failure: `ModuleNotFoundError: No module named 'dotenv'`.
- **Add venv bin to PATH.** The service runs subprocess calls (`yt-dlp`, `ffmpeg`, `curl`) that live in the Hermes venv bin. Without `Environment=PATH=...` including `/usr/local/lib/hermes-agent/venv/bin`, subprocess calls fail with `FileNotFoundError: No such file or directory: 'yt-dlp'` even though the binary exists. The `ExecStart` python is in the venv but subprocesses don't inherit that — PATH must be set explicitly.
- **Restart=on-failure with backoff.** Don't use `Restart=always` — it restarts even on clean exit code 0. `Restart=on-failure` + `RestartSteps=10` + `RestartMaxDelaySec=60` gives exponential backoff.
- **EnvironmentFile loads .env.** `EnvironmentFile=/root/.hermes/.env` injects `DEEPSEEK_API_KEY`, `EDGEE_API_KEY`, and other env vars. The service doesn't need `.env` at the project level because systemd provides them.

## Commands

```bash
systemctl status kb-agent          # Check status
systemctl restart kb-agent         # Restart after code changes
systemctl stop kb-agent            # Stop
journalctl -u kb-agent -f          # Follow logs
journalctl -u kb-agent -n 50       # Last 50 log lines
```

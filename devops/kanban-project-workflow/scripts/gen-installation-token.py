#!/usr/bin/env python3
"""Generate a GitHub App installation token for hermes-sevenai-reviewer.

Uses JWT auth with the App's private key, then exchanges it for an
installation access token valid for 1 hour. Outputs the token to stdout.

Required when gh CLI version < 2.60 (lacks --app-id flag). Older versions
must use `gh api -H "Authorization: Bearer $TOKEN"` instead of `gh pr
review --approve`.

Prerequisites:
- PyJWT: pip install pyjwt
- requests or curl available
- Private key at KEY_PATH

Usage:
  TOKEN=$(python3 gen-installation-token.py)
  gh api repos/OWNER/REPO/pulls/N/reviews \
    -H "Authorization: Bearer $TOKEN" \
    -f event=APPROVE
"""
import jwt, time, subprocess, json, os, sys

# === CONFIGURATION ===
APP_ID = "3788528"
INSTALLATION_ID = "134194993"
# Path relative to reviewer profile HOME
KEY_PATH = os.path.expanduser("~/.config/hermes-sevenai-reviewer.pem")


def main():
    with open(KEY_PATH, "rb") as f:
        private_key = f.read()

    now = int(time.time())
    jwt_token = jwt.encode(
        {"iat": now - 60, "exp": now + 600, "iss": APP_ID},
        private_key,
        algorithm="RS256",
    )

    result = subprocess.run(
        [
            "curl", "-s", "-X", "POST",
            "-H", f"Authorization: Bearer {jwt_token}",
            "-H", "Accept: application/vnd.github+json",
            f"https://api.github.com/app/installations/{INSTALLATION_ID}/access_tokens",
        ],
        capture_output=True, text=True,
    )

    data = json.loads(result.stdout)
    print(data["token"])


if __name__ == "__main__":
    main()

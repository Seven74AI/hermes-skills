# Pyannote Gating — Diagnostic Procedure

When a worker reports `GatedRepoError` or 401 on `speaker-diarization-3.1`, run this
BEFORE escalating to the user. Most blocks are real, but false positives happen when:

- Token was created before license acceptance (HF tokens can lag)
- User accepted license for 3.0 but not 3.1 (different repos)
- Transient HF auth outage

## Step 1 — Load token

```bash
export HF_TOKEN=$(grep -oP 'HF_TOKEN=\K[^#\n]+' /root/.hermes/profiles/researcher-videos/.env | head -1)
```

## Step 2 — Verify token identity

```bash
curl -sH "Authorization: Bearer $HF_TOKEN" https://huggingface.co/api/whoami-v2 | python3 -m json.tool
```

Expected: `{"type":"user","name":"..."}` — token is valid and belongs to a user.

## Step 3 — Verify model file access

The worker failed on this exact endpoint:

```bash
curl -sIH "Authorization: Bearer $HF_TOKEN" \
  "https://huggingface.co/pyannote/speaker-diarization-3.1/resolve/main/config.yaml"
```

| HTTP code | Meaning | Action |
|-----------|---------|--------|
| 200 | Token has access | Retry diarization (transient error) |
| 401 | Access denied truly | Escalate to user — license not accepted |
| 403 | Forbidden | Escalate to user — repo is private or token lacks scope |

## Step 4 — If truly denied, list all pyannote models

```bash
for model in \
  "pyannote/speaker-diarization-3.1" \
  "pyannote/speaker-diarization-3.0" \
  "pyannote/segmentation-3.0"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $HF_TOKEN" \
    "https://huggingface.co/api/models/$model")
  echo "$code — $model"
done
```

The user must accept the license for each model returning non-200. 3.0 acceptance does
NOT cover 3.1 — they are separate repositories.

## Root cause categories

| Category | Symptom | Fix |
|----------|---------|-----|
| License not accepted for 3.1 | 401 on 3.1, 200 on 3.0 | User visits HF page and clicks Accept |
| Token created before license | whoami works, all models 401 | User creates new token after accepting license |
| Transient HF error | 401 that resolves on retry | Wait 60s, retry |
| Token expired/revoked | whoami returns error | User creates new token |

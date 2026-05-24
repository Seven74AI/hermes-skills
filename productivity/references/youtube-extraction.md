# YouTube Video Extraction Pipeline

Pipeline complet pour télécharger, transcrire et archiver une vidéo YouTube dans le knowledge base.

## Prérequis

- `yt-dlp` (pip) — **toujours utiliser `--js-runtimes node`** (YouTube bloque les IP datacenter via n-sig challenge, même avec cookies)
- `faster-whisper` (pip)
- `ffmpeg` (système)
- `minio` Python client (pip) — pour l'upload MinIO
- `node` ≥ v20 (système) — requis par yt-dlp pour le n-sig challenge solver
- Cookies YouTube : `/tmp/yt_cookies.txt` (exportés depuis le navigateur desktop de l'utilisateur)

## Pipeline — étapes

### 1. Lister les chapitres YouTube natifs

```bash
yt-dlp --cookies /tmp/yt_cookies.txt --js-runtimes node \
  --print "%(chapters)s" \
  --sleep-requests 1 --sleep-interval 3 --max-sleep-interval 10 --limit-rate 4M \
  "https://www.youtube.com/watch?v=VIDEO_ID"
```

Sortie formatée en JSON avec `start_time`, `end_time`, `title`. Si vide → pas de chapitres natifs, fallback NLP.

### 2. Extraire les métadonnées

```bash
yt-dlp --cookies /tmp/yt_cookies.txt --js-runtimes node \
  --print "%(title)s||%(uploader)s||%(duration)s||%(view_count)s||%(upload_date)s" \
  --sleep-requests 1 --sleep-interval 3 --max-sleep-interval 10 --limit-rate 4M \
  "https://www.youtube.com/watch?v=VIDEO_ID"
```

Sortie : `Titre||Chaîne||Durée (secondes)||Vues||YYYYMMDD`

### 3. Télécharger la vidéo (WebM VP9, max 720p)

```bash
yt-dlp --cookies /tmp/yt_cookies.txt --js-runtimes node \
  -f "bestvideo[height<=720][vcodec^=vp9]+bestaudio[acodec^=opus]/bestvideo[height<=720]+bestaudio/best[height<=720]" \
  --merge-output-format webm \
  -o "/tmp/yt_%(id)s.webm" \
  --sleep-requests 1 --sleep-interval 3 --max-sleep-interval 10 --limit-rate 4M \
  "https://www.youtube.com/watch?v=VIDEO_ID"
```

**Pitfall:** YouTube sert vidéo + audio en flux DASH séparés. `--merge-output-format webm` les fusionne. Si le merge échoue (codec incompatible), fallback : `-f "best[height<=720]"` qui prend le meilleur flux combiné natif.

### 4. Extraire l'audio en MP3

```bash
ffmpeg -y -i /tmp/yt_VIDEO_ID.webm -vn -acodec libmp3lame -q:a 2 /tmp/yt_VIDEO_ID.mp3
```

`-q:a 2` = VBR ~190 kbps, bon compromis qualité/taille.

### 5. Transcrire avec faster-whisper

```bash
# Convertir en WAV 16kHz mono pour whisper
ffmpeg -y -i /tmp/yt_VIDEO_ID.mp3 -vn -acodec pcm_s16le -ar 16000 -ac 1 /tmp/yt_audio_16k.wav

# Transcrire
python3 -c "
import json
from faster_whisper import WhisperModel

model = WhisperModel('small', device='cpu', compute_type='int8')
segments, info = model.transcribe('/tmp/yt_audio_16k.wav', language=None)

results = {
    'language': info.language,
    'duration': info.duration,
    'segments': [{'start': s.start, 'end': s.end, 'text': s.text} for s in segments]
}
with open('/tmp/yt_VIDEO_ID_transcript.json', 'w') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f'Language: {info.language}, Segments: {len(results[\"segments\"])}')
"
```

**Note:** `language=None` active la détection auto. faster-whisper détecte bien français vs anglais.

### 6. Chapitrage (fallback NLP si pas de chapitres natifs)

Si l'étape 1 n'a pas retourné de chapitres :

```python
# Chapitrage NLP basé sur les gaps de pause et les shifts thématiques
import json, re

with open('/tmp/yt_VIDEO_ID_transcript.json') as f:
    data = json.load(f)

segments = data['segments']
full_text = ' '.join(s['text'] for s in segments)

# Détection simple : sauts > 3 secondes entre segments = limite potentielle de chapitre
chapters = []
current_start = segments[0]['start']
current_text = []

for i, seg in enumerate(segments):
    if i > 0:
        gap = seg['start'] - segments[i-1]['end']
        if gap > 3.0 and len(current_text) > 0:
            chapters.append({
                'start': current_start,
                'title': f'Section {len(chapters)+1}',
                'summary': ' '.join(current_text)[:500]
            })
            current_start = seg['start']
            current_text = []
    current_text.append(seg['text'])

# Dernier chapitre
if current_text:
    chapters.append({
        'start': current_start,
        'title': f'Section {len(chapters)+1}',
        'summary': ' '.join(current_text)[:500]
    })

print(json.dumps(chapters, indent=2))
```

### 7. Générer résumé approfondi + points clés par chapitre

Le LLM (dans le worker researcher-videos) suit le prompt en deux passes
documenté dans `references/resume-prompt.md` :

- **Passe 1** — Extraction des concepts clés (titres, mécanismes, timestamps, type d'évidence)
- **Passe 2** — Note complète en 7 sections : Résumé → Métadonnées → Concepts clés →
  Chapitres → Points clés → Nuances & Limites → Extractions utiles → Voir aussi

Ne pas improviser : suivre le prompt structuré pour garantir densité et profondeur.
Template de note dans `references/youtube-note-template.md`.

### 8. Uploader vers MinIO

```bash
# Configurer le client MinIO
mc alias set minio http://vmi3304846.tail5c02a1.ts.net:9000 ACCESS_KEY SECRET_KEY

# Uploader les 3 fichiers
mc cp /tmp/yt_VIDEO_ID.webm minio/knowledge-base/videos/<slug>.webm
mc cp /tmp/yt_VIDEO_ID.mp3 minio/knowledge-base/videos/<slug>.mp3
mc cp /tmp/yt_VIDEO_ID_transcript.json minio/knowledge-base/videos/<slug>.json
```

### 9. Créer la note dans le vault

Template (voir `references/youtube-note-template.md`). Sauvegarder dans `Connaissances/videos/<slug>.md`, puis push Git.

### 10. Nettoyage

```bash
rm /tmp/yt_VIDEO_ID.webm /tmp/yt_VIDEO_ID.mp3 /tmp/yt_audio_16k.wav /tmp/yt_VIDEO_ID_transcript.json
```

## Rate limiting

- **Toujours** utiliser `--sleep-requests 1 --sleep-interval 3 --max-sleep-interval 10 --limit-rate 4M`
- **Toujours** utiliser `--js-runtimes node` (n-sig challenge)
- Max **2 vidéos** par worker session
- Au-delà de 2 URLs, sérialiser avec `--parent`
- Cookies fichier persistant `/tmp/yt_cookies.txt` — ne pas supprimer

## Anti-pitfalls

- **n-sig challenge:** Sur IP datacenter, yt-dlp échoue avec "n challenge solving failed". Le flag `--js-runtimes node` est OBLIGATOIRE (Node ≥ v20 requis). Sans lui, yt-dlp ne voit que les images storyboard.
- **Bot detection:** Si yt-dlp retourne "Sign in to confirm you're not a bot", les cookies sont expirés. L'utilisateur doit les ré-exporter depuis son navigateur.
- **Format non trouvé:** Si VP9 720p non dispo, fallback `-f "best[height<=720]"` sur le meilleur format natif.
- **Audio > 2h:** Le WAV 16kHz fait ~700 MB pour 2h. Vérifier l'espace disque avant.
- **whisper OOM:** Si le modèle `small` crash (RAM insuffisante), réduire à `base` pour cette session. Faire remonter à l'utilisateur.
- **Chapitres vides:** YouTube peut lister des chapitres sans titre. Les ignorer et fallback NLP.
- **Vidéo privée/non listée:** yt-dlp échoue. Le worker doit catcher l'erreur et notifier.

## Performance benchmarks

Mesuré sur ce serveur (CPU only, no GPU). faster-whisper `small` int8.

| Vidéo | Audio réel | Modèle | Temps | Ratio | Segments | Texte |
|-------|-----------|--------|-------|-------|----------|-------|
| 96 min (workshop) | 68 min | small | 41 min | 1.7× temps réel | 2079 | 64K chars |

**Règle d'estimation :** compter ~60-70% de la durée vidéo en temps de traitement pour `small`, ~35-40% pour `base`, ~2× pour `medium`. La durée audio réelle est souvent plus courte que la durée vidéo (silences, pauses).

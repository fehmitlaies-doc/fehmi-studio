#!/usr/bin/env bash
# Rendu d'une vidéo Radar (Short 9:16) ou d'une vidéo longue YouTube (16:9, chapitres).
# JOB (JSON en base64, éventuellement compressé gzip) et UPLOAD (lien d'envoi Dropbox) arrivent par l'événement GitHub.
# Vidéo longue : le lien d'envoi est dans le job (stockage Post for Me, sans limite de taille Dropbox).
set -euo pipefail
ROOT=$(pwd)
HF="npx -y hyperframes@0.8.199"
W=$(mktemp -d)
# base64 → JSON (gzip détecté automatiquement)
unpack='import sys,base64,gzip;b=base64.b64decode(sys.stdin.read());sys.stdout.buffer.write(gzip.decompress(b) if b[:2]==b"\x1f\x8b" else b)'
if [ -n "${GITHUB_EVENT_PATH:-}" ] && [ -z "${JOB:-}" ]; then
  # sur GitHub : entrées lues dans l'événement, liens d'envoi masqués dans les journaux
  UPLOAD=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['inputs'].get('upload') or '')" "$GITHUB_EVENT_PATH")
  [ -n "$UPLOAD" ] && echo "::add-mask::$UPLOAD"
  python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['inputs']['job'])" "$GITHUB_EVENT_PATH" | python3 -c "$unpack" > "$W/job.json"
else
  printf '%s' "$JOB" | python3 -c "$unpack" > "$W/job.json"
fi
python3 - "$W/job.json" <<'PY'
import json, sys
j = json.load(open(sys.argv[1]))
for v in [j.get('voice'), j.get('upload'), *(j.get('voices') or [])]:
    if v: print('::add-mask::' + v)
PY
LONG=$(python3 -c "import json,sys;print(1 if json.load(open(sys.argv[1])).get('format')=='long' else 0)" "$W/job.json")
PUT=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('upload') or '')" "$W/job.json")
python3 "$ROOT/radar/tools/prepare.py" "$W"
LC=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('lang','fr'))" "$W/job.json")
cd "$W"
$HF transcribe assets/voice.m4a -m small -l "$LC" --json > tr.out
TP=$(python3 -c "import json;print(json.loads(open('tr.out').read().strip().splitlines()[-1])['transcriptPath'])")
[ "$TP" -ef assets/transcript.json ] || cp "$TP" assets/transcript.json
if [ "$LONG" = 1 ]; then python3 "$ROOT/radar/tools/long_build.py" "$W"; else python3 "$ROOT/radar/tools/radar_build.py" "$W"; fi
$HF lint || true
$HF render --output out.mp4
ls -la out.mp4
if [ -n "$PUT" ]; then
  # vidéo longue : envoi direct dans le stockage Post for Me (lien signé valable 2 h)
  CODE=$(curl -sS -X PUT "$PUT" -H "Content-Type: video/mp4" --data-binary @out.mp4 -o up.out -w "%{http_code}")
  if [ "$CODE" -ge 300 ]; then
    echo "::error::Post for Me a refusé l'envoi (HTTP $CODE) : $(head -c 300 up.out)"
    exit 1
  fi
  # chapitres pour la description YouTube : le Studio les lit dans cette annotation (API publique GitHub)
  [ -f chapters.json ] && echo "::notice title=chapitres::$(python3 -c "import json;print(json.dumps(json.load(open('chapters.json')),ensure_ascii=False).replace('%','%25'))")"
  echo "envoyé"
elif [ -n "${UPLOAD:-}" ]; then
  CODE=$(curl -sS -X POST "$UPLOAD" -H "Content-Type: application/octet-stream" --data-binary @out.mp4 -o up.out -w "%{http_code}")
  if [ "$CODE" -ge 300 ]; then
    echo "::error::Dropbox a refusé l'envoi (HTTP $CODE) : $(head -c 300 up.out). Cause fréquente : Dropbox plein (vérifier l'espace libre)."
    exit 1
  fi
  echo "envoyé"
fi
[ -n "${GITHUB_EVENT_PATH:-}" ] || { cp out.mp4 "$ROOT/out.mp4"; [ -f chapters.json ] && cp chapters.json "$ROOT/chapters.json" || true; }

#!/usr/bin/env bash
# Rendu d'une vidéo Radar : JOB (JSON en base64) et UPLOAD (lien d'envoi Dropbox) arrivent par l'environnement.
set -euo pipefail
ROOT=$(pwd)
HF="npx -y hyperframes@0.8.199"
W=$(mktemp -d)
if [ -n "${GITHUB_EVENT_PATH:-}" ] && [ -z "${JOB:-}" ]; then
  # sur GitHub : entrées lues dans l'événement, lien d'envoi masqué dans les journaux
  UPLOAD=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['inputs'].get('upload') or '')" "$GITHUB_EVENT_PATH")
  [ -n "$UPLOAD" ] && echo "::add-mask::$UPLOAD"
  python3 -c "import json,sys,base64;open(sys.argv[2],'wb').write(base64.b64decode(json.load(open(sys.argv[1]))['inputs']['job']))" "$GITHUB_EVENT_PATH" "$W/job.json"
else
  printf '%s' "$JOB" | base64 -d > "$W/job.json"
fi
python3 -c "import json,sys;v=json.load(open(sys.argv[1])).get('voice','');print('::add-mask::'+v) if v else None" "$W/job.json"
python3 "$ROOT/radar/tools/prepare.py" "$W"
LC=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('lang','fr'))" "$W/job.json")
cd "$W"
$HF transcribe assets/voice.m4a -m small -l "$LC" --json > tr.out
TP=$(python3 -c "import json;print(json.loads(open('tr.out').read().strip().splitlines()[-1])['transcriptPath'])")
[ "$TP" -ef assets/transcript.json ] || cp "$TP" assets/transcript.json
python3 "$ROOT/radar/tools/radar_build.py" "$W"
$HF lint || true
$HF render --output out.mp4
ls -la out.mp4
if [ -n "${UPLOAD:-}" ]; then
  CODE=$(curl -sS -X POST "$UPLOAD" -H "Content-Type: application/octet-stream" --data-binary @out.mp4 -o up.out -w "%{http_code}")
  if [ "$CODE" -ge 300 ]; then
    echo "::error::Dropbox a refusé l'envoi (HTTP $CODE) : $(head -c 300 up.out). Cause fréquente : Dropbox plein (vérifier l'espace libre)."
    exit 1
  fi
  echo "envoyé"
fi
[ -n "${GITHUB_EVENT_PATH:-}" ] || cp out.mp4 "$ROOT/out.mp4"

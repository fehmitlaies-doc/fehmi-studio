#!/usr/bin/env bash
# Rendu d'une vidéo Radar : JOB (JSON en base64) et UPLOAD (lien d'envoi Dropbox) arrivent par l'environnement.
set -euo pipefail
ROOT=$(pwd)
HF="npx -y hyperframes@0.8.199"
W=$(mktemp -d)
printf '%s' "$JOB" | base64 -d > "$W/job.json"
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
  curl -sSf -X POST "$UPLOAD" -H "Content-Type: application/octet-stream" --data-binary @out.mp4 -o /dev/null
  echo "envoyé"
fi
cp out.mp4 "$ROOT/out.mp4"

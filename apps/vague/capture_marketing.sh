#!/usr/bin/env bash
# Matériel marketing de Vague (vidéos courtes, TikTok) depuis le simulateur iOS.
#
#   scripts/capture_marketing.sh [dossier_sortie]
#
# 1. Compile un build de démonstration (EXPO_PUBLIC_DEMO=1, sans clé
#    RevenueCat) : données fictives, achats désactivés, aucune statistique
#    envoyée.
# 2. Barre d'état propre (9:41, batterie pleine), installation neuve.
# 3. Captures en résolution native, par liens directs et par le pilote
#    XCUITest (scripts/marketing/driver) pour les écrans qui demandent un geste.
# 4. Vidéos : simctl recordVideo pendant que le pilote joue un parcours, puis
#    montage ffmpeg et manifest.json (scripts/marketing/cut.py).
#
# Variables : DEVICE (UDID, sinon le premier simulateur démarré),
# SKIP_BUILD=1 (réutiliser le build de démo), WORK (dossier de travail),
# STEPS (par défaut « shots videos » ; « onboarding » refait seulement les
# captures de l'onboarding), VIDEOS (liste de tests vidéo à refaire, par
# défaut les quatre).
# Prérequis : Xcode, xcodegen, ffmpeg, node (pour Metro), python3.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/marketing-media}"
WORK="${WORK:-$ROOT/.marketing-build}"
DEVICE="${DEVICE:-$(xcrun simctl list devices booted | grep -m1 -oE '[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}' || true)}"
BUNDLE=app.vague.ios
DRIVER="$ROOT/scripts/marketing/driver"

[ -n "$DEVICE" ] || { echo "Aucun simulateur démarré : lance-en un (iPhone 16 Pro ou plus récent) ou passe DEVICE=<udid>." >&2; exit 1; }
mkdir -p "$WORK" "$OUT/screenshots" "$OUT/videos"
APP="$WORK/app/Build/Products/Release-iphonesimulator/Vague.app"

log() { printf '\n▸ %s\n' "$*"; }

# ── Builds ─────────────────────────────────────────────────────────────────
if [ "${SKIP_BUILD:-0}" != 1 ] || [ ! -d "$APP" ]; then
  log "Build de démonstration de Vague (Release, simulateur)"
  ( cd "$ROOT" && EXPO_PUBLIC_DEMO=1 EXPO_PUBLIC_REVENUECAT_IOS_KEY= xcodebuild \
      -workspace ios/Vague.xcworkspace -scheme Vague -configuration Release \
      -sdk iphonesimulator -destination "platform=iOS Simulator,id=$DEVICE" \
      -derivedDataPath "$WORK/app" build > "$WORK/build-app.log" 2>&1 ) \
    || { tail -30 "$WORK/build-app.log"; exit 1; }
fi
if strings "$APP/main.jsbundle" | grep -q 'appl_'; then
  echo "La clé RevenueCat est dans le build de démo : arrêt." >&2; exit 1
fi

log "Pilote XCUITest"
( cd "$DRIVER" && xcodegen generate --quiet && xcodebuild build-for-testing \
    -project VagueMarketing.xcodeproj -scheme MarketingUITests \
    -destination "platform=iOS Simulator,id=$DEVICE" -derivedDataPath "$WORK/driver" \
    > "$WORK/build-driver.log" 2>&1 ) || { tail -30 "$WORK/build-driver.log"; exit 1; }

# ── Outils ─────────────────────────────────────────────────────────────────
fresh() {
  xcrun simctl terminate "$DEVICE" "$BUNDLE" >/dev/null 2>&1 || true
  xcrun simctl uninstall "$DEVICE" "$BUNDLE" >/dev/null 2>&1 || true
  xcrun simctl install "$DEVICE" "$APP"
  xcrun simctl status_bar "$DEVICE" override --time 9:41 --batteryState charged \
    --batteryLevel 100 --cellularBars 4 --wifiBars 3
  xcrun simctl privacy "$DEVICE" grant notifications "$BUNDLE" >/dev/null 2>&1 || true
  xcrun simctl launch "$DEVICE" "$BUNDLE" >/dev/null
  sleep 7
}
seeded() { fresh; xcrun simctl openurl "$DEVICE" "vague://demo"; sleep 5; }
link() { xcrun simctl openurl "$DEVICE" "vague://$1"; sleep "${2:-3}"; }
shot() { xcrun simctl io "$DEVICE" screenshot "$OUT/screenshots/$1.png" >/dev/null 2>&1; echo "  $1.png"; }
uitest() {
  TEST_RUNNER_MARKETING_OUT="$OUT/screenshots" xcodebuild test-without-building \
    -project "$DRIVER/VagueMarketing.xcodeproj" -scheme MarketingUITests \
    -destination "platform=iOS Simulator,id=$DEVICE" -derivedDataPath "$WORK/driver" \
    -only-testing:"MarketingUITests/VagueMarketingTests/$1" > "$WORK/$1.log" 2>&1 \
    || { grep -E "error|Introuvable" "$WORK/$1.log" | tail -5; return 1; }
}
record() {  # record <test> : vidéo brute $WORK/<test>.mp4 + heure de départ
  local test="$1" raw="$WORK/$1.mp4" err="$WORK/$1.rec.log"
  rm -f "$raw" "$err"
  xcrun simctl io "$DEVICE" recordVideo --codec=h264 --force "$raw" 2> "$err" &
  local pid=$!
  for _ in $(seq 1 50); do grep -q "Recording started" "$err" 2>/dev/null && break; sleep 0.1; done
  python3 -c 'import time; print(time.time())' > "$WORK/$test.t0"
  uitest "$test" || true
  sleep 1
  kill -INT "$pid"; wait "$pid" 2>/dev/null || true
  echo "  $test.mp4"
}

STEPS="${STEPS:-shots videos}"
VIDEOS="${VIDEOS:-testVideoCraving testVideoProgress testVideoOnboarding testVideoWow}"
has() { case " $1 " in *" $2 "*) return 0;; *) return 1;; esac; }

# ── Captures ───────────────────────────────────────────────────────────────
if has "$STEPS" shots; then
  log "Captures d'écran"
  rm -f "$OUT"/screenshots/*.png
  fresh;  shot 00-ouverture
  seeded; shot 01-accueil
  link program;      shot 07-programme
  link day/12;       shot 08-jour-12
  link subscription; shot 09-economies
  link quit;         shot 11-date-d-arret
  seeded; uitest testShotsSession
fi
if has "$STEPS" shots || has "$STEPS" onboarding; then
  log "Captures de l'onboarding"
  rm -f "$OUT"/screenshots/10-onboarding-*.png
  fresh;  uitest testShotsOnboarding
fi

# ── Vidéos ─────────────────────────────────────────────────────────────────
if has "$STEPS" videos; then
  log "Vidéos"
  for t in $VIDEOS; do
    case "$t" in testVideoOnboarding) fresh ;; *) seeded ;; esac
    record "$t"
  done
fi

log "Montage et manifest"
python3 "$ROOT/scripts/marketing/cut.py" "$WORK" "$OUT"

xcrun simctl status_bar "$DEVICE" clear || true
find "$OUT" -type f -size +50M -exec echo "Attention, plus de 50 Mo : {}" \;
log "Terminé : $OUT"

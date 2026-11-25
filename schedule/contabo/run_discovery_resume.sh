#!/usr/bin/env bash
# Wznowienie discovery z cache JSON (--respect-cache): pomija URL już w contacts.
set -euo pipefail
# shellcheck disable=SC1091
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

DAY_LABEL="${1:-sroda-resume}"
JOB="discovery/${DAY_LABEL}"
LOG="$ROOT/logs/${DAY_LABEL}_discovery.log"
# też dopisz do głównego logu środy, jeśli istnieje
MAIN_LOG="$ROOT/logs/sroda_discovery.log"
export SCRAPER_MAX_RUNTIME_SECONDS="${SCRAPER_MAX_RUNTIME_SECONDS:-21600}"
unset DISABLE_SEND_WINDOW SCRAPER_IGNORE_SEND_WINDOW || true

pipeline_notify start "$JOB" --log "$LOG" \
  --detail "Restart ICP + --respect-cache (pomija rekordy już w pl_spedycja_cache.json)."
{
  echo "[$(date '+%F %T')] START discovery resume ($DAY_LABEL) --respect-cache"
} | tee -a "$LOG" >>"$MAIN_LOG"

GAP_FILL_ARGS=()
# GAP_FILL_AFTER_MAPS=1 lub --with-gap-fill → Faza B zaraz po Maps w tym samym jobie
if [[ "${GAP_FILL_AFTER_MAPS:-0}" =~ ^(1|true|yes|on)$ ]] || [[ "${WITH_GAP_FILL:-0}" =~ ^(1|true|yes|on)$ ]]; then
  GAP_FILL_ARGS+=(--with-gap-fill)
fi

set +e
"$PY" pl_fas_spedycja_scraper.py \
  --run-config run_config/pl_fas_spedycja.json \
  --serper-only-discovery \
  --no-auto-email \
  --respect-cache \
  "${GAP_FILL_ARGS[@]}" >>"$LOG" 2>&1
EC=$?
set -e

{
  echo "[$(date '+%F %T')] END discovery resume ($DAY_LABEL) exit=$EC"
} | tee -a "$LOG" >>"$MAIN_LOG"

if [[ "$EC" -eq 0 ]]; then
  pipeline_notify ok "$JOB" --log "$LOG" --exit-code "$EC"
else
  pipeline_notify alert "$JOB" --log "$LOG" --exit-code "$EC" \
    --detail "Resume discovery zakończone błędem (exit=$EC)."
fi
exit "$EC"

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
export SCRAPER_MAX_RUNTIME_SECONDS="${SCRAPER_MAX_RUNTIME_SECONDS:-43200}"
unset DISABLE_SEND_WINDOW SCRAPER_IGNORE_SEND_WINDOW || true

pipeline_notify start "$JOB" --log "$LOG" \
  --detail "Resume 1 woj. (--rotate-bundesland) + --respect-cache."
{
  echo "[$(date '+%F %T')] START discovery resume ($DAY_LABEL) --rotate-bundesland --respect-cache"
  "$PY" -c "from pathlib import Path; from gu_bundesland_rotation import format_rotation_status; print(format_rotation_status(Path('Wyniki')))" || true
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
  --rotate-bundesland \
  "${GAP_FILL_ARGS[@]}" >>"$LOG" 2>&1
EC=$?
set -e

{
  echo "[$(date '+%F %T')] END discovery resume ($DAY_LABEL) exit=$EC"
} | tee -a "$LOG" >>"$MAIN_LOG"

if [[ "$EC" -eq 0 ]]; then
  pipeline_notify ok "$JOB" --log "$LOG" --exit-code "$EC" \
    --detail "Po OK: gap-fill Serper za ~$(( ${GAP_FILL_DELAY_SECONDS:-3600} / 60 )) min."
else
  pipeline_notify alert "$JOB" --log "$LOG" --exit-code "$EC" \
    --detail "Resume discovery zakończone błędem (exit=$EC)."
fi
schedule_gap_fill_after_discovery
exit "$EC"

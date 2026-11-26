#!/usr/bin/env bash
# Discovery Maps/Serper+www (pon–pt 07:00). Zawsze --respect-cache
# + --rotate-bundesland (1 województwo / dzień; pełne miasta+powiaty).
# (stempel z run_cache_verify.sh ~04:00; pomija znane URL, zachowuje serper_discovery).
set -euo pipefail
# shellcheck disable=SC1091
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

DAY_LABEL="${1:-discovery}"
JOB="discovery/${DAY_LABEL}"
LOG="$ROOT/logs/${DAY_LABEL}_discovery.log"
# Pełne miasta+powiaty: 1 woj. potrafi >6h Maps — domyślnie 12h.
export SCRAPER_MAX_RUNTIME_SECONDS="${SCRAPER_MAX_RUNTIME_SECONDS:-43200}"
unset DISABLE_SEND_WINDOW SCRAPER_IGNORE_SEND_WINDOW || true

STAMP="$ROOT/Wyniki/.cache_verified_for_discovery.json"
DETAIL="Discovery 1 woj. (--rotate-bundesland) + --respect-cache + pełne geo."
if [[ -f "$STAMP" ]]; then
  DETAIL="${DETAIL} Stempel: $(head -c 400 "$STAMP" | tr '\n' ' ')"
else
  DETAIL="${DETAIL} Brak stempla 04:00 — i tak respektujemy cache."
fi

pipeline_notify start "$JOB" --log "$LOG" --detail "$DETAIL"
{
  echo "[$(date '+%F %T')] START discovery ($DAY_LABEL) --rotate-bundesland --respect-cache"
  if [[ -f "$STAMP" ]]; then
    echo "[$(date '+%F %T')] cache stamp present: $STAMP"
  else
    echo "[$(date '+%F %T')] WARN: brak $STAMP (verify 04:00 nie zapisał stempla)"
  fi
  "$PY" -c "from pathlib import Path; from gu_bundesland_rotation import format_rotation_status; print(format_rotation_status(Path('Wyniki')))" || true
} >>"$LOG" 2>&1

set +e
"$PY" pl_fas_spedycja_scraper.py \
  --run-config run_config/pl_fas_spedycja.json \
  --serper-only-discovery \
  --no-auto-email \
  --respect-cache \
  --rotate-bundesland >>"$LOG" 2>&1
EC=$?
set -e

echo "[$(date '+%F %T')] END discovery ($DAY_LABEL) exit=$EC" >>"$LOG"
if [[ "$EC" -eq 0 ]]; then
  pipeline_notify ok "$JOB" --log "$LOG" --exit-code "$EC" \
    --detail "Po OK: gap-fill Serper za ~$(( ${GAP_FILL_DELAY_SECONDS:-3600} / 60 )) min."
else
  pipeline_notify alert "$JOB" --log "$LOG" --exit-code "$EC" \
    --detail "Discovery zakończone błędem (exit=$EC)."
fi
# Faza B z opóźnieniem (nie wieczorny cron) — także po częściowym OK/exit 0
schedule_gap_fill_after_discovery
exit "$EC"

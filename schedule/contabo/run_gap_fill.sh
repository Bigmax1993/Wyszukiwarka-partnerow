#!/usr/bin/env bash
# Faza B — Serper gap-fill po discovery Maps (uzupełnia luki w JSON).
set -euo pipefail
# shellcheck disable=SC1091
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

JOB="gap-fill/serper"
LOG="$ROOT/logs/gap_fill_serper.log"
export SCRAPER_MAX_RUNTIME_SECONDS="${SCRAPER_MAX_RUNTIME_SECONDS:-7200}"
export GAP_FILL_MAX="${GAP_FILL_MAX:-40}"

pipeline_notify start "$JOB" --log "$LOG" \
  --detail "Faza B: Serper uzupełnia luki (email/www/telefon) w contacts JSON."
echo "[$(date '+%F %T')] START gap-fill Serper (max=${GAP_FILL_MAX})" | tee -a "$LOG"

set +e
"$PY" gap_fill_serper.py \
  --run-config run_config/pl_fas_spedycja.json \
  --max "$GAP_FILL_MAX" >>"$LOG" 2>&1
EC=$?
set -e

echo "[$(date '+%F %T')] END gap-fill exit=$EC" | tee -a "$LOG"
if [[ "$EC" -eq 0 ]]; then
  pipeline_notify ok "$JOB" --log "$LOG" --exit-code "$EC"
else
  pipeline_notify alert "$JOB" --log "$LOG" --exit-code "$EC" \
    --detail "Gap-fill Serper zakończone błędem (exit=$EC)."
fi
exit "$EC"

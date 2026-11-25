#!/usr/bin/env bash
# Discovery Serper+www (pon–pt). Arg1 opcjonalny: etykieta dnia (log).
set -euo pipefail
# shellcheck disable=SC1091
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

DAY_LABEL="${1:-discovery}"
JOB="discovery/${DAY_LABEL}"
LOG="$ROOT/logs/${DAY_LABEL}_discovery.log"
export SCRAPER_MAX_RUNTIME_SECONDS="${SCRAPER_MAX_RUNTIME_SECONDS:-21600}"
unset DISABLE_SEND_WINDOW SCRAPER_IGNORE_SEND_WINDOW || true

pipeline_notify start "$JOB" --log "$LOG"
echo "[$(date '+%F %T')] START discovery ($DAY_LABEL)" >>"$LOG"

set +e
"$PY" pl_fas_spedycja_scraper.py \
  --run-config run_config/pl_fas_spedycja.json \
  --serper-only-discovery \
  --no-auto-email >>"$LOG" 2>&1
EC=$?
set -e

echo "[$(date '+%F %T')] END discovery ($DAY_LABEL) exit=$EC" >>"$LOG"
if [[ "$EC" -eq 0 ]]; then
  pipeline_notify ok "$JOB" --log "$LOG" --exit-code "$EC"
else
  pipeline_notify alert "$JOB" --log "$LOG" --exit-code "$EC" \
    --detail "Discovery zakończone błędem (exit=$EC)."
fi
exit "$EC"

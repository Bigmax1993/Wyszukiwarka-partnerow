#!/usr/bin/env bash
# Weryfikacja cache JSON przed porannym discovery (cron ~04:00).
# Zapisuje stempel Wyniki/.cache_verified_for_discovery.json;
# run_discovery.sh startuje z --respect-cache.
set -euo pipefail
# shellcheck disable=SC1091
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

JOB="cache/verify"
LOG="$ROOT/logs/cache_verify.log"
# Jawny odbiorca powiadomień (START/OK/ALERT weryfikacji cache)
export PIPELINE_NOTIFY_TO="${PIPELINE_NOTIFY_TO:-svinchak1993@gmail.com}"
export DISABLE_PIPELINE_NOTIFY="${DISABLE_PIPELINE_NOTIFY:-0}"

pipeline_notify start "$JOB" --log "$LOG" \
  --detail "Weryfikacja cache RUSZYŁA (pl_spedycja_cache.json). Po OK discovery o 07:00 startuje z --respect-cache. Odbiorca: ${PIPELINE_NOTIFY_TO}"
echo "[$(date '+%F %T')] START cache verify → notify ${PIPELINE_NOTIFY_TO}" | tee -a "$LOG"

set +e
"$PY" scripts/verify_pl_cache.py --campaign-dir "$ROOT" >>"$LOG" 2>&1
EC=$?
set -e

echo "[$(date '+%F %T')] END cache verify exit=$EC" | tee -a "$LOG"
if [[ "$EC" -eq 0 ]]; then
  pipeline_notify ok "$JOB" --log "$LOG" --exit-code "$EC" \
    --detail "Cache OK — discovery 07:00 użyje --respect-cache."
else
  pipeline_notify alert "$JOB" --log "$LOG" --exit-code "$EC" \
    --detail "Weryfikacja cache nieudana (exit=$EC). Sprawdź Wyniki/pl_spedycja_cache.json."
fi
exit "$EC"

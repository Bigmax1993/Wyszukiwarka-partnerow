#!/usr/bin/env bash
# Niedziela — verify pending + backfill e-maili + rebuild Excel.
set -euo pipefail
# shellcheck disable=SC1091
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

JOB="backfill/niedziela"
LOG="$ROOT/logs/niedziela_backfill.log"
unset DISABLE_SEND_WINDOW || true

pipeline_notify start "$JOB" --log "$LOG"
echo "[$(date '+%F %T')] START backfill" >>"$LOG"

set +e
"$PY" pl_fas_spedycja_scraper.py --verify-pending-contacts >>"$LOG" 2>&1
EC1=$?
"$PY" pl_fas_spedycja_scraper.py --backfill-emails-from-cache >>"$LOG" 2>&1
EC2=$?
"$PY" pl_fas_spedycja_scraper.py --rebuild-from-cache >>"$LOG" 2>&1
EC3=$?
set -e

EC=0
if [[ "$EC1" -ne 0 || "$EC2" -ne 0 || "$EC3" -ne 0 ]]; then
  EC=1
fi

echo "[$(date '+%F %T')] END backfill exit=$EC (verify=$EC1 backfill=$EC2 rebuild=$EC3)" >>"$LOG"
if [[ "$EC" -eq 0 ]]; then
  pipeline_notify ok "$JOB" --log "$LOG" --exit-code 0 \
    --detail "verify=$EC1 backfill=$EC2 rebuild=$EC3"
else
  pipeline_notify alert "$JOB" --log "$LOG" --exit-code "$EC" \
    --detail "Backfill błąd: verify=$EC1 backfill=$EC2 rebuild=$EC3"
fi
exit "$EC"

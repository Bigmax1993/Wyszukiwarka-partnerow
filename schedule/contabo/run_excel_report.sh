#!/usr/bin/env bash
# Raport Excel → Gmail (wewnętrzny, nie B2B).
set -euo pipefail
# shellcheck disable=SC1091
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

JOB="excel/niedziela"
LOG="$ROOT/logs/excel_report.log"
FLAG="${DISABLE_EXCEL_REPORT_EMAIL:-0}"

case "${FLAG,,}" in
  1|true|yes|on)
    echo "[$(date '+%F %T')] [NO-OP] Raport Excel wylaczony." >>"$LOG"
    exit 0
    ;;
esac

pipeline_notify start "$JOB" --log "$LOG"
echo "[$(date '+%F %T')] START excel report" >>"$LOG"

set +e
"$PY" scripts/send_excel_gmail.py >>"$LOG" 2>&1
EC=$?
set -e

echo "[$(date '+%F %T')] END excel report exit=$EC" >>"$LOG"
if [[ "$EC" -eq 0 ]]; then
  pipeline_notify ok "$JOB" --log "$LOG" --exit-code "$EC"
else
  pipeline_notify alert "$JOB" --log "$LOG" --exit-code "$EC" \
    --detail "Raport Excel zakończony błędem (exit=$EC)."
fi
exit "$EC"

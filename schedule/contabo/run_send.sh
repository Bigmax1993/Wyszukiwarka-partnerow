#!/usr/bin/env bash
# Wysyłka B2B (--send-emails-only). NO-OP gdy DISABLE_CONTRACTOR_EMAILS≠0.
set -euo pipefail
# shellcheck disable=SC1091
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

DAY_LABEL="${1:-send}"
JOB="send/${DAY_LABEL}"
LOG="$ROOT/logs/${DAY_LABEL}_send.log"
FLAG="${DISABLE_CONTRACTOR_EMAILS:-1}"

case "${FLAG,,}" in
  0|false|no|off)
    ;;
  *)
    echo "[$(date '+%F %T')] [NO-OP] Wysylka kontrahentow wylaczona (DISABLE_CONTRACTOR_EMAILS=$FLAG)." >>"$LOG"
    exit 0
    ;;
esac

pipeline_notify start "$JOB" --log "$LOG"
echo "[$(date '+%F %T')] START send ($DAY_LABEL)" >>"$LOG"
unset DISABLE_SEND_WINDOW SEND_WINDOW_START_HOUR SEND_WINDOW_END_HOUR || true

set +e
"$PY" pl_fas_spedycja_scraper.py --send-emails-only >>"$LOG" 2>&1
EC=$?
set -e

echo "[$(date '+%F %T')] END send ($DAY_LABEL) exit=$EC" >>"$LOG"
if [[ "$EC" -eq 0 ]]; then
  pipeline_notify ok "$JOB" --log "$LOG" --exit-code "$EC"
else
  pipeline_notify alert "$JOB" --log "$LOG" --exit-code "$EC" \
    --detail "Send B2B zakończone błędem (exit=$EC)."
fi
exit "$EC"

#!/usr/bin/env bash
# Raport Excel → Gmail + Google Drive (wewnętrzny, nie B2B). Cron Contabo: pon 07:30.
set -euo pipefail
# shellcheck disable=SC1091
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

JOB="excel/poniedzialek"
LOG="$ROOT/logs/excel_report.log"
export PIPELINE_NOTIFY_TO="${PIPELINE_NOTIFY_TO:-svinchak1993@gmail.com}"
export EXCEL_REPORT_TO="${EXCEL_REPORT_TO:-svinchak1993@gmail.com}"
FLAG="${DISABLE_EXCEL_REPORT_EMAIL:-0}"
XLSX="$ROOT/Wyniki/pl_spedycja_kontakte.xlsx"

case "${FLAG,,}" in
  1|true|yes|on)
    echo "[$(date '+%F %T')] [NO-OP] Raport Excel wylaczony (DISABLE_EXCEL_REPORT_EMAIL=${FLAG})." | tee -a "$LOG"
    pipeline_notify alert "$JOB" --log "$LOG" \
      --detail "Excel OFF (DISABLE_EXCEL_REPORT_EMAIL=1). Ustaw 0 w .env Contabo."
    exit 0
    ;;
esac

pipeline_notify start "$JOB" --log "$LOG" \
  --detail "Wysyłka końcowego Excela → ${EXCEL_REPORT_TO} + upload Google Drive (poniedziałek 07:30)."
echo "[$(date '+%F %T')] START excel report → ${EXCEL_REPORT_TO} + Drive" >>"$LOG"

set +e
"$PY" scripts/send_excel_gmail.py >>"$LOG" 2>&1
EC_MAIL=$?
set -e

# Upload tylko .xlsx (bez cache/log). Nadpisz globalne DISABLE_GOOGLE_DRIVE=1 tylko w tym kroku.
EC_DRIVE=0
if [[ -f "$XLSX" ]]; then
  TMP_DRIVE="$(mktemp -d /tmp/excel-drive-XXXXXX)"
  mkdir -p "$TMP_DRIVE/Wyniki"
  cp "$XLSX" "$TMP_DRIVE/Wyniki/pl_spedycja_kontakte.xlsx"
  if [[ -z "${GDRIVE_FOLDER_ID:-}" ]]; then
    echo "[$(date '+%F %T')] ERROR: brak GDRIVE_FOLDER_ID w .env — pomijam Drive" >>"$LOG"
    EC_DRIVE=1
    rm -rf "$TMP_DRIVE"
  else
    echo "[$(date '+%F %T')] START Google Drive upload → folder ${GDRIVE_FOLDER_ID}" >>"$LOG"
    set +e
    DISABLE_GOOGLE_DRIVE=0 \
    GDRIVE_VERSION_XLSX="${GDRIVE_VERSION_XLSX:-0}" \
      "$PY" scripts/gdrive_upload_wyniki.py \
        --campaign-dir "$TMP_DRIVE" \
        --folder-id "$GDRIVE_FOLDER_ID" >>"$LOG" 2>&1
    EC_DRIVE=$?
    set -e
    rm -rf "$TMP_DRIVE"
    echo "[$(date '+%F %T')] END Google Drive upload exit=$EC_DRIVE" >>"$LOG"
  fi
else
  echo "[$(date '+%F %T')] WARN: brak $XLSX — pomijam Drive" >>"$LOG"
  EC_DRIVE=1
fi

echo "[$(date '+%F %T')] END excel report mail=$EC_MAIL drive=$EC_DRIVE" >>"$LOG"

if [[ "$EC_MAIL" -eq 0 && "$EC_DRIVE" -eq 0 ]]; then
  pipeline_notify ok "$JOB" --log "$LOG" --exit-code 0 \
    --detail "Excel → mail OK + Google Drive OK."
  exit 0
fi

pipeline_notify alert "$JOB" --log "$LOG" --exit-code 1 \
  --detail "Excel: mail_exit=${EC_MAIL} drive_exit=${EC_DRIVE}."
# Mail ważniejszy — niech cron nie failuje tylko przez Drive, ale alert idzie zawsze przy błędzie.
if [[ "$EC_MAIL" -ne 0 ]]; then
  exit "$EC_MAIL"
fi
exit "$EC_DRIVE"

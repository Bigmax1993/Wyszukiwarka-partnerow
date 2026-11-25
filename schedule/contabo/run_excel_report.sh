#!/usr/bin/env bash
# Raport Excel (wewnętrzny, nie B2B).
# Contabo: pon 06:30 mail | pon 06:45 Google Drive (przed discovery 07:00).
# Użycie: run_excel_report.sh [mail|drive|all]
set -euo pipefail
# shellcheck disable=SC1091
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

MODE="${1:-all}"
case "${MODE}" in
  mail|drive|all) ;;
  *)
    echo "Użycie: $0 [mail|drive|all]" >&2
    exit 2
    ;;
esac

JOB="excel/poniedzialek-${MODE}"
LOG="$ROOT/logs/excel_report.log"
export PIPELINE_NOTIFY_TO="${PIPELINE_NOTIFY_TO:-svinchak1993@gmail.com}"
export EXCEL_REPORT_TO="${EXCEL_REPORT_TO:-svinchak1993@gmail.com}"
FLAG="${DISABLE_EXCEL_REPORT_EMAIL:-0}"
XLSX="$ROOT/Wyniki/pl_spedycja_kontakte.xlsx"
EC_MAIL=0
EC_DRIVE=0

do_mail() {
  case "${FLAG,,}" in
    1|true|yes|on)
      echo "[$(date '+%F %T')] [NO-OP] Raport Excel mail wylaczony (DISABLE_EXCEL_REPORT_EMAIL=${FLAG})." | tee -a "$LOG"
      pipeline_notify alert "$JOB" --log "$LOG" \
        --detail "Excel mail OFF (DISABLE_EXCEL_REPORT_EMAIL=1). Ustaw 0 w .env Contabo."
      return 0
      ;;
  esac
  echo "[$(date '+%F %T')] START excel mail → ${EXCEL_REPORT_TO}" >>"$LOG"
  set +e
  "$PY" scripts/send_excel_gmail.py >>"$LOG" 2>&1
  EC_MAIL=$?
  set -e
  echo "[$(date '+%F %T')] END excel mail exit=$EC_MAIL" >>"$LOG"
  return "$EC_MAIL"
}

do_drive() {
  if [[ ! -f "$XLSX" ]]; then
    echo "[$(date '+%F %T')] WARN: brak $XLSX — pomijam Drive" >>"$LOG"
    EC_DRIVE=1
    return 1
  fi
  if [[ -z "${GDRIVE_FOLDER_ID:-}" ]]; then
    echo "[$(date '+%F %T')] ERROR: brak GDRIVE_FOLDER_ID w .env — pomijam Drive" >>"$LOG"
    EC_DRIVE=1
    return 1
  fi
  TMP_DRIVE="$(mktemp -d /tmp/excel-drive-XXXXXX)"
  mkdir -p "$TMP_DRIVE/Wyniki"
  cp "$XLSX" "$TMP_DRIVE/Wyniki/pl_spedycja_kontakte.xlsx"
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
  return "$EC_DRIVE"
}

pipeline_notify start "$JOB" --log "$LOG" \
  --detail "Excel mode=${MODE} (mail 06:30 / Drive 06:45, przed discovery 07:00)."
echo "[$(date '+%F %T')] START excel report mode=${MODE}" >>"$LOG"

set +e
case "$MODE" in
  mail) do_mail ;;
  drive) do_drive ;;
  all)
    do_mail
    do_drive
    ;;
esac
set -e

echo "[$(date '+%F %T')] END excel report mode=${MODE} mail=$EC_MAIL drive=$EC_DRIVE" >>"$LOG"

if [[ "$MODE" == "mail" ]]; then
  if [[ "$EC_MAIL" -eq 0 ]]; then
    pipeline_notify ok "$JOB" --log "$LOG" --exit-code 0 --detail "Excel mail OK → ${EXCEL_REPORT_TO}."
    exit 0
  fi
  pipeline_notify alert "$JOB" --log "$LOG" --exit-code "$EC_MAIL" \
    --detail "Excel mail błąd (exit=$EC_MAIL)."
  exit "$EC_MAIL"
fi

if [[ "$MODE" == "drive" ]]; then
  if [[ "$EC_DRIVE" -eq 0 ]]; then
    pipeline_notify ok "$JOB" --log "$LOG" --exit-code 0 --detail "Excel Google Drive OK."
    exit 0
  fi
  pipeline_notify alert "$JOB" --log "$LOG" --exit-code "$EC_DRIVE" \
    --detail "Excel Drive błąd (exit=$EC_DRIVE)."
  exit "$EC_DRIVE"
fi

# all
if [[ "$EC_MAIL" -eq 0 && "$EC_DRIVE" -eq 0 ]]; then
  pipeline_notify ok "$JOB" --log "$LOG" --exit-code 0 \
    --detail "Excel → mail OK + Google Drive OK."
  exit 0
fi
pipeline_notify alert "$JOB" --log "$LOG" --exit-code 1 \
  --detail "Excel: mail_exit=${EC_MAIL} drive_exit=${EC_DRIVE}."
if [[ "$EC_MAIL" -ne 0 ]]; then
  exit "$EC_MAIL"
fi
exit "$EC_DRIVE"

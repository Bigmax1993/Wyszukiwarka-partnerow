#!/usr/bin/env bash
# Dogrywka maila START + waiter OK/ALERT na koniec ręcznego gap-fill-full.
set -euo pipefail
ROOT=/opt/bots/Wyszukiwarka-partnerow
cd "$ROOT"
set -a
# shellcheck disable=SC1091
[ -f .env ] && . ./.env
set +a
PY="$ROOT/.venv/bin/python"
LOG="$ROOT/logs/gap_fill_serper_full.log"
JOB="gap-fill/serper-full"

"$PY" "$ROOT/scripts/pipeline_notify.py" start --job "$JOB" --log "$LOG" \
  --detail "Ręczny pełny gap-fill (max=170, do 6h): uzupełnia mail+telefon. START był pominięty przy nohup — dogrywka."
echo "NOTIFY_START_OK"

PID="$(pgrep -f 'gap_fill_serper.py --run-config' | head -1 || true)"
if [[ -z "${PID}" ]]; then
  echo "Brak działającego gap_fill — tylko START wysłany"
  exit 0
fi
echo "watching pid=${PID}"

nohup bash -c "
PID=${PID}
LOG=${LOG}
JOB=${JOB}
ROOT=${ROOT}
PY=${PY}
while kill -0 \"\$PID\" 2>/dev/null; do sleep 30; done
cd \"\$ROOT\"
set -a
[ -f .env ] && . ./.env
set +a
EC=1
if grep -q '^\\[GAP-FILL\\]' \"\$LOG\"; then
  EC=0
fi
if grep -q 'Traceback (most recent call last)' \"\$LOG\"; then
  # traceback na końcu = błąd
  if tail -n 40 \"\$LOG\" | grep -q 'Traceback (most recent call last)'; then
    EC=1
  fi
fi
KIND=alert
[[ \"\$EC\" -eq 0 ]] && KIND=ok
\"\$PY\" \"\$ROOT/scripts/pipeline_notify.py\" \"\$KIND\" --job \"\$JOB\" --log \"\$LOG\" --exit-code \"\$EC\" \
  --detail \"Koniec pełnego gap-fill (Excel tylko z mail+telefon; luki zostają w JSON).\"
echo \"[$(date '+%F %T')] notify \$KIND exit=\$EC\" >> \"\$ROOT/logs/gap_fill_notify_waiter.log\"
" >>"$ROOT/logs/gap_fill_notify_waiter.log" 2>&1 &
echo "waiter_pid=$!"

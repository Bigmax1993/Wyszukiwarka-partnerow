#!/usr/bin/env bash
# Czeka na koniec gap_fill_serper.py i wysyła mail OK/ALERT (bez ponownego START).
set -euo pipefail
ROOT=/opt/bots/Wyszukiwarka-partnerow
cd "$ROOT"
LOG="$ROOT/logs/gap_fill_serper_full.log"
JOB="gap-fill/serper-full"
PY="$ROOT/.venv/bin/python"
PID="$(pgrep -f 'gap_fill_serper.py --run-config' | head -1 || true)"
if [[ -z "${PID}" ]]; then
  echo "Brak działającego gap_fill — nic do waitowania"
  exit 0
fi
echo "waiting for pid=${PID}"
nohup bash -c "
PID=${PID}
ROOT=${ROOT}
LOG=${LOG}
JOB=${JOB}
PY=${PY}
while kill -0 \"\$PID\" 2>/dev/null; do sleep 30; done
cd \"\$ROOT\"
set -a
[ -f .env ] && . ./.env
set +a
EC=1
if grep -q '^\\[GAP-FILL\\]' \"\$LOG\"; then EC=0; fi
if tail -n 40 \"\$LOG\" | grep -q 'Traceback (most recent call last)'; then EC=1; fi
KIND=alert
[[ \"\$EC\" -eq 0 ]] && KIND=ok
\"\$PY\" \"\$ROOT/scripts/pipeline_notify.py\" \"\$KIND\" --job \"\$JOB\" --log \"\$LOG\" --exit-code \"\$EC\" \
  --detail \"Koniec pełnego gap-fill (Excel tylko z mail+telefon; luki zostają w JSON).\"
echo \"[\$(date '+%F %T')] notify \$KIND exit=\$EC\" >> \"\$ROOT/logs/gap_fill_notify_waiter.log\"
" >>"$ROOT/logs/gap_fill_notify_waiter.log" 2>&1 &
echo "waiter_pid=$!"

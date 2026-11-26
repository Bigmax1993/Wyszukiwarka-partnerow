#!/usr/bin/env bash
# Wspólne helpery cron Contabo — kampania PL FAS / spedycja.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

export KANBUD_PROJECT_ROOT="${KANBUD_PROJECT_ROOT:-$ROOT/libs}"
export SCRAPER_TIMEZONE="${SCRAPER_TIMEZONE:-Europe/Warsaw}"
export PIPELINE_NOTIFY_TO="${PIPELINE_NOTIFY_TO:-${EXCEL_REPORT_TO:-svinchak1993@gmail.com}}"
export GOOGLE_MAPS_DISCOVERY="${GOOGLE_MAPS_DISCOVERY:-1}"
export GOOGLE_MAPS_HEADLESS="${GOOGLE_MAPS_HEADLESS:-1}"
# Faza B: NIE w tym samym procesie co Maps — start z opóźnieniem po discovery
# (schedule_gap_fill_after_discovery). Wieczorny cron 20:00 wyłączony.
export GAP_FILL_AFTER_MAPS="${GAP_FILL_AFTER_MAPS:-0}"
export GAP_FILL_MAX="${GAP_FILL_MAX:-150}"
# Opóźnienie gap-fill po końcu discovery (sekundy). Domyślnie 1 h.
export GAP_FILL_DELAY_SECONDS="${GAP_FILL_DELAY_SECONDS:-3600}"

# >>> schedule_gap_fill_after_discovery
# Po discovery: odczekaj GAP_FILL_DELAY_SECONDS, potem run_gap_fill.sh (flock).
schedule_gap_fill_after_discovery() {
  local delay_sec="${GAP_FILL_DELAY_SECONDS:-3600}"
  local delay_log="$ROOT/logs/gap_fill_delayed.log"
  local lock="$ROOT/logs/gap_fill_delayed.lock"
  local when
  when="$(date -d "+${delay_sec} seconds" '+%F %T' 2>/dev/null || date -v+"${delay_sec}S" '+%F %T' 2>/dev/null || echo "+${delay_sec}s")"
  {
    echo "[$(date '+%F %T')] SCHEDULE gap-fill za ${delay_sec}s (ok. ${when}), max=${GAP_FILL_MAX:-150}"
  } | tee -a "$delay_log"
  # Odwołaj poprzedni sleep-waiter tego samego typu (jeśli jeszcze czeka)
  if [[ -f "$ROOT/logs/gap_fill_delayed.pid" ]]; then
    old_pid="$(cat "$ROOT/logs/gap_fill_delayed.pid" 2>/dev/null || true)"
    if [[ -n "${old_pid}" ]] && kill -0 "$old_pid" 2>/dev/null; then
      # zabij całą grupę waitera (sleep + bash)
      kill "$old_pid" 2>/dev/null || true
      echo "[$(date '+%F %T')] CANCEL poprzedni delayed gap-fill pid=${old_pid}" >>"$delay_log"
    fi
  fi
  nohup bash -c "
    sleep ${delay_sec}
    cd '${ROOT}'
    set -a
    [ -f .env ] && . ./.env
    set +a
    export GAP_FILL_MAX='${GAP_FILL_MAX:-150}'
    export SCRAPER_MAX_RUNTIME_SECONDS=\"\${SCRAPER_MAX_RUNTIME_SECONDS:-7200}\"
    echo \"[\$(date '+%F %T')] START delayed gap-fill (po discovery)\" >>'${delay_log}'
    if command -v flock >/dev/null 2>&1; then
      flock -n '${lock}' -c './schedule/contabo/run_gap_fill.sh' >>'${delay_log}' 2>&1
      ec=\$?
    else
      ./schedule/contabo/run_gap_fill.sh >>'${delay_log}' 2>&1
      ec=\$?
    fi
    echo \"[\$(date '+%F %T')] END delayed gap-fill exit=\$ec\" >>'${delay_log}'
    rm -f '${ROOT}/logs/gap_fill_delayed.pid'
  " >>"$delay_log" 2>&1 &
  echo $! >"$ROOT/logs/gap_fill_delayed.pid"
  echo "[$(date '+%F %T')] delayed waiter pid=$(cat "$ROOT/logs/gap_fill_delayed.pid")" >>"$delay_log"
}
# Chromium pod Selenium (system lub Playwright)
if [[ -z "${CHROME_BIN:-}" ]]; then
  for c in /usr/bin/google-chrome-stable /usr/bin/google-chrome /usr/bin/chromium /usr/bin/chromium-browser; do
    if [[ -x "$c" ]]; then export CHROME_BIN="$c"; break; fi
  done
fi
if [[ -z "${CHROME_BIN:-}" ]]; then
  pw_chrome="$(ls -d /root/.cache/ms-playwright/chromium-*/chrome-linux/chrome 2>/dev/null | tail -n1 || true)"
  if [[ -n "$pw_chrome" && -x "$pw_chrome" ]]; then
    export CHROME_BIN="$pw_chrome"
  fi
fi
export PATH="$ROOT/.venv/bin:$PATH"

PY="${ROOT}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "BRAK venv: $PY" >&2
  exit 1
fi

mkdir -p "$ROOT/Wyniki" "$ROOT/wyslane" "$ROOT/logs"

# Powiadomienie e-mail (START/OK/ALERT). Nie wywala joba przy błędzie SMTP.
pipeline_notify() {
  local kind="$1"
  local job="$2"
  shift 2
  "$PY" "$ROOT/scripts/pipeline_notify.py" "$kind" --job "$job" "$@" || true
}

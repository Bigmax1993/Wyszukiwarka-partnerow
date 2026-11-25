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
# Faza B: domyślnie wieczorny cron (run_gap_fill.sh), nie w tym samym jobie co Maps
export GAP_FILL_AFTER_MAPS="${GAP_FILL_AFTER_MAPS:-0}"
export GAP_FILL_MAX="${GAP_FILL_MAX:-40}"
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

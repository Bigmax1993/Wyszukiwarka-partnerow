#!/usr/bin/env bash
# Instaluje blok cron PL FAS na Contabo (Europe/Berlin ≈ Warsaw CET/CEST).
# Plan jak register_tasks_5_dni.ps1: pon–pt 07:00 discovery | nd 06:00 backfill
# | pon/wt 09:00 send | nd 09:00 Excel (jak GHA) + watchdog co 15 min.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MARKER_BEGIN="# BEGIN wyszukiwarka-partnerow"
MARKER_END="# END wyszukiwarka-partnerow"

chmod +x "$ROOT"/schedule/contabo/*.sh

BLOCK=$(cat <<EOF
$MARKER_BEGIN
# PL FAS Contabo — discovery 07:00 | backfill nd 06:00 | send pon/wt 09:00 | Excel nd 09:00
# Watchdog: co 15 min — ALERT gdy job running > limit
# Strefa serwera: Europe/Berlin (CET/CEST = Warsaw)
0 7 * * 1 cd $ROOT && ./schedule/contabo/run_discovery.sh poniedzialek
0 7 * * 2 cd $ROOT && ./schedule/contabo/run_discovery.sh wtorek
0 7 * * 3 cd $ROOT && ./schedule/contabo/run_discovery.sh sroda
0 7 * * 4 cd $ROOT && ./schedule/contabo/run_discovery.sh czwartek
0 7 * * 5 cd $ROOT && ./schedule/contabo/run_discovery.sh piatek
# Faza B — Serper gap-fill wieczorem (po Maps discovery; osobny budżet/czas)
0 20 * * 1-5 cd $ROOT && ./schedule/contabo/run_gap_fill.sh
0 6 * * 0 cd $ROOT && ./schedule/contabo/run_backfill.sh
0 9 * * 1 cd $ROOT && ./schedule/contabo/run_send.sh poniedzialek
0 9 * * 2 cd $ROOT && ./schedule/contabo/run_send.sh wtorek
0 9 * * 0 cd $ROOT && ./schedule/contabo/run_excel_report.sh
*/15 * * * * cd $ROOT && .venv/bin/python scripts/pipeline_watchdog.py >> $ROOT/logs/watchdog.log 2>&1
$MARKER_END
EOF
)

EXISTING="$(crontab -l 2>/dev/null || true)"
FILTERED="$(printf '%s\n' "$EXISTING" | awk -v b="$MARKER_BEGIN" -v e="$MARKER_END" '
  $0==b {skip=1; next}
  $0==e {skip=0; next}
  !skip {print}
')"

{
  printf '%s\n' "$FILTERED"
  printf '%s\n' "$BLOCK"
} | crontab -

echo "OK: crontab PL FAS zainstalowany"
crontab -l | awk -v b="$MARKER_BEGIN" -v e="$MARKER_END" '
  $0==b {show=1}
  show {print}
  $0==e {show=0}
'

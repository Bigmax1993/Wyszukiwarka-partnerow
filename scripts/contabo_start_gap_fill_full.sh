#!/usr/bin/env bash
# Jednorazowy pełny gap-fill (max 170, limit 6h) + reset TTL luk.
set -euo pipefail
ROOT=/opt/bots/Wyszukiwarka-partnerow
cd "$ROOT"
# shellcheck disable=SC1091
set -a
[ -f .env ] && . ./.env
set +a

cp /tmp/pl_fas_spedycja_scraper.py "$ROOT/" 2>/dev/null || true
cp /tmp/gap_fill_serper.py "$ROOT/" 2>/dev/null || true
cp /tmp/test_gap_fill_serper.py "$ROOT/tests/unit/" 2>/dev/null || true

.venv/bin/python -m pytest tests/unit/test_gap_fill_serper.py tests/unit/test_excel_requires_email.py -q --tb=line

.venv/bin/python - <<'PY'
import json
from pathlib import Path
from gap_fill_serper import contact_has_gap, has_email, has_phone

p = Path("Wyniki/pl_spedycja_cache.json")
cache = json.loads(p.read_text(encoding="utf-8"))
n = 0
for info in (cache.get("contacts") or {}).values():
    if not isinstance(info, dict):
        continue
    if contact_has_gap(info):
        info["enriched_at"] = ""
        if not has_email(info):
            info["serper_gap_queries"] = []
        n += 1
p.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
both = sum(
    1
    for i in cache["contacts"].values()
    if isinstance(i, dict) and has_email(i) and has_phone(i)
)
print(f"reset_ttl_for={n} already_both={both} total={len(cache['contacts'])}")
PY

if pgrep -f "gap_fill_serper.py" >/dev/null 2>&1; then
  echo "gap_fill already running — not starting another"
  pgrep -af "gap_fill_serper.py" || true
  exit 0
fi

export SCRAPER_MAX_RUNTIME_SECONDS=21600
export GAP_FILL_MAX=170
LOG="$ROOT/logs/gap_fill_serper_full.log"
STATE="$ROOT/logs/pipeline_state.json"
python3 - <<PY
import json
from datetime import datetime
from pathlib import Path
Path("$STATE").write_text(json.dumps({
    "job": "gap-fill/serper-full",
    "status": "running",
    "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    "log_file": "$LOG",
}, ensure_ascii=False, indent=2))
PY

echo "[$(date '+%F %T')] START gap-fill-full max=170" | tee -a "$LOG"
nohup .venv/bin/python gap_fill_serper.py \
  --run-config run_config/pl_fas_spedycja.json \
  --max 170 >>"$LOG" 2>&1 &
echo "pid=$!"
sleep 3
tail -n 20 "$LOG" || true
pgrep -af "gap_fill_serper.py" || true

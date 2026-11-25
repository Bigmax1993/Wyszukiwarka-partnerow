# -*- coding: utf-8 -*-
"""
Watchdog Contabo: job ze statusem=running dłużej niż limit → ALERT (raz).

  python scripts/pipeline_watchdog.py
  python scripts/pipeline_watchdog.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent
for p in (ROOT / "libs", ROOT, SCRIPTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

STATE_PATH = ROOT / "logs" / "pipeline_state.json"


def _parse_iso(val: str) -> datetime | None:
    if not val:
        return None
    try:
        dt = datetime.fromisoformat(val)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--max-age-seconds",
        type=int,
        default=0,
        help="Nadpisz próg (domyślnie SCRAPER_MAX_RUNTIME+3600, min 25200)",
    )
    args = parser.parse_args()

    if not STATE_PATH.is_file():
        print("Brak state — OK")
        return 0

    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"Nieczytelny state: {e}")
        return 0

    if (state.get("status") or "").lower() != "running":
        print(f"Status={state.get('status')!r} — brak alertu")
        return 0

    if state.get("alert_sent"):
        print("ALERT już wysłany dla tego biegu — skip")
        return 0

    started = _parse_iso(str(state.get("started_at") or ""))
    if not started:
        print("Brak started_at — skip")
        return 0

    runtime = int(os.environ.get("SCRAPER_MAX_RUNTIME_SECONDS") or "21600")
    limit = args.max_age_seconds or max(runtime + 3600, 25200)
    age = (datetime.now(timezone.utc) - started.astimezone(timezone.utc)).total_seconds()
    job = str(state.get("job") or "unknown")
    log_file = str(state.get("log_file") or "")

    print(f"Job={job} age={int(age)}s limit={limit}s")
    if age < limit:
        print("Jeszcze w limicie — OK")
        return 0

    import kanbud_bootstrap

    kanbud_bootstrap.ensure_import_paths(ROOT)
    from pipeline_notify import send_event

    detail = (
        f"Pipeline stoi / przekroczył limit.\n"
        f"Wiek: {int(age)} s (limit {limit} s).\n"
        f"started_at: {state.get('started_at')}\n"
        f"pid (parent przy starcie): {state.get('pid')}"
    )
    code = send_event(
        "alert",
        job,
        detail=detail,
        log_file=log_file,
        exit_code=None,
        dry_run=args.dry_run,
    )
    if code == 0 and not args.dry_run:
        state["status"] = "stale_alert"
        state["alert_sent"] = True
        state["alert_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        state["finished_at"] = state["alert_at"]
        STATE_PATH.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return code


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""
Powiadomienia pipeline Contabo → e-mail (START / OK / ALERT).

  python scripts/pipeline_notify.py start --job discovery/sroda
  python scripts/pipeline_notify.py ok --job discovery/sroda --exit-code 0
  python scripts/pipeline_notify.py alert --job discovery/sroda --detail "timeout" --exit-code 1

Odbiorca: PIPELINE_NOTIFY_TO → EXCEL_REPORT_TO → svinchak1993@gmail.com
Kill-switch: DISABLE_PIPELINE_NOTIFY=1
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT / "libs", ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import kanbud_bootstrap

kanbud_bootstrap.ensure_import_paths(ROOT)

from mail_transport import send_smtp_email
from scraper_env import get_excel_report_to

STATE_PATH = ROOT / "logs" / "pipeline_state.json"
DEFAULT_TO = "svinchak1993@gmail.com"


def _truthy(val: str | None) -> bool:
    return (val or "").strip().lower() in {"1", "true", "yes", "on"}


def _notify_to() -> str:
    return (
        (os.environ.get("PIPELINE_NOTIFY_TO") or "").strip()
        or get_excel_report_to()
        or DEFAULT_TO
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_state(data: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _tail(path: str, n: int = 40) -> str:
    if not path:
        return ""
    p = Path(path)
    if not p.is_file():
        return f"(brak logu: {path})"
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-n:])
    except OSError as e:
        return f"(nie mogę czytać logu: {e})"


def _logger() -> logging.Logger:
    log = logging.getLogger("pipeline_notify")
    if not log.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        log.addHandler(h)
        log.setLevel(logging.INFO)
    return log


def mark_running(job: str, log_file: str = "") -> None:
    _write_state(
        {
            "job": job,
            "status": "running",
            "started_at": _now_iso(),
            "pid": os.getppid(),
            "log_file": log_file,
            "alert_sent": False,
        }
    )


def mark_finished(job: str, status: str, exit_code: int | None = None) -> None:
    data = _read_state()
    data.update(
        {
            "job": job,
            "status": status,
            "finished_at": _now_iso(),
            "exit_code": exit_code,
        }
    )
    _write_state(data)


def send_event(
    kind: str,
    job: str,
    *,
    detail: str = "",
    log_file: str = "",
    exit_code: int | None = None,
    dry_run: bool = False,
) -> int:
    kind_u = kind.upper()
    if kind_u not in {"START", "OK", "ALERT"}:
        print(f"Nieznany kind: {kind}", file=sys.stderr)
        return 2

    if _truthy(os.environ.get("DISABLE_PIPELINE_NOTIFY")):
        print(f"[NO-OP] DISABLE_PIPELINE_NOTIFY=1 — pomijam {kind_u} ({job})")
        return 0

    to_email = _notify_to()
    host = os.environ.get("HOSTNAME") or "contabo"
    subject = f"[PL FAS] {kind_u}: {job} @ {host}"
    lines = [
        f"Status: {kind_u}",
        f"Job: {job}",
        f"Host: {host}",
        f"Czas: {_now_iso()}",
    ]
    if exit_code is not None:
        lines.append(f"Exit code: {exit_code}")
    if detail:
        lines.append("")
        lines.append("Szczegóły:")
        lines.append(detail.strip())
    if log_file:
        lines.append("")
        lines.append(f"Log: {log_file}")
        lines.append("--- ogon logu ---")
        lines.append(_tail(log_file))

    body = "\n".join(lines) + "\n"
    if dry_run:
        print(f"[DRY-RUN] Do: {to_email}")
        print(f"[DRY-RUN] Temat: {subject}")
        print(body)
        return 0

    logger = _logger()
    ok, info = send_smtp_email(
        to_email,
        subject,
        body,
        logger,
        mail_type=f"pipeline_{kind_u.lower()}",
        campaign="pl_fas_pipeline",
    )
    if ok:
        print(f"OK: {kind_u} → {to_email}")
        return 0
    print(f"BŁĄD wysyłki {kind_u}: {info}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Powiadomienia pipeline Contabo")
    parser.add_argument("kind", choices=["start", "ok", "alert"])
    parser.add_argument("--job", required=True, help="np. discovery/sroda")
    parser.add_argument("--detail", default="")
    parser.add_argument("--log", default="", dest="log_file")
    parser.add_argument("--exit-code", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--no-state",
        action="store_true",
        help="Nie aktualizuj logs/pipeline_state.json",
    )
    args = parser.parse_args()

    kind = args.kind.lower()
    if not args.no_state:
        if kind == "start":
            mark_running(args.job, args.log_file)
        elif kind == "ok":
            mark_finished(args.job, "ok", args.exit_code if args.exit_code is not None else 0)
        else:
            mark_finished(
                args.job,
                "alert",
                args.exit_code if args.exit_code is not None else 1,
            )

    return send_event(
        kind,
        args.job,
        detail=args.detail,
        log_file=args.log_file,
        exit_code=args.exit_code,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())

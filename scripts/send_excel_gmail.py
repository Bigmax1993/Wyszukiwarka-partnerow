# -*- coding: utf-8 -*-
"""
Wysyłka pliku Excel (GU Kontakte) przez Gmail / yagmail.

Uruchomienie:
  python scripts/send_excel_gmail.py
  python scripts/send_excel_gmail.py --dry-run

Wymaga w .env / secrets:
  MAIL_USER=twoje.konto@gmail.com
  MAIL_PASSWORD=haslo_aplikacji_gmail
  EXCEL_REPORT_TO=svinchak1993@gmail.com   (opcjonalnie — domyślnie ten adres)
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT / "libs", ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import kanbud_bootstrap

kanbud_bootstrap.ensure_import_paths(ROOT)

from campaign_data_paths import campaign_output_paths
from mail_transport import send_smtp_email_with_attachments
from scraper_env import get_excel_report_to, get_mail_user

DEFAULT_TZ = "Europe/Warsaw"


def setup_logging() -> logging.Logger:
    paths = campaign_output_paths(ROOT, "de_gu_bauunternehmen")
    log_file = paths["log_file"]
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("send_excel_gmail")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        logger.addHandler(fh)
        logger.addHandler(sh)
    return logger


def resolve_excel_path(explicit: str = "") -> Path:
    if explicit.strip():
        path = Path(explicit).expanduser()
        if path.is_file():
            return path.resolve()
        raise FileNotFoundError(f"Nie znaleziono pliku Excel: {path}")
    paths = campaign_output_paths(ROOT, "de_gu_bauunternehmen")
    primary = paths["output_file"]
    if primary.is_file():
        return primary.resolve()
    alt = primary.with_name(f"{primary.stem}_export{primary.suffix}")
    if alt.is_file():
        return alt.resolve()
    raise FileNotFoundError(
        f"Brak pliku Excel: {primary} (uruchom najpierw backfill / prep)"
    )


def count_kontakte_rows(path: Path) -> int:
    try:
        import pandas as pd  # pyright: ignore[reportMissingImports]

        df = pd.read_excel(path, sheet_name="Kontakte")
        return len(df.index)
    except Exception:
        return 0


def build_email_subject(path: Path) -> str:
    tz = ZoneInfo(DEFAULT_TZ)
    today = datetime.now(tz).strftime("%Y-%m-%d")
    return f"GU Kontakte Excel — {today} ({path.name})"


def build_email_body(path: Path, row_count: int) -> str:
    tz = ZoneInfo(DEFAULT_TZ)
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M")
    size_kb = path.stat().st_size / 1024
    rows_note = f"{row_count} wierszy w arkuszu Kontakte" if row_count else "arkusz Kontakte"
    return (
        f"Cześć,\n\n"
        f"w załączniku aktualny plik Excel z kampanii GU (Generalunternehmer).\n\n"
        f"Plik: {path.name}\n"
        f"Rozmiar: {size_kb:.0f} KB\n"
        f"{rows_note}\n"
        f"Wygenerowano/wysłano: {now} ({DEFAULT_TZ})\n\n"
        f"— automat Wyszukiwarka-partnerow\n"
    )


def send_excel_report(
    *,
    to_email: str = "",
    excel_path: str = "",
    dry_run: bool = False,
    logger: logging.Logger | None = None,
) -> tuple[bool, str]:
    """
    Raport wewnętrzny (Excel → jeden odbiorca EXCEL_REPORT_TO).
    NIE jest to wysyłka B2B do kontrahentów.
    Kill-switch: DISABLE_EXCEL_REPORT_EMAIL=1 (domyślnie raport WŁĄCZONY).
    """
    log = logger or setup_logging()
    try:
        from scraper_env import is_excel_report_email_disabled

        if is_excel_report_email_disabled() and not dry_run:
            msg = (
                "raport Excel wyłączony (DISABLE_EXCEL_REPORT_EMAIL=1); "
                "to nie jest mail B2B — włącz: ustaw 0"
            )
            log.info("[NO-OP] %s", msg)
            print(f"[NO-OP] {msg}")
            return True, "disabled_excel_report_email"
    except Exception:
        pass

    recipient = (to_email or get_excel_report_to()).strip()
    if not recipient or "@" not in recipient:
        return False, "brak poprawnego adresu EXCEL_REPORT_TO"
    # Jeden odbiorca — bez rozdzielania na listę / CC z tej ścieżki.
    if "," in recipient or ";" in recipient:
        return False, "EXCEL_REPORT_TO musi być jednym adresem (bez przecinków)"

    path = resolve_excel_path(excel_path)
    subject = build_email_subject(path)
    body = build_email_body(path, count_kontakte_rows(path))
    sender = get_mail_user() or "(brak MAIL_USER)"

    log.info("Excel report → %s | plik: %s | nadawca: %s", recipient, path, sender)
    if dry_run:
        print(f"[DRY-RUN] Do: {recipient}")
        print(f"[DRY-RUN] Temat: {subject}")
        print(f"[DRY-RUN] Załącznik: {path}")
        return True, "dry_run"

    return send_smtp_email_with_attachments(
        recipient,
        subject,
        body,
        [path],
        log,
        mail_type="Excel GU",
        campaign="de_gu_bauunternehmen",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Wyślij Excel GU na Gmail")
    parser.add_argument("--to", dest="to_email", default="", help="Adres odbiorcy")
    parser.add_argument("--excel", dest="excel_path", default="", help="Ścieżka do .xlsx")
    parser.add_argument("--dry-run", action="store_true", help="Bez wysyłki SMTP")
    args = parser.parse_args()
    logger = setup_logging()
    try:
        ok, info = send_excel_report(
            to_email=args.to_email,
            excel_path=args.excel_path,
            dry_run=args.dry_run,
            logger=logger,
        )
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        print(f"BŁĄD: {exc}", file=sys.stderr)
        return 1
    if ok:
        print(f"OK: {info}")
        return 0
    print(f"BŁĄD: {info}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

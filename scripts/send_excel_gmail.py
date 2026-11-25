# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Uzupełnienie opisu modułu scripts/send_excel_gmail (komentarz; docstring poniżej opisuje cel i wymagane zmienne).
#   Rola w pipeline: raport WEWNĘTRZNY (nie B2B) — wysyła Excel PL FAS (Kontakte) na jeden adres (EXCEL_REPORT_TO). Nie jest blokowany kill-switchem
#   DISABLE_CONTRACTOR_EMAILS; osobna flaga DISABLE_EXCEL_REPORT_EMAIL (domyślnie wyłączona) steruje raportem.
#   Zależności: kanbud_bootstrap (ścieżki), pl_spedycja_data_paths.campaign_output_paths, mail_transport.send_smtp_email_with_attachments,
#   scraper_env.get_excel_report_to/get_mail_user, stdlib (argparse, logging, zoneinfo…).
#   Wejście: --to, --excel, --dry-run. Wyjście: kod wyjścia 0/1 oraz komunikaty (OK/BŁĄD).
# ============================================================
"""
Wysyłka pliku Excel (PL FAS Kontakte) przez Gmail / yagmail.

Raport wewnętrzny kampanii PL spedycja — **nie** B2B do kontrahentów.

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

from pl_spedycja_data_paths import campaign_output_paths
from mail_transport import send_smtp_email_with_attachments
from scraper_env import get_excel_report_to, get_mail_user

DEFAULT_TZ = "Europe/Warsaw"


def setup_logging() -> logging.Logger:
    """
    Logger plik + konsola dla skryptu raportu Excel.

    =====================================================================
    PO CO
    =====================================================================
    Zapis do ``Wyniki/pl_spedycja_scraper.log`` (ta sama ścieżka co scraper)
    oraz stdout — GHA / lokalnie widać dry-run i błędy SMTP.

    Nie dokłada handlerów ponownie, jeśli logger już je ma.
    """
    paths = campaign_output_paths(ROOT, "pl_spedycja")
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
    """
    Wybiera plik ``.xlsx`` do załączenia w mailu raportu.

    =====================================================================
    PO CO
    =====================================================================
    CLI ``--excel`` albo domyślny output kampanii PL FAS
    (``pl_spedycja_kontakte.xlsx`` / wariant ``*_export.xlsx``).

    =====================================================================
    PRZEBIEG
    =====================================================================
    1. Niepusty ``explicit`` → ten plik (musi istnieć) albo ``FileNotFoundError``.
    2. ``campaign_output_paths(..., "pl_spedycja")["output_file"]``.
    3. Fallback: ``{stem}_export{suffix}`` obok primary.
    4. Brak obu → ``FileNotFoundError`` (najpierw backfill / prep).

    =====================================================================
    ZWRACA
    =====================================================================
    ``Path`` absolute; nigdy nieistniejący plik.
    """
    if explicit.strip():
        path = Path(explicit).expanduser()
        if path.is_file():
            return path.resolve()
        raise FileNotFoundError(f"Nie znaleziono pliku Excel: {path}")
    paths = campaign_output_paths(ROOT, "pl_spedycja")
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
    """
    Liczba wierszy w arkuszu ``Kontakte`` (do body maila).

    =====================================================================
    PO CO
    =====================================================================
    Krótka metryka w treści raportu („N wierszy”). Nazwa arkusza **legacy**
    — writer ``pl_fas_spedycja_scraper`` nadal używa ``Kontakte``;
    nie zmieniać tu bez zmiany ``write_excel_*``.

    =====================================================================
    ZWRACA
    =====================================================================
    ``len(df)`` albo ``0`` przy braku arkusza / błędzie pandas (nie crashuj SMTP).
    """
    try:
        import pandas as pd  # pyright: ignore[reportMissingImports]

        # Celowo „Kontakte” — spójne z pl_fas_spedycja_scraper Excel append.
        df = pd.read_excel(path, sheet_name="Kontakte")
        return len(df.index)
    except Exception:
        return 0


# >>> OPIS FUNKCJI: funkcja build_email_subject
# Cel: zbudować temat maila raportu. Parametry: path (Path) — załączany plik. Zwraca: str "PL FAS Kontakte Excel — RRRR-MM-DD (nazwa_pliku)"
# (data w strefie DEFAULT_TZ). Efekty uboczne/błędy: brak.
def build_email_subject(path: Path) -> str:
    """
    Temat maila raportu PL FAS.

    Format: ``PL FAS Kontakte Excel — YYYY-MM-DD ({filename})``
    (strefa ``Europe/Warsaw``).
    """
    tz = ZoneInfo(DEFAULT_TZ)
    today = datetime.now(tz).strftime("%Y-%m-%d")
    return f"PL FAS Kontakte Excel — {today} ({path.name})"


def build_email_body(path: Path, row_count: int) -> str:
    """
    Treść plain-text raportu wewnętrznego.

    =====================================================================
    PO CO
    =====================================================================
    Opis kampanii **PL FAS / spedycja drogowa** + metadane pliku
    (nazwa, KB, wiersze Kontakte, timestamp). Bez stringów GU/DE.

    ``row_count`` z ``count_kontakte_rows`` (0 = ogólny opis arkusza).
    """
    tz = ZoneInfo(DEFAULT_TZ)
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M")
    size_kb = path.stat().st_size / 1024
    rows_note = f"{row_count} wierszy w arkuszu Kontakte" if row_count else "arkusz Kontakte"
    return (
        f"Cześć,\n\n"
        f"w załączniku aktualny plik Excel z kampanii PL FAS / spedycja drogowa.\n\n"
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
    Wysyła (lub symuluje) raport Excel PL FAS na jeden adres Gmail.

    =====================================================================
    PO CO
    =====================================================================
    Raport **wewnętrzny** (nd 09:00 / lokalnie) — ``EXCEL_REPORT_TO``
    (default ``svinchak1993@gmail.com``). **Nie** jest to B2B do kontrahentów
    (osobny kill-switch: ``DISABLE_CONTRACTOR_EMAILS``).

    Kill-switch raportu: ``DISABLE_EXCEL_REPORT_EMAIL=1`` → NO-OP
    (zwraca ``(True, "disabled_excel_report_email")``; dry-run i tak pokazuje plan).

    =====================================================================
    PRZEBIEG
    =====================================================================
    1. Kill-switch (pomijany przy ``dry_run``).
    2. Odbiorca: ``to_email`` albo ``get_excel_report_to()`` — jeden adres.
    3. ``resolve_excel_path`` → subject / body / row count.
    4. ``dry_run`` → print planu, bez SMTP.
    5. ``send_smtp_email_with_attachments`` (``mail_type="Excel PL FAS"``).

    =====================================================================
    ZWRACA
    =====================================================================
    ``(ok, info)`` — ``info`` to status SMTP / ``dry_run`` / powód błędu.
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
        mail_type="Excel PL FAS",
        campaign="pl_spedycja",
    )


# >>> OPIS FUNKCJI: funkcja main
# Cel: wejście CLI (--to, --excel, --dry-run) wywołujące send_excel_report. Parametry: brak. Zwraca: int — 0 po sukcesie; 1 przy braku pliku, błędzie SMTP lub złym adresie.
# Efekty uboczne: konfiguracja logowania, ewentualna wysyłka maila, komunikaty na stdout/stderr. Błędy: FileNotFoundError łapany (log + komunikat); wynik (False, info) → BŁĄD i kod 1.
def main() -> int:
    """
    CLI: ``--to`` / ``--excel`` / ``--dry-run`` → ``send_excel_report``.

    Exit: ``0`` OK, ``1`` brak pliku / błąd SMTP / zły adres.
    """
    parser = argparse.ArgumentParser(description="Wyślij Excel PL FAS (Kontakte) na Gmail")
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

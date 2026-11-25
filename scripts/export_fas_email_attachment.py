# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Uzupełnienie opisu modułu scripts/export_fas_email_attachment (komentarz; docstring poniżej opisuje CLI).
#   Rola w pipeline: przygotowanie załączników PPTX (oferta + prezentacja) do maili B2B przed SMTP — pobranie z Google Drive do assets/campaign/.
#   Zależności: pl_fas_email_attachment (ID plików Drive, ensure_*), poświadczenia GDRIVE_OAUTH_*, stdlib argparse, logging, os, sys, pathlib.
#   Wejście: opcje CLI (np. --primary-only, --dest). Wyjście: kod wyjścia i pliki PPTX na dysku. Na czas pobrania tymczasowo zmienia flagę DISABLE_GOOGLE_DRIVE (patrz docstring).
# ============================================================
"""
Eksport załączników B2B FAS z Google Drive → lokalne PPTX (GHA / lokalnie).

=============================================================================
PO CO
=============================================================================
Pobiera **ofertę** + **dodatkową prezentację** do ``assets/campaign/``,
żeby maile B2B miały oba pliki bez ręcznego kopiowania z Drive.

Kanoniczny CLI::

  python scripts/export_fas_email_attachment.py
  python scripts/export_fas_email_attachment.py --primary-only

Shim legacy::

  python scripts/export_mfg_slides_attachment.py

Wymaga Drive credentials (``GDRIVE_OAUTH_*``) oraz ID z ``pl_fas_email_attachment``.
Na czas pobrania ustawia ``DISABLE_GOOGLE_DRIVE=0``.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pl_fas_email_attachment import (  # noqa: E402
    ATTACHMENT_EXTRA_FILENAME,
    ATTACHMENT_FILENAME,
    EMAIL_ATTACHMENT_DRIVE_FILE_ID,
    EMAIL_ATTACHMENT_DRIVE_URL,
    EMAIL_ATTACHMENT_EXTRA_DRIVE_FILE_ID,
    EMAIL_ATTACHMENT_EXTRA_DRIVE_URL,
    _download_attachment_pptx,
)


def main() -> int:
    """
    Pobierz PPTX FAS z Drive (oferta + prezentacja); zwróć kod wyjścia.

    =====================================================================
    PO CO
    =====================================================================
    CLI / krok GHA przed SMTP B2B — zapisuje pliki pod ``assets/campaign/``
    (albo ``--dest`` / ``--dest-extra``), żeby workflow mógł ustawić
    ``FAS_EMAIL_ATTACHMENT_PATH`` / ``FAS_EMAIL_ATTACHMENT_EXTRA_PATH``.

    =====================================================================
    PRZEBIEG
    =====================================================================
    1. Parse argparse (ścieżki dest, flaga ``--primary-only``).
    2. ``DISABLE_GOOGLE_DRIVE=0`` — inaczej download jest zablokowany.
    3. Pobierz ofertę (plik 1) → przy fail return ``1``.
    4. Jeśli nie ``--primary-only``: pobierz prezentację (plik 2) → fail = ``1``.
    5. Sukces → ``0`` + logi rozmiaru MB.

    =====================================================================
    ZWRACA
    =====================================================================
    ``0`` — OK (oba pliki albo tylko oferta przy ``--primary-only``).
    ``1`` — błąd pobrania / credentials / udostępnienia Drive.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Eksport załączników FAS (Drive → PPTX). "
            "Shim: scripts/export_mfg_slides_attachment.py"
        )
    )
    parser.add_argument(
        "--dest",
        default=str(ROOT / "assets" / "campaign" / ATTACHMENT_FILENAME),
        help=f"Docelowa ścieżka oferty (domyślnie assets/campaign/{ATTACHMENT_FILENAME})",
    )
    parser.add_argument(
        "--dest-extra",
        default=str(ROOT / "assets" / "campaign" / ATTACHMENT_EXTRA_FILENAME),
        help=(
            "Docelowa ścieżka prezentacji "
            f"(domyślnie assets/campaign/{ATTACHMENT_EXTRA_FILENAME})"
        ),
    )
    parser.add_argument(
        "--primary-only",
        action="store_true",
        help="Pobierz tylko ofertę (plik 1), bez dodatkowej prezentacji",
    )
    args = parser.parse_args()
    # Eksport GHA/lokalny — jawne pobranie (nie blokuj kill-switchiem).
    os.environ["DISABLE_GOOGLE_DRIVE"] = "0"
    logger = logging.getLogger("export_fas_attachment")
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    dest = Path(args.dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    ok_primary = _download_attachment_pptx(
        dest,
        logger,
        file_id=EMAIL_ATTACHMENT_DRIVE_FILE_ID,
        drive_url=EMAIL_ATTACHMENT_DRIVE_URL,
    )
    if not ok_primary:
        print(
            f"BLAD: nie pobrano oferty FAS z Drive ({EMAIL_ATTACHMENT_DRIVE_URL}). "
            "Sprawdz GDRIVE_OAUTH_* lub udostepnienie pliku.",
            file=sys.stderr,
        )
        return 1
    print(f"OK oferta: {dest} ({dest.stat().st_size / (1024 * 1024):.1f} MB)")

    if args.primary_only:
        return 0

    dest_extra = Path(args.dest_extra)
    dest_extra.parent.mkdir(parents=True, exist_ok=True)
    ok_extra = _download_attachment_pptx(
        dest_extra,
        logger,
        file_id=EMAIL_ATTACHMENT_EXTRA_DRIVE_FILE_ID,
        drive_url=EMAIL_ATTACHMENT_EXTRA_DRIVE_URL,
    )
    if not ok_extra:
        print(
            f"BLAD: nie pobrano prezentacji FAS z Drive "
            f"({EMAIL_ATTACHMENT_EXTRA_DRIVE_URL}). "
            "Sprawdz GDRIVE_OAUTH_* / udostepnienie pliku.",
            file=sys.stderr,
        )
        return 1
    print(
        f"OK prezentacja: {dest_extra} "
        f"({dest_extra.stat().st_size / (1024 * 1024):.1f} MB)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

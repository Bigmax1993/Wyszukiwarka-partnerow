# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Uzupełnienie opisu modułu scripts/export_mfg_slides_attachment (komentarz; docstring poniżej opisuje shim).
#   Rola: wyłącznie most zgodności — przy uruchomieniu jako skrypt wykonuje runpy.run_path na export_fas_email_attachment.py (run_name="__main__").
#   Zależności: stdlib runpy, pathlib. Funkcji własnych brak; wejście i wyjście identyczne jak w export_fas_email_attachment.py.
# ============================================================
"""
Shim legacy: ``export_mfg_slides_attachment`` → ``export_fas_email_attachment``.

PO CO: stare CI / dokumentacja wołały „MFG Slides”; kanoniczny eksport to FAS PPTX z Drive.

Nowy CLI::

  python scripts/export_fas_email_attachment.py
  python scripts/export_fas_email_attachment.py --dest assets/campaign/FAS_zalacznik_kampania.pptx

Ten plik tylko przekazuje ``__main__`` do ``export_fas_email_attachment.py``.
"""
from __future__ import annotations

import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(
        str(Path(__file__).resolve().with_name("export_fas_email_attachment.py")),
        run_name="__main__",
    )

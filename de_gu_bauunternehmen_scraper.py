# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Moduł: de_gu_bauunternehmen_scraper — SHIM legacy → pl_fas_spedycja_scraper.
#
# CO ROBI
#   Zachowuje starą nazwę pliku wejściowego (kampania DE GU/Filialbau). Importuje wszystko z
#   pl_fas_spedycja_scraper (import *) oraz main(). Przy uruchomieniu jako skrypt wykonuje
#   runpy.run_path na pl_fas_spedycja_scraper.py z run_name="__main__", dzięki czemu działają
#   wszystkie przełączniki CLI (--test, --run-config, --serper-only-discovery itd.).
#
# ROLA W PIPELINE: wyłącznie most kompatybilności (stare workflowy, harmonogramy, dokumentacja).
# ZALEŻNOŚCI: pl_fas_spedycja_scraper, runpy, pathlib. Funkcji własnych brak.
# ============================================================
"""
Shim legacy: ``de_gu_bauunternehmen_scraper`` → ``pl_fas_spedycja_scraper``.

Nowy kod / CLI::

  python pl_fas_spedycja_scraper.py --test
  from pl_fas_spedycja_scraper import main
"""
from __future__ import annotations

import runpy
from pathlib import Path

from pl_fas_spedycja_scraper import *  # noqa: F403
from pl_fas_spedycja_scraper import main  # noqa: F401

if __name__ == "__main__":
    # Pełna ścieżka __main__ (m.in. --test / --smoke), nie tylko main().
    runpy.run_path(
        str(Path(__file__).resolve().with_name("pl_fas_spedycja_scraper.py")),
        run_name="__main__",
    )

# -*- coding: utf-8 -*-
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

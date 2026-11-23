# -*- coding: utf-8 -*-
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

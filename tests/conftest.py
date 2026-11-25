# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# MODUŁ TESTOWY: tests/conftest.py
# CO ROBI: wspólna konfiguracja pytest: dodaje libs/ i katalog główny repo na początek sys.path oraz ustawia domyślne zmienne środowiskowe (KANBUD_PROJECT_ROOT, PYTHONUTF8, USE_GEMINI_REPLY_INTELLIGENCE=0).
# ROLA W PIPELINE: pozwala testom importować moduły kampanii (pl_fas_spedycja_scraper, libs.*) bez instalacji pakietu i wyłącza inteligencję odpowiedzi opartą o Gemini w testach.
# ZALEŻNOŚCI: pytest (automatycznie ładuje conftest), sys, pathlib, os.
# WEJŚCIE/WYJŚCIE: Brak funkcji i fixtur — działanie następuje przy imporcie (efekt uboczny: modyfikacja sys.path i os.environ).
# ============================================================
"""Wsp├│lna konfiguracja pytest."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIBS = ROOT / "libs"
for p in (LIBS, ROOT):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

import os

os.environ.setdefault("KANBUD_PROJECT_ROOT", str(LIBS))
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("USE_GEMINI_REPLY_INTELLIGENCE", "0")

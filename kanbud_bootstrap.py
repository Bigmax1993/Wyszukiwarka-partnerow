# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Moduł: kanbud_bootstrap — przygotowanie sys.path / zmiennej KANBUD_PROJECT_ROOT.
#
# CO ROBI
#   Dodaje do sys.path katalog kampanii, korzeń repozytorium i podkatalog libs/ (tak, aby
#   importy typu `import scraper_env`, `import polish_text` działały niezależnie od katalogu
#   roboczego), oraz ustawia (setdefault) zmienną środowiskową KANBUD_PROJECT_ROOT = libs/.
#
# ROLA W PIPELINE
#   Pierwszy krok bootstrapu: wołany na samym początku pl_fas_spedycja_scraper.py i skryptów
#   w scripts/ (np. send_excel_gmail.py) przed importem modułów z libs/.
#
# ZALEŻNOŚCI: os, sys, pathlib. Wymaga istnienia libs/polish_text.py (inaczej ImportError).
# WEJŚCIE/WYJŚCIE: ensure_import_paths(campaign_dir) -> Path do katalogu libs/.
# Uwaga: docstring pliku zawiera zniekształcone znaki (mojibake) — nie zmieniano go (tylko komentarze).
# ============================================================
"""Repo GU â€” sys.path: korzeĹ„ repo + libs/."""
from __future__ import annotations
import os, sys
from pathlib import Path
_REPO = Path(__file__).resolve().parent
_LIBS = _REPO / "libs"

# >>> OPIS FUNKCJI: funkcja ensure_import_paths
# Cel: zagwarantować, że katalog kampanii, korzeń repo i libs/ są w sys.path oraz że
# KANBUD_PROJECT_ROOT wskazuje libs/.
# Parametry: campaign_dir (Path | None) — katalog kampanii; None => bieżący katalog roboczy.
# Zwraca: Path — absolutna ścieżka do libs/ (_LIBS).
# Efekty uboczne: wstawia ścieżki na POCZĄTEK sys.path (insert(0, ...)), jeśli ich tam nie ma;
# dopisuje libs/ na KONIEC sys.path (append) i robi os.environ.setdefault("KANBUD_PROJECT_ROOT", ...).
# Błędy: gdy libs/polish_text.py nie istnieje — rzuca ImportError("Brak libs/polish_text.py w
# repozytorium GU."). Pozostałe wyjątki (np. brak uprawnień) nie są łapane.
def ensure_import_paths(campaign_dir: Path | None = None) -> Path:
    campaign_dir = (campaign_dir or Path.cwd()).resolve()
    for folder in (campaign_dir, _REPO, _LIBS):
        s = str(folder.resolve())
        if s not in sys.path:
            sys.path.insert(0, s)
    if (_LIBS / "polish_text.py").is_file():
        libs_s = str(_LIBS.resolve())
        os.environ.setdefault("KANBUD_PROJECT_ROOT", libs_s)
        if libs_s not in sys.path:
            sys.path.append(libs_s)
        return _LIBS
    raise ImportError("Brak libs/polish_text.py w repozytorium GU.")

# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Moduł: libs/project_config — ścieżki projektu niezależne od maszyny (bez twardych ścieżek użytkownika Windows).
#
# CO ROBI
#   Wylicza korzeń aplikacji (get_app_root), katalog danych operacyjnych (get_data_root; nadpisywalny
#   zmienną KANBUD_DATA_DIR), interpreter Pythona dla subprocessów, katalogi wyników kampanii
#   (results_dir, switzerland_wyniki_dir), katalog GUI oraz wykrywa wdrożenie chmurowe (brak lokalnych
#   folderów Wyniki_*). To dziedzictwo wspólnej biblioteki Kanbud/GUI — scraper PL FAS używa głównie
#   get_data_root-podobnej logiki z pl_spedycja_data_paths.
#
# ROLA W PIPELINE: konfiguracja środowiska (ścieżki), wykorzystywana przez moduły pomocnicze/GUI; nie
#   uczestniczy w samym wyszukiwaniu ani weryfikacji firm.
#
# ZALEŻNOŚCI: pathlib, scraper_env (ENV_KANBUD_DATA_DIR, get_env_value); stdlib os, sys (importowane lokalnie).
# STAN: PROJECT_ROOT = katalog tego pliku (libs/).
# WEJŚCIE: zmienne środowiskowe KANBUD_APP_ROOT, KANBUD_DATA_DIR, KANBUD_FORCE_LOCAL, KANBUD_CLOUD_HOST.
# WYJŚCIE: Path-e, str (ścieżka do python) lub bool.
# ============================================================
"""Ścieżki projektu — bez twardych ścieżek użytkownika Windows (GitHub / inne maszyny)."""
from __future__ import annotations

from pathlib import Path

from scraper_env import ENV_KANBUD_DATA_DIR, get_env_value

PROJECT_ROOT = Path(__file__).resolve().parent


# >>> OPIS FUNKCJI: funkcja get_app_root
# Cel: ustalić katalog z aplikacją i skryptami. Parametry: brak.
# Zwraca: Path — kolejność: env KANBUD_APP_ROOT (expanduser + resolve); dla zamrożonego EXE
# (sys.frozen) katalog pliku wykonywalnego; w pozostałych przypadkach PROJECT_ROOT.
# Efekty uboczne: odczyt env/sys. Błędy: brak własnej obsługi.
def get_app_root() -> Path:
    """
    Katalog z app.py i scraperami.
    Dla EXE desktop: ustawiane przez desktop_app (KANBUD_APP_ROOT).
    """
    import os
    import sys

    raw = os.environ.get("KANBUD_APP_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return PROJECT_ROOT


# >>> OPIS FUNKCJI: funkcja resolve_python_executable
# Cel: wskazać interpreter Pythona do uruchamiania scraperów jako subprocesów.
# Parametry: brak. Zwraca: str — ścieżka runtime/Scripts/python.exe lub runtime/python.exe w katalogu
# aplikacji, jeśli istnieje (pakiet desktop); inaczej sys.executable.
# Efekty uboczne: odczyt systemu plików (is_file). Błędy: brak.
def resolve_python_executable() -> str:
    """Python do subprocessów (scrapery). Przy pakiecie desktop: runtime/."""
    import sys

    root = get_app_root()
    for rel in (
        Path("runtime") / "Scripts" / "python.exe",
        Path("runtime") / "python.exe",
    ):
        p = root / rel
        if p.is_file():
            return str(p)
    return sys.executable


# >>> OPIS FUNKCJI: funkcja get_data_root
# Cel: katalog danych operacyjnych (cache, Excel, logi). Parametry: brak.
# Zwraca: Path — wartość KANBUD_DATA_DIR (expanduser+resolve), a gdy pusta: get_app_root().
# Efekty uboczne: odczyt env (get_env_value). Błędy: brak.
def get_data_root() -> Path:
    """
    Katalog danych operacyjnych (cache, Excel, logi).
    Domyślnie = folder projektu; nadpisz: KANBUD_DATA_DIR w .env / zmiennych Windows.
    """
    raw = get_env_value(ENV_KANBUD_DATA_DIR, "")
    if raw:
        return Path(raw).expanduser().resolve()
    return get_app_root()


# >>> OPIS FUNKCJI: funkcja results_dir
# Cel: zbudować ścieżkę folderu wyników o podanej nazwie, np. "Wyniki_Transport_PL".
# Parametry: folder_name (str). Zwraca: Path = get_data_root() / folder_name.
# Efekty uboczne: brak (nie tworzy katalogu). Błędy: brak.
def results_dir(folder_name: str) -> Path:
    """Np. results_dir('Wyniki_Transport_PL')."""
    return get_data_root() / folder_name


# >>> OPIS FUNKCJI: funkcja gui_data_dir
# Cel: katalog danych GUI. Parametry: brak. Zwraca: Path = get_app_root() / "gui_data".
# Efekty uboczne: brak (nie tworzy katalogu). Błędy: brak.
def gui_data_dir() -> Path:
    return get_app_root() / "gui_data"


# >>> OPIS FUNKCJI: funkcja has_local_campaign_data
# Cel: sprawdzić, czy na dysku istnieją lokalne foldery kampanii. Parametry: brak.
# Zwraca: bool — True, jeśli w get_data_root() istnieje którykolwiek z katalogów Wyniki_Gdansk,
# Wyniki_Warszawa, Wyniki_Saalfeld, Wyniki_Transport_PL. Efekty uboczne: odczyt systemu plików. Błędy: brak.
def has_local_campaign_data() -> bool:
    """Czy na dysku są foldery Wyniki_* (kampanie PL/DE)."""
    root = get_data_root()
    markers = (
        "Wyniki_Gdansk",
        "Wyniki_Warszawa",
        "Wyniki_Saalfeld",
        "Wyniki_Transport_PL",
    )
    return any((root / name).is_dir() for name in markers)


# >>> OPIS FUNKCJI: funkcja is_cloud_deployment
# Cel: rozpoznać hosting chmurowy (np. Streamlit Cloud) bez lokalnych wyników. Parametry: brak.
# Zwraca: bool — False przy KANBUD_FORCE_LOCAL in (1,true,yes); True przy KANBUD_CLOUD_HOST in (1,true,yes);
# inaczej True, gdy nie ma lokalnych danych kampanii (not has_local_campaign_data()).
# Efekty uboczne: odczyt env i systemu plików. Błędy: brak.
def is_cloud_deployment() -> bool:
    """Streamlit Cloud / hosting bez lokalnych Wyniki_*."""
    import os

    if os.environ.get("KANBUD_FORCE_LOCAL", "").strip() in ("1", "true", "yes"):
        return False
    if os.environ.get("KANBUD_CLOUD_HOST", "").strip() in ("1", "true", "yes"):
        return True
    return not has_local_campaign_data()


# >>> OPIS FUNKCJI: funkcja switzerland_wyniki_dir
# Cel: katalog wyników kampanii CH (legacy). Parametry: brak. Zwraca: Path —
# get_data_root()/Szwajcaria/Wyniki, a gdy nie istnieje i istnieje stary PROJECT_ROOT/Szwajcaria/Wyniki — ten stary.
# Efekty uboczne: odczyt systemu plików. Błędy: brak.
def switzerland_wyniki_dir() -> Path:
    """
    Folder wyników kampanii CH (cache, Excel).
    Szuka w KANBUD_DATA_DIR/Szwajcaria/Wyniki, potem w PROJECT_ROOT/Szwajcaria/Wyniki.
    """
    primary = get_data_root() / "Szwajcaria" / "Wyniki"
    legacy = PROJECT_ROOT / "Szwajcaria" / "Wyniki"
    if primary.exists() or not legacy.exists():
        return primary
    return legacy

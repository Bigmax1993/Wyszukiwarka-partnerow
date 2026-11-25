# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Uzupełnienie opisu modułu pl_spedycja_data_paths (komentarz; docstring poniżej opisuje drzewo katalogów).
#   Rola w pipeline: najwcześniejszy krok — ustala, gdzie scraper zapisuje cache JSON, Excel, log i kopie
#   wysłanych maili (Wyniki/, wyslane/); chroni przed zapisem cache/logu na zmapowany Google Drive.
#   Zależności: stdlib (os, pathlib). Wejście: katalog kampanii (Path), zmienna env KANBUD_DATA_DIR.
#   Wyjście: Path-e katalogów/plików, słowniki ścieżek, tekst/JSON diagnostyczny (CLI). Shim legacy:
#   campaign_data_paths.py.
# ============================================================
"""
Ścieżki wyników kampanii PL FAS / spedycja: cache JSON, Excel, log, ``wyslane/``.

=============================================================================
PO CO TEN MODUŁ
=============================================================================
Jedno źródło prawdy dla **lokalnych** ścieżek artefaktów scrapera
(``pl_fas_spedycja_scraper``) oraz diagnostyki „czy cache/log nie poszły
na Google Drive”.

Zapisuje się w drzewie kampanii (zwykle root repo)::

  Wyniki/pl_spedycja_cache.json      # stan pipeline / dedupe
  Wyniki/pl_spedycja_kontakte.xlsx   # Excel kontaktów (lokalna kopia)
  Wyniki/pl_spedycja_scraper.log     # log uruchomienia
  wyslane/                           # kopie .eml (puste przy B2B OFF)

=============================================================================
LOKALNIE VS GOOGLE DRIVE
=============================================================================
**Cache JSON i log NIGDY nie idą na Drive** przez ten moduł.
``resolve_data_root`` świadomie **ignoruje** ``KANBUD_GOOGLE_DRIVE_*``
i ścieżki typu „My Drive” — tylko:

  1. istniejący lokalny ``KANBUD_DATA_DIR``, albo
  2. ``campaign_dir`` (repo / workspace GHA).

Upload **końcowego** Excela na Drive robią osobne skrypty GHA
(``scripts/gdrive_upload_wyniki.py``, ``scripts/sync_week_single_excel_gdrive.py``)
do folderu ``GOOGLE_DRIVE_FAS_FOLDER_ID`` (secret ``GDRIVE_FOLDER_ID``).

``Wyniki/`` jest zwykle w ``.gitignore``; w GHA wychodzą jako artifact.

=============================================================================
STAŁE FOLDERU EXCELA
=============================================================================
Kanoniczne: ``GOOGLE_DRIVE_FAS_*`` (PL FAS / Forwarding Assistant).
Legacy:     ``GOOGLE_DRIVE_GU_*`` (= te same obiekty; stare importy).

Dawna nazwa pliku: ``campaign_data_paths.py`` (shim re-exportuje API).

CLI diagnostyczny::

  python pl_spedycja_data_paths.py .
  python pl_spedycja_data_paths.py . --basename pl_spedycja --apply-env
"""
from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# GOOGLE_DRIVE_FAS_FOLDER_ID / _URL
# ---------------------------------------------------------------------------
# PO CO: domyślny folder Drive na **końcowy** ``pl_spedycja_kontakte.xlsx``
#        (upload GHA — zwykle niedziela 09:00, cykl tygodniowy).
# NIE:   cache JSON, log, ``wyslane/``, załącznik PPTX (ten ma osobny plik
#        Drive w ``pl_fas_email_attachment``).
# SECRET: GHA ``GDRIVE_FOLDER_ID`` powinien mieć tę samą wartość co ID poniżej.
# DOCS:   ``docs/GOOGLE_DRIVE.md``
# CZYTA:  ``scripts/gdrive_upload_wyniki.py``, ``scripts/sync_week_single_excel_gdrive.py``,
#         testy unit/integration, ``debug_data_paths``.
GOOGLE_DRIVE_FAS_FOLDER_ID = "1bRCAqle6BS46YEw0fScq4P095LsJUSgL"
GOOGLE_DRIVE_FAS_FOLDER_URL = (
    f"https://drive.google.com/drive/folders/{GOOGLE_DRIVE_FAS_FOLDER_ID}?usp=drive_link"
)

# ---------------------------------------------------------------------------
# Aliasy legacy GOOGLE_DRIVE_GU_*
# ---------------------------------------------------------------------------
# PO CO: kompatybilność po rename GU → FAS (stare importy / skrypty / docs).
# WARTOŚĆ: ten sam string / URL co ``GOOGLE_DRIVE_FAS_*`` (identity alias).
# NOWY KOD: importuj wyłącznie ``GOOGLE_DRIVE_FAS_*``.
GOOGLE_DRIVE_GU_FOLDER_ID = GOOGLE_DRIVE_FAS_FOLDER_ID
GOOGLE_DRIVE_GU_FOLDER_URL = GOOGLE_DRIVE_FAS_FOLDER_URL


def resolve_data_root(campaign_dir: Path) -> Path:
    """
    Katalog danych kampanii: tu powstaną ``Wyniki/`` i ``wyslane/``.

    Priorytet
    ---------
    1. ``KANBUD_DATA_DIR`` — tylko jeśli to **istniejący katalog lokalny**
       (nie ustawiaj na zmapowany folder Google Drive / „My Drive”).
    2. ``campaign_dir`` — folder repozytorium kampanii (domyślnie root repo).

    Świadomie **bez**
    -----------------
    - ``KANBUD_GOOGLE_DRIVE_GU_PATH`` / ``KANBUD_GOOGLE_DRIVE_*``,
    - auto-wykrywania „Google Drive” / „Mój dysk” na dysku użytkownika.

    Cache i log mają żyć w repo (albo w jawnie wskazanym lokalnym katalogu),
    nie w chmurze — upload xlsx jest osobnym krokiem API Drive.
    """
    raw_data = (os.environ.get("KANBUD_DATA_DIR") or "").strip()
    if raw_data:
        p = Path(raw_data).expanduser().resolve()
        if p.is_dir():
            return p

    return Path(campaign_dir).resolve()


def wyniki_dir(data_root: Path) -> Path:
    """
    Podkatalog ``Wyniki/`` pod ``data_root``.

    Tu leżą: cache JSON, lokalny Excel kontaktów, log scrapera.
    Nazwy plików buduje ``campaign_output_paths`` z ``basename`` (np. ``pl_spedycja``).
    """
    return data_root / "Wyniki"


def wyslane_dir(data_root: Path) -> Path:
    """
    Podkatalog ``wyslane/`` — kopie wysłanych ``.eml``.

    Przy ``DISABLE_CONTRACTOR_EMAILS=1`` (B2B OFF) katalog zwykle pusty;
    ``mail_transport`` i tak oczekuje tej samej ścieżki co scraper
    (patrz ``apply_data_root_to_env``).
    """
    return data_root / "wyslane"


# >>> OPIS FUNKCJI: funkcja ensure_data_dirs
# Cel: utworzyć katalogi Wyniki/ i wyslane/ pod data_root. Parametry: data_root (Path).
# Zwraca: None. Efekty uboczne: mkdir(parents=True, exist_ok=True) — idempotentne, nie kasuje plików.
# Błędy: OSError (brak uprawnień, ścieżka-plik) nie jest łapany.
def ensure_data_dirs(data_root: Path) -> None:
    """
    Tworzy ``Wyniki/`` i ``wyslane/`` jeśli nie istnieją (``mkdir -p``).

    Bezpieczne do wielokrotnego wywołania; nie usuwa istniejących plików.
    """
    wyniki_dir(data_root).mkdir(parents=True, exist_ok=True)
    wyslane_dir(data_root).mkdir(parents=True, exist_ok=True)


def apply_data_root_to_env(data_root: Path) -> Path:
    """
    Ustawia ``KANBUD_DATA_DIR`` na lokalny root i tworzy podfoldery.

    PO CO
    -----
    Spina scraper z ``mail_transport.get_wyslane_dir`` / innymi helperami,
    które czytają wyłącznie env — ten sam ``data_root`` w całym procesie.

    Efekt uboczny: mutuje ``os.environ`` (jak produkcyjny start scrapera).
    Do czystego podglądu użyj ``debug_data_paths(..., apply_env=False)``.
    """
    root = data_root.resolve()
    os.environ["KANBUD_DATA_DIR"] = str(root)
    ensure_data_dirs(root)
    return root


def campaign_output_paths(campaign_dir: Path, basename: str) -> dict[str, Path]:
    """
    Buduje mapę **lokalnych** ścieżek wyjściowych (w repo / ``KANBUD_DATA_DIR``).

    Przebieg
    --------
    1. ``resolve_data_root(campaign_dir)``
    2. ``apply_data_root_to_env`` (ustawia env + mkdir)
    3. Zwraca słownik Path pod kluczami używanymi przez scrapera / send_excel.

    ``basename`` np. ``pl_spedycja`` → w ``Wyniki/``::

      pl_spedycja_kontakte.xlsx
      pl_spedycja_cache.json
      pl_spedycja_scraper.log

    Klucze zwracane: ``data_root``, ``output_dir``, ``output_file``,
    ``cache_file``, ``log_file``, ``wyslane_dir``.
    """
    root = apply_data_root_to_env(resolve_data_root(campaign_dir))
    out = wyniki_dir(root)
    return {
        "data_root": root,
        "output_dir": out,
        "output_file": out / f"{basename}_kontakte.xlsx",
        "cache_file": out / f"{basename}_cache.json",
        "log_file": out / f"{basename}_scraper.log",
        "wyslane_dir": wyslane_dir(root),
    }


def debug_data_paths(
    campaign_dir: Path | str | None = None,
    *,
    basename: str = "pl_spedycja",
    apply_env: bool = False,
) -> dict:
    """
    Diagnostyka ścieżek kampanii: gdzie pójdą cache/log/xlsx (lokalnie vs Drive).

    PO CO
    -----
    Szybki snapshot (JSON z CLI) potwierdzający, że:

    - JSON/log **nie** lecą na Google Drive przez ``resolve_data_root``,
    - folder uploadu Excela to ``GOOGLE_DRIVE_FAS_FOLDER_ID``,
    - widać, czy ``KANBUD_DATA_DIR`` / ``KANBUD_GOOGLE_DRIVE_FAS_PATH``
      (alias legacy ``KANBUD_GOOGLE_DRIVE_GU_PATH``) są ustawione —
      raportowane, ale **ignorowane** przy resolve
      (``drive_env_ignored_for_resolve: true``).

    ``apply_env``
    -------------
    - ``False`` (domyślnie) — **nie** mutuje ``KANBUD_DATA_DIR``, nie tworzy
      katalogów (bezpieczne w testach / samym podglądzie).
    - ``True`` — jak produkcja: ``campaign_output_paths`` + mkdir.

    Heurystyka ``looks_like_google_drive_path``: ostrzeżenie, jeśli ktoś
    wskazał ``KANBUD_DATA_DIR`` na ścieżkę z „My Drive” / „Mój dysk” itd.
    """
    camp = Path(campaign_dir) if campaign_dir else Path(__file__).resolve().parent
    camp = camp.resolve()

    env_data = (os.environ.get("KANBUD_DATA_DIR") or "").strip()
    # FAS / legacy GU — tylko do raportu; resolve_data_root ich nie używa.
    env_drive_fas = (os.environ.get("KANBUD_GOOGLE_DRIVE_FAS_PATH") or "").strip()
    env_drive_gu = (os.environ.get("KANBUD_GOOGLE_DRIVE_GU_PATH") or "").strip()
    env_drive = env_drive_fas or env_drive_gu
    root = resolve_data_root(camp)

    if apply_env:
        paths = {k: str(v) for k, v in campaign_output_paths(camp, basename).items()}
        root = Path(paths["data_root"])
    else:
        out = wyniki_dir(root)
        paths = {
            "data_root": str(root),
            "output_dir": str(out),
            "output_file": str(out / f"{basename}_kontakte.xlsx"),
            "cache_file": str(out / f"{basename}_cache.json"),
            "log_file": str(out / f"{basename}_scraper.log"),
            "wyslane_dir": str(wyslane_dir(root)),
        }

    root_s = str(root).lower()
    looks_like_drive = any(
        m in root_s
        for m in ("google drive", "my drive", "dyski współdzielone", "mój dysk")
    )

    cache_p = Path(paths["cache_file"])
    log_p = Path(paths["log_file"])
    xlsx_p = Path(paths["output_file"])

    return {
        "campaign_dir": str(camp),
        "basename": basename,
        "env": {
            "KANBUD_DATA_DIR": env_data or None,
            "KANBUD_GOOGLE_DRIVE_FAS_PATH": env_drive_fas or None,
            "KANBUD_GOOGLE_DRIVE_GU_PATH": env_drive_gu or None,
            "drive_env_ignored_for_resolve": True,
        },
        "resolved_data_root": str(root),
        "looks_like_google_drive_path": looks_like_drive,
        "cache_and_log_on_drive": False if not looks_like_drive else True,
        "paths": paths,
        "exists": {
            "data_root": root.is_dir(),
            "wyniki": wyniki_dir(root).is_dir(),
            "cache_file": cache_p.is_file(),
            "log_file": log_p.is_file(),
            "excel_file": xlsx_p.is_file(),
        },
        "excel_drive_upload": {
            "folder_id": GOOGLE_DRIVE_FAS_FOLDER_ID,
            "folder_url": GOOGLE_DRIVE_FAS_FOLDER_URL,
            "note": "Tylko końcowy xlsx (GHA nd 09:00) — nie cache/log",
        },
    }


def _cli_debug(argv: list[str] | None = None) -> int:
    """
    CLI: ``python pl_spedycja_data_paths.py [campaign_dir] [--basename pl_spedycja]``.

    Wypisuje JSON z ``debug_data_paths`` na stdout (UTF-8, ``ensure_ascii=False``).

    Argumenty
    ---------
    ``campaign_dir`` — folder kampanii / repo (domyślnie ``.``).
    ``--basename`` — prefiks plików w ``Wyniki/`` (domyślnie ``pl_spedycja``).
    ``--apply-env`` — jak scraper: ustaw ``KANBUD_DATA_DIR`` i utwórz katalogi.

    Zwraca ``0`` (sukces). Shim ``campaign_data_paths.py`` deleguje tu.
    """
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description=(
            "Debug lokalnych ścieżek Wyniki/ (pl_spedycja_data_paths). "
            "Kanoniczny folder Excela Drive: GOOGLE_DRIVE_FAS_FOLDER_ID."
        )
    )
    parser.add_argument(
        "campaign_dir",
        nargs="?",
        default=".",
        help="Folder kampanii / repo (domyślnie .)",
    )
    parser.add_argument(
        "--basename",
        default="pl_spedycja",
        help="Prefiks plików w Wyniki/ (domyślnie pl_spedycja)",
    )
    parser.add_argument(
        "--apply-env",
        action="store_true",
        help="Ustaw KANBUD_DATA_DIR i utwórz Wyniki/ (jak scraper)",
    )
    args = parser.parse_args(argv)
    payload = debug_data_paths(
        args.campaign_dir,
        basename=args.basename,
        apply_env=args.apply_env,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli_debug())

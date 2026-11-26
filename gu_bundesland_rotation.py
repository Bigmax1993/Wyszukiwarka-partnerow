# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Moduł: gu_bundesland_rotation — rotacja „jedno województwo na cykl discovery”.
#
# CO ROBI
#   Utrzymuje trwały stan rotacji (Wyniki/gu_bundesland_rotation.json): który region (klucz z
#   BUNDESLAND_CONFIG — w wersji PL są to województwa) jest aktualny, historię ostatnich uruchomień
#   (do 32 wpisów) i indeks następnego regionu. Nazwa pliku/stałych to dziedzictwo po Bundesländerach.
#
# ROLA W PIPELINE
#   Wywoływany przez run_scraper(rotate_bundesland=True) w pl_fas_spedycja_scraper (tryb rotacji;
#   nie dotyczy discovery_mode="emails_only" ani rebuild_from_cache): apply_rotation_to_module
#   zawęża konfigurację kampanii do jednego regionu przed discovery, a commit_rotation_after_run
#   przesuwa indeks dopiero po udanym przebiegu (z wystarczającą liczbą zweryfikowanych kontaktów).
#
# ZALEŻNOŚCI
#   pl_spedycja_keywords (BUNDESLAND_CONFIG, configure_campaign_bundeslaender); stdlib json, datetime,
#   pathlib, typing. Na imporcie wykonuje assert, że kolejność rotacji obejmuje DOKŁADNIE wszystkie
#   klucze BUNDESLAND_CONFIG (AssertionError przy niespójności słownika i listy).
#
# WEJŚCIE / WYJŚCIE
#   Wejście: katalog Wyniki/ (Path), obiekt modułu scrapera, stan (dict). Wyjście: nazwa regionu (str),
#   stan (dict), ścieżka pliku stanu (Path) oraz zapisany JSON {version, next_index, history}.
# ============================================================
"""
Rotacja Bundesländer — jeden land na cykl discovery (np. piątek).

Stan: Wyniki/gu_bundesland_rotation.json
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from pl_spedycja_keywords import BUNDESLAND_CONFIG, configure_campaign_bundeslaender

# Kolejność rotacji 1 woj./cykl — start od Dolnośląskiego (jak pl_fas_spedycja.json).
# Po Mazowieckim: Zachodniopomorskie → Lubuskie → Wielkopolskie.
BUNDESLAND_ROTATION_ORDER: tuple[str, ...] = (
    "Dolnoslaskie",
    "Mazowieckie",
    "Zachodniopomorskie",
    "Lubuskie",
    "Wielkopolskie",
    "Lodzkie",
    "Slaskie",
    "Malopolskie",
    "Pomorskie",
    "Kujawsko-Pomorskie",
    "Warminsko-Mazurskie",
    "Podlaskie",
    "Lubelskie",
    "Podkarpackie",
    "Swietokrzyskie",
    "Opolskie",
)
assert set(BUNDESLAND_ROTATION_ORDER) == set(BUNDESLAND_CONFIG.keys())

STATE_FILENAME = "gu_bundesland_rotation.json"
DEFAULT_MIN_CONTACTS_SINGLE_LAND = 20


# >>> OPIS FUNKCJI: funkcja rotation_state_path
# Cel: wyznaczyć ścieżkę pliku stanu rotacji. Parametry: wyniki_dir (Path) — katalog Wyniki/.
# Zwraca: Path = wyniki_dir / "gu_bundesland_rotation.json". Efekty uboczne/błędy: brak (nie dotyka dysku).
def rotation_state_path(wyniki_dir: Path) -> Path:
    """Ścieżka pliku stanu rotacji w katalogu Wyniki/."""
    return wyniki_dir / STATE_FILENAME


# >>> OPIS FUNKCJI: funkcja _empty_state
# Cel: zbudować domyślny, pusty stan rotacji. Parametry: brak.
# Zwraca: dict {"version": 1, "next_index": 0, "history": []} (nowy obiekt przy każdym wywołaniu).
# Efekty uboczne/błędy: brak.
def _empty_state() -> dict[str, Any]:
    """Pusty stan rotacji (start od indeksu 0)."""
    return {"version": 1, "next_index": 0, "history": []}


# >>> OPIS FUNKCJI: funkcja load_rotation_state
# Cel: wczytać stan rotacji z dysku, zawsze zwracając poprawną strukturę.
# Parametry: path (Path) — plik JSON stanu.
# Zwraca: dict ze stanem; brakujące klucze version/next_index/history są uzupełniane (setdefault).
#   Gdy plik nie istnieje, nie jest obiektem JSON, jest uszkodzony lub nieczytelny — zwraca _empty_state().
# Efekty uboczne: odczyt pliku (UTF-8). Błędy: OSError i JSONDecodeError są łapane i ignorowane (fallback).
def load_rotation_state(path: Path) -> dict[str, Any]:
    """Wczytaj stan rotacji z JSON (lub pusty przy braku/uszkodzeniu)."""
    if not path.exists():
        return _empty_state()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return _empty_state()
        data.setdefault("version", 1)
        data.setdefault("next_index", 0)
        data.setdefault("history", [])
        return data
    except (OSError, json.JSONDecodeError):
        return _empty_state()


# >>> OPIS FUNKCJI: funkcja save_rotation_state
# Cel: zapisać stan rotacji do JSON.
# Parametry: path (Path) — plik docelowy; state (dict) — stan do zapisu.
# Zwraca: None. Efekty uboczne: tworzy katalogi nadrzędne (mkdir parents) i nadpisuje plik
#   (UTF-8, ensure_ascii=False, wcięcie 2). Błędy: OSError/TypeError nie są łapane — propagują się.
def save_rotation_state(path: Path, state: dict[str, Any]) -> None:
    """Zapisz stan rotacji do JSON (tworzy katalog nadrzędny)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# >>> OPIS FUNKCJI: funkcja peek_next_bundesland
# Cel: odczytać region wskazywany przez next_index bez przesuwania indeksu.
# Parametry: state (dict|None) — stan; None → pusty stan (region o indeksie 0, Dolnoslaskie).
# Zwraca: str — nazwa regionu z BUNDESLAND_ROTATION_ORDER; indeks brany modulo długości listy.
# Efekty uboczne: brak. Błędy: ValueError/TypeError, gdy next_index nie da się zrzutować na int.
def peek_next_bundesland(state: dict[str, Any] | None = None) -> str:
    """Podgląd bieżącego województwa bez przesuwania indeksu."""
    st = state if state is not None else _empty_state()
    idx = int(st.get("next_index", 0)) % len(BUNDESLAND_ROTATION_ORDER)
    return BUNDESLAND_ROTATION_ORDER[idx]


# >>> OPIS FUNKCJI: funkcja apply_rotation_to_module
# Cel: ustawić scraper na bieżący region rotacji (bez przesunięcia indeksu).
# Parametry: module — moduł scrapera (konfigurowany przez configure_campaign_bundeslaender);
#   wyniki_dir (Path); min_contacts (keyword-only, int, domyślnie 20) — cel kontaktów dla jednego regionu,
#   ustawiany jako module.MIN_CONTACTS_TARGET, jeśli taki atrybut istnieje; max_discovery_terms
#   (keyword-only, int, domyślnie 120) — limit fraz discovery.
# Zwraca: krotkę (land: str, state: dict, state_path: Path) — do późniejszego commit_rotation_after_run.
# Efekty uboczne: odczyt pliku stanu; mutacja konfiguracji modułu scrapera (lista regionów, termy,
#   MIN_CONTACTS_TARGET). Błędy: te z load_rotation_state są wyciszone; błędy configure_* propagują się.
def apply_rotation_to_module(
    module,
    wyniki_dir: Path,
    *,
    min_contacts: int = DEFAULT_MIN_CONTACTS_SINGLE_LAND,
    max_discovery_terms: int = 120,
) -> tuple[str, dict[str, Any], Path]:
    """Wybiera bieżący land (bez przesunięcia indeksu) i konfiguruje scraper."""
    state_path = rotation_state_path(wyniki_dir)
    state = load_rotation_state(state_path)
    land = peek_next_bundesland(state)
    configure_campaign_bundeslaender(
        module, [land], max_discovery_terms=max_discovery_terms
    )
    if hasattr(module, "MIN_CONTACTS_TARGET"):
        module.MIN_CONTACTS_TARGET = min_contacts
    return land, state, state_path


# >>> OPIS FUNKCJI: funkcja commit_rotation_after_run
# Cel: po udanym discovery zapisać wpis historii i przesunąć rotację na następny region.
# Parametry: state_path (Path); state (dict, mutowany); land (str) — region użyty w przebiegu
#   (jeśli różni się od regionu pod next_index, zostaje nadpisany wartością z indeksu — źródłem prawdy
#   jest indeks); run_date (keyword-only, date|None) — data wpisu (domyślnie dziś).
# Zwraca: str — nazwa NASTĘPNEGO regionu po przesunięciu.
# Efekty uboczne: dopisuje do state["history"] {land, index, at} (ucina do 32 ostatnich), ustawia
#   state["next_index"] = (idx+1) % N i zapisuje plik (save_rotation_state).
# Błędy: nie łapie wyjątków I/O ani konwersji int — propagują się do wywołującego.
def commit_rotation_after_run(
    state_path: Path,
    state: dict[str, Any],
    land: str,
    *,
    run_date: date | None = None,
) -> str:
    """Po udanym discovery przesuwa rotację na następny land (≥20 retail_verified)."""
    idx = int(state.get("next_index", 0)) % len(BUNDESLAND_ROTATION_ORDER)
    if BUNDESLAND_ROTATION_ORDER[idx] != land:
        land = BUNDESLAND_ROTATION_ORDER[idx]
    history = list(state.get("history") or [])
    history.append(
        {
            "land": land,
            "index": idx,
            "at": (run_date or date.today()).isoformat(),
        }
    )
    state["history"] = history[-32:]
    state["next_index"] = (idx + 1) % len(BUNDESLAND_ROTATION_ORDER)
    save_rotation_state(state_path, state)
    return peek_next_bundesland(state)


# >>> OPIS FUNKCJI: funkcja format_rotation_status
# Cel: zbudować czytelny tekst statusu rotacji do logu / CLI.
# Parametry: wyniki_dir (Path). Zwraca: str w formacie
#   "Bieżący land (ten tydzień): X | następny po zakończeniu: Y | indeks=i/N".
# Efekty uboczne: odczyt pliku stanu. Błędy: uszkodzony/brakujący plik → status liczony z pustego stanu.
# Uwaga: „następny” liczony jest jako element po indeksie next_index+1 (kolejność jak w tablicy rotacji).
def format_rotation_status(wyniki_dir: Path) -> str:
    """Krótki status tekstowy: bieżące i następne województwo rotacji."""
    state_path = rotation_state_path(wyniki_dir)
    state = load_rotation_state(state_path)
    current = peek_next_bundesland(state)
    nxt_idx = int(state.get("next_index", 0))
    nxt = BUNDESLAND_ROTATION_ORDER[(nxt_idx + 1) % len(BUNDESLAND_ROTATION_ORDER)]
    return (
        f"Bieżący land (ten tydzień): {current} | "
        f"następny po zakończeniu: {nxt} | "
        f"indeks={nxt_idx}/{len(BUNDESLAND_ROTATION_ORDER)}"
    )

# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Uzupełnienie opisu modułu scraper_runtime_limit (komentarz — docstring poniżej jest pełny).
#   Zależności: tylko stdlib (os, time, typing). Stan globalny: _SCRAPER_RUN_STARTED_AT (monotonic).
#   Wejście: zmienna środowiskowa SCRAPER_MAX_RUNTIME_SECONDS (odczytywana RAZ przy imporcie).
#   Wyjście: funkcje zwracają bool/float|None; request_stop_on_runtime_limit sygnalizuje stop pętlom
#   scrapera bez rzucania wyjątku (cache i wiersze zostają zapisane w normalnym toku zamknięcia).
#   Rola: zabezpieczenie wall-clock w discovery (Serper/Claude) w CI i na Raspberry Pi.
# ============================================================
"""
Twardy limit czasu działania scrapera (``SCRAPER_MAX_RUNTIME_SECONDS``).

Po co: discovery Serper/Claude może ciągnąć się godzinami; env ustawia
górny limit wall-clock (monotonic), a pętle scrapera periodicznie wołają
``request_stop_on_runtime_limit`` i czysto przerywają run (cache zostaje).

``0`` / brak env = limit wyłączony. Nazwa modułu bez zmian (import scrapera).
"""
from __future__ import annotations

import os
import time
from typing import Callable

# Start bieżącego runu (monotonic). ``None`` = zegar nieaktywny / limit OFF.
_SCRAPER_RUN_STARTED_AT: float | None = None


def _parse_max_runtime_seconds() -> int:
    """
    Czyta ``SCRAPER_MAX_RUNTIME_SECONDS`` z env → int ≥ 0.

    Pusty / nieparsowalny ciąg → ``0`` (brak limitu). Ujemne wartości
    są obcinane do zera, żeby nie odwracać logiki porównania.
    """
    raw = (os.environ.get("SCRAPER_MAX_RUNTIME_SECONDS") or "").strip()
    if not raw:
        return 0
    try:
        return max(0, int(raw))
    except ValueError:
        return 0


# Snapshot limitu przy imporcie modułu (jak inne flagi scrapera z env).
# Zmiana env w trakcie procesu wymaga ponownego importu / ręcznego setu.
SCRAPER_MAX_RUNTIME_SECONDS = _parse_max_runtime_seconds()


def start_scraper_runtime_clock() -> None:
    """
    Startuje zegar monotonic na początku ``run_scraper`` / discovery.

    Przy limicie ``≤ 0`` czyści stan (zegar OFF) — kolejne
    ``is_scraper_runtime_limit_reached`` zawsze zwracają ``False``.
    """
    global _SCRAPER_RUN_STARTED_AT
    if SCRAPER_MAX_RUNTIME_SECONDS <= 0:
        _SCRAPER_RUN_STARTED_AT = None
        return
    _SCRAPER_RUN_STARTED_AT = time.monotonic()


# >>> OPIS FUNKCJI: funkcja scraper_runtime_elapsed_seconds
# Cel: podać czas, który upłynął od startu zegara scrapera.
# Parametry: brak. Zwraca: float (sekundy, time.monotonic) lub None gdy zegar nie wystartował /
#   limit wyłączony. Efekty uboczne: brak (odczyt zegara). Błędy: brak.
def scraper_runtime_elapsed_seconds() -> float | None:
    """
    Sekundy od ``start_scraper_runtime_clock`` (monotonic).

    ``None`` gdy zegar nie został uruchomiony (limit OFF albo brak startu).
    """
    if _SCRAPER_RUN_STARTED_AT is None:
        return None
    return time.monotonic() - _SCRAPER_RUN_STARTED_AT


# >>> OPIS FUNKCJI: funkcja is_scraper_runtime_limit_reached
# Cel: sprawdzić, czy przekroczono limit SCRAPER_MAX_RUNTIME_SECONDS.
# Parametry: brak. Zwraca: bool — False gdy limit <= 0, zegar nieaktywny lub elapsed < limit;
#   True gdy elapsed >= limit. Efekty uboczne: brak. Błędy: brak.
def is_scraper_runtime_limit_reached() -> bool:
    """
    Czy upłynął limit ``SCRAPER_MAX_RUNTIME_SECONDS`` od startu zegara.

    ``False`` gdy limit wyłączony, zegar nieaktywny albo elapsed < limit.
    """
    if SCRAPER_MAX_RUNTIME_SECONDS <= 0 or _SCRAPER_RUN_STARTED_AT is None:
        return False
    elapsed = scraper_runtime_elapsed_seconds()
    return elapsed is not None and elapsed >= SCRAPER_MAX_RUNTIME_SECONDS


def request_stop_on_runtime_limit(
    logger,
    *,
    console_step_fn: Callable[[str], None] | None = None,
) -> bool:
    """
    Hook pętli scrapera: przy przekroczonym limicie loguje i sygnalizuje stop.

    Zwraca ``True`` = caller powinien przerwać discovery / run (nie rzuca
    wyjątku). ``console_step_fn`` — opcjonalny UI/konsola scrapera;
    ``logger.warning`` gdy logger podany.
    """
    if not is_scraper_runtime_limit_reached():
        return False
    hours = SCRAPER_MAX_RUNTIME_SECONDS // 3600
    msg = (
        f"Limit czasu scrapera ({SCRAPER_MAX_RUNTIME_SECONDS}s = {hours}h) — zatrzymanie"
    )
    if console_step_fn:
        console_step_fn(msg)
    if logger:
        logger.warning(msg)
    return True


# >>> OPIS FUNKCJI: funkcja reset_scraper_runtime_clock_for_tests
# Cel: wyzerować globalny znacznik startu zegara (używane w testach jednostkowych).
# Parametry: brak. Zwraca: None.
# Efekty uboczne: ustawia globalne _SCRAPER_RUN_STARTED_AT = None (nie zmienia limitu ze snapshotu env).
# Błędy: brak.
def reset_scraper_runtime_clock_for_tests() -> None:
    """
    Czyści globalny start zegara — tylko pod testy jednostkowe.

    Nie zmienia ``SCRAPER_MAX_RUNTIME_SECONDS`` (to snapshot z env przy imporcie).
    """
    global _SCRAPER_RUN_STARTED_AT
    _SCRAPER_RUN_STARTED_AT = None

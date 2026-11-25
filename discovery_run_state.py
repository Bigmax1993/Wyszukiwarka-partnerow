# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Moduł: discovery_run_state — zapis stanu zakończonego przebiegu discovery w cache JSON.
#
# CO ROBI
#   Po przebiegu Serper-only zapisuje w cache["discovery_run_state"] krótkie podsumowanie:
#   data kampanii, liczba zużytych zapytań Serper, czy budżet Serper wyczerpany, czy osiągnięto
#   cel nowych firm oraz liczba nowych wierszy. Drugi helper odczytuje to podsumowanie.
#
# ROLA W PIPELINE
#   Wywoływany z run_scraper() (blok finally) w pl_fas_spedycja_scraper.py — dzięki temu
#   kolejne uruchomienia lub skrypty zewnętrzne mogą odczytać, czy poprzedni etap zakończył się
#   wyczerpaniem limitu Serper czy osiągnięciem celu. Zapis następuje tylko gdy serper_only i
#   tryb nie jest emails_only ani rebuild_from_cache.
#
# ZALEŻNOŚCI
#   Tylko biblioteka standardowa (typing.Any). Wszystkie funkcje stanu scrapera są przekazywane
#   jako argumenty (wstrzykiwanie zależności), więc moduł nie importuje scrapera (brak cykli).
#
# WEJŚCIE / WYJŚCIE
#   record_discovery_run_state(...) modyfikuje przekazany słownik cache w miejscu (zwraca None).
#   discovery_run_state_summary(cache) zwraca kopię słownika stanu (pusty dict, gdy brak).
# ============================================================
"""Stan discovery (Serper / cel) — zapis po zakonczeniu piatkowego discovery."""
from __future__ import annotations

from typing import Any


# >>> OPIS FUNKCJI: funkcja record_discovery_run_state
# Cel: zapisać do cache["discovery_run_state"] wynik discovery w trybie serper_only.
# Parametry (wszystkie keyword-only poza cache):
#   cache — słownik cache scrapera (mutowany); musi być dict-em; klucz "serper_daily" opcjonalny.
#   all_rows — lista wierszy pipeline (przekazywana do discovery_target_reached_fn).
#   total_new_rows — ile NOWYCH firm dodano w tym przebiegu.
#   serper_only — jeśli False funkcja kończy działanie bez zapisu (return).
#   rotate_mode — flaga trybu rotacji Bundeslandów/regionów (przekazywana dalej).
#   campaign_today — data kampanii ISO (YYYY-MM-DD) będąca kluczem w cache["serper_daily"].
#   serper_daily_limit, serper_discovery_reserve — limit dzienny i rezerwa (do progu wyczerpania).
#   is_serper_unlimited — True => exhausted zawsze False.
#   is_serper_limit_reached_today_fn, is_serper_api_exhausted_fn — callbacki (cache)->bool.
#   discovery_target_reached_fn — callback oceniający osiągnięcie celu (all_rows, total_new_rows=...,
#   rotate_mode=..., serper_only=True).
# Zwraca: None.
# Efekty uboczne: nadpisuje cache["discovery_run_state"] słownikiem {campaign_date, serper_used,
# serper_exhausted, target_reached, total_new_rows}. exhausted = limit dzienny osiągnięty LUB API
# wyczerpane LUB used >= max(0, limit - rezerwa) (chyba że unlimited).
# Błędy: brak try/except — wyjątki z callbacków lub rzutowania int() propagują się do wywołującego
# (run_scraper wywołuje to w finally, więc błąd tu mógłby przerwać zapis końcowy).
def record_discovery_run_state(
    cache: dict,
    *,
    all_rows: list,
    total_new_rows: int,
    serper_only: bool,
    rotate_mode: bool,
    campaign_today: str,
    serper_daily_limit: int,
    serper_discovery_reserve: int,
    is_serper_unlimited: bool,
    is_serper_limit_reached_today_fn,
    is_serper_api_exhausted_fn,
    discovery_target_reached_fn,
) -> None:
    if not serper_only:
        return
    used = int((cache.get("serper_daily") or {}).get(campaign_today, 0))
    if is_serper_unlimited:
        exhausted = False
    else:
        exhausted = (
            bool(is_serper_limit_reached_today_fn(cache))
            or bool(is_serper_api_exhausted_fn(cache))
            or used >= max(0, serper_daily_limit - serper_discovery_reserve)
        )
    target = discovery_target_reached_fn(
        all_rows,
        total_new_rows=total_new_rows,
        rotate_mode=rotate_mode,
        serper_only=True,
    )
    cache["discovery_run_state"] = {
        "campaign_date": campaign_today,
        "serper_used": used,
        "serper_exhausted": exhausted,
        "target_reached": target,
        "total_new_rows": int(total_new_rows),
    }


# >>> OPIS FUNKCJI: funkcja discovery_run_state_summary
# Cel: odczytać zapisany stan ostatniego discovery z cache.
# Parametry: cache (dict) — cache scrapera.
# Zwraca: dict — płytka KOPIA cache["discovery_run_state"] albo pusty słownik, gdy klucza brak lub jest pusty.
# Efekty uboczne: brak (nie modyfikuje cache).
# Błędy: brak własnej obsługi; przy cache nie będącym dict wystąpi AttributeError.
def discovery_run_state_summary(cache: dict) -> dict[str, Any]:
    return dict(cache.get("discovery_run_state") or {})

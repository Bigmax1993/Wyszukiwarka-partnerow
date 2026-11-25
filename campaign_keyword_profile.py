# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Moduł: campaign_keyword_profile — wspólny „profil słów kluczowych” kampanii PL spedycja (FAS).
#
# CO ROBI
#   Udostępnia krótkie, czytelne PRÓBKI list słów kluczowych (role spedytora, usługi
#   transportowe, segmenty FTL/LTL/ADR, markery małej i dużej firmy, negatywy) oraz
#   stały zbiór ról odrzucanych w werdykcie LLM (REJECT_PRIMARY_ROLES). Próbki są
#   wstrzykiwane do promptów Claude (claude_prompts.py) tak, aby model widział te same
#   sygnały co reguły tekstowe w pl_spedycja_filter.py.
#
# ROLA W PIPELINE
#   Etap „Claude verify / discovery terms / row cleanup”: moduł jest warstwą pośrednią
#   między słownikami (pl_spedycja_keywords, pl_spedycja_filter) a budową promptów.
#   Nie wykonuje żadnych zapytań sieciowych i nie ma stanu.
#
# ZALEŻNOŚCI
#   - pl_spedycja_keywords: SERPER_NEGATIVE_TERMS, SIMPLE_TERM_TEMPLATES, TERM_TEMPLATES.
#   - pl_spedycja_filter: COURIER_REJECT_MARKERS, FORWARDER_ROLE_MARKERS,
#     IRRELEVANT_ROLE_MARKERS, TRANSPORT_SEGMENT_MARKERS, TRANSPORT_SERVICE_MARKERS.
#   Importowany przez: claude_prompts.py, page_verify.py (REJECT_PRIMARY_ROLES) i testy.
#
# CO PRZYJMUJE / ZWRACA
#   Stałe modułu: REJECT_PRIMARY_ROLES (frozenset[str]) oraz SERPER_TEMPLATE_PATTERNS
#   (tuple[str, ...] — unikalne szablony fraz w kolejności SIMPLE, potem TERM).
#   Funkcje *_sample(max_items=...) zwracają list[str] o długości <= max_items.
#
# UWAGA O NAZEWNICTWIE
#   Nazwy funkcji (gu_*, retail_*) są dziedzictwem po kampanii GU/Filialbau; semantycznie
#   dotyczą teraz spedycji (rola spedytora, segmenty transportu). Nie zmieniono ich,
#   żeby nie łamać importów w innych modułach i testach.
# ============================================================
"""
Wspólny słownik kampanii PL spedycja — używany przez Serper, regex i Claude.
"""
from __future__ import annotations

from pl_spedycja_keywords import (
    SERPER_NEGATIVE_TERMS,
    SIMPLE_TERM_TEMPLATES,
    TERM_TEMPLATES,
)
from pl_spedycja_filter import (
    COURIER_REJECT_MARKERS,
    FORWARDER_ROLE_MARKERS,
    IRRELEVANT_ROLE_MARKERS,
    TRANSPORT_SEGMENT_MARKERS,
    TRANSPORT_SERVICE_MARKERS,
)

# Role odrzucane w werdykcie LLM (primary_role)
REJECT_PRIMARY_ROLES = frozenset(
    {
        "Kurier",
        "GieldaFrachtowa",
        "PortalOgloszeniowy",
        "MediaLogistyczne",
        "TylkoFlotaWlasna",
        "Producent",
        "HR",
        "Urzad",
        "Inne",
    }
)

SERPER_TEMPLATE_PATTERNS: tuple[str, ...] = tuple(
    dict.fromkeys((*SIMPLE_TERM_TEMPLATES, *TERM_TEMPLATES))
)


# >>> OPIS FUNKCJI: funkcja gu_required_keywords_sample
# Cel: zwrócić próbkę markerów ROLI SPEDYTORA (legacy nazwa „gu_required” = markery wymagane).
# Parametry: max_items (keyword-only, int, domyślnie 12) — maksymalna liczba zwracanych pozycji.
# Zwraca: list[str] — pierwsze max_items elementów FORWARDER_ROLE_MARKERS w kolejności źródłowej.
# Efekty uboczne: brak (czysta funkcja, bez I/O).
# Błędy: nie obsługuje i nie rzuca własnych wyjątków; przy max_items<=0 zwróci pustą listę
# (wycinek [:0]); przy ujemnym max_items zadziała semantyka wycinka Pythona.
def gu_required_keywords_sample(*, max_items: int = 12) -> list[str]:
    """Próbka markerów roli spedytora (prompt / Serper sample)."""
    return list(FORWARDER_ROLE_MARKERS)[:max_items]


# >>> OPIS FUNKCJI: funkcja retail_context_keywords_sample
# Cel: zbudować próbkę słów „kontekstu oferty” = markery roli spedytora + usługi transportowe,
# bez duplikatów (porównanie po lower().strip()), z zachowaniem kolejności grup.
# Parametry: max_items (keyword-only, int, domyślnie 16) — limit długości wyniku.
# Zwraca: list[str] — pozycje w oryginalnej pisowni (po strip), unikalne case-insensitive.
# Efekty uboczne: brak. Zmienia tylko lokalne struktury (seen/out).
# Błędy: puste/białe elementy źródłowe są pomijane; nie ma try/except — wyjątek wystąpiłby
# tylko gdyby źródło zawierało elementy nie-tekstowe.
def retail_context_keywords_sample(*, max_items: int = 16) -> list[str]:
    """Próbka słów kontekstu oferty (rola + usługi transportu)."""
    seen: set[str] = set()
    out: list[str] = []
    for group in (
        FORWARDER_ROLE_MARKERS,
        TRANSPORT_SERVICE_MARKERS,
    ):
        for item in group:
            key = item.strip().lower()
            if key and key not in seen:
                seen.add(key)
                out.append(item.strip())
            if len(out) >= max_items:
                return out
    return out


# >>> OPIS FUNKCJI: funkcja retail_chain_keywords_sample
# Cel: próbka SEGMENTÓW TRANSPORTU (FTL/LTL/ADR/…); nazwa „retail_chain” to relikt po sieciach
# handlowych — w prompcie pełni rolę listy „wymaganych segmentów”.
# Parametry: max_items (keyword-only, int, domyślnie 12).
# Zwraca: list[str] — pierwsze max_items z TRANSPORT_SEGMENT_MARKERS.
# Efekty uboczne: brak. Błędy: brak własnej obsługi.
def retail_chain_keywords_sample(*, max_items: int = 12) -> list[str]:
    """Próbka segmentów transportu (FTL/LTL/ADR/… — legacy nazwa chain)."""
    return list(TRANSPORT_SEGMENT_MARKERS)[:max_items]


# >>> OPIS FUNKCJI: funkcja small_company_markers_sample
# Cel: zwrócić zakodowaną na stałe listę przykładowych fraz świadczących o MAŁEJ/LOKALNEJ firmie
# spedycyjnej (np. „firma rodzinna”, „od lat na rynku”, „właściciel”) — trafia do promptu jako
# wskazówka dla pola is_small_firm.
# Parametry: max_items (keyword-only, int, domyślnie 10).
# Zwraca: list[str] — wycinek stałej listy (max 10 pozycji istnieje w źródle).
# Efekty uboczne: brak. Błędy: brak własnej obsługi.
def small_company_markers_sample(*, max_items: int = 10) -> list[str]:
    """Przykładowe markery małej/lokalnej firmy spedycyjnej."""
    return [
        "firma rodzinna",
        "spedycja lokalna",
        "biuro w",
        "od lat na rynku",
        "właściciel",
        "wlasciciel",
        "mała firma",
        "mala firma",
        "polska spedycja",
        "regionalnie",
    ][:max_items]


# >>> OPIS FUNKCJI: funkcja large_company_markers_sample
# Cel: zwrócić przykładowe nazwy/markery DUŻYCH graczy i holdingów (Raben, DB Schenker, DHL, DPD,
# InPost, Kuehne+Nagel, DSV, …) używane jako negatywny sygnał ICP w prompcie weryfikacji.
# Parametry: max_items (keyword-only, int, domyślnie 14).
# Zwraca: list[str] — wycinek stałej listy.
# Efekty uboczne: brak. Błędy: brak własnej obsługi.
def large_company_markers_sample(*, max_items: int = 14) -> list[str]:
    """Przykładowe markery dużych graczy / holdingu (negatyw ICP soft)."""
    return [
        "Raben",
        "DB Schenker",
        "Schenker",
        "DHL",
        "DPD",
        "InPost",
        "GEODIS",
        "Kuehne",
        "Kuehne+Nagel",
        "DSV",
        "PEKAES",
        "Rohlig",
        "FM Logistic",
        "holding",
    ][:max_items]


# >>> OPIS FUNKCJI: funkcja negative_keywords_sample
# Cel: złożyć próbkę NEGATYWÓW (role nieistotne, markery kurierskie, wybrane SERPER_NEGATIVE_TERMS)
# bez duplikatów case-insensitive; używana w promptach jako „odrzuć, jeśli dominuje”.
# Parametry: max_items (keyword-only, int, domyślnie 14) — wynik jest ucinany (break) po osiągnięciu limitu.
# Zwraca: list[str] — kolejność: IRRELEVANT_ROLE_MARKERS, COURIER_REJECT_MARKERS, pierwsze 20
# z SERPER_NEGATIVE_TERMS.
# Efekty uboczne: brak. Błędy: puste elementy są pomijane; brak try/except.
def negative_keywords_sample(*, max_items: int = 14) -> list[str]:
    """Próbka negatywów Serper/ICP (kurier, giełda, nieistotne role)."""
    seen: set[str] = set()
    out: list[str] = []
    for item in (
        *IRRELEVANT_ROLE_MARKERS,
        *COURIER_REJECT_MARKERS,
        *SERPER_NEGATIVE_TERMS[:20],
    ):
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(item.strip())
        if len(out) >= max_items:
            break
    return out

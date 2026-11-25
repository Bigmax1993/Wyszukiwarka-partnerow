# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Moduł: claude_discovery_terms — generowanie dodatkowych fraz Serper przez Claude (Haiku).
#
# CO ROBI
#   Gdy gotowe szablony fraz dały za mało wyników, prosi Claude (tier „fast”) o dodatkowe frazy
#   wyszukiwania dla wskazanych województw/miast, parsuje odpowiedź (linie, numeracja), WALIDUJE każdą
#   frazę względem ICP PL spedycji (długość 12–55 znaków, rola spedytora, segment FTL/LTL/ADR…, brak
#   negatywów Serper, brak „legacy DE” typu bauunternehmen/filialbau) i buforuje wynik w cache
#   (klucz claude_discovery_terms → województwo, z datą i terminem ważności).
#
# ROLA W PIPELINE
#   Etap discovery (przed zapytaniami Serper); aktywny tylko, gdy ENABLE_CLAUDE_DISCOVERY_TERMS=True
#   (domyślnie False w scraper_web_config). Każda przepuszczona fraza jest bezpieczna dla filtra.
#
# ZALEŻNOŚCI
#   claude_prompts.build_discovery_terms_prompt, claude_client.claude_generate_text,
#   pl_spedycja_keywords (BUNDESLAND_CONFIG, RETAIL_CHAINS_ROTATION jako TRANSPORT_SEGMENTS,
#   SERPER_NEGATIVE_TERMS), pl_spedycja_filter.is_forwarder_role, scraper_env.get_anthropic_api_key.
#
# WEJŚCIE / WYJŚCIE
#   Wejście: cache (dict), logger, lista województw, parametry (liczba fraz, dni cache, wykluczenia).
#   Wyjście: list[str] zwalidowanych fraz (max terms_requested) — pusta lista przy błędzie/braku klucza.
# ============================================================
"""Claude Haiku: generowanie fraz Serper (uzupełnienie) gdy szablony dały za mało wyników."""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from claude_prompts import build_discovery_terms_prompt as _build_discovery_terms_prompt
from claude_client import claude_generate_text
from pl_spedycja_keywords import (
    BUNDESLAND_CONFIG,
    RETAIL_CHAINS_ROTATION as TRANSPORT_SEGMENTS,
    SERPER_NEGATIVE_TERMS,
)
from pl_spedycja_filter import is_forwarder_role
from scraper_env import get_anthropic_api_key

DISCOVERY_MAX_TERM_LEN = 55
DISCOVERY_MIN_TERM_LEN = 12
# Fallback gdy lista województw/regionów pusta (prompt + klucz cache).
DEFAULT_DISCOVERY_LAND = "Polska"
# Higiena: Claude czasem dokłada stare DE GU — nie do fraz Serper PL FAS.
_LEGACY_DE_DISCOVERY_MARKERS = (
    "bauunternehmen",
    "filialbau",
    "generalunternehmer",
    "general-unternehmer",
)
_PARSE_LINE_RE = re.compile(r"^\s*(?:\d+[\.\)]\s*)?(.+?)\s*$")


# >>> OPIS FUNKCJI: funkcja parse_discovery_term_lines
# Cel: wyciągnąć listę fraz z surowej odpowiedzi modelu (jedna fraza na linię, opcjonalna numeracja "1." / "1)").
# Parametry: text (str|None) — odpowiedź Claude.
# Zwraca: list[str] — unikalne frazy (kolejność zachowana), bez cudzysłowów brzegowych; linie puste oraz
#   zaczynające się od "{" lub "[" (JSON) są pomijane.
# Efekty uboczne/błędy: brak (czysta funkcja).
def parse_discovery_term_lines(text: str) -> list[str]:
    """Wyciągnij listę fraz z odpowiedzi Claude (linie / numeracja)."""
    lines: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("{") or line.startswith("["):
            continue
        m = _PARSE_LINE_RE.match(line)
        candidate = (m.group(1) if m else line).strip().strip('"').strip("'")
        if candidate and candidate not in lines:
            lines.append(candidate)
    return lines


# >>> OPIS FUNKCJI: funkcja validate_discovery_term
# Cel: sprawdzić, czy fraza Serper nadaje się do kampanii PL spedycja (patrz lista kroków w docstringu).
# Parametry: term (str|None).
# Zwraca: bool — True tylko gdy fraza przejdzie wszystkie 5 testów: długość, is_forwarder_role,
#   obecność segmentu transportu, brak negatywów (tylko >= 4 znaków) oraz brak markerów legacy DE.
# Efekty uboczne/błędy: brak.
def validate_discovery_term(term: str) -> bool:
    """
    Czy fraza Serper pasuje do ICP PL spedycja (FAS).

    Rdzeń (kolejność):
      1. długość DISCOVERY_MIN/MAX_TERM_LEN
      2. rola spedytora — ``is_forwarder_role``
      3. segment oferty — FTL/LTL/ADR/… (``TRANSPORT_SEGMENTS``)
      4. bez ``SERPER_NEGATIVE_TERMS`` (kurier, giełda, praca, …)
      5. higiena: bez legacy DE (bauunternehmen / filialbau / …)
    """
    t = (term or "").strip()
    if len(t) < DISCOVERY_MIN_TERM_LEN or len(t) > DISCOVERY_MAX_TERM_LEN:
        return False
    low = t.lower()
    # 2) Rola PL: spedycja / spedytor / freight forwarder …
    if not is_forwarder_role(low)[0]:
        return False
    # 3) Segment transportu (legacy symbol: RETAIL_CHAINS_ROTATION)
    segments_low = [s.lower() for s in TRANSPORT_SEGMENTS]
    if not any(seg in low for seg in segments_low):
        return False
    # 4) Negatives kampanii PL
    if any(neg.lower() in low for neg in SERPER_NEGATIVE_TERMS if len(neg) >= 4):
        return False
    # 5) Higiena — nie mieszaj DE GU do discovery PL
    if any(m in low for m in _LEGACY_DE_DISCOVERY_MARKERS):
        return False
    return True


# >>> OPIS FUNKCJI: funkcja _cities_for_lands
# Cel: zebrać listę miast z konfiguracji województw (BUNDESLAND_CONFIG[land]["cities"]).
# Parametry: lands (list[str]); max_cities (keyword-only, int, domyślnie 8).
# Zwraca: list[str] — unikalne miasta w kolejności; kończy zbieranie po osiągnięciu limitu.
# Efekty uboczne: brak. Błędy: nieznane województwo jest ignorowane (pusty słownik).
def _cities_for_lands(lands: list[str], *, max_cities: int = 8) -> list[str]:
    """Zbierz miasta z BUNDESLAND_CONFIG dla podanych województw."""
    cities: list[str] = []
    for land in lands:
        cfg = BUNDESLAND_CONFIG.get(land) or {}
        for city in cfg.get("cities") or ():
            if city not in cities:
                cities.append(city)
            if len(cities) >= max_cities:
                return cities
    return cities


# >>> OPIS FUNKCJI: funkcja build_discovery_terms_prompt
# Cel: złożyć prompt dla Haiku generujący dodatkowe frazy Serper.
# Parametry: lands (list[str]) — województwa; cities (keyword-only, list[str]|None) — miasta (domyślnie
#   z _cities_for_lands); terms_requested (int, domyślnie 10); exclude_terms (list[str]|None) — frazy
#   już użyte (do 20 trafia do bloku "nie powtarzaj").
# Zwraca: str — prompt zbudowany przez claude_prompts.build_discovery_terms_prompt (land_str = lista
#   województw lub DEFAULT_DISCOVERY_LAND="Polska"; miasta ograniczone do 8).
# Efekty uboczne/błędy: brak.
def build_discovery_terms_prompt(
    lands: list[str],
    *,
    cities: list[str] | None = None,
    terms_requested: int = 10,
    exclude_terms: list[str] | None = None,
) -> str:
    """Złóż prompt Haiku na dodatkowe frazy Serper dla województw/miast."""
    city_list = cities or _cities_for_lands(lands)
    land_str = ", ".join(lands) if lands else DEFAULT_DISCOVERY_LAND
    city_str = ", ".join(city_list[:8]) if city_list else "—"
    exclude_block = ""
    if exclude_terms:
        exclude_block = (
            "\nJuż użyte (nie powtarzaj):\n"
            + "\n".join(f"- {t}" for t in exclude_terms[:20])
        )
    return _build_discovery_terms_prompt(
        lands,
        city_str=city_str,
        land_str=land_str,
        terms_requested=terms_requested,
        exclude_block=exclude_block,
        max_term_len=DISCOVERY_MAX_TERM_LEN,
    )


# >>> OPIS FUNKCJI: funkcja _cache_bucket
# Cel: zwrócić (i w razie braku utworzyć) sekcję cache["claude_discovery_terms"].
# Parametry: cache (dict). Zwraca: dict — referencja do sekcji (mutowalna).
# Efekty uboczne: setdefault tworzy klucz w cache. Błędy: AttributeError, gdy cache nie jest dict.
def _cache_bucket(cache: dict) -> dict:
    """Sekcja cache na frazy Claude discovery (tworzy klucz jeśli brak)."""
    return cache.setdefault("claude_discovery_terms", {})


# >>> OPIS FUNKCJI: funkcja get_cached_discovery_terms
# Cel: odczytać frazy zapisane wcześniej dla danego województwa, jeśli nie wygasły.
# Parametry: cache (dict); land (str); cache_days (keyword-only, int) — maksymalny wiek wpisu w dniach.
# Zwraca: list[str] niepustych fraz albo None (brak wpisu, zła struktura, błędna data, wygaśnięcie,
#   pusta lista). Obsługuje też stary klucz cache["gemini_discovery_terms"] (migracja z Gemini).
# Efekty uboczne: utworzenie pustej sekcji claude_discovery_terms (przez _cache_bucket); poza tym tylko odczyt.
# Błędy: TypeError/ValueError przy parsowaniu daty są łapane → None.
def get_cached_discovery_terms(
    cache: dict,
    land: str,
    *,
    cache_days: int,
) -> list[str] | None:
    """Odczytaj zcache'owane frazy dla województwa (None = brak/expired)."""
    bucket = _cache_bucket(cache)
    entry = bucket.get((land or "").strip())
    if entry is None:
        legacy = (cache.get("gemini_discovery_terms") or {}).get((land or "").strip())
        if isinstance(legacy, dict):
            entry = legacy
    if not isinstance(entry, dict):
        return None
    at_raw = entry.get("at") or ""
    try:
        at = datetime.fromisoformat(at_raw)
    except (TypeError, ValueError):
        return None
    if datetime.now() - at > timedelta(days=cache_days):
        return None
    terms = entry.get("terms")
    if isinstance(terms, list) and terms:
        return [str(t) for t in terms if str(t).strip()]
    return None


# >>> OPIS FUNKCJI: funkcja store_cached_discovery_terms
# Cel: zapisać wygenerowane frazy w cache z bieżącym znacznikiem czasu.
# Parametry: cache (dict, mutowany); land (str) — pusty → "Polska"; terms (list[str]).
# Zwraca: None. Efekty uboczne: cache["claude_discovery_terms"][land] = {"at": ISO now, "terms": [...]}.
# Błędy: brak własnej obsługi.
def store_cached_discovery_terms(cache: dict, land: str, terms: list[str]) -> None:
    """Zapisz frazy Claude discovery dla województwa z timestampem."""
    land_key = (land or "").strip() or DEFAULT_DISCOVERY_LAND
    _cache_bucket(cache)[land_key] = {
        "at": datetime.now().isoformat(),
        "terms": list(terms),
    }


# >>> OPIS FUNKCJI: funkcja generate_claude_discovery_terms
# Cel: zwrócić zwalidowane frazy Serper — z cache albo świeżo wygenerowane przez Claude.
# Parametry: cache (dict); logger; lands (list[str]) — pierwszy element jest kluczem cache (pusty → "Polska");
#   terms_requested (keyword-only, int, 10); cache_days (7); use_cache (True); exclude_terms (list|None).
# Zwraca: list[str] — max terms_requested fraz; [] gdy brak klucza API albo błąd wywołania.
# Efekty uboczne: wywołanie API Anthropic (model_tier="fast", liczone w cache przez claude_client),
#   odczyt/zapis cache (store_cached_discovery_terms tylko gdy są wyniki i use_cache), logowanie.
# Błędy: wyjątki z claude_generate_text są łapane (warning) → []. Brak klucza → warning + [].
def generate_claude_discovery_terms(
    cache: dict,
    logger,
    lands: list[str],
    *,
    terms_requested: int = 10,
    cache_days: int = 7,
    use_cache: bool = True,
    exclude_terms: list[str] | None = None,
) -> list[str]:
    """Zwraca zwalidowane frazy Serper (max terms_requested)."""
    land_key = (lands[0] if lands else "").strip() or DEFAULT_DISCOVERY_LAND
    if use_cache:
        cached = get_cached_discovery_terms(cache, land_key, cache_days=cache_days)
        if cached:
            logger.info("Claude discovery: cache %s (%s fraz)", land_key, len(cached))
            return cached[:terms_requested]

    api_key = get_anthropic_api_key()
    if not api_key:
        logger.warning("Claude discovery: brak ANTHROPIC_API_KEY")
        return []

    prompt = build_discovery_terms_prompt(
        lands,
        terms_requested=terms_requested,
        exclude_terms=exclude_terms,
    )
    try:
        logger.info("Claude discovery: generowanie %s fraz", terms_requested)
        text, model = claude_generate_text(prompt, logger, api_key, cache=cache, model_tier="fast")
        logger.info("Claude discovery terms, model=%s", model)
    except Exception as exc:
        logger.warning("Claude discovery terms: %s", exc)
        return []

    validated: list[str] = []
    for line in parse_discovery_term_lines(text):
        if validate_discovery_term(line) and line not in validated:
            validated.append(line)
        if len(validated) >= terms_requested:
            break

    if validated and use_cache:
        store_cached_discovery_terms(cache, land_key, validated)
    return validated

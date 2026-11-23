# -*- coding: utf-8 -*-
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


def parse_discovery_term_lines(text: str) -> list[str]:
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


def _cities_for_lands(lands: list[str], *, max_cities: int = 8) -> list[str]:
    cities: list[str] = []
    for land in lands:
        cfg = BUNDESLAND_CONFIG.get(land) or {}
        for city in cfg.get("cities") or ():
            if city not in cities:
                cities.append(city)
            if len(cities) >= max_cities:
                return cities
    return cities


def build_discovery_terms_prompt(
    lands: list[str],
    *,
    cities: list[str] | None = None,
    terms_requested: int = 10,
    exclude_terms: list[str] | None = None,
) -> str:
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


def _cache_bucket(cache: dict) -> dict:
    return cache.setdefault("claude_discovery_terms", {})


def get_cached_discovery_terms(
    cache: dict,
    land: str,
    *,
    cache_days: int,
) -> list[str] | None:
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


def store_cached_discovery_terms(cache: dict, land: str, terms: list[str]) -> None:
    land_key = (land or "").strip() or DEFAULT_DISCOVERY_LAND
    _cache_bucket(cache)[land_key] = {
        "at": datetime.now().isoformat(),
        "terms": list(terms),
    }


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

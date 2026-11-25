# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Uzupełnienie opisu modułu claude_page_verify (komentarz; docstring poniżej opisuje 5 kroków orkiestracji).
#   Rola w pipeline: etap „Claude verify” — jedyna funkcja publiczna claude_verify_company_page łączy cache,
#   twarde NO-GO, wywołanie Claude (tier verify = Sonnet) i interpretację odpowiedzi w page_verify.
#   Zależności: claude_client.claude_generate_text, page_verify (hard_reject_page_context, build_page_verify_prompt,
#   parse_page_verify_response, apply_page_verdict …), pl_spedycja_filter.is_forwarder_role,
#   scraper_env.get_anthropic_api_key. Wejście: nazwa firmy, www, tekst strony, cache, logger.
#   Wyjście: dict werdyktu albo None (brak klucza API lub błąd).
# ============================================================
"""
Claude: weryfikacja kontekstu strony www pod ICP PL spedycja (FTL/LTL).

=============================================================================
PO CO TEN MODUŁ
=============================================================================
Orchestrator LLM nad ``page_verify``:

  1. Cache hit (``claude_page_verify`` / legacy ``gemini_page_verify``) → return.
  2. Twarde NO-GO bez LLM (``hard_reject_page_context``).
  3. Prompt + Claude (``build_page_verify_prompt`` → ``claude_generate_text``).
  4. Parse JSON → ``apply_page_verdict`` (reguły PL + filtry).
  5. Marker roli z ``is_forwarder_role`` → out (klucz legacy ``is_gu``).

Wywołujący: ``pl_fas_spedycja_scraper`` (oraz testy).

=============================================================================
ZWROT
=============================================================================
``None``
    Brak API key albo błąd Claude / parse — scraper może pominąć / retry.
``{verified: False, verification_reason, …}``
    Hard reject albo werdykt negatywny ICP (kody PL z ``page_verify``).
``{verified: True, …}``
    Lead OK pod flagami require_*; segmenty w ``retail_chains`` (legacy key).

=============================================================================
KLUCZE JSON — LEGACY (NIE ZMIENIAĆ NAZW)
=============================================================================
``is_gu``           → is_forwarder_ok (rola spedytora)
``gu_marker``       → marker tekstowy roli
``retail_chains``   → segmenty transportu (ftl, ltl, adr, …)
``is_small_firm``   → z JSON Claude
``claude``          → pełny parsed dict z modelu

Docstring legacy mówił o GU/Filialbau — semantyka to forwarder + segmenty
transportu. Nazwy kluczy bez zmian (Excel / cache / scraper).
"""
from __future__ import annotations

from typing import Callable

from claude_client import claude_generate_text
from page_verify import (
    apply_page_verdict,
    build_page_verify_prompt,
    hard_reject_page_context,
    parse_page_verify_response,
)
from pl_spedycja_filter import is_forwarder_role
from scraper_env import get_anthropic_api_key


def claude_verify_company_page(
    company_name: str,
    website: str,
    page_text: str,
    logger,
    cache: dict | None,
    *,
    cache_key: str = "",
    serper_blob: str = "",
    require_forwarder_role: bool = True,
    require_generalunternehmer: bool | None = None,
    require_small_firm: bool = True,
    on_step: Callable[[str], None] | None = None,
) -> dict | None:
    """
    Czyta stronę (tekst) i zwraca werdykt JSON; None przy braku API lub błędzie.

    Przebieg
    --------
    0. Alias: ``require_generalunternehmer`` nadpisuje ``require_forwarder_role``.
    1. Brak ``ANTHROPIC`` key → ``None``.
    2. Cache ``claude_page_verify[cache_key]`` (ew. migracja z ``gemini_page_verify``).
    3. ``hard_reject_page_context`` → ``verified=False`` + reason (bez Claude).
    4. Prompt + Claude → ``parse_page_verify_response``.
    5. ``apply_page_verdict`` (flagi require_*).
    6. ``is_forwarder_role`` na tekście → ``is_gu`` / ``gu_marker`` (legacy keys).

    ``require_forwarder_role``
        Preferowana nazwa PL (rola spedytora). Default ``True`` (bezpiecznie).
        Kampania PL FAS zwykle przekazuje ``False`` z run_config
        (``require_generalunternehmer: false`` → ``REQUIRE_FORWARDER_ROLE=False``
        w ``pl_fas_spedycja_scraper``).
    ``require_generalunternehmer``
        Alias legacy — jeśli podane, nadpisuje ``require_forwarder_role``.
    ``require_small_firm``
        Gdy True, odrzuca holding / big 3PL wg Claude ``is_small_firm``.

    W wyniku: ``is_gu`` = is_forwarder_ok; ``retail_chains`` = transport_segments.
    """
    if require_generalunternehmer is not None:
        require_forwarder_role = require_generalunternehmer

    api_key = get_anthropic_api_key()
    if not api_key:
        return None

    verify_cache = (cache or {}).setdefault("claude_page_verify", {})
    if not verify_cache and cache_key:
        legacy = (cache or {}).get("gemini_page_verify") or {}
        if cache_key in legacy:
            verify_cache[cache_key] = dict(legacy[cache_key])
    if cache_key and cache_key in verify_cache:
        return dict(verify_cache[cache_key])

    hard, hard_reason = hard_reject_page_context(
        url=website, name=company_name, page_text=page_text
    )
    if hard:
        out = {
            "verified": False,
            "verification_reason": hard_reason,
            "retail_chains": [],  # legacy key = transport_segments
            "claude": {},
        }
        if cache_key:
            verify_cache[cache_key] = out
        return out

    pages_crawled = (page_text or "").count("=== http")
    prompt = build_page_verify_prompt(
        company_name,
        website,
        page_text,
        serper_blob=serper_blob,
        pages_crawled=pages_crawled,
    )
    try:
        text, model = claude_generate_text(
            prompt, logger, api_key, cache=cache, model_tier="verify", on_step=on_step
        )
        logger.info("Claude page verify PL FAS (ICP spedycja), model=%s", model)
        parsed = parse_page_verify_response(text)
    except Exception as exc:
        logger.warning("Claude page verify PL FAS: %s", exc)
        return None

    verified, reason, transport_segments = apply_page_verdict(
        parsed,
        page_text=page_text,
        serper_blob=serper_blob,
        require_forwarder_role=require_forwarder_role,
        require_small_firm=require_small_firm,
    )
    # is_gu w out = is_forwarder_ok (marker z filtra tekstowego)
    forwarder_ok, forwarder_marker = is_forwarder_role(
        " ".join(
            [
                page_text,
                serper_blob,
                " ".join(parsed.get("matched_gu_keywords") or []),
            ]
        )
    )
    out = {
        "verified": verified,
        "verification_reason": reason,
        "retail_chains": transport_segments,  # legacy key = segmenty FTL/LTL/…
        "is_gu": forwarder_ok,  # legacy key = is_forwarder_ok
        "gu_marker": forwarder_marker,
        "is_small_firm": bool(parsed.get("is_small_firm")),
        "claude": parsed,
    }
    if cache_key:
        verify_cache[cache_key] = out
    return out

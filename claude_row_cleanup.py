# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Moduł: claude_row_cleanup — czyszczenie pól wiersza Excela przez Claude (tier „fast” = Haiku).
#
# CO ROBI
#   Wysyła do Claude prompt „cleanup” (zbudowany w claude_prompts.py) z surowymi polami firmy
#   (nazwa, adres, telefon, www, województwo, segmenty, url) i parsuje odpowiedź JSON na ujednolicony
#   słownik pól pipeline. Dzięki temu do Excela trafia czysta nazwa firmy i poprawnie uzupełnione pola.
#
# ROLA W PIPELINE
#   Etap post-processingu przed zapisem wiersza do Excela/cache (włączany flagą
#   ENABLE_CLAUDE_ROW_CLEANUP z scraper_web_config). Gdy flaga/klucz API/odpowiedź zawiodą,
#   scraper po prostu używa pól niewyczyszczonych (funkcja zwraca None).
#
# ZALEŻNOŚCI
#   - claude_client.claude_generate_text (wywołanie API, limity dzienne, cache, model_tier).
#   - scraper_env.get_anthropic_api_key (klucz ANTHROPIC_API_KEY).
#   - biblioteka standardowa: json, re, typing.Callable.
#
# WEJŚCIE / WYJŚCIE
#   Wejście: gotowy tekst promptu, logger, cache (dict|None), opcjonalnie on_step (callback UI).
#   Wyjście: dict z kluczami company_name_clean, address, phone, website, bundesland (= województwo),
#   handelsketten (= segmenty), url — albo None przy braku klucza / błędzie.
# ============================================================
"""Claude Haiku: czyszczenie wiersza przed eksportem do Excela."""
from __future__ import annotations

import json
import re
from typing import Callable

from claude_client import claude_generate_text
from scraper_env import get_anthropic_api_key

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


# >>> OPIS FUNKCJI: funkcja parse_claude_row_cleanup_response
# Cel: zamienić surowy tekst odpowiedzi Claude na ujednolicony słownik pól wiersza.
# Parametry: text (str) — odpowiedź modelu; może zawierać prozę wokół obiektu JSON (wycinany jest
#   pierwszy–ostatni nawias klamrowy regexem _JSON_BLOCK_RE, DOTALL). None/pusty tekst traktowany jak "".
# Zwraca: dict z 7 kluczami tekstowymi (company_name_clean, address, phone, website, bundesland,
#   handelsketten, url); każda wartość jest str i po strip(). Aliasy PL: wojewodztwo/Województwo →
#   bundesland, segmenty/Segmenty → handelsketten.
# Efekty uboczne: brak (czysta funkcja).
# Błędy: json.loads rzuca JSONDecodeError przy niepoprawnym JSON; ValueError("Claude row cleanup: not a
#   JSON object"), gdy wynik nie jest obiektem. Wyjątki NIE są łapane tutaj — obsługuje je
#   claude_cleanup_row_fields.
def parse_claude_row_cleanup_response(text: str) -> dict:
    """
    Parsuje JSON cleanupu Claude → pola pipeline.

    Aliasy PL: ``segmenty`` → ``handelsketten``, ``wojewodztwo`` / ``Województwo``
    → ``bundesland`` (Excel: Segmenty / Województwo).
    """
    raw = (text or "").strip()
    match = _JSON_BLOCK_RE.search(raw)
    payload = match.group(0) if match else raw
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("Claude row cleanup: not a JSON object")
    bundesland = str(
        data.get("bundesland")
        or data.get("wojewodztwo")
        or data.get("Województwo")
        or ""
    ).strip()
    handelsketten = str(
        data.get("handelsketten") or data.get("segmenty") or data.get("Segmenty") or ""
    ).strip()
    email = str(
        data.get("email") or data.get("E-mail") or data.get("e-mail") or ""
    ).strip()
    return {
        "company_name_clean": str(data.get("company_name_clean") or "").strip(),
        "address": str(data.get("address") or "").strip(),
        "phone": str(data.get("phone") or "").strip(),
        "email": email,
        "website": str(data.get("website") or "").strip(),
        "bundesland": bundesland,
        "handelsketten": handelsketten,
        "url": str(data.get("url") or "").strip(),
    }


# >>> OPIS FUNKCJI: funkcja claude_cleanup_row_fields
# Cel: wykonać jedno wywołanie Claude (tier fast) czyszczące pola wiersza Excela.
# Parametry: prompt (str) — gotowy prompt cleanup; logger — obiekt logging (info/warning);
#   cache (dict|None) — cache scrapera przekazywany do licznika/limitów w claude_client;
#   on_step (keyword-only, callable|None) — callback do raportowania kroku w UI/konsoli.
# Zwraca: dict z parse_claude_row_cleanup_response albo None (brak klucza API lub dowolny błąd).
# Efekty uboczne: wywołanie sieciowe do API Anthropic (bypass_daily_limit=True — cleanup nie liczy się
#   do dziennego limitu weryfikacji), zapis do cache przez claude_client, logowanie modelu i ostrzeżeń.
# Błędy: wszystkie wyjątki (sieć, parsowanie JSON) są łapane (except Exception), logowane na poziomie
#   warning i zamieniane na None — pipeline nigdy nie pada z powodu cleanupu.
def claude_cleanup_row_fields(
    prompt: str,
    logger,
    cache: dict | None,
    *,
    on_step: Callable[[str], None] | None = None,
) -> dict | None:
    """Claude fast: cleanup pól wiersza Excel; None gdy brak klucza/błąd."""
    api_key = get_anthropic_api_key()
    if not api_key:
        return None
    try:
        text, model = claude_generate_text(
            prompt,
            logger,
            api_key,
            cache=cache,
            bypass_daily_limit=True,
            model_tier="fast",
            on_step=on_step,
        )
        logger.info("Claude row cleanup, model=%s", model)
        return parse_claude_row_cleanup_response(text)
    except Exception as exc:
        logger.warning("Claude row cleanup: %s", exc)
        return None

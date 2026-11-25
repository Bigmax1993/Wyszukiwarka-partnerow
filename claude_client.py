# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Moduł: claude_client — klient Anthropic Messages API (modele hybrydowe: Haiku „fast” / Sonnet „verify”).
#
# CO ROBI
#   Jedno miejsce komunikacji z API Claude: wybór modelu (zmienne CLAUDE_MODEL_VERIFY / CLAUDE_MODEL /
#   CLAUDE_MODEL_FAST), limit dzienny z rezerwą i tryb „unlimited” (domyślnie włączony), throttling
#   (min. 1,2 s między wywołaniami), cooldown 90 s po błędzie 429, ponawianie przy błędach sieci
#   (3 próby co 20 s), składanie tekstu z bloków odpowiedzi.
#
# ROLA W PIPELINE
#   Wspólna warstwa dla etapów: weryfikacja strony (claude_page_verify), ekstrakcja kontaktów
#   (claude_contact_extract), cleanup wiersza (claude_row_cleanup) i generowanie fraz discovery
#   (claude_discovery_terms). Liczniki i stan rate-limit są trzymane w cache scrapera
#   (klucze "claude_daily" i "claude_api"), więc przeżywają kolejne przebiegi.
#
# ZALEŻNOŚCI: requests, scraper_env (get_anthropic_api_key, get_env_value); stdlib logging, time, datetime.
# STAN GLOBALNY: CLAUDE_DAILY_LIMIT / CLAUDE_DISCOVERY_RESERVE / CLAUDE_UNLIMITED (zmieniane przez
#   configure_claude_limits; przy imporcie CLAUDE_UNLIMITED=True wymuszane przez CLAUDE_UNLIMITED lub
#   DISABLE_CLAUDE_DAILY_LIMIT w env).
#
# WEJŚCIE / WYJŚCIE
#   claude_generate_text(prompt, logger, api_key, cache, ...) → (tekst, nazwa_modelu); błędy jako wyjątki.
# ============================================================
"""Klient Anthropic Messages API — modele hybrydowe (Haiku / Sonnet)."""
from __future__ import annotations

import logging
import time
from datetime import date, datetime
from typing import Callable, Literal

import requests

from scraper_env import get_anthropic_api_key, get_env_value

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
# claude-sonnet-4-20250514 wycofany ~15.06.2026 → 404 na API
DEFAULT_CLAUDE_MODEL_VERIFY = "claude-sonnet-4-6"
DEFAULT_CLAUDE_MODEL_FAST = "claude-haiku-4-5"
# Kompatybilność wsteczna (CLAUDE_MODEL = tier verify)
DEFAULT_CLAUDE_MODEL = DEFAULT_CLAUDE_MODEL_VERIFY
CLAUDE_MODEL_TIER = Literal["fast", "verify"]
CLAUDE_REQUEST_TIMEOUT = 120
CLAUDE_MIN_INTERVAL_SECONDS = 1.2
CLAUDE_API_RETRY_ATTEMPTS = 3
CLAUDE_API_RETRY_WAIT_SECONDS = 20
CLAUDE_DAILY_LIMIT = 3000
CLAUDE_DISCOVERY_RESERVE = 1000
# Domyślnie bez dziennego limitu wywołań (jak SERPER_UNLIMITED).
CLAUDE_UNLIMITED = True


# >>> OPIS FUNKCJI: funkcja _truthy_env
# Cel: zinterpretować tekst z env jako flagę. Parametry: raw (str). Zwraca: bool — True dla
# "1", "true", "yes", "tak", "on" (po strip, bez wielkości liter). Efekty uboczne/błędy: brak.
def _truthy_env(raw: str) -> bool:
    return str(raw or "").strip().lower() in ("1", "true", "yes", "tak", "on")


# >>> OPIS FUNKCJI: funkcja configure_claude_limits
# Cel: nadpisać globalne limity wywołań Claude (np. z run_config).
# Parametry (keyword-only): daily_limit (int|None), reserve (int|None), unlimited (bool|None) — None = bez zmiany.
# Zwraca: None. Efekty uboczne: modyfikuje globalne CLAUDE_DAILY_LIMIT, CLAUDE_DISCOVERY_RESERVE,
# CLAUDE_UNLIMITED. Błędy: ValueError/TypeError, gdy wartości nie da się zrzutować na int.
def configure_claude_limits(
    *,
    daily_limit: int | None = None,
    reserve: int | None = None,
    unlimited: bool | None = None,
) -> None:
    global CLAUDE_DAILY_LIMIT, CLAUDE_DISCOVERY_RESERVE, CLAUDE_UNLIMITED
    if daily_limit is not None:
        CLAUDE_DAILY_LIMIT = int(daily_limit)
    if reserve is not None:
        CLAUDE_DISCOVERY_RESERVE = int(reserve)
    if unlimited is not None:
        CLAUDE_UNLIMITED = bool(unlimited)


# >>> OPIS FUNKCJI: funkcja is_claude_unlimited
# Cel: powiedzieć, czy dzienny limit wywołań Claude jest wyłączony. Parametry: brak.
# Zwraca: bool (CLAUDE_UNLIMITED). Efekty uboczne/błędy: brak.
def is_claude_unlimited() -> bool:
    """Brak dziennego limitu / rezerwy na wywołania Claude."""
    return bool(CLAUDE_UNLIMITED)


if _truthy_env(get_env_value("CLAUDE_UNLIMITED", "")) or _truthy_env(
    get_env_value("DISABLE_CLAUDE_DAILY_LIMIT", "")
):
    CLAUDE_UNLIMITED = True


# >>> OPIS FUNKCJI: funkcja get_claude_model_verify
# Cel: nazwa modelu do weryfikacji (tier verify, domyślnie Sonnet). Parametry: brak.
# Zwraca: str — kolejność: env CLAUDE_MODEL_VERIFY, env CLAUDE_MODEL (legacy), DEFAULT_CLAUDE_MODEL_VERIFY.
# Efekty uboczne: odczyt env. Błędy: brak.
def get_claude_model_verify() -> str:
    legacy = get_env_value("CLAUDE_MODEL", "")
    explicit = get_env_value("CLAUDE_MODEL_VERIFY", "")
    return explicit or legacy or DEFAULT_CLAUDE_MODEL_VERIFY


# >>> OPIS FUNKCJI: funkcja get_claude_model_fast
# Cel: nazwa taniego modelu (tier fast, domyślnie Haiku). Parametry: brak.
# Zwraca: str — env CLAUDE_MODEL_FAST lub DEFAULT_CLAUDE_MODEL_FAST (także gdy env jest pusty).
# Efekty uboczne: odczyt env. Błędy: brak.
def get_claude_model_fast() -> str:
    return get_env_value("CLAUDE_MODEL_FAST", DEFAULT_CLAUDE_MODEL_FAST) or DEFAULT_CLAUDE_MODEL_FAST


# >>> OPIS FUNKCJI: funkcja get_claude_model
# Cel: alias zgodności wstecznej — zwraca model tier verify. Parametry: brak. Zwraca: str
# (= get_claude_model_verify()). Efekty uboczne/błędy: brak.
def get_claude_model() -> str:
    return get_claude_model_verify()


# >>> OPIS FUNKCJI: funkcja resolve_claude_model
# Cel: wybrać nazwę modelu dla pojedynczego wywołania.
# Parametry (keyword-only): model (str|None) — jawna nazwa (ma pierwszeństwo, po strip); model_tier
#   ("fast"|"verify"|None) — "fast" → Haiku; wszystko inne (w tym None) → tier verify.
# Zwraca: str. Efekty uboczne: odczyt env. Błędy: brak.
def resolve_claude_model(
    *,
    model: str | None = None,
    model_tier: CLAUDE_MODEL_TIER | None = None,
) -> str:
    if model:
        return model.strip()
    if model_tier == "fast":
        return get_claude_model_fast()
    return get_claude_model_verify()


# >>> OPIS FUNKCJI: funkcja _campaign_today
# Cel: data „dzisiejsza” dla liczników dziennych w strefie kampanii.
# Parametry: brak. Zwraca: str ISO (YYYY-MM-DD) wg strefy z env SCRAPER_TIMEZONE (domyślnie Europe/Warsaw).
# Błędy: dowolny wyjątek (brak zoneinfo / zła strefa) łapany → date.today() w strefie lokalnej OS.
def _campaign_today() -> str:
    try:
        from zoneinfo import ZoneInfo

        tz = get_env_value("SCRAPER_TIMEZONE", "Europe/Warsaw")
        return datetime.now(ZoneInfo(tz)).date().isoformat()
    except Exception:
        return date.today().isoformat()


# >>> OPIS FUNKCJI: funkcja _claude_rate_bucket
# Cel: zwrócić sekcję cache["claude_api"] (stan throttlingu / cooldown). Parametry: cache (dict|None).
# Zwraca: dict — referencja do sekcji; dla None zwracany jest tymczasowy słownik (zmiany nie są zapisywane).
# Efekty uboczne: setdefault tworzy klucz. Błędy: brak.
def _claude_rate_bucket(cache: dict | None) -> dict:
    return (cache or {}).setdefault("claude_api", {})


# >>> OPIS FUNKCJI: funkcja get_remaining_daily_claude_limit
# Cel: policzyć zużycie i pozostały limit dzienny wywołań Claude.
# Parametry: cache (dict|None) — korzysta z cache["claude_daily"][data].
# Zwraca: (data_iso: str, zużyte: int, pozostałe: int). W trybie unlimited trzecia wartość to CLAUDE_DAILY_LIMIT
#   (nie „pozostałe”).
# Efekty uboczne: tworzy cache["claude_daily"], jeśli brak. Błędy: ValueError przy nienumerycznych licznikach.
def get_remaining_daily_claude_limit(cache: dict | None) -> tuple[str, int, int]:
    today = _campaign_today()
    daily = (cache or {}).setdefault("claude_daily", {})
    used_today = int(daily.get(today, 0))
    if is_claude_unlimited():
        return today, used_today, CLAUDE_DAILY_LIMIT
    remaining = max(0, CLAUDE_DAILY_LIMIT - used_today)
    return today, used_today, remaining


# >>> OPIS FUNKCJI: funkcja increase_daily_claude_counter
# Cel: zwiększyć dzienny licznik wywołań Claude. Parametry: cache (dict|None); increment (int, domyślnie 1).
# Zwraca: None. Efekty uboczne: cache["claude_daily"][dzisiaj] += increment (dla cache=None zmiana jest tracona).
# Błędy: ValueError przy nienumerycznych wartościach.
def increase_daily_claude_counter(cache: dict | None, increment: int = 1) -> None:
    today = _campaign_today()
    daily = (cache or {}).setdefault("claude_daily", {})
    daily[today] = int(daily.get(today, 0)) + int(increment)


# >>> OPIS FUNKCJI: funkcja is_claude_limit_reached_today
# Cel: sprawdzić, czy dzienny limit (z rezerwą) został osiągnięty. Parametry: cache (dict|None).
# Zwraca: bool — zawsze False przy unlimited; inaczej True, gdy pozostałe wywołania <= CLAUDE_DISCOVERY_RESERVE.
# Efekty uboczne: jak get_remaining_daily_claude_limit. Błędy: brak własnej obsługi.
def is_claude_limit_reached_today(cache: dict | None) -> bool:
    if is_claude_unlimited():
        return False
    _, _, remaining = get_remaining_daily_claude_limit(cache)
    return remaining <= CLAUDE_DISCOVERY_RESERVE


# >>> OPIS FUNKCJI: funkcja is_claude_rate_limited
# Cel: sprawdzić, czy trwa cooldown po błędzie 429. Parametry: cache (dict|None).
# Zwraca: bool — True, gdy cache["claude_api"]["cooldown_until"] > time.time().
# Efekty uboczne: może utworzyć cache["claude_api"]. Błędy: ValueError przy nienumerycznej wartości.
def is_claude_rate_limited(cache: dict | None) -> bool:
    bucket = _claude_rate_bucket(cache)
    until = float(bucket.get("cooldown_until") or 0)
    return until > time.time()


# >>> OPIS FUNKCJI: funkcja mark_claude_rate_limited
# Cel: uruchomić 90-sekundowy cooldown po rate limicie. Parametry: cache (dict|None); logger (Logger|None).
# Zwraca: None. Efekty uboczne: zapisuje cooldown_until = teraz + 90 s w cache["claude_api"]; loguje warning.
# Błędy: brak.
def mark_claude_rate_limited(cache: dict | None, logger: logging.Logger | None = None) -> None:
    bucket = _claude_rate_bucket(cache)
    bucket["cooldown_until"] = time.time() + 90
    if logger:
        logger.warning("Claude API: cooldown 90s (rate limit)")


# >>> OPIS FUNKCJI: funkcja wait_for_claude_slot
# Cel: wymusić minimalny odstęp CLAUDE_MIN_INTERVAL_SECONDS (1,2 s) między wywołaniami API.
# Parametry: cache (dict|None) — przechowuje last_call_at. Zwraca: None.
# Efekty uboczne: BLOKUJĄCY time.sleep do brakującego czasu; aktualizuje last_call_at. Błędy: brak.
def wait_for_claude_slot(cache: dict | None) -> None:
    bucket = _claude_rate_bucket(cache)
    last = float(bucket.get("last_call_at") or 0)
    wait = CLAUDE_MIN_INTERVAL_SECONDS - (time.time() - last)
    if wait > 0:
        time.sleep(wait)
    bucket["last_call_at"] = time.time()


# >>> OPIS FUNKCJI: funkcja _is_rate_limit_error
# Cel: rozpoznać błąd rate limit (HTTP 429). Parametry: err (Exception).
# Zwraca: bool — True, jeśli tekst błędu zawiera "429" lub "rate", albo err.response.status_code == 429.
# Efekty uboczne/błędy: brak. Uwaga: dopasowanie po słowie "rate" bywa szerokie (np. „generate”).
def _is_rate_limit_error(err: Exception) -> bool:
    text = str(err).lower()
    if "429" in text or "rate" in text:
        return True
    resp = getattr(err, "response", None)
    return resp is not None and getattr(resp, "status_code", None) == 429


# >>> OPIS FUNKCJI: funkcja _should_retry_claude_api_call
# Cel: zdecydować, czy ponawiać wywołanie po błędzie. Parametry: err (Exception).
# Zwraca: bool — True tylko dla requests.RequestException (sieć/HTTP); inne wyjątki nie są ponawiane.
# Efekty uboczne/błędy: brak.
def _should_retry_claude_api_call(err: Exception) -> bool:
    """Ponów przy błędzie HTTP/sieci (nie przy braku klucza / limicie dziennym)."""
    return isinstance(err, requests.RequestException)


# >>> OPIS FUNKCJI: funkcja claude_generate_text
# Cel: wysłać prompt do Anthropic Messages API i zwrócić tekst odpowiedzi oraz użyty model.
# Parametry: prompt (str); logger; api_key (str|None; domyślnie z get_anthropic_api_key); cache (dict|None)
#   — liczniki/cooldown; max_tokens (keyword-only, 4096); bypass_daily_limit (False) — pomija sprawdzanie
#   i zliczanie limitu dziennego; model (str|None) — jawna nazwa; model_tier ("fast"|"verify"|None);
#   on_step (callable|None) — callback "Claude: <model>".
# Zwraca: (text: str po strip, model: str).
# Efekty uboczne: żądanie HTTP POST (timeout 120 s), sleep przy throttlingu i ponowieniach, zapis
#   cooldown/licznika w cache, logowanie.
# Błędy: RuntimeError — brak klucza ("Brak ANTHROPIC_API_KEY"), cooldown rate-limit, osiągnięta rezerwa
#   dzienna, pusta odpowiedź, brak danych po ponowieniach. Błędy sieci (requests) są ponawiane do 3 razy
#   co 20 s, po czym wyjątek jest rzucany dalej; 429 ustawia cooldown 90 s.
def claude_generate_text(
    prompt: str,
    logger: logging.Logger,
    api_key: str | None = None,
    cache: dict | None = None,
    *,
    max_tokens: int = 4096,
    bypass_daily_limit: bool = False,
    model: str | None = None,
    model_tier: CLAUDE_MODEL_TIER | None = None,
    on_step: Callable[[str], None] | None = None,
) -> tuple[str, str]:
    """Zwraca (text, model). model_tier: fast=Haiku, verify=Sonnet (domyslnie)."""
    key = (api_key or get_anthropic_api_key()).strip()
    if not key:
        raise RuntimeError("Brak ANTHROPIC_API_KEY")
    if is_claude_rate_limited(cache):
        raise RuntimeError("Claude API w cooldown (rate limit)")
    skip_daily_limit = bypass_daily_limit or is_claude_unlimited()
    if not skip_daily_limit and is_claude_limit_reached_today(cache):
        _, used, remaining = get_remaining_daily_claude_limit(cache)
        raise RuntimeError(
            f"Claude Tageslimit-Reserve erreicht ({_campaign_today()}: "
            f"genutzt={used}, rest={remaining}, reserve={CLAUDE_DISCOVERY_RESERVE}, "
            f"max={CLAUDE_DAILY_LIMIT})"
        )

    model = resolve_claude_model(model=model, model_tier=model_tier)
    headers = {
        "x-api-key": key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    data: dict | None = None
    last_exc: Exception | None = None
    for attempt in range(1, CLAUDE_API_RETRY_ATTEMPTS + 1):
        try:
            wait_for_claude_slot(cache)
            resp = requests.post(
                ANTHROPIC_MESSAGES_URL,
                headers=headers,
                json=payload,
                timeout=CLAUDE_REQUEST_TIMEOUT,
            )
            if resp.status_code == 429:
                mark_claude_rate_limited(cache, logger)
            resp.raise_for_status()
            data = resp.json()
            break
        except Exception as exc:
            last_exc = exc
            if _is_rate_limit_error(exc):
                mark_claude_rate_limited(cache, logger)
            if (
                attempt >= CLAUDE_API_RETRY_ATTEMPTS
                or not _should_retry_claude_api_call(exc)
            ):
                raise
            logger.warning(
                "Claude API: błąd (próba %s/%s): %s — ponowienie za %ss",
                attempt,
                CLAUDE_API_RETRY_ATTEMPTS,
                exc,
                CLAUDE_API_RETRY_WAIT_SECONDS,
            )
            time.sleep(CLAUDE_API_RETRY_WAIT_SECONDS)
    if data is None:
        raise last_exc or RuntimeError("Claude API: brak odpowiedzi po ponowieniach")

    if not skip_daily_limit:
        increase_daily_claude_counter(cache, 1)
    blocks = data.get("content") or []
    text = ""
    for block in blocks:
        if isinstance(block, dict) and block.get("type") == "text":
            text += str(block.get("text") or "")
    if not text.strip():
        raise RuntimeError("Claude: pusta odpowiedź")
    if on_step:
        on_step(f"Claude: {model}")
    return text.strip(), model

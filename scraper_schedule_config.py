# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Uzupełnienie opisu modułu scraper_schedule_config (komentarz; docstring poniżej jest pełny).
#   Zależności: stdlib os, dataclasses, datetime; opcjonalnie zoneinfo (brak → fallback na lokalny zegar OS).
#   Wejście: zmienne środowiskowe DISABLE_SEND_WINDOW, SCRAPER_IGNORE_SEND_WINDOW, SEND_WINDOW_START_HOUR,
#   SEND_WINDOW_END_HOUR, SCRAPER_TIMEZONE. Wyjście: SendWindowConfig (frozen dataclass), godzina (int), bool.
#   Rola w pipeline: bramka czasowa przed etapem wysyłki maili B2B (_process_email_jobs w scraperze).
# ============================================================
"""
Okno wysyłki e-mail i strefa czasu — konfiguracja przez zmienne środowiskowe.

Co robi ten moduł
-----------------
To **strażnik godzin wysyłki** dla scrapera: czyta env (GHA / cron / Task Scheduler)
i odpowiada na pytanie „czy teraz wolno wysyłać maile B2B?”.

- ``load_send_window_config()`` — wczytuje start/koniec okna, strefę, flagę DISABLE
- ``current_local_hour()`` — aktualna godzina w ``Europe/Warsaw`` (albo lokalna OS)
- ``is_within_send_window()`` — ``True`` = scraper może wysyłać; ``False`` = poczekaj

Nie wysyła maili sam, nie rusza SMTP ani treści — tylko decyzja czasowa.
Nie dotyczy raportu Excel na Gmail (osobne flagi ``DISABLE_EXCEL_REPORT_EMAIL``).
Przy kampanii discovery-only / ``DISABLE_CONTRACTOR_EMAILS=1`` i tak nie ma B2B,
ale okno zostaje na rollback wysyłki.

Po co: job o 2:00 UTC nie powinien „wyglądać” jak spam o północy w PL —
albo ustawiasz ``SCRAPER_TIMEZONE=Europe/Warsaw`` + godziny biurowe,
albo ``DISABLE_SEND_WINDOW=1`` (zalecane w CI, gdy cron i tak kontroluje start).

Przykłady env::

  DISABLE_SEND_WINDOW=1          → wysyłka o każdej godzinie (zalecane dla CI/cron)
  SCRAPER_IGNORE_SEND_WINDOW=1   → alias tego samego
  SEND_WINDOW_START_HOUR=0       → od północy
  SEND_WINDOW_END_HOUR=24        → do północy (cała doba przy starcie 0)
  SCRAPER_TIMEZONE=Europe/Warsaw → godzina okna wg PL (nie UTC runnera)

Domyślnie (bez DISABLE): 8–18 w lokalnej strefie procesu albo ``SCRAPER_TIMEZONE``.
Nazwa modułu bez zmian.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore


# >>> OPIS FUNKCJI: funkcja _truthy
# Cel: zinterpretować wartość zmiennej środowiskowej jako flagę. Parametry: val (str|None).
# Zwraca: bool — True dla "1", "true", "yes", "on" (bez rozróżniania wielkości liter, po strip).
# Efekty uboczne/błędy: brak (None → False).
def _truthy(val: str | None) -> bool:
    """Czy wartość env jest „włączona” (``1`` / ``true`` / ``yes`` / ``on``)."""
    return (val or "").strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class SendWindowConfig:
    """
    Snapshot okna wysyłki z env (immutable).

    ``start_hour`` / ``end_hour``: godziny 0–23 / 1–24 (koniec półotwarty).
    ``disabled=True``: ignoruj godziny — zawsze wolno wysyłać.
    ``timezone``: IANA (np. ``Europe/Warsaw``); pusty = lokalny zegar OS.
    """

    start_hour: int
    end_hour: int
    disabled: bool
    timezone: str


def load_send_window_config() -> SendWindowConfig:
    """
    Buduje ``SendWindowConfig`` z bieżącego środowiska procesu.

    ``DISABLE_SEND_WINDOW`` lub ``SCRAPER_IGNORE_SEND_WINDOW`` → ``disabled``.
    Start/end z ``SEND_WINDOW_*_HOUR`` (fallback 8 i 18); złe wartości → default.
    Clamp: start 0…23, end 1…24. Strefa z ``SCRAPER_TIMEZONE`` (może być pusta).
    """
    disabled = _truthy(os.getenv("DISABLE_SEND_WINDOW")) or _truthy(
        os.getenv("SCRAPER_IGNORE_SEND_WINDOW")
    )
    try:
        start = int((os.getenv("SEND_WINDOW_START_HOUR") or "8").strip())
    except ValueError:
        start = 8
    try:
        end = int((os.getenv("SEND_WINDOW_END_HOUR") or "18").strip())
    except ValueError:
        end = 18
    start = max(0, min(23, start))
    end = max(1, min(24, end))
    tz = (os.getenv("SCRAPER_TIMEZONE") or "").strip()
    return SendWindowConfig(
        start_hour=start,
        end_hour=end,
        disabled=disabled,
        timezone=tz,
    )


def current_local_hour(timezone: str = "") -> int:
    """
    Bieżąca godzina (0–23) w podanej strefie albo lokalnej OS.

    Kolejność: argument ``timezone`` → env ``SCRAPER_TIMEZONE`` → ``datetime.now()``.
    Błędna nazwa IANA / brak ``zoneinfo`` → cichy fallback na lokalny zegar.
    """
    tz = (timezone or os.getenv("SCRAPER_TIMEZONE") or "").strip()
    if tz and ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo(tz)).hour
        except Exception:
            pass
    return datetime.now().hour


def is_within_send_window(cfg: SendWindowConfig | None = None) -> bool:
    """
    ``True`` = wolno wysyłać maile teraz.

    Przy ``cfg.disabled`` zawsze ``True``. Inaczej porównuje
    ``current_local_hour(cfg.timezone)`` z ``[start_hour, end_hour)``.
    Gdy ``start >= end`` (np. 22–6): okno przez północ
    (``hour >= start`` **lub** ``hour < end``).

    ``cfg=None`` → świeży odczyt env przez ``load_send_window_config()``.
    """
    c = cfg or load_send_window_config()
    if c.disabled:
        return True
    hour = current_local_hour(c.timezone)
    if c.start_hour < c.end_hour:
        return c.start_hour <= hour < c.end_hour
    # Okno przez północ, np. 22–6
    return hour >= c.start_hour or hour < c.end_hour

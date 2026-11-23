# -*- coding: utf-8 -*-
"""
Wspólne flagi www / Claude / Playwright — kampania PL FAS / spedycja.

=============================================================================
PO CO TEN MODUŁ
=============================================================================
Jedno miejsce ON/OFF dla pipeline PL (``pl_fas_spedycja_scraper`` i inne
scrapery w repo). **Brak funkcji** — tylko stałe bool importowane przez
scrapera / Playwright / ``claude_client``.

  - crawl strony: requests + BeautifulSoup;
  - baner cookie: Playwright (PL: ``pl-PL`` / „Akceptuję” —
    ``playwright_cookie_consent``);
  - kontakty: regex / mailto; brak celu → Claude na crawl;
  - weryfikacja ICP + cleanup wiersza: Claude (Anthropic).

=============================================================================
NADPISYWANIE (run_config)
=============================================================================
Wartości poniżej = **default biblioteki**.

Produkcja PL: ``run_config/pl_fas_spedycja.json`` +
``apply_gu_run_config_extras`` ustawia na module scrapera m.in.
``ENABLE_CLAUDE_*`` / ``CLAUDE_UNLIMITED`` (klucze JSON
``enable_claude_*`` / ``claude_unlimited``).

``apply_run_config_file`` samych flag Claude **nie** ustawia — extras tak.
CLI ``--run-config`` oraz ``main(path)`` wołają oba.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# ENABLE_CLAUDE_PAGE_VERIFY
# ---------------------------------------------------------------------------
# PO CO: Claude Sonnet czyta tekst www i zwraca werdykt ICP (FTL/LTL, rola
#        spedytora, mała firma) przez ``claude_page_verify`` / ``page_verify``.
# ON:    scraper woła verify przy crawl / retail_verified.
# OFF:   tylko heurystyki tekstowe / Serper — bez LLM page verify.
# CZYTA: ``pl_fas_spedycja_scraper`` (import + run_config extras).
# JSON:  ``enable_claude_page_verify``
ENABLE_CLAUDE_PAGE_VERIFY = True

# ---------------------------------------------------------------------------
# ENABLE_CLAUDE_CONTACT_EXTRACT
# ---------------------------------------------------------------------------
# PO CO: gdy regex / mailto nie da maila lub telefonu, Claude wyciąga kontakty
#        z crawla (``claude_contact_extract`` → merge do collected).
# ON:    dodatkowy call LLM po nieudanym / ubogim scrape kontaktów.
# OFF:   tylko regex + filtr commercial.
# CZYTA: ``pl_fas_spedycja_scraper`` (ścieżka contacts).
# JSON:  ``enable_claude_contact_extract``
ENABLE_CLAUDE_CONTACT_EXTRACT = True

# ---------------------------------------------------------------------------
# CLAUDE_UNLIMITED
# ---------------------------------------------------------------------------
# PO CO: wyłącza dzienny limit wywołań Anthropic (verify, cleanup, contact,
#        discovery) — ``claude_client.configure_claude_limits(unlimited=…)``.
# ON:    brak capu (dev / produkcja FAS z dużym budżetem API).
# OFF:   obowiązuje ``CLAUDE_DAILY_LIMIT`` (+ reserve discovery).
# CZYTA: scraper przy starcie / po run_config; env ``CLAUDE_UNLIMITED`` może
#        nadpisać w scraperze osobno.
# JSON:  ``claude_unlimited``
CLAUDE_UNLIMITED = True

# ---------------------------------------------------------------------------
# ENABLE_CLAUDE_ROW_CLEANUP
# ---------------------------------------------------------------------------
# PO CO: przed zapisem Excela Claude czyści nazwę firmy, telefon, adres
#        (``claude_row_cleanup``) — spójne komórki PL.
# ON:    cleanup w pipeline eksportu / wiersza.
# OFF:   surowe wartości z Serper / crawl / regex.
# CZYTA: ``pl_fas_spedycja_scraper`` (helper enable + wywołanie cleanup).
# JSON:  ``enable_claude_row_cleanup``
ENABLE_CLAUDE_ROW_CLEANUP = True

# ---------------------------------------------------------------------------
# ENABLE_CLAUDE_DISCOVERY_TERMS
# ---------------------------------------------------------------------------
# PO CO: Claude Haiku generuje dodatkowe frazy Serper, gdy szablony keywords
#        dają za mało hitów (``claude_discovery_terms``).
# ON:    rundy supplement discovery w scraperze.
# OFF:   (default biblioteki — bezpiecznie) tylko ``pl_spedycja_keywords``.
# PL:    produkcja zwykle True przez JSON → ``apply_gu_run_config_extras``.
# CZYTA: ``pl_fas_spedycja_scraper`` (discovery supplement / warunek rundy).
# JSON:  ``enable_claude_discovery_terms`` (w ``pl_fas_spedycja.json`` = true)
ENABLE_CLAUDE_DISCOVERY_TERMS = False

# ---------------------------------------------------------------------------
# ENABLE_PLAYWRIGHT_COOKIE_CONSENT
# ---------------------------------------------------------------------------
# PO CO: przed pobraniem treści www Playwright klika zgodę na cookies
#        (lokalizacja PL — „Akceptuję” / CMP; nie CAPTCHA, nie mapy).
# ON:    ``playwright_cookie_consent`` aktywny przy crawl.
# OFF:   sam requests/BS4 — baner może zasłaniać kontakt.
# CZYTA: ``playwright_cookie_consent`` (import flagi); scraper przy full crawl.
# JSON:  brak osobnego klucza w typowym run_config (zostaje default True).
ENABLE_PLAYWRIGHT_COOKIE_CONSENT = True

# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# MODUŁ TESTOWY: tests/unit/test_playwright_cookie_consent.py
# CO ROBI: testy modułu playwright_cookie_consent: decyzja o użyciu Playwrighta, rozpoznawanie przycisków akceptuj/odrzuć, fallback ponownego parsowania i narzędzia debug.
# ROLA W PIPELINE: chroni obsługę banerów cookies podczas crawla (bez uruchamiania przeglądarki).
# ZALEŻNOŚCI: pytest (monkeypatch, capsys), playwright_cookie_consent.
# WEJŚCIE/WYJŚCIE: Moduł nie przyjmuje argumentów CLI; pytest/unittest odkrywa i uruchamia testy; nic nie zwraca (wynik = zielone/czerwone testy).
# ============================================================
"""Testy jednostkowe: playwright_cookie_consent (PL CMP / Akceptuj)."""
from __future__ import annotations

import logging

import pytest

from playwright_cookie_consent import (
    _cli_debug,
    _is_polish_accept_label,
    _is_reject_label,
    apply_playwright_cookie_fallback,
    debug_accept_label,
    debug_cookie_consent_decision,
    should_use_playwright_cookie_fallback,
)

pytestmark = pytest.mark.unit

_LOG = logging.getLogger("test_playwright_cookie_consent")


# >>> OPIS FUNKCJI: klasa TestShouldUsePlaywrightCookieFallback
# Grupa testów: decyzja, czy użyć fallbacku Playwright.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestShouldUsePlaywrightCookieFallback:
    # >>> OPIS FUNKCJI: funkcja TestShouldUsePlaywrightCookieFallback.test_polish_banner_text
    # Test: polski tekst baneru uruchamia fallback.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_polish_banner_text(self):
        assert should_use_playwright_cookie_fallback(
            "Ta strona używa ciasteczek. Akceptuj wszystkie."
        )

    # >>> OPIS FUNKCJI: funkcja TestShouldUsePlaywrightCookieFallback.test_cmp_html_hint
    # Test: znacznik CMP w HTML uruchamia fallback.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_cmp_html_hint(self):
        assert should_use_playwright_cookie_fallback(
            "",
            html='<div id="CybotCookiebotDialogBodyButtonAccept"></div>',
        )

    # >>> OPIS FUNKCJI: funkcja TestShouldUsePlaywrightCookieFallback.test_borlabs_marker
    # Test: marker Borlabs uruchamia fallback.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_borlabs_marker(self):
        assert should_use_playwright_cookie_fallback(
            "Zarządzaj zgodami",
            html='<div class="borlabs-cookie"></div>',
        )

    # >>> OPIS FUNKCJI: funkcja TestShouldUsePlaywrightCookieFallback.test_no_cookie_signal
    # Test: brak sygnału cookies — fallback nie jest potrzebny.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_no_cookie_signal(self):
        assert not should_use_playwright_cookie_fallback(
            "Firma spedycyjna FTL Głogów. Kontakt: biuro@example.pl"
        )

    # >>> OPIS FUNKCJI: funkcja TestShouldUsePlaywrightCookieFallback.test_fallback_en_accept_all
    # Test: angielski komunikat 'accept all cookies' też uruchamia fallback.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_fallback_en_accept_all(self):
        assert should_use_playwright_cookie_fallback("Please accept all cookies to continue")


# >>> OPIS FUNKCJI: klasa TestAcceptRejectLabels
# Grupa testów: rozpoznawanie etykiet przycisków.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestAcceptRejectLabels:
    # >>> OPIS FUNKCJI: funkcja TestAcceptRejectLabels.test_accept_exact_and_regex
    # Test: etykiety akceptacji (Akceptuj wszystkie, Zgadzam się, Rozumiem) są rozpoznawane.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_accept_exact_and_regex(self):
        assert _is_polish_accept_label("Akceptuj wszystkie")
        assert _is_polish_accept_label("Zgadzam się")
        assert _is_polish_accept_label("Rozumiem")
        assert _is_polish_accept_label("akceptuj cookies")

    # >>> OPIS FUNKCJI: funkcja TestAcceptRejectLabels.test_reject_and_settings_blocked
    # Test: etykiety odrzucenia/ustawień (Odrzuć, Tylko niezbędne) są rozpoznawane jako odrzucające i nie jako akceptacja.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_reject_and_settings_blocked(self):
        assert _is_reject_label("Odrzuć")
        assert _is_reject_label("Tylko niezbędne")
        assert _is_reject_label("Ustawienia cookies")
        assert not _is_polish_accept_label("Tylko niezbędne")
        assert not _is_polish_accept_label("Odmów")

    # >>> OPIS FUNKCJI: funkcja TestAcceptRejectLabels.test_long_rodo_paragraph_not_accept
    # Test: długi akapit RODO (>90 znaków) nie jest etykietą akceptacji.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_long_rodo_paragraph_not_accept(self):
        blob = "Akceptuj " + ("rodo " * 40)
        assert len(blob) > 90
        assert not _is_polish_accept_label(blob)

    # >>> OPIS FUNKCJI: funkcja TestAcceptRejectLabels.test_empty_label
    # Test: pusta etykieta nie jest ani akceptacją, ani odrzuceniem.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_empty_label(self):
        assert not _is_polish_accept_label("")
        assert not _is_reject_label("")


# >>> OPIS FUNKCJI: klasa TestApplyPlaywrightCookieFallback
# Grupa testów: funkcja apply_playwright_cookie_fallback.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestApplyPlaywrightCookieFallback:
    # >>> OPIS FUNKCJI: funkcja TestApplyPlaywrightCookieFallback.test_disabled_flag_returns_parsed
    # Test: przy wyłączonej fladze zwracany jest wejściowy wynik parsowania bez zmian.
    # Parametry: self, monkeypatch. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: monkeypatch zmienia zmienne środowiskowe tylko na czas testu (cofane automatycznie). Błędy: AssertionError przy niespełnionej asercji.
    def test_disabled_flag_returns_parsed(self, monkeypatch):
        import playwright_cookie_consent as m

        monkeypatch.setattr(m, "ENABLE_PLAYWRIGHT_COOKIE_CONSENT", False)
        parsed = {"page_text": "ciasteczka", "emails": []}
        out = apply_playwright_cookie_fallback(
            "https://firma.pl",
            _LOG,
            "<html>cookies</html>",
            parsed,
            parse_contacts_from_html=lambda u, h: {"emails": ["x@y.pl"]},
        )
        assert out is parsed

    # >>> OPIS FUNKCJI: funkcja TestApplyPlaywrightCookieFallback.test_no_banner_skips_playwright
    # Test: brak baneru → Playwright nie jest wywoływany (licznik wywołań 0).
    # Parametry: self, monkeypatch. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: monkeypatch zmienia zmienne środowiskowe tylko na czas testu (cofane automatycznie). Błędy: AssertionError przy niespełnionej asercji.
    def test_no_banner_skips_playwright(self, monkeypatch):
        import playwright_cookie_consent as m

        called = {"n": 0}

        # >>> OPIS FUNKCJI: funkcja TestApplyPlaywrightCookieFallback.test_no_banner_skips_playwright.boom
        # Atrapa testowa: podmieniona funkcja pobierania HTML przez Playwright; zlicza wywołania, aby test mógł sprawdzić, że nie została użyta. Parametry: *args/**kwargs. Zwraca: str lub rzuca — zależnie od testu. Efekty uboczne: zwiększa licznik. Błędy: brak.
        def boom(*_a, **_k):
            called["n"] += 1
            return "<html>pw</html>"

        monkeypatch.setattr(m, "fetch_html_with_cookie_consent", boom)
        parsed = {"page_text": "spedycja FTL bez banera"}
        out = apply_playwright_cookie_fallback(
            "https://firma.pl",
            _LOG,
            "<html>oferta</html>",
            parsed,
            parse_contacts_from_html=lambda u, h: {"emails": ["x@y.pl"]},
        )
        assert out is parsed
        assert called["n"] == 0

    # >>> OPIS FUNKCJI: funkcja TestApplyPlaywrightCookieFallback.test_banner_triggers_reparse
    # Test: przy bannerze HTML z Playwrighta jest ponownie parsowany, a krok jest zgłaszany callbackiem on_step.
    # Parametry: self, monkeypatch. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: monkeypatch zmienia zmienne środowiskowe tylko na czas testu (cofane automatycznie). Błędy: AssertionError przy niespełnionej asercji.
    def test_banner_triggers_reparse(self, monkeypatch):
        import playwright_cookie_consent as m

        monkeypatch.setattr(
            m,
            "fetch_html_with_cookie_consent",
            lambda url, logger, **kw: "<html>po zgodzie biuro@sped.pl</html>",
        )
        steps: list[str] = []
        parsed = {"page_text": "Akceptuj wszystkie cookies", "emails": []}
        out = apply_playwright_cookie_fallback(
            "https://firma.pl",
            _LOG,
            '<div class="borlabs-cookie"></div>',
            parsed,
            parse_contacts_from_html=lambda u, h: {
                "page_text": h,
                "emails": ["biuro@sped.pl"],
            },
            on_step=steps.append,
        )
        assert out["emails"] == ["biuro@sped.pl"]
        assert steps and "cookie" in steps[0].lower()

    # >>> OPIS FUNKCJI: funkcja TestApplyPlaywrightCookieFallback.test_empty_playwright_html_keeps_parsed
    # Test: pusty HTML z Playwrighta → zachowany pierwotny wynik parsowania.
    # Parametry: self, monkeypatch. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: monkeypatch zmienia zmienne środowiskowe tylko na czas testu (cofane automatycznie). Błędy: AssertionError przy niespełnionej asercji.
    def test_empty_playwright_html_keeps_parsed(self, monkeypatch):
        import playwright_cookie_consent as m

        monkeypatch.setattr(m, "fetch_html_with_cookie_consent", lambda *a, **k: "")
        parsed = {"page_text": "ciasteczka akceptuj", "emails": []}
        out = apply_playwright_cookie_fallback(
            "https://firma.pl",
            _LOG,
            "<html>cookiebot</html>",
            parsed,
            parse_contacts_from_html=lambda u, h: {"emails": ["x@y.pl"]},
        )
        assert out is parsed


# >>> OPIS FUNKCJI: klasa TestDebugCookieConsent
# Grupa testów: funkcje diagnostyczne.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestDebugCookieConsent:
    # >>> OPIS FUNKCJI: funkcja TestDebugCookieConsent.test_debug_decision_with_banner
    # Test: debug_cookie_decision dla tekstu z bannerem: would_run_playwright=True, trafione markery PL, przycisk do kliknięcia.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_debug_decision_with_banner(self):
        d = debug_cookie_consent_decision(
            "Akceptuj wszystkie cookies",
            '<div class="borlabs-cookie"></div>',
            button_label="Akceptuj wszystkie",
        )
        assert d["would_run_playwright"] is True
        assert d["has_cookie_signal"] is True
        assert "ciasteczka" in d["pl_marker_hits"] or "akceptuj wszystkie" in d["pl_marker_hits"]
        assert d["button"]["would_click"] is True
        assert d["button"]["is_reject"] is False

    # >>> OPIS FUNKCJI: funkcja TestDebugCookieConsent.test_debug_decision_no_banner
    # Test: bez bannera: would_run_playwright=False.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_debug_decision_no_banner(self):
        d = debug_cookie_consent_decision("Spedycja FTL Głogów bez banera")
        assert d["would_run_playwright"] is False
        assert d["has_cookie_signal"] is False

    # >>> OPIS FUNKCJI: funkcja TestDebugCookieConsent.test_debug_accept_label_reject
    # Test: etykieta odrzucająca: is_reject=True, would_click=False.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_debug_accept_label_reject(self):
        d = debug_accept_label("Tylko niezbędne")
        assert d["is_reject"] is True
        assert d["would_click"] is False

    # >>> OPIS FUNKCJI: funkcja TestDebugCookieConsent.test_cli_debug_json
    # Test: _cli_debug zwraca 0 i wypisuje JSON z would_run_playwright/would_click.
    # Parametry: self, capsys. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: przechwytywanie stdout (capsys). Błędy: AssertionError przy niespełnionej asercji.
    def test_cli_debug_json(self, capsys):
        assert _cli_debug(["--text", "ciasteczka", "--label", "Akceptuj"]) == 0
        out = capsys.readouterr().out
        assert '"would_run_playwright": true' in out
        assert '"would_click": true' in out

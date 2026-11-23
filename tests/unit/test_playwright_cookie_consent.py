# -*- coding: utf-8 -*-
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


class TestShouldUsePlaywrightCookieFallback:
    def test_polish_banner_text(self):
        assert should_use_playwright_cookie_fallback(
            "Ta strona używa ciasteczek. Akceptuj wszystkie."
        )

    def test_cmp_html_hint(self):
        assert should_use_playwright_cookie_fallback(
            "",
            html='<div id="CybotCookiebotDialogBodyButtonAccept"></div>',
        )

    def test_borlabs_marker(self):
        assert should_use_playwright_cookie_fallback(
            "Zarządzaj zgodami",
            html='<div class="borlabs-cookie"></div>',
        )

    def test_no_cookie_signal(self):
        assert not should_use_playwright_cookie_fallback(
            "Firma spedycyjna FTL Głogów. Kontakt: biuro@example.pl"
        )

    def test_fallback_en_accept_all(self):
        assert should_use_playwright_cookie_fallback("Please accept all cookies to continue")


class TestAcceptRejectLabels:
    def test_accept_exact_and_regex(self):
        assert _is_polish_accept_label("Akceptuj wszystkie")
        assert _is_polish_accept_label("Zgadzam się")
        assert _is_polish_accept_label("Rozumiem")
        assert _is_polish_accept_label("akceptuj cookies")

    def test_reject_and_settings_blocked(self):
        assert _is_reject_label("Odrzuć")
        assert _is_reject_label("Tylko niezbędne")
        assert _is_reject_label("Ustawienia cookies")
        assert not _is_polish_accept_label("Tylko niezbędne")
        assert not _is_polish_accept_label("Odmów")

    def test_long_rodo_paragraph_not_accept(self):
        blob = "Akceptuj " + ("rodo " * 40)
        assert len(blob) > 90
        assert not _is_polish_accept_label(blob)

    def test_empty_label(self):
        assert not _is_polish_accept_label("")
        assert not _is_reject_label("")


class TestApplyPlaywrightCookieFallback:
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

    def test_no_banner_skips_playwright(self, monkeypatch):
        import playwright_cookie_consent as m

        called = {"n": 0}

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


class TestDebugCookieConsent:
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

    def test_debug_decision_no_banner(self):
        d = debug_cookie_consent_decision("Spedycja FTL Głogów bez banera")
        assert d["would_run_playwright"] is False
        assert d["has_cookie_signal"] is False

    def test_debug_accept_label_reject(self):
        d = debug_accept_label("Tylko niezbędne")
        assert d["is_reject"] is True
        assert d["would_click"] is False

    def test_cli_debug_json(self, capsys):
        assert _cli_debug(["--text", "ciasteczka", "--label", "Akceptuj"]) == 0
        out = capsys.readouterr().out
        assert '"would_run_playwright": true' in out
        assert '"would_click": true' in out

# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# MODUŁ TESTOWY: tests/test_claude_campaign.py
# CO ROBI: testy warstwy Claude bez live API: parsowanie odpowiedzi cleanupu wiersza, weryfikacja strony (page verify), limity dzienne Claude, regex e-maili (do 50 znaków części lokalnej) oraz cleanup wiersza z fallbackiem regex.
# ROLA W PIPELINE: zabezpieczenie regresji kroków 'Claude verify' i 'row cleanup' pipeline PL FAS (claude_page_verify, claude_client, claude_row_cleanup, pl_fas_spedycja_scraper).
# ZALEŻNOŚCI: unittest, unittest.mock (MagicMock, patch), claude_row_cleanup, claude_page_verify, claude_client, pl_fas_spedycja_scraper; ścieżki repo dodawane do sys.path.
# WEJŚCIE/WYJŚCIE: Moduł nie przyjmuje argumentów CLI; pytest/unittest odkrywa i uruchamia testy; nic nie zwraca (wynik = zielone/czerwone testy).
# ============================================================
"""Testy warstwy Claude (bez live API) — PL FAS."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
LIBS = ROOT / "libs"
for p in (str(ROOT), str(LIBS)):
    if p not in sys.path:
        sys.path.insert(0, p)

from claude_row_cleanup import parse_claude_row_cleanup_response


# >>> OPIS FUNKCJI: klasa ClaudeRowCleanupTest
# Grupa testów: parser odpowiedzi JSON cleanupu wiersza (claude_row_cleanup).
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class ClaudeRowCleanupTest(unittest.TestCase):
    # >>> OPIS FUNKCJI: funkcja ClaudeRowCleanupTest.test_parse_cleanup_json
    # Test: parse_claude_row_cleanup_response czyta klucze company_name_clean, bundesland, handelsketten z poprawnego JSON-a.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_parse_cleanup_json(self):
        raw = (
            '{"company_name_clean":"Trans Spedycja Sp. z o.o.",'
            '"address":"ul. Test 1, 00-001 Warszawa",'
            '"phone":"+48 22 111 22 33","website":"https://trans-spedycja.pl",'
            '"bundesland":"Mazowieckie","handelsketten":"ftl, ltl"}'
        )
        parsed = parse_claude_row_cleanup_response(raw)
        self.assertEqual(parsed["company_name_clean"], "Trans Spedycja Sp. z o.o.")
        self.assertEqual(parsed["bundesland"], "Mazowieckie")
        self.assertEqual(parsed["handelsketten"], "ftl, ltl")

    # >>> OPIS FUNKCJI: funkcja ClaudeRowCleanupTest.test_parse_cleanup_pl_aliases
    # Test: parser akceptuje polskie aliasy kluczy (wojewodztwo → bundesland, segmenty → handelsketten).
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_parse_cleanup_pl_aliases(self):
        raw = (
            '{"company_name_clean":"Euro Fracht S.A.",'
            '"address":"","phone":"","website":"https://euro-fracht.pl",'
            '"wojewodztwo":"Dolnoslaskie","segmenty":"ftl, adr"}'
        )
        parsed = parse_claude_row_cleanup_response(raw)
        self.assertEqual(parsed["bundesland"], "Dolnoslaskie")
        self.assertEqual(parsed["handelsketten"], "ftl, adr")


# >>> OPIS FUNKCJI: klasa ClaudePageVerifyIntegrationTest
# Grupa testów: integracja weryfikacji strony przez Claude, limitów API i cleanupu wiersza (z mockami).
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class ClaudePageVerifyIntegrationTest(unittest.TestCase):
    # >>> OPIS FUNKCJI: funkcja ClaudePageVerifyIntegrationTest.test_claude_verify_accepts_spedycja_ftl
    # Test: claude_verify_company_page akceptuje firmę spedycyjną FTL/LTL (verified=True, is_small_firm=True).
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: patche unittest.mock podmieniają klienta Claude/klucz API — brak połączeń sieciowych. Błędy: AssertionError przy niespełnionej asercji.
    def test_claude_verify_accepts_spedycja_ftl(self):
        from claude_page_verify import claude_verify_company_page

        response_json = (
            '{"is_gu": true, "has_retail_context": true, '
            '"primary_role": "Spedytor", '
            '"matched_gu_keywords": ["spedycja"], '
            '"matched_retail_keywords": ["transport drogowy"], '
            '"matched_chains": ["ftl", "ltl"], '
            '"matched_negative_keywords": [], '
            '"is_small_firm": true, '
            '"reason": "Oferta FTL/LTL Europa"}'
        )
        with patch("claude_page_verify.get_anthropic_api_key", return_value="test-key"):
            with patch(
                "claude_page_verify.claude_generate_text",
                return_value=(response_json, "claude-sonnet-test"),
            ):
                result = claude_verify_company_page(
                    "Trans Spedycja Sp. z o.o.",
                    "https://trans-spedycja.pl",
                    "Firma spedycyjna. Organizujemy transport drogowy FTL LTL Europa. "
                    "Oferta fracht, ADR. Biuro rodzinne, 40 osób.",
                    logger=MagicMock(),
                    cache={},
                )
        self.assertIsNotNone(result)
        self.assertTrue(result["verified"])
        self.assertTrue(result["is_small_firm"])
        self.assertTrue(
            "ftl" in result["retail_chains"] or "ltl" in result["retail_chains"]
        )

    # >>> OPIS FUNKCJI: funkcja ClaudePageVerifyIntegrationTest.test_claude_verify_rejects_large_3pl_not_small
    # Test: duży 3PL (is_small_firm=false) jest odrzucany z powodem claude_nie_mala_firma.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: patche unittest.mock podmieniają klienta Claude/klucz API — brak połączeń sieciowych. Błędy: AssertionError przy niespełnionej asercji.
    def test_claude_verify_rejects_large_3pl_not_small(self):
        from claude_page_verify import claude_verify_company_page

        response_json = (
            '{"is_gu": true, "has_retail_context": true, '
            '"primary_role": "Spedytor", '
            '"matched_gu_keywords": ["spedycja"], '
            '"matched_retail_keywords": ["transport drogowy"], '
            '"matched_chains": ["ftl"], '
            '"matched_negative_keywords": [], '
            '"is_small_firm": false, '
            '"reason": "Globalny 3PL"}'
        )
        with patch("claude_page_verify.get_anthropic_api_key", return_value="test-key"):
            with patch(
                "claude_page_verify.claude_generate_text",
                return_value=(response_json, "claude-sonnet-test"),
            ):
                # URL bez hard-reject domeny 3PL — testuje flagę is_small_firm
                result = claude_verify_company_page(
                    "Mega Forwarder SA",
                    "https://mega-forwarder-example.pl",
                    "Mega Forwarder — firma spedycyjna. Transport drogowy FTL Europa. "
                    "Tysiące pracowników, holding międzynarodowy.",
                    logger=MagicMock(),
                    cache={},
                )
        self.assertIsNotNone(result)
        self.assertFalse(result["verified"])
        self.assertFalse(result["is_small_firm"])
        self.assertEqual(result["verification_reason"], "claude_nie_mala_firma")

    # >>> OPIS FUNKCJI: funkcja ClaudePageVerifyIntegrationTest.test_claude_reserve_blocks_api_at_buffer_when_limited
    # Test: w trybie limitowanym wywołanie claude_generate_text przy wyczerpanym budżecie (dzienny limit − rezerwa discovery) kończy się RuntimeError.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: patche unittest.mock podmieniają klienta Claude/klucz API — brak połączeń sieciowych; modyfikuje globalną konfigurację limitów claude_client (configure_claude_limits). Błędy: AssertionError; RuntimeError jest oczekiwany wewnątrz assertRaises.
    def test_claude_reserve_blocks_api_at_buffer_when_limited(self):
        import claude_client as cc

        cc.configure_claude_limits(daily_limit=3000, reserve=1000, unlimited=False)
        used = cc.CLAUDE_DAILY_LIMIT - cc.CLAUDE_DISCOVERY_RESERVE
        cache = {"claude_daily": {"2099-01-01": used}}
        with patch("claude_client._campaign_today", return_value="2099-01-01"):
            self.assertTrue(cc.is_claude_limit_reached_today(cache))
            with patch("claude_client.get_anthropic_api_key", return_value="test-key"):
                with self.assertRaises(RuntimeError):
                    cc.claude_generate_text("ping", MagicMock(), cache=cache)

    # >>> OPIS FUNKCJI: funkcja ClaudePageVerifyIntegrationTest.test_claude_unlimited_skips_daily_cap
    # Test: w trybie unlimited limit dzienny nie blokuje zapytań, a licznik dzienny pozostaje bez zmian.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: patche unittest.mock podmieniają klienta Claude/klucz API — brak połączeń sieciowych; modyfikuje globalną konfigurację limitów claude_client. Błędy: AssertionError przy niespełnionej asercji.
    def test_claude_unlimited_skips_daily_cap(self):
        import claude_client as cc

        cc.configure_claude_limits(daily_limit=3000, reserve=1000, unlimited=True)
        cache = {"claude_daily": {"2099-01-01": cc.CLAUDE_DAILY_LIMIT}}
        with patch("claude_client._campaign_today", return_value="2099-01-01"):
            self.assertFalse(cc.is_claude_limit_reached_today(cache))
            with patch("claude_client.get_anthropic_api_key", return_value="test-key"):
                with patch("claude_client.requests.post") as mock_post:
                    mock_post.return_value.status_code = 200
                    mock_post.return_value.json.return_value = {
                        "content": [
                            {
                                "type": "text",
                                "text": '{"company_name_clean":"OK Sp. z o.o."}',
                            }
                        ]
                    }
                    text, _ = cc.claude_generate_text("cleanup", MagicMock(), cache=cache)
        self.assertIn("OK Sp. z o.o.", text)
        self.assertEqual(cache["claude_daily"]["2099-01-01"], cc.CLAUDE_DAILY_LIMIT)

    # >>> OPIS FUNKCJI: funkcja ClaudePageVerifyIntegrationTest.test_wide_email_regex_50_chars_local
    # Test: regex e-maili przyjmuje część lokalną o długości 50 znaków i odrzuca 51 znaków.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_wide_email_regex_50_chars_local(self):
        import pl_fas_spedycja_scraper as scraper

        local = "a" * 50
        email = f"{local}@example.pl"
        found = scraper._find_emails_in_text_regex(f"Kontakt: {email}")
        self.assertIn(email.lower(), found)
        too_long = f"{'b' * 51}@example.pl"
        found_long = scraper._find_emails_in_text_regex(f"Kontakt: {too_long}")
        self.assertNotIn(too_long.lower(), found_long)

    # >>> OPIS FUNKCJI: funkcja ClaudePageVerifyIntegrationTest.test_row_cleanup_claude_then_regex
    # Test: cleanup wiersza: wynik Claude (nazwa, adres, telefon) jest dopełniony regexem e-mail/telefon ze snippeta strony i trafia do kolumn Excela.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: patche unittest.mock podmieniają klienta Claude/klucz API — brak połączeń sieciowych. Błędy: AssertionError przy niespełnionej asercji.
    def test_row_cleanup_claude_then_regex(self):
        import pl_fas_spedycja_scraper as scraper

        row = {
            "url": "https://trans-spedycja.pl",
            "nazwa": "Trans Spedycja",
            "page_snippet": "Impressum biuro@trans-spedycja.pl Tel +48 22 111 22 33",
            "email_target": "",
            "telefon": "",
        }
        with patch(
            "claude_row_cleanup.claude_cleanup_row_fields",
            return_value={
                "company_name_clean": "Trans Spedycja Sp. z o.o.",
                "address": "ul. Test 1, 00-001 Warszawa",
                "phone": "+48 22 111 22 33",
                "website": "https://trans-spedycja.pl",
                "bundesland": "Mazowieckie",
                "handelsketten": "ftl, ltl",
                "url": "https://trans-spedycja.pl",
            },
        ):
            with patch.object(scraper, "get_anthropic_api_key", return_value="key"):
                out = scraper.enrich_row_with_claude_cleanup(
                    dict(row), MagicMock(), {}
                )
        self.assertEqual(out["company_name_clean"], "Trans Spedycja Sp. z o.o.")
        self.assertEqual(out["email_target"], "biuro@trans-spedycja.pl")
        self.assertTrue(
            "22111" in out["telefon"].replace(" ", "")
            or "+48" in out["telefon"]
        )
        self.assertEqual(out["retail_chains_found"], "ftl, ltl")
        excel = scraper.row_to_excel_kontakte_columns(out)
        self.assertEqual(excel["Nazwa firmy"], "Trans Spedycja Sp. z o.o.")
        self.assertEqual(excel["Segmenty"], "ftl, ltl")
        self.assertIn("Województwo", excel)
        self.assertEqual(excel["Województwo"], "Mazowieckie")


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# MODUŁ TESTOWY: tests/test_claude_llm_campaign.py
# CO ROBI: testy fraz discovery Claude (parsowanie i walidacja), narzędzi ekstrakcji kontaktów oraz werdyktu weryfikacji strony (parse_page_verify_response, apply_page_verdict) dla kampanii PL FAS.
# ROLA W PIPELINE: pilnuje higieny discovery (tylko spedycja + segment, bez kurierów i legacy DE) oraz bramek ICP po odpowiedzi LLM.
# ZALEŻNOŚCI: unittest, claude_discovery_terms, contact_extract_utils, page_verify, pl_fas_spedycja_scraper (find_emails_in_text).
# WEJŚCIE/WYJŚCIE: Moduł nie przyjmuje argumentów CLI; pytest/unittest odkrywa i uruchamia testy; nic nie zwraca (wynik = zielone/czerwone testy).
# ============================================================
"""Testy Claude discovery + page verify (bez live API) — PL FAS."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIBS = ROOT / "libs"
for p in (str(ROOT), str(LIBS)):
    if p not in sys.path:
        sys.path.insert(0, p)

from claude_discovery_terms import parse_discovery_term_lines, validate_discovery_term
from contact_extract_utils import normalize_phone_contact, parse_contact_extract_response
from page_verify import (
    apply_page_verdict,
    is_forwarder_ok_from_llm,
    parse_page_verify_response,
)


# >>> OPIS FUNKCJI: klasa ClaudeDiscoveryTermsTest
# Grupa testów: parsowanie i walidacja fraz discovery.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class ClaudeDiscoveryTermsTest(unittest.TestCase):
    # >>> OPIS FUNKCJI: funkcja ClaudeDiscoveryTermsTest.test_parse_lines_strips_numbering
    # Test: parse_discovery_term_lines usuwa numerację i zwraca 2 frazy.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_parse_lines_strips_numbering(self):
        raw = "1. spedycja FTL Warszawa\nfirma spedycyjna Radom LTL"
        lines = parse_discovery_term_lines(raw)
        self.assertEqual(len(lines), 2)
        self.assertIn("spedycja", lines[0].lower())

    # >>> OPIS FUNKCJI: funkcja ClaudeDiscoveryTermsTest.test_validate_accepts_spedycja_with_segment
    # Test: validate_discovery_term akceptuje frazy ze spedycją i segmentem (FTL/LTL).
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_validate_accepts_spedycja_with_segment(self):
        self.assertTrue(validate_discovery_term("spedycja FTL Warszawa"))
        self.assertTrue(validate_discovery_term("firma spedycyjna Głogów LTL"))

    # >>> OPIS FUNKCJI: funkcja ClaudeDiscoveryTermsTest.test_validate_rejects_without_segment
    # Test: fraza bez segmentu (FTL/LTL…) jest odrzucana.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_validate_rejects_without_segment(self):
        self.assertFalse(validate_discovery_term("firma spedycyjna Warszawa"))

    # >>> OPIS FUNKCJI: funkcja ClaudeDiscoveryTermsTest.test_validate_rejects_courier_or_generic
    # Test: frazy o kurierach (InPost) i zbyt ogólne ('transport Warszawa') są odrzucane.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_validate_rejects_courier_or_generic(self):
        self.assertFalse(validate_discovery_term("InPost paczkomaty Warszawa"))
        self.assertFalse(validate_discovery_term("transport Warszawa"))

    # >>> OPIS FUNKCJI: funkcja ClaudeDiscoveryTermsTest.test_validate_rejects_legacy_de_gu
    # Test: frazy legacy DE (Generalunternehmer/Filialbau/Aldi) i hybrydy PL+DE są odrzucane.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_validate_rejects_legacy_de_gu(self):
        self.assertFalse(
            validate_discovery_term("Generalunternehmer Filialbau Hannover Aldi markt")
        )
        # Hybryda PL+DE też odpada (higiena discovery)
        self.assertFalse(
            validate_discovery_term("spedycja bauunternehmen FTL Warszawa")
        )
        self.assertFalse(
            validate_discovery_term("spedycja filialbau LTL Kraków")
        )


# >>> OPIS FUNKCJI: klasa ContactExtractUtilsTest
# Grupa testów: narzędzia ekstrakcji kontaktów (parsowanie JSON, normalizacja telefonu).
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class ContactExtractUtilsTest(unittest.TestCase):
    # >>> OPIS FUNKCJI: funkcja ContactExtractUtilsTest.test_parse_contact_json
    # Test: parse_contact_extract_response zwraca nazwę, e-maile i telefony, odfiltrowując adres z katalogu 11880.de.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_parse_contact_json(self):
        raw = (
            '{"company_name": "Trans Sp. z o.o.", "emails": ["biuro@trans.pl", "x@11880.de"], '
            '"phones": ["+48 22 111 22 33"], "reason": "Kontakt"}'
        )
        parsed = parse_contact_extract_response(raw)
        self.assertEqual(parsed["company_name"], "Trans Sp. z o.o.")
        self.assertIn("biuro@trans.pl", parsed["emails"])
        self.assertNotIn("x@11880.de", parsed["emails"])
        self.assertTrue(parsed["phones"])

    # >>> OPIS FUNKCJI: funkcja ContactExtractUtilsTest.test_normalize_phone_rejects_year
    # Test: normalize_phone_contact odrzuca ciąg będący rokiem (np. '2024').
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_normalize_phone_rejects_year(self):
        self.assertEqual(normalize_phone_contact("2024"), "")

    # >>> OPIS FUNKCJI: funkcja ContactExtractUtilsTest.test_find_emails_uses_regex_only
    # Test: find_emails_in_text znajduje adres wyłącznie regexem w zwykłym tekście.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_find_emails_uses_regex_only(self):
        import pl_fas_spedycja_scraper as scraper

        found = scraper.find_emails_in_text("Kontakt: biuro@trans-spedycja.pl Dane firmy")
        self.assertIn("biuro@trans-spedycja.pl", found)


# >>> OPIS FUNKCJI: klasa PageVerifyTest
# Grupa testów: parsowanie odpowiedzi page verify i bramki apply_page_verdict.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class PageVerifyTest(unittest.TestCase):
    # >>> OPIS FUNKCJI: funkcja PageVerifyTest.test_parse_json_response
    # Test: parse_page_verify_response czyta is_gu, primary_role i matched_chains.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_parse_json_response(self):
        text = (
            '{"is_gu": true, "has_retail_context": true, '
            '"primary_role": "Spedytor", '
            '"matched_gu_keywords": ["spedycja"], '
            '"matched_retail_keywords": ["transport drogowy"], '
            '"matched_chains": ["ftl"], '
            '"matched_negative_keywords": [], '
            '"is_small_firm": true, '
            '"reason": "Oferta FTL Europa"}'
        )
        parsed = parse_page_verify_response(text)
        self.assertTrue(parsed["is_gu"])
        self.assertEqual(parsed["primary_role"], "Spedytor")
        self.assertEqual(parsed["matched_chains"], ["ftl"])

    # >>> OPIS FUNKCJI: funkcja PageVerifyTest.test_apply_verdict_accepts_spedycja_ftl
    # Test: apply_page_verdict akceptuje spedytora z FTL/LTL (powód zawiera 'claude').
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_apply_verdict_accepts_spedycja_ftl(self):
        llm = {
            "is_gu": True,
            "has_retail_context": True,
            "primary_role": "Spedytor",
            "matched_gu_keywords": ["spedycja"],
            "matched_retail_keywords": ["transport drogowy"],
            "matched_chains": ["ftl", "ltl"],
            "matched_negative_keywords": [],
            "is_small_firm": True,
            "reason": "OK",
        }
        ok, reason, chains = apply_page_verdict(
            llm,
            page_text=(
                "Firma spedycyjna. Organizujemy transport drogowy FTL LTL Europa. "
                "Oferta fracht ADR."
            ),
        )
        self.assertTrue(ok)
        self.assertIn("claude", reason)
        self.assertTrue("ftl" in chains or "ltl" in chains)

    def test_apply_verdict_accepts_transport_firm_when_claude_sets_is_gu(self):
        # Warstwa 2: Claude stawia is_gu=true dla firmy transportowej (bez słowa spedycja).
        # Bramki po Claude bez poluzowania — spełnione przez JSON Claude.
        llm = {
            "is_gu": True,
            "has_retail_context": True,
            "primary_role": "FirmaTransportowa",
            "matched_gu_keywords": ["firma transportowa"],
            "matched_retail_keywords": ["transport drogowy", "flota"],
            "matched_chains": ["ftl", "europa"],
            "matched_negative_keywords": [],
            "is_small_firm": True,
            "reason": "Firma transportowa FTL Europa",
        }
        ok, reason, chains = apply_page_verdict(
            llm,
            page_text=(
                "Usługi transportowe. Transport drogowy FTL Europa. "
                "Flota naczep. Oferty pracy kierowca."
            ),
            require_forwarder_role=False,
        )
        self.assertTrue(ok, reason)
        self.assertIn("claude", reason)
        self.assertIn("ftl", chains)

    def test_apply_verdict_rejects_when_claude_says_no_even_if_page_has_evidence(self):
        # Claude = sędzia: is_gu=false → reject, bez dogrywki tekstem (stara bramka 4 OUT).
        llm = {
            "is_gu": False,
            "has_retail_context": False,
            "primary_role": "",
            "matched_gu_keywords": [],
            "matched_retail_keywords": [],
            "matched_chains": [],
            "matched_negative_keywords": [],
            "is_small_firm": True,
            "reason": "niepewne",
        }
        page = (
            "Firma spedycyjna — spedycja drogowa. Transport drogowy FTL i LTL "
            "na Europę. Organizacja przewozu, flota naczep."
        )
        ok, reason, _chains = apply_page_verdict(
            llm,
            page_text=page,
            require_forwarder_role=True,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "claude_brak_roli_spedycji")

    def test_apply_verdict_trusts_claude_is_gu_without_segment_gate(self):
        # Po usunięciu bramek 6–8: is_gu=true wystarczy (segmenty tylko do Excela).
        llm = {
            "is_gu": True,
            "has_retail_context": True,
            "is_small_firm": True,
            "primary_role": "Spedytor",
            "matched_gu_keywords": ["spedycja"],
            "matched_retail_keywords": ["logistyka"],
            "matched_chains": [],
            "matched_negative_keywords": [],
            "reason": "sama logistyka",
        }
        page = "Firma spedycyjna w Polsce. Świadczymy usługi logistyczne regionalnie."
        ok, reason, _chains = apply_page_verdict(
            llm,
            page_text=page,
            require_forwarder_role=True,
        )
        self.assertTrue(ok, reason)
        self.assertIn("claude", reason)

    # >>> OPIS FUNKCJI: funkcja PageVerifyTest.test_apply_verdict_accepts_adr_europa_segments
    # Test: segmenty ADR/Europa wystarczają do akceptacji dla freight forwardera.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_apply_verdict_accepts_adr_europa_segments(self):
        llm = {
            "is_gu": True,
            "has_retail_context": True,
            "is_small_firm": True,
            "primary_role": "FreightForwarder",
            "matched_gu_keywords": ["freight forwarder"],
            "matched_retail_keywords": ["organizacja transportu"],
            "matched_chains": ["adr", "europa"],
            "matched_negative_keywords": [],
            "reason": "ADR Europa",
        }
        page = (
            "Freight forwarding. Organizacja transportu ADR, linie Europa. "
            "Biuro spedycyjne PL–DE."
        )
        ok, reason, chains = apply_page_verdict(llm, page_text=page)
        self.assertTrue(ok)
        self.assertTrue("adr" in chains or "europa" in chains)

    # >>> OPIS FUNKCJI: funkcja PageVerifyTest.test_apply_verdict_rejects_large_firm_when_claude_says_not_small
    # Test: is_small_firm=false → odrzut z powodem claude_nie_mala_firma.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_apply_verdict_rejects_large_firm_when_claude_says_not_small(self):
        llm = {
            "is_gu": True,
            "has_retail_context": True,
            "is_small_firm": False,
            "primary_role": "Spedytor",
            "matched_gu_keywords": ["spedycja"],
            "matched_retail_keywords": ["ftl"],
            "matched_chains": ["ftl"],
            "matched_negative_keywords": [],
            "reason": "3PL",
        }
        ok, reason, _ = apply_page_verdict(
            llm,
            page_text=(
                "Raben Group — międzynarodowa spedycja FTL Europa, tysiące pracowników."
            ),
            require_small_firm=True,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "claude_nie_mala_firma")

    # >>> OPIS FUNKCJI: funkcja PageVerifyTest.test_apply_verdict_rejects_courier
    # Test: firma kurierska jest odrzucana.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_apply_verdict_rejects_courier(self):
        llm = {
            "is_gu": True,
            "has_retail_context": True,
            "is_small_firm": True,
            "primary_role": "Kurier",
            "matched_gu_keywords": [],
            "matched_retail_keywords": [],
            "matched_chains": ["ftl"],
            "matched_negative_keywords": [],
            "reason": "paczki",
        }
        page = "Nadaj paczkę InPost DPD. Kurier last mile Warszawa."
        ok, reason, _ = apply_page_verdict(llm, page_text=page)
        self.assertFalse(ok)
        self.assertTrue(
            "kurier" in reason.lower() or "claude_role" in reason.lower()
        )

    # >>> OPIS FUNKCJI: funkcja PageVerifyTest.test_apply_verdict_rejects_exchange_operator_context
    # Test: operator giełdy transportowej (kontekst) jest odrzucany.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_apply_verdict_rejects_exchange_operator_context(self):
        llm = {
            "is_gu": True,
            "has_retail_context": True,
            "primary_role": "GieldaFrachtowa",
            "matched_gu_keywords": [],
            "matched_retail_keywords": [],
            "matched_chains": [],
            "matched_negative_keywords": [],
            "reason": "giełda",
        }
        ok, reason, _ = apply_page_verdict(
            llm,
            page_text="Timocom giełda frachtów — znajdź ładunek Trans.eu",
            require_forwarder_role=True,
        )
        self.assertFalse(ok)

    # >>> OPIS FUNKCJI: funkcja PageVerifyTest.test_is_forwarder_ok_reads_legacy_is_gu_key
    # Test: is_forwarder_ok_from_llm czyta legacy klucz is_gu (True/False/brak).
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_is_forwarder_ok_reads_legacy_is_gu_key(self):
        self.assertTrue(is_forwarder_ok_from_llm({"is_gu": True}))
        self.assertFalse(is_forwarder_ok_from_llm({"is_gu": False}))
        self.assertFalse(is_forwarder_ok_from_llm({}))

    # >>> OPIS FUNKCJI: funkcja PageVerifyTest.test_require_generalunternehmer_alias_still_works
    # Test: legacy alias require_generalunternehmer nadpisuje require_forwarder_role i werdykt nadal jest akceptowany.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_require_generalunternehmer_alias_still_works(self):
        """Alias legacy nadpisuje require_forwarder_role."""
        llm = {
            "is_gu": True,
            "has_retail_context": True,
            "is_small_firm": True,
            "primary_role": "Spedytor",
            "matched_gu_keywords": ["spedycja"],
            "matched_retail_keywords": [],
            "matched_chains": ["ftl"],
            "matched_negative_keywords": [],
            "reason": "alias",
        }
        page = "Firma spedycyjna FTL Polska. Transport drogowy, flota."
        ok, _, chains = apply_page_verdict(
            llm,
            page_text=page,
            require_forwarder_role=False,
            require_generalunternehmer=True,
        )
        self.assertTrue(ok)
        self.assertIn("ftl", chains)


if __name__ == "__main__":
    unittest.main(verbosity=2)

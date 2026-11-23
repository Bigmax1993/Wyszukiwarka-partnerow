# -*- coding: utf-8 -*-
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


class ClaudeDiscoveryTermsTest(unittest.TestCase):
    def test_parse_lines_strips_numbering(self):
        raw = "1. spedycja FTL Warszawa\nfirma spedycyjna Radom LTL"
        lines = parse_discovery_term_lines(raw)
        self.assertEqual(len(lines), 2)
        self.assertIn("spedycja", lines[0].lower())

    def test_validate_accepts_spedycja_with_segment(self):
        self.assertTrue(validate_discovery_term("spedycja FTL Warszawa"))
        self.assertTrue(validate_discovery_term("firma spedycyjna Głogów LTL"))

    def test_validate_rejects_without_segment(self):
        self.assertFalse(validate_discovery_term("firma spedycyjna Warszawa"))

    def test_validate_rejects_courier_or_generic(self):
        self.assertFalse(validate_discovery_term("InPost paczkomaty Warszawa"))
        self.assertFalse(validate_discovery_term("transport Warszawa"))

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


class ContactExtractUtilsTest(unittest.TestCase):
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

    def test_normalize_phone_rejects_year(self):
        self.assertEqual(normalize_phone_contact("2024"), "")

    def test_find_emails_uses_regex_only(self):
        import pl_fas_spedycja_scraper as scraper

        found = scraper.find_emails_in_text("Kontakt: biuro@trans-spedycja.pl Dane firmy")
        self.assertIn("biuro@trans-spedycja.pl", found)


class PageVerifyTest(unittest.TestCase):
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

    def test_apply_verdict_accepts_when_claude_missed_role_but_page_has_evidence(self):
        # primary_role puste — nie wpada w REJECT_PRIMARY_ROLES („Inne”)
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
        ok, reason, chains = apply_page_verdict(
            llm,
            page_text=page,
            require_forwarder_role=True,
        )
        self.assertTrue(ok)
        self.assertTrue(any(c in chains for c in ("ftl", "ltl", "europa")))

    def test_apply_verdict_rejects_without_segment(self):
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
        ok, reason, chains = apply_page_verdict(
            llm,
            page_text=page,
            require_forwarder_role=True,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "brak_segmentu_ftl_ltl")
        self.assertEqual(chains, [])

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

    def test_is_forwarder_ok_reads_legacy_is_gu_key(self):
        self.assertTrue(is_forwarder_ok_from_llm({"is_gu": True}))
        self.assertFalse(is_forwarder_ok_from_llm({"is_gu": False}))
        self.assertFalse(is_forwarder_ok_from_llm({}))

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

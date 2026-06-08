# -*- coding: utf-8 -*-
"""Testy modułów Gemini discovery + page verify (bez live API)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gemini_discovery_terms import (
    parse_gemini_term_lines,
    validate_discovery_term,
)
from gemini_contact_extract import (
    normalize_phone_contact,
    parse_gemini_contact_extract_response,
)
from gemini_page_verify import (
    apply_gemini_page_verdict,
    parse_gemini_page_verify_response,
)


class GeminiDiscoveryTermsTest(unittest.TestCase):
    def test_parse_lines_strips_numbering(self):
        raw = "1. Generalunternehmer Filialbau Hannover\nGU Supermarktbau Braunschweig"
        lines = parse_gemini_term_lines(raw)
        self.assertEqual(len(lines), 2)
        self.assertIn("Generalunternehmer", lines[0])

    def test_validate_accepts_gu_term(self):
        self.assertTrue(
            validate_discovery_term("Generalunternehmer Filialbau Hannover")
        )

    def test_validate_rejects_ladenbau_only(self):
        self.assertFalse(validate_discovery_term("Ladenbau Hannover GmbH"))

    def test_validate_rejects_bauunternehmen_only(self):
        self.assertFalse(validate_discovery_term("Bauunternehmen Gewerbebau Hannover"))


class GeminiContactExtractTest(unittest.TestCase):
    def test_parse_contact_json(self):
        raw = (
            '{"company_name": "Bau GmbH", "emails": ["info@bau.de", "x@11880.de"], '
            '"phones": ["+49 231 1234567"], "reason": "Impressum"}'
        )
        parsed = parse_gemini_contact_extract_response(raw)
        self.assertEqual(parsed["company_name"], "Bau GmbH")
        self.assertIn("info@bau.de", parsed["emails"])
        self.assertNotIn("x@11880.de", parsed["emails"])
        self.assertTrue(parsed["phones"])

    def test_normalize_phone_rejects_year(self):
        self.assertEqual(normalize_phone_contact("2024"), "")


class GeminiPageVerifyTest(unittest.TestCase):
    def test_parse_json_response(self):
        text = (
            '{"is_gu": true, "has_retail_context": true, '
            '"primary_role": "Generalunternehmer", '
            '"matched_gu_keywords": ["generalunternehmer"], '
            '"matched_retail_keywords": ["filialbau"], '
            '"matched_chains": ["rewe"], '
            '"matched_negative_keywords": [], '
            '"reason": "GU mit Filialbau"}'
        )
        parsed = parse_gemini_page_verify_response(text)
        self.assertTrue(parsed["is_gu"])
        self.assertEqual(parsed["primary_role"], "Generalunternehmer")

    def test_apply_verdict_accepts_gu_retail(self):
        gemini = {
            "is_gu": True,
            "has_retail_context": True,
            "primary_role": "Generalunternehmer",
            "matched_gu_keywords": ["generalunternehmer"],
            "matched_retail_keywords": ["filialbau"],
            "matched_chains": ["rewe"],
            "matched_negative_keywords": [],
            "reason": "OK",
        }
        ok, reason, chains = apply_gemini_page_verdict(
            gemini,
            page_text="Wir sind Generalunternehmer für Filialbau und Rewe Projekte.",
        )
        self.assertTrue(ok)
        self.assertIn("gemini", reason)
        self.assertIn("rewe", chains)

    def test_apply_verdict_rejects_operator_context(self):
        gemini = {
            "is_gu": True,
            "has_retail_context": True,
            "primary_role": "Betreiber",
            "matched_gu_keywords": [],
            "matched_retail_keywords": [],
            "matched_chains": [],
            "matched_negative_keywords": [],
            "reason": "Markt",
        }
        ok, reason, _ = apply_gemini_page_verdict(
            gemini,
            page_text="REWE Markt Öffnungszeiten Prospekt Filialfinder",
            require_generalunternehmer=True,
        )
        self.assertFalse(ok)
        self.assertIn("einzelhandel_betrieb", reason)


if __name__ == "__main__":
    unittest.main(verbosity=2)

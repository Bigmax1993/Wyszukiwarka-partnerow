# -*- coding: utf-8 -*-
"""Testy extract kontaktów Claude + promptów PL FAS (bez live API)."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from claude_contact_extract import (
    claude_extract_contacts_from_pages,
    merge_claude_contacts_into_collected,
)
from claude_prompts import (
    _CONTACT_EXTRACT_TEXT_PRIORITY,
    build_contact_extract_prompt,
    prioritize_page_text_for_verify,
)
from contact_extract_utils import parse_contact_extract_response


class TestClaudeContactExtract(unittest.TestCase):
    def test_build_contact_extract_prompt_prioritizes_kontakt(self):
        text = (
            "x " * 8000
            + "\n=== https://firma.pl/kontakt ===\nbiuro@firma.pl +48 22 100 20 30"
        )
        p = build_contact_extract_prompt(
            "Firma Spedycja Sp. z o.o.", "https://firma.pl", text
        )
        self.assertIn("biuro@firma.pl", p)
        self.assertIn("impressum_emails", p)
        self.assertIn("WPROST", p)
        self.assertIn("/kontakt", p)
        self.assertIn("/dane-firmy", p)
        self.assertNotIn("WÖRTLICH", p)

    def test_prioritize_contact_keywords_pl(self):
        long_tail = "y " * 5000
        text = (
            f"{long_tail}\nKontakt biuro spedycja NIP biuro@przyklad.pl Tel +48 71 111"
        )
        out = prioritize_page_text_for_verify(
            text,
            max_chars=160,
            priority_keywords=_CONTACT_EXTRACT_TEXT_PRIORITY,
        )
        self.assertIn("biuro@przyklad.pl", out)

    def test_parse_contact_extract_impressum_emails(self):
        parsed = parse_contact_extract_response(
            '{"company_name":"Trans Sp. z o.o.","emails":["biuro@trans.pl"],'
            '"impressum_emails":["biuro@trans.pl"],"phones":["+48 22 1"],'
            '"reason":"Kontakt"}'
        )
        self.assertEqual(parsed["impressum_emails"], ["biuro@trans.pl"])
        self.assertEqual(parsed["company_name"], "Trans Sp. z o.o.")

    def test_merge_claude_contacts_into_collected(self):
        collected = {
            "emails": [],
            "impressum_emails": [],
            "phones": [],
            "company_name": "",
        }
        parsed = {
            "emails": ["kontakt@spedycja.pl"],
            "impressum_emails": ["kontakt@spedycja.pl"],
            "phones": ["+48 22 123 45 67"],
            "company_name": "Spedycja Sp. z o.o.",
            "reason": "Kontakt",
        }
        out = merge_claude_contacts_into_collected(collected, parsed)
        self.assertEqual(out["emails"], ["kontakt@spedycja.pl"])
        self.assertEqual(out["impressum_emails"], ["kontakt@spedycja.pl"])
        self.assertEqual(out["phones"], ["+48 22 123 45 67"])
        self.assertEqual(out["company_name"], "Spedycja Sp. z o.o.")

    @patch("claude_contact_extract.claude_generate_text")
    @patch("claude_contact_extract.get_anthropic_api_key", return_value="test-key")
    def test_claude_extract_uses_cache(self, _key, mock_gen):
        mock_gen.return_value = (
            '{"emails":["biuro@test.pl"],"phones":[],"impressum_emails":[],'
            '"company_name":"","reason":"ok"}',
            "claude-sonnet-4-6",
        )
        cache: dict = {"claude_contact_extract": {}}
        page = "Kontakt biuro@test.pl"
        first = claude_extract_contacts_from_pages(
            "Test Sp. z o.o.", "https://test.pl", page, None, cache, cache_key="k1"
        )
        second = claude_extract_contacts_from_pages(
            "Test Sp. z o.o.", "https://test.pl", page, None, cache, cache_key="k1"
        )
        self.assertEqual(first["emails"], ["biuro@test.pl"])
        self.assertEqual(second["emails"], ["biuro@test.pl"])
        mock_gen.assert_called_once()


if __name__ == "__main__":
    unittest.main()

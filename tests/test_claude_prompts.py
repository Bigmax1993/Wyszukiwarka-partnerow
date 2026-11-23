# -*- coding: utf-8 -*-
"""Testy jednostkowe ``claude_prompts`` — kampania PL FAS (bez live API)."""
from __future__ import annotations

import unittest

from claude_prompts import (
    CONTACT_EXTRACT_MAX_CHARS,
    PAGE_VERIFY_MAX_CHARS,
    _CONTACT_EXTRACT_TEXT_PRIORITY,
    _PAGE_VERIFY_TEXT_PRIORITY,
    _REQUIRED_CHAINS,
    build_contact_extract_prompt,
    build_custom_email_prompt_de,
    build_custom_email_prompt_pl,
    build_discovery_terms_prompt,
    build_page_verify_prompt,
    build_row_cleanup_prompt,
    prioritize_page_text_for_verify,
)
from pl_spedycja_filter import TRANSPORT_SEGMENT_MARKERS


class TestClaudePromptsPageVerify(unittest.TestCase):
    def test_page_verify_prompt_structure_pl_fas(self):
        p = build_page_verify_prompt(
            "Trans Spedycja Sp. z o.o.",
            "https://trans-spedycja.pl",
            "Spedycja drogowa FTL LTL Europa",
        )
        self.assertIn("DRZEWO DECYZYJNE", p)
        self.assertIn("spedycyjnych", p)
        self.assertIn("is_small_firm", p)
        self.assertIn("is_gu", p)
        self.assertIn("has_retail_context", p)
        self.assertIn("matched_chains", p)
        self.assertIn("Trans Spedycja Sp. z o.o.", p)
        self.assertIn("ftl", p.lower())
        self.assertIn("ltl", p.lower())
        self.assertIn("adr", p.lower())
        self.assertIn("whitelist", p.lower())
        self.assertIn("Timocom", p)
        self.assertIn("InPost", p)
        self.assertNotIn("Filialbau", p)
        self.assertNotIn("Generalunternehmer Filialbau", p)
        self.assertEqual(PAGE_VERIFY_MAX_CHARS, 18000)

    def test_required_chains_are_transport_segments(self):
        low = _REQUIRED_CHAINS.lower()
        for seg in ("ftl", "ltl", "adr"):
            self.assertIn(seg, low)
        self.assertNotIn("aldi", low)
        self.assertNotIn("rewe", low)
        for marker in TRANSPORT_SEGMENT_MARKERS[:5]:
            self.assertIn(marker, _REQUIRED_CHAINS)


class TestClaudePromptsPrioritize(unittest.TestCase):
    def test_prioritize_puts_spedycja_lines_first(self):
        long_tail = "x " * 5000
        text = f"{long_tail}\nSpedycja FTL LTL oferta transport drogowy Europa"
        out = prioritize_page_text_for_verify(text, max_chars=200)
        self.assertTrue(out.startswith("Spedycja FTL"))

    def test_prioritize_sections_prefer_oferta_over_blog(self):
        filler = "blog wpis " * 800
        text = (
            f"=== https://firma.pl/blog ===\n{filler}\n"
            "=== https://firma.pl/oferta ===\n"
            "Spedycja drogowa FTL LTL Europa — nasza oferta\n"
        )
        out = prioritize_page_text_for_verify(text, max_chars=400)
        self.assertIn("/oferta", out)
        blog_pos = out.find("/blog")
        oferta_pos = out.find("/oferta")
        self.assertGreaterEqual(oferta_pos, 0)
        if blog_pos >= 0:
            self.assertLess(oferta_pos, blog_pos)

    def test_default_priority_keywords_are_pl_not_de_retail(self):
        self.assertIn("spedycja", _PAGE_VERIFY_TEXT_PRIORITY)
        self.assertIn("ftl", _PAGE_VERIFY_TEXT_PRIORITY)
        self.assertIn("firma spedycyjna", _PAGE_VERIFY_TEXT_PRIORITY)
        self.assertNotIn("aldi", _PAGE_VERIFY_TEXT_PRIORITY)
        self.assertNotIn("filialbau", _PAGE_VERIFY_TEXT_PRIORITY)
        self.assertNotIn("rewe", _PAGE_VERIFY_TEXT_PRIORITY)
        self.assertIn("biuro", _CONTACT_EXTRACT_TEXT_PRIORITY)
        self.assertIn("nip", _CONTACT_EXTRACT_TEXT_PRIORITY)
        self.assertIn("spedycja", _CONTACT_EXTRACT_TEXT_PRIORITY)
        self.assertIn("kontakt", _CONTACT_EXTRACT_TEXT_PRIORITY)

    def test_short_text_returned_unchanged(self):
        raw = "Spedycja FTL Głogów"
        self.assertEqual(
            prioritize_page_text_for_verify(raw, max_chars=5000),
            raw,
        )


class TestClaudePromptsRowCleanup(unittest.TestCase):
    def test_row_cleanup_prompt_excel_schema_pl(self):
        p = build_row_cleanup_prompt(
            company="Trans Spedycja Sp. z o.o.",
            address="ul. Test 1, 00-001 Warszawa",
            phone="+48 22 111 22 33",
            email="biuro@trans-spedycja.pl",
            website="https://trans-spedycja.pl",
            states="Mazowieckie, Dolnoslaskie",
            handelsketten="ftl, ltl",
        )
        self.assertIn("company_name_clean", p)
        self.assertIn("handelsketten", p)
        self.assertIn("Województwo", p)
        self.assertIn("Segmenty", p)
        self.assertIn("Sp. z o.o.", p)
        self.assertIn("S.A.", p)
        self.assertIn("+48", p)
        self.assertIn("Mazowieckie, Dolnoslaskie", p)
        self.assertIn("ftl", p.lower())
        self.assertIn("segmenty=", p)
        self.assertIn("nie wpisuj sieci handlowych", p)
        self.assertNotIn("Handelskette", p)
        self.assertNotIn("Bundesland →", p)


class TestClaudePromptsContactExtract(unittest.TestCase):
    def test_contact_extract_prompt_schema_pl(self):
        p = build_contact_extract_prompt(
            "Trans Spedycja Sp. z o.o.",
            "https://trans-spedycja.pl",
            "=== https://trans-spedycja.pl/kontakt ===\nbiuro@trans-spedycja.pl +48 22 111",
        )
        self.assertIn("impressum_emails", p)
        self.assertIn("WPROST", p)
        self.assertIn("/kontakt", p)
        self.assertIn("/dane-firmy", p)
        self.assertIn("/o-firmie", p)
        self.assertIn("+48", p)
        self.assertIn("noreply", p)
        self.assertIn("timocom", p.lower())
        self.assertIn("biuro@trans-spedycja.pl", p)
        self.assertEqual(CONTACT_EXTRACT_MAX_CHARS, 16000)
        self.assertNotIn("WÖRTLICH", p)
        self.assertNotIn("Generalunternehmer", p)


class TestClaudePromptsDiscovery(unittest.TestCase):
    def test_discovery_terms_prompt_pl_templates(self):
        p = build_discovery_terms_prompt(
            ["Mazowieckie"],
            city_str="Warszawa, Radom",
            land_str="Mazowieckie",
            terms_requested=5,
        )
        self.assertIn("Dokładnie 5 linii", p)
        self.assertIn("Województwo:", p)
        self.assertIn("Mazowieckie", p)
        self.assertIn("Warszawa", p)
        self.assertIn("spedycja FTL", p)
        self.assertIn("ftl", p.lower())
        self.assertIn("ltl", p.lower())
        self.assertIn("adr", p.lower())
        self.assertIn("{city}", p)
        self.assertIn("spedycja {chain}", p.lower())
        self.assertIn("ZŁE PRZYKŁADY", p)
        self.assertIn("DOBRE PRZYKŁADY", p)
        self.assertNotIn("Handelskette", p)
        self.assertNotIn("Bundesland:", p)
        self.assertNotIn("Genau 5 Zeilen", p)

    def test_discovery_exclude_block_appended(self):
        p = build_discovery_terms_prompt(
            ["Dolnoslaskie"],
            city_str="Głogów",
            land_str="Dolnoslaskie",
            terms_requested=3,
            exclude_block="\nJuż użyte:\n- spedycja FTL Głogów\n",
        )
        self.assertIn("spedycja FTL Głogów", p)
        self.assertIn("Dokładnie 3 linii", p)


class TestClaudePromptsEmail(unittest.TestCase):
    def test_email_prompt_pl_is_default_fas(self):
        pl = build_custom_email_prompt_pl(
            "Cześć,\n\nZnam ten ból: ile za trasę?\n"
            "FAS nie wymyśla stawki, kwotę podajecie Wy.\n\n"
            "Pozdrawiam\nMaksym Swinczak\nswinczakdata.pl\n+48 516 513 965",
            "Trans Spedycja Sp. z o.o.",
            city_name="Głogów",
            delivery_address="www: https://trans-spedycja.pl",
        )
        self.assertIn('"subject"', pl)
        self.assertIn("Forwarding Assistant", pl)
        self.assertIn("ludzki", pl.lower())
        self.assertIn("Głogów", pl)
        self.assertIn("FAS nie wymyśla stawki", pl)
        self.assertIn("Wymyślanie cen", pl)
        self.assertIn("Szanowni Państwo", pl)  # jako zakaz w prompcie

    def test_email_prompt_de_marked_legacy(self):
        de = build_custom_email_prompt_de("Hallo", "Firma GmbH")
        self.assertIn('"subject"', de)
        self.assertIn("Legacy", de)


if __name__ == "__main__":
    unittest.main(verbosity=2)

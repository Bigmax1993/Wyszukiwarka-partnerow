# -*- coding: utf-8 -*-
"""Testy przygotowania tekstu crawla + prompt verify (PL FAS)."""
from __future__ import annotations

import unittest

from claude_page_text import (
    build_automatic_evidence_excerpt,
    build_claude_context_header,
    format_crawl_text_for_claude,
    sort_crawl_urls_for_claude,
)
from claude_prompts import PAGE_VERIFY_MAX_CHARS, build_page_verify_prompt
from website_full_crawl import WebsiteCrawlResult


class ClaudePageTextTest(unittest.TestCase):
    def test_sort_verify_puts_oferta_first(self):
        urls = [
            "https://firma.pl/kontakt",
            "https://firma.pl/oferta",
            "https://firma.pl/blog",
        ]
        out = sort_crawl_urls_for_claude(urls, purpose="verify")
        self.assertEqual(out[0], "https://firma.pl/oferta")

    def test_sort_contact_puts_kontakt_first(self):
        urls = [
            "https://firma.pl/oferta",
            "https://firma.pl/kontakt",
        ]
        out = sort_crawl_urls_for_claude(urls, purpose="contact")
        self.assertEqual(out[0], "https://firma.pl/kontakt")

    def test_format_crawl_truncates_per_section(self):
        result = WebsiteCrawlResult(
            pages={
                "https://firma.pl/kontakt": {
                    "page_text": "x" * 3000,
                }
            },
            urls_visited=["https://firma.pl/kontakt"],
        )
        text = format_crawl_text_for_claude(
            result, purpose="contact", per_section_max_chars=500
        )
        self.assertIn("=== https://firma.pl/kontakt ===", text)
        body = text.split("\n", 1)[1]
        self.assertLessEqual(len(body), 503)
        self.assertTrue(body.endswith("..."))

    def test_evidence_excerpt_finds_spedycja_line(self):
        page = (
            "=== https://firma.pl/oferta ===\n"
            "Spedycja drogowa FTL LTL Europa — organizacja transportu"
        )
        out = build_automatic_evidence_excerpt(page)
        self.assertIn("Spedycja", out)
        self.assertIn("FTL", out)

    def test_verify_prompt_includes_serper_and_evidence(self):
        page = (
            "=== https://firma.pl/oferta ===\n"
            "Spedycja drogowa FTL LTL Europa ADR"
        )
        p = build_page_verify_prompt(
            "Trans Sp. z o.o.",
            "https://firma.pl",
            page,
            serper_blob="spedycja FTL Warszawa",
            pages_crawled=1,
        )
        self.assertIn("SERPER-KONTEXT", p)
        self.assertIn("AUTOMATISCHE DOWODY", p)
        self.assertIn("FTL", p)
        self.assertIn("spedycyjnych", p)
        self.assertEqual(PAGE_VERIFY_MAX_CHARS, 18000)

    def test_context_header(self):
        h = build_claude_context_header(
            "Trans Sp. z o.o.",
            "https://firma.pl",
            serper_blob="spedycja FTL Głogów",
            pages_crawled=5,
        )
        self.assertIn("Trans Sp. z o.o.", h)
        self.assertIn("spedycja FTL Głogów", h)
        self.assertIn("5", h)


if __name__ == "__main__":
    unittest.main()

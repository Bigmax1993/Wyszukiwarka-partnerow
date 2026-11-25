# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# MODUŁ TESTOWY: tests/test_claude_page_text.py
# CO ROBI: testy przygotowania tekstu crawla dla Claude: sortowanie URL-i, przycinanie sekcji, wycinek dowodów i prompt weryfikacji.
# ROLA W PIPELINE: pilnuje jakości wejścia do Claude verify (claude_page_text, claude_prompts).
# ZALEŻNOŚCI: unittest, claude_page_text, claude_prompts (PAGE_VERIFY_MAX_CHARS, build_page_verify_prompt), website_full_crawl.WebsiteCrawlResult.
# WEJŚCIE/WYJŚCIE: Moduł nie przyjmuje argumentów CLI; pytest/unittest odkrywa i uruchamia testy; nic nie zwraca (wynik = zielone/czerwone testy).
# ============================================================
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


# >>> OPIS FUNKCJI: klasa ClaudePageTextTest
# Grupa testów: przygotowanie tekstu strony dla Claude.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class ClaudePageTextTest(unittest.TestCase):
    # >>> OPIS FUNKCJI: funkcja ClaudePageTextTest.test_sort_verify_puts_oferta_first
    # Test: sortowanie URL-i do verify stawia /oferta na początku.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_sort_verify_puts_oferta_first(self):
        urls = [
            "https://firma.pl/kontakt",
            "https://firma.pl/oferta",
            "https://firma.pl/blog",
        ]
        out = sort_crawl_urls_for_claude(urls, purpose="verify")
        self.assertEqual(out[0], "https://firma.pl/oferta")

    # >>> OPIS FUNKCJI: funkcja ClaudePageTextTest.test_sort_contact_puts_kontakt_first
    # Test: sortowanie URL-i do ekstrakcji kontaktów stawia /kontakt na początku.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_sort_contact_puts_kontakt_first(self):
        urls = [
            "https://firma.pl/oferta",
            "https://firma.pl/kontakt",
        ]
        out = sort_crawl_urls_for_claude(urls, purpose="contact")
        self.assertEqual(out[0], "https://firma.pl/kontakt")

    # >>> OPIS FUNKCJI: funkcja ClaudePageTextTest.test_format_crawl_truncates_per_section
    # Test: format_crawl_text_for_claude przycina każdą sekcję do limitu (z '...') i oznacza ją nagłówkiem '=== URL ==='.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
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

    # >>> OPIS FUNKCJI: funkcja ClaudePageTextTest.test_evidence_excerpt_finds_spedycja_line
    # Test: wycinek dowodów odnajduje linie ze słowami spedycja/FTL.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_evidence_excerpt_finds_spedycja_line(self):
        page = (
            "=== https://firma.pl/oferta ===\n"
            "Spedycja drogowa FTL LTL Europa — organizacja transportu"
        )
        out = build_automatic_evidence_excerpt(page)
        self.assertIn("Spedycja", out)
        self.assertIn("FTL", out)

    # >>> OPIS FUNKCJI: funkcja ClaudePageTextTest.test_verify_prompt_includes_serper_and_evidence
    # Test: prompt verify zawiera kontekst Serpera, automatyczne dowody i polskie sformułowania; PAGE_VERIFY_MAX_CHARS == 18000.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
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

    # >>> OPIS FUNKCJI: funkcja ClaudePageTextTest.test_context_header
    # Test: nagłówek kontekstu zawiera nazwę firmy, frazę discovery i liczbę stron.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
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

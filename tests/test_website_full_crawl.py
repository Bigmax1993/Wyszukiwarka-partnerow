# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# MODUŁ TESTOWY: tests/test_website_full_crawl.py
# CO ROBI: testy pełnego crawla domeny: linki wewnętrzne, odwiedzanie stron, serializacja wyniku.
# ROLA W PIPELINE: zabezpiecza website_full_crawl używany do zebrania tekstu dla Claude.
# ZALEŻNOŚCI: unittest, unittest.mock.MagicMock, json, website_full_crawl.
# WEJŚCIE/WYJŚCIE: Moduł nie przyjmuje argumentów CLI; pytest/unittest odkrywa i uruchamia testy; nic nie zwraca (wynik = zielone/czerwone testy).
# ============================================================
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json

from website_full_crawl import (
    WebsiteCrawlResult,
    crawl_entire_website,
    extract_all_internal_links,
    format_crawl_text_for_claude,
    website_crawl_result_from_dict,
    website_crawl_result_to_dict,
)


# >>> OPIS FUNKCJI: funkcja _norm
# Pomocnik testowy: normalizuje URL na potrzeby crawlera (dodaje prefiks https://, jeśli brak http, i usuwa końcowy ukośnik przy URL-ach ze ścieżką). Parametry: url (str). Zwraca: str — znormalizowany URL. Efekty uboczne/błędy: brak.
def _norm(url: str) -> str:
    u = url.strip()
    if not u.startswith("http"):
        u = "https://" + u
    return u.rstrip("/") if u.endswith("/") and u.count("/") > 2 else u


# >>> OPIS FUNKCJI: klasa WebsiteFullCrawlTest
# Grupa testów: crawl całej domeny z atrapami fetch/parse.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class WebsiteFullCrawlTest(unittest.TestCase):
    # >>> OPIS FUNKCJI: funkcja WebsiteFullCrawlTest.test_extract_internal_links_same_domain
    # Test: extract_internal_links zwraca linki z tej samej domeny (np. karriere) i pomija zewnętrzne.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_extract_internal_links_same_domain(self):
        html = '<a href="/karriere/stelle">Jobs</a><a href="https://other.com/x">X</a>'
        links = extract_all_internal_links(
            "https://wijcobau.de/",
            html,
            site_domain="wijcobau.de",
            normalize_website=_norm,
        )
        self.assertTrue(any("karriere" in u for u in links))
        self.assertFalse(any("other.com" in u for u in links))

    # >>> OPIS FUNKCJI: funkcja WebsiteFullCrawlTest.test_crawl_visits_all_internal_pages
    # Test: crawl_entire_website odwiedza 3 strony wewnętrzne i buduje tekst z nagłówkami '=== URL' (zawiera treść sekcji karriere).
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: funkcje fetch i parse są atrapami w pamięci (bez sieci). Błędy: AssertionError przy niespełnionej asercji.
    def test_crawl_visits_all_internal_pages(self):
        pages = {
            "https://example.de": (
                '<a href="https://example.de/ueber-uns">About</a>'
                "<p>Generalunternehmer Einzelhandel</p>"
            ),
            "https://example.de/ueber-uns": (
                '<a href="https://example.de/karriere">Karriere</a>'
                "<p>Auftraggeber Netto</p>"
            ),
            "https://example.de/karriere": "<p>Retail Projekte</p>",
        }

        # >>> OPIS FUNKCJI: funkcja WebsiteFullCrawlTest.test_crawl_visits_all_internal_pages.fetch
        # Atrapa pobierania strony w teście: zwraca zdefiniowany HTML dla znanego URL-a. Parametry: url (str). Zwraca: str. Efekty uboczne/błędy: brak.
        def fetch(url: str) -> str:
            key = url.rstrip("/")
            return pages.get(key, pages.get(key + "/", ""))

        # >>> OPIS FUNKCJI: funkcja WebsiteFullCrawlTest.test_crawl_visits_all_internal_pages.parse
        # Atrapa parsowania strony w teście: zwraca słownik (emails, phones, company_name, contact_urls, page_text) wraz z linkami wewnętrznymi. Parametry: url, html (str). Zwraca: dict. Efekty uboczne/błędy: brak.
        def parse(url: str, html: str) -> dict:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")
            return {
                "emails": [],
                "phones": [],
                "company_name": "",
                "contact_urls": [],
                "page_text": soup.get_text(" ", strip=True),
            }

        result = crawl_entire_website(
            "https://example.de",
            logger=MagicMock(),
            fetch_page_html=fetch,
            parse_html_page=parse,
            normalize_website=_norm,
            max_pages=10,
        )
        self.assertEqual(len(result.urls_visited), 3)
        text = format_crawl_text_for_claude(result)
        self.assertIn("=== https://example.de/karriere", text)
        self.assertIn("Netto", text)

    # >>> OPIS FUNKCJI: funkcja WebsiteFullCrawlTest.test_crawl_result_json_roundtrip
    # Test: wynik crawla serializowany do JSON i odtworzony zachowuje urls_visited, pages i flagę capped.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_crawl_result_json_roundtrip(self):
        original = WebsiteCrawlResult(
            pages={"https://firma.de/impressum": {"emails": ["info@firma.de"]}},
            urls_visited=["https://firma.de/impressum"],
            urls_skipped=["https://firma.de/feed"],
            capped=True,
        )
        payload = {"website_crawl": {"https://firma.de": website_crawl_result_to_dict(original)}}
        raw = json.dumps(payload)
        loaded = json.loads(raw)
        restored = website_crawl_result_from_dict(loaded["website_crawl"]["https://firma.de"])
        self.assertEqual(restored.urls_visited, original.urls_visited)
        self.assertEqual(restored.pages, original.pages)
        self.assertTrue(restored.capped)


if __name__ == "__main__":
    unittest.main(verbosity=2)

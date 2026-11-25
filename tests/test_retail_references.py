# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# MODUŁ TESTOWY: tests/test_retail_references.py
# CO ROBI: testy dowodów oferty/referencji spedycji (flota, trasy, FTL/LTL) i negacji portfolio oraz limitu Serper unlimited.
# ROLA W PIPELINE: bramki dowodowe w weryfikacji strony i ograniczenia Serper.
# ZALEŻNOŚCI: unittest, unittest.mock.patch, pl_fas_spedycja_scraper, pl_spedycja_filter.
# WEJŚCIE/WYJŚCIE: Moduł nie przyjmuje argumentów CLI; pytest/unittest odkrywa i uruchamia testy; nic nie zwraca (wynik = zielone/czerwone testy).
# ============================================================
"""Referencje / oferta spedycji: flota, trasy, FTL/LTL, opisy oferty."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pl_fas_spedycja_scraper as scraper
from pl_spedycja_filter import (
    detect_required_retail_chains,
    has_market_project_evidence_on_website,
    has_retail_references_or_portfolio,
    has_required_retail_chain_mention,
    portfolio_negates_market_projects,
)


# >>> OPIS FUNKCJI: klasa RetailReferenceEvidence
# Grupa testów: dowody referencji/oferty.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class RetailReferenceEvidence(unittest.TestCase):
    # >>> OPIS FUNKCJI: funkcja RetailReferenceEvidence.test_classic_referenzen_tab
    # Test: klasyczna zakładka referencji jest rozpoznawana.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_classic_referenzen_tab(self):
        text = (
            "Firma spedycyjna. Referencje: transport FTL "
            "Polska Niemcy, trasy Europa."
        )
        self.assertTrue(has_retail_references_or_portfolio(text))

    # >>> OPIS FUNKCJI: funkcja RetailReferenceEvidence.test_offer_section_with_role_and_segment
    # Test: sekcja oferty z rolą i segmentem jest dowodem.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_offer_section_with_role_and_segment(self):
        text = (
            "Firma spedycyjna. Flota i trasy. "
            "Transport drogowy FTL międzynarodowy."
        )
        self.assertTrue(has_market_project_evidence_on_website(text))

    # >>> OPIS FUNKCJI: funkcja RetailReferenceEvidence.test_project_description_only
    # Test: sam opis projektu wystarcza jako dowód.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_project_description_only(self):
        text = (
            "Jesteśmy firmą spedycyjną. Realizujemy transport FTL "
            "i organizację przewozu — oferta z zakresem usług."
        )
        self.assertTrue(has_market_project_evidence_on_website(text))

    # >>> OPIS FUNKCJI: funkcja RetailReferenceEvidence.test_gu_without_any_reference_rejected
    # Test: rola bez żadnych referencji nie jest dowodem.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_gu_without_any_reference_rejected(self):
        text = (
            "Firma budowlana. Budujemy biurowce i hale. "
            "Bez transportu i bez spedycji."
        )
        self.assertFalse(has_market_project_evidence_on_website(text))

    # >>> OPIS FUNKCJI: funkcja RetailReferenceEvidence.test_page_verify_requires_reference_when_enabled
    # Test: page_mentions_retail_store_projects wymaga dowodu, gdy bramka jest włączona.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: patche flag REQUIRE_*. Błędy: AssertionError przy niespełnionej asercji.
    def test_page_verify_requires_reference_when_enabled(self):
        text = (
            "Firma spedycyjna. Transport FTL. Flota. "
            "Referencje: trasy Europa, fracht Polska Niemcy."
        )
        ok, chains, reason = scraper.page_mentions_retail_store_projects(text)
        self.assertTrue(ok, reason)
        self.assertTrue(any(c in ("ftl", "fracht", "europa") for c in chains) or chains)

    # >>> OPIS FUNKCJI: funkcja RetailReferenceEvidence.test_rejects_gu_without_named_chain
    # Test: brak nazwanego segmentu → odrzut z powodem keine_handelskette.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: patche flag REQUIRE_*. Błędy: AssertionError przy niespełnionej asercji.
    def test_rejects_gu_without_named_chain(self):
        text = (
            "Firma spedycyjna. Referencje: organizacja transportu. "
            "Oferta ogólna bez wskazania segmentu usług."
        )
        ok, _, reason = scraper.page_mentions_retail_store_projects(text)
        self.assertFalse(ok)
        self.assertEqual(reason, "keine_handelskette")

    # >>> OPIS FUNKCJI: funkcja RetailReferenceEvidence.test_required_chain_detection
    # Test: wykrywanie wymaganych segmentów w tekście (FTL…) i brak dla niepasującej treści.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_required_chain_detection(self):
        self.assertTrue(has_required_retail_chain_mention("Oferta FTL Polska Niemcy"))
        self.assertEqual(
            set(detect_required_retail_chains("FTL i LTL oraz fracht")),
            {"ftl", "ltl", "fracht"},
        )
        self.assertFalse(has_required_retail_chain_mention("Tylko przeprowadzki lokalne"))

    # >>> OPIS FUNKCJI: funkcja RetailReferenceEvidence.test_references_ftl_without_portfolio_heading
    # Test: referencje FTL są rozpoznawane bez nagłówka portfolio.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_references_ftl_without_portfolio_heading(self):
        text = (
            "Firma spedycyjna. Nasze referencje: "
            "transport międzynarodowy i spedycja FTL."
        )
        self.assertTrue(has_retail_references_or_portfolio(text))

    # >>> OPIS FUNKCJI: funkcja RetailReferenceEvidence.test_offer_without_jpg_paths
    # Test: oferta bez ścieżek obrazów też jest dowodem.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_offer_without_jpg_paths(self):
        text = (
            "Firma spedycyjna. Oferta: flota i trasy. "
            "Transport drogowy FTL."
        )
        self.assertTrue(has_market_project_evidence_on_website(text))

    # >>> OPIS FUNKCJI: funkcja RetailReferenceEvidence.test_simple_negation_overrides_offer
    # Test: jawna negacja portfolio przesłania ofertę.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_simple_negation_overrides_offer(self):
        # Krok E: prosta negacja bez okien — fraza zawsze odrzuca
        text = (
            "Firma spedycyjna. Referencje: transport FTL Europa. "
            "Nie prowadzimy spedycji."
        )
        self.assertTrue(portfolio_negates_market_projects(text))
        self.assertFalse(has_retail_references_or_portfolio(text))

    # >>> OPIS FUNKCJI: funkcja RetailReferenceEvidence.test_negation_without_forwarding_signal
    # Test: negacja bez sygnału spedycyjnego unieważnia dowód.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_negation_without_forwarding_signal(self):
        text = (
            "Wyłącznie magazynowanie towarów własnych. "
            "Nie prowadzimy spedycji."
        )
        self.assertTrue(portfolio_negates_market_projects(text))
        self.assertFalse(has_market_project_evidence_on_website(text))


# >>> OPIS FUNKCJI: klasa SerperUnlimited
# Grupa testów: tryb unlimited Serper.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class SerperUnlimited(unittest.TestCase):
    # >>> OPIS FUNKCJI: funkcja SerperUnlimited.test_unlimited_bypasses_daily_cap
    # Test: przy SERPER_UNLIMITED limit dzienny nie blokuje (is_serper_limit_reached_today=False).
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: patch.object na stałej SERPER_UNLIMITED. Błędy: AssertionError przy niespełnionej asercji.
    def test_unlimited_bypasses_daily_cap(self):
        cache = scraper._empty_cache()
        today = scraper.campaign_today()
        cache["serper_daily"][today] = 9999
        with patch.object(scraper, "SERPER_UNLIMITED", True):
            self.assertFalse(scraper.is_serper_limit_reached_today(cache))


if __name__ == "__main__":
    unittest.main(verbosity=2)

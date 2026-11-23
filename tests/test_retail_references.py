# -*- coding: utf-8 -*-
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


class RetailReferenceEvidence(unittest.TestCase):
    def test_classic_referenzen_tab(self):
        text = (
            "Firma spedycyjna. Referencje: transport FTL "
            "Polska Niemcy, trasy Europa."
        )
        self.assertTrue(has_retail_references_or_portfolio(text))

    def test_offer_section_with_role_and_segment(self):
        text = (
            "Firma spedycyjna. Flota i trasy. "
            "Transport drogowy FTL międzynarodowy."
        )
        self.assertTrue(has_market_project_evidence_on_website(text))

    def test_project_description_only(self):
        text = (
            "Jesteśmy firmą spedycyjną. Realizujemy transport FTL "
            "i organizację przewozu — oferta z zakresem usług."
        )
        self.assertTrue(has_market_project_evidence_on_website(text))

    def test_gu_without_any_reference_rejected(self):
        text = (
            "Firma budowlana. Budujemy biurowce i hale. "
            "Bez transportu i bez spedycji."
        )
        self.assertFalse(has_market_project_evidence_on_website(text))

    def test_page_verify_requires_reference_when_enabled(self):
        text = (
            "Firma spedycyjna. Transport FTL. Flota. "
            "Referencje: trasy Europa, fracht Polska Niemcy."
        )
        ok, chains, reason = scraper.page_mentions_retail_store_projects(text)
        self.assertTrue(ok, reason)
        self.assertTrue(any(c in ("ftl", "fracht", "europa") for c in chains) or chains)

    def test_rejects_gu_without_named_chain(self):
        text = (
            "Firma spedycyjna. Referencje: organizacja transportu. "
            "Oferta ogólna bez wskazania segmentu usług."
        )
        ok, _, reason = scraper.page_mentions_retail_store_projects(text)
        self.assertFalse(ok)
        self.assertEqual(reason, "keine_handelskette")

    def test_required_chain_detection(self):
        self.assertTrue(has_required_retail_chain_mention("Oferta FTL Polska Niemcy"))
        self.assertEqual(
            set(detect_required_retail_chains("FTL i LTL oraz fracht")),
            {"ftl", "ltl", "fracht"},
        )
        self.assertFalse(has_required_retail_chain_mention("Tylko przeprowadzki lokalne"))

    def test_references_ftl_without_portfolio_heading(self):
        text = (
            "Firma spedycyjna. Nasze referencje: "
            "transport międzynarodowy i spedycja FTL."
        )
        self.assertTrue(has_retail_references_or_portfolio(text))

    def test_offer_without_jpg_paths(self):
        text = (
            "Firma spedycyjna. Oferta: flota i trasy. "
            "Transport drogowy FTL."
        )
        self.assertTrue(has_market_project_evidence_on_website(text))

    def test_simple_negation_overrides_offer(self):
        # Krok E: prosta negacja bez okien — fraza zawsze odrzuca
        text = (
            "Firma spedycyjna. Referencje: transport FTL Europa. "
            "Nie prowadzimy spedycji."
        )
        self.assertTrue(portfolio_negates_market_projects(text))
        self.assertFalse(has_retail_references_or_portfolio(text))

    def test_negation_without_forwarding_signal(self):
        text = (
            "Wyłącznie magazynowanie towarów własnych. "
            "Nie prowadzimy spedycji."
        )
        self.assertTrue(portfolio_negates_market_projects(text))
        self.assertFalse(has_market_project_evidence_on_website(text))


class SerperUnlimited(unittest.TestCase):
    def test_unlimited_bypasses_daily_cap(self):
        cache = scraper._empty_cache()
        today = scraper.campaign_today()
        cache["serper_daily"][today] = 9999
        with patch.object(scraper, "SERPER_UNLIMITED", True):
            self.assertFalse(scraper.is_serper_limit_reached_today(cache))


if __name__ == "__main__":
    unittest.main(verbosity=2)

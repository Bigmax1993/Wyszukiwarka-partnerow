# -*- coding: utf-8 -*-
"""Testy jednostkowe: referencje market├│w na stronie www."""
from __future__ import annotations

import pytest

from retail_store_builder_filter import (
    RETAIL_CHAIN_IN_PORTFOLIO_MARKERS,
    has_market_project_evidence_on_website,
    has_retail_references_or_portfolio,
    portfolio_negates_market_projects,
)

pytestmark = pytest.mark.unit


class TestRetailReferenceEvidence:
    def test_classic_referenzen_tab(self):
        text = (
            "Generalunternehmer f├╝r Filialbau. Referenzen: Neubau Rewe "
            "Supermarkt in Hannover."
        )
        assert has_retail_references_or_portfolio(text)

    def test_store_photos_without_referenzen_tab(self):
        text = (
            "Generalunternehmer Filialbau. Fotogalerie. "
            "img alt='Rewe Filiale Neubau' src='/uploads/rewe-filiale-neubau.jpg' "
            "Supermarkt Umbau realisiert."
        )
        assert has_market_project_evidence_on_website(text)

    def test_gu_without_reference_rejected(self):
        text = (
            "Generalunternehmer f├╝r Gewerbebau und Hallenbau. "
            "Wir bauen B├╝rogeb├Ąude und Logistikhallen."
        )
        assert not has_market_project_evidence_on_website(text)

    def test_chain_markers_detected_in_text(self):
        text = "Neubau Aldi S├╝d Filiale und Penny Markt."
        low = text.lower()
        found = [m for m in RETAIL_CHAIN_IN_PORTFOLIO_MARKERS if m in low and len(m) >= 4]
        assert any("aldi" in m for m in found)
        assert any("penny" in m for m in found)

    def test_portfolio_negates_non_retail(self):
        text = "Portfolio: Wohnungsbau, B├╝rogeb├Ąude, Hallenbau ÔÇö keine Einzelhandelsprojekte."
        assert portfolio_negates_market_projects(text)

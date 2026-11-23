# -*- coding: utf-8 -*-
"""Testy jednostkowe: referencje / oferta spedycji na stronie www."""
from __future__ import annotations

import pytest

from pl_spedycja_filter import (
    TRANSPORT_SEGMENT_MARKERS,
    has_market_project_evidence_on_website,
    has_retail_references_or_portfolio,
    portfolio_negates_market_projects,
)

pytestmark = pytest.mark.unit


class TestRetailReferenceEvidence:
    def test_classic_referenzen_tab(self):
        text = (
            "Firma spedycyjna. Referencje: transport FTL "
            "Polska Niemcy, trasy Europa."
        )
        assert has_retail_references_or_portfolio(text)

    def test_offer_section_with_role_and_segment(self):
        text = (
            "Firma spedycyjna. Flota i trasy. "
            "Transport drogowy FTL międzynarodowy."
        )
        assert has_market_project_evidence_on_website(text)

    def test_gu_without_reference_rejected(self):
        text = (
            "Firma budowlana. Budujemy biurowce i hale. "
            "Bez transportu i bez spedycji."
        )
        assert not has_market_project_evidence_on_website(text)

    def test_chain_markers_detected_in_text(self):
        text = "Oferta: FTL, LTL i fracht Europa."
        low = text.lower()
        found = [m for m in TRANSPORT_SEGMENT_MARKERS if m in low and len(m) >= 3]
        assert any("ftl" in m for m in found)
        assert any("ltl" in m for m in found)

    def test_portfolio_negates_non_retail(self):
        text = "O nas: wyłącznie usługi magazynowe. Nie prowadzimy spedycji."
        assert portfolio_negates_market_projects(text)

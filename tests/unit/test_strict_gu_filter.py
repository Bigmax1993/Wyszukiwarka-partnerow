# -*- coding: utf-8 -*-
"""Testy jednostkowe: retail_store_builder_filter (GU strict)."""
from __future__ import annotations

import pytest

from retail_store_builder_filter import (
    RETAIL_CHAIN_IN_PORTFOLIO_MARKERS,
    is_retail_store_operator_contact,
    is_valid_retail_store_builder_contact,
    mentions_retail_store_build_activity_core,
)

pytestmark = pytest.mark.unit


class TestStrictGuFilter:
    def test_retail_chain_markers_include_major_chains(self):
        chains = {m for m in RETAIL_CHAIN_IN_PORTFOLIO_MARKERS if len(m) >= 4}
        for expected in ("aldi", "rewe", "edeka", "netto", "penny", "kaufland", "lidl"):
            assert any(expected in c for c in chains)

    def test_valid_gu_with_retail_reference(self):
        text = "Generalunternehmer Filialbau. Referenz: Rewe Neubau Leipzig."
        assert mentions_retail_store_build_activity_core(text)
        assert is_valid_retail_store_builder_contact(
            email="info@bau-gmbh.de",
            url="https://bau-gmbh.de",
            name="Bau GmbH",
            text=text,
        )

    def test_rejects_retail_operator_domain(self):
        assert is_retail_store_operator_contact(
            url="https://www.rewe.de/maerkte",
            email="",
            text="Öffnungszeiten Wochenangebot Prospekt",
        )

    def test_accepts_filialbau_with_chain_reference(self):
        text = (
            "Generalunternehmer Filialbau. Supermarktbau. "
            "Referenzprojekt Norma Neubau Dresden."
        )
        assert mentions_retail_store_build_activity_core(text)
        assert is_valid_retail_store_builder_contact(
            email="kontakt@filialbau.de",
            url="https://filialbau.de",
            name="Filialbau GmbH",
            text=text,
        )

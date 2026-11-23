# -*- coding: utf-8 -*-
"""Testy jednostkowe: pl_spedycja_filter (PL spedycja)."""
from __future__ import annotations

import pytest

from pl_spedycja_filter import (
    FORWARDER_ROLE_MARKERS,
    TRANSPORT_SEGMENT_MARKERS,
    debug_filter_decision,
    has_forwarding_signal,
    has_offer_evidence,
    has_serper_trade_signal,
    is_cache_contact_not_store_builder,
    is_forwarder_role,
    is_generalunternehmer,
    is_loose_serper_discovery_candidate,
    is_retail_store_operator_contact,
    is_serper_only_pending_candidate,
    is_valid_retail_store_builder_contact,
    mentions_retail_store_build_activity_core,
    mentions_retail_store_build_activity_serper_discovery,
    portfolio_negates,
    reject_reason,
)

pytestmark = pytest.mark.unit

_OK = dict(
    email="biuro@spedycja-example.pl",
    url="https://spedycja-example.pl",
    name="Spedycja Example Sp. z o.o.",
)


class TestMarkersAndRole:
    def test_segment_markers_include_ftl_ltl(self):
        chains = {m for m in TRANSPORT_SEGMENT_MARKERS if len(m) >= 3}
        for expected in ("ftl", "ltl", "fracht", "europa", "niemcy"):
            assert any(expected in c for c in chains)

    def test_role_markers_include_spedycja(self):
        assert any("spedycja" in m for m in FORWARDER_ROLE_MARKERS)

    def test_forwarder_role_alias(self):
        text = "Firma spedycyjna transport drogowy"
        assert is_forwarder_role(text) == is_generalunternehmer(text)
        assert is_forwarder_role(text)[0] is True
        assert is_forwarder_role("HELIA Ladenbau Filialbau")[0] is False


class TestForwardingSignal:
    def test_role_and_segment(self):
        assert has_forwarding_signal("Firma spedycyjna. FTL Europa.")
        assert mentions_retail_store_build_activity_core(
            "Firma spedycyjna. FTL Europa."
        )

    def test_role_and_service(self):
        assert has_forwarding_signal("Spedytor. Transport drogowy Polska.")

    def test_role_alone_insufficient(self):
        assert not has_forwarding_signal("Firma spedycyjna Sp. z o.o.")

    def test_serper_discovery_looser(self):
        text = "Firma spedycyjna Warszawa"
        assert mentions_retail_store_build_activity_serper_discovery(text)
        assert not mentions_retail_store_build_activity_core(text)


class TestRejectReason:
    def test_courier(self):
        assert reject_reason(text="InPost paczkomaty kurier") == "courier"

    def test_exchange_domain(self):
        assert (
            reject_reason(url="https://www.timocom.com/pl", text="giełda")
            == "exchange_or_big3pl"
        )

    def test_media(self):
        assert (
            reject_reason(
                url="https://trans.info/artykul/1",
                name="Portal branżowy",
                text="aktualności transport",
            )
            == "media"
        )

    def test_irrelevant_role(self):
        assert (
            reject_reason(text="oferty pracy kierowca agencja pracy")
            == "irrelevant_role"
        )

    def test_clean_forwarder(self):
        assert (
            reject_reason(
                url="https://spedycja-example.pl",
                name="Spedycja Example",
                text="Firma spedycyjna FTL",
            )
            is None
        )


class TestOfferAndNegation:
    def test_offer_evidence(self):
        text = "Firma spedycyjna. Oferta: flota i trasy. FTL Europa."
        assert has_offer_evidence(text)
        assert not portfolio_negates(text)

    def test_portfolio_negates(self):
        text = "Spedycja FTL. Nie prowadzimy spedycji."
        assert portfolio_negates(text)
        assert not has_offer_evidence(text)


class TestValidContact:
    def test_valid_spedycja_with_ftl(self):
        text = "Firma spedycyjna. Transport drogowy FTL Polska Niemcy."
        assert mentions_retail_store_build_activity_core(text)
        assert is_valid_retail_store_builder_contact(**_OK, text=text)

    def test_accepts_freight_forwarding(self):
        text = (
            "Freight forwarding. Spedycja FTL. "
            "Transport międzynarodowy Europa."
        )
        assert is_valid_retail_store_builder_contact(**_OK, text=text)

    def test_rejects_negation(self):
        text = "Firma spedycyjna FTL. Nie prowadzimy spedycji."
        assert not is_valid_retail_store_builder_contact(**_OK, text=text)

    def test_rejects_retail_operator_domain(self):
        assert is_retail_store_operator_contact(
            url="https://www.timocom.com/pl",
            email="",
            text="Giełda transportowa oferty frachtów",
        )
        assert is_retail_store_operator_contact(
            url="https://inpost.pl",
            email="",
            text="Paczkomat śledź paczkę",
        )


class TestSerper:
    def test_accepts_spedycja_snippet(self):
        assert is_serper_only_pending_candidate(
            **_OK,
            text="Firma spedycyjna FTL transport drogowy Warszawa",
            search_term="spedycja FTL Warszawa",
        )

    def test_accepts_segment_from_search_term(self):
        assert is_serper_only_pending_candidate(
            **_OK,
            text="Biuro w Warszawie — kontakt",
            search_term="spedycja FTL Mazowieckie",
        )

    def test_rejects_ladenbau(self):
        assert not is_serper_only_pending_candidate(
            email="",
            url="https://helia-ladenbau.de",
            name="HELIA Ladenbau GmbH",
            text="Ladenbau in Ulm",
        )

    def test_rejects_media(self):
        assert not is_serper_only_pending_candidate(
            url="https://www.hi-heute.de/supermarkte",
            name="hi-heute.de Verlag",
            text="Nachrichten Supermarkt",
        )

    def test_rejects_negation(self):
        assert not is_serper_only_pending_candidate(
            **_OK,
            text="Firma spedycyjna FTL. Nie prowadzimy spedycji.",
            search_term="spedycja FTL",
        )

    def test_loose_is_alias(self):
        kwargs = dict(
            **_OK,
            text="Firma spedycyjna FTL Warszawa",
            search_term="spedycja FTL",
        )
        assert is_loose_serper_discovery_candidate(
            **kwargs
        ) == is_serper_only_pending_candidate(**kwargs)

    def test_trade_signal_helper(self):
        assert has_serper_trade_signal("biuro", "transport drogowy mazowieckie")
        assert not has_serper_trade_signal("biuro kontakt", "")


class TestCacheAdapter:
    def test_pending_kept(self):
        assert (
            is_cache_contact_not_store_builder(
                "https://a.pl",
                {
                    "verification_reason": "pending_www_verify",
                    "retail_verified": False,
                },
            )
            is False
        )

    def test_wojewodztwo_without_email_kept(self):
        assert (
            is_cache_contact_not_store_builder(
                "https://a.pl",
                {
                    "discovery_wojewodztwo": "Mazowieckie",
                    "company_name_clean": "X",
                },
            )
            is False
        )

    def test_legacy_bundesland_key_still_kept(self):
        assert (
            is_cache_contact_not_store_builder(
                "https://a.pl",
                {
                    "discovery_bundesland": "Mazowieckie",
                    "company_name_clean": "X",
                },
            )
            is False
        )


class TestDebugFilterDecision:
    def test_debug_accept_path(self):
        d = debug_filter_decision(
            **_OK,
            text="Firma spedycyjna. Transport drogowy FTL Europa.",
            search_term="spedycja FTL",
        )
        assert d["reject_reason"] is None
        assert d["role_ok"] is True
        assert d["forwarding_signal"] is True
        assert d["is_valid"] is True
        assert d["is_serper_candidate"] is True
        assert "ftl" in d["segments"]

    def test_debug_reject_courier(self):
        d = debug_filter_decision(
            email="",
            url="https://lokalny-kurier-example.pl",
            name="Lokalny Kurier",
            text="usługi kurierskie paczka same day delivery",
        )
        assert d["reject_reason"] == "courier"
        assert d["is_valid"] is False
        assert d["is_serper_candidate"] is False

    def test_debug_reject_exchange_domain(self):
        d = debug_filter_decision(
            email="",
            url="https://inpost.pl",
            name="InPost",
            text="paczkomaty kurier",
        )
        assert d["reject_reason"] == "exchange_or_big3pl"

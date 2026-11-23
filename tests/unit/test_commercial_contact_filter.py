# -*- coding: utf-8 -*-
"""Testy jednostkowe: commercial_contact_filter."""
from __future__ import annotations

import pytest

from commercial_contact_filter import (
    filter_commercial_emails,
    is_junk_scraped_email,
    is_non_commercial_contact,
    is_non_commercial_email,
    is_non_commercial_name,
    is_valid_commercial_company_contact,
)

pytestmark = pytest.mark.unit


class TestNonCommercialEmail:
    def test_rejects_city_domain(self):
        assert is_non_commercial_email("info@leipzig.de")

    def test_rejects_pl_gov_and_catalog(self):
        assert is_non_commercial_email("kontakt@mf.gov.pl")
        assert is_non_commercial_email("biuro@um.warszawa.pl")
        assert is_non_commercial_email("info@panoramafirm.pl")
        assert is_non_commercial_email("x@zus.pl")

    def test_accepts_company_domain(self):
        assert not is_non_commercial_email("office@bau-gmbh.de")
        assert not is_non_commercial_email("biuro@trans-spedycja.pl")
        # Nie false-positive na zwykłej firmie (um. w środku słowa domeny)
        assert not is_non_commercial_email("biuro@premium-log.pl")


class TestJunkScrapedEmail:
    def test_rejects_cookie_banner(self):
        assert is_junk_scraped_email("akzeptieren@cookie-banner.de")

    def test_accepts_normal_email(self):
        assert not is_junk_scraped_email("kontakt@firma-gmbh.de")


class TestCommercialContact:
    def test_rejects_institution_name(self):
        assert is_non_commercial_contact(name="Stadt Leipzig, Dezernat Wirtschaft")

    def test_rejects_pl_institution_name(self):
        assert is_non_commercial_contact(name="Urząd Miasta Warszawa")
        assert is_non_commercial_contact(name="Powiatowy Urząd Pracy Gdańsk")
        assert is_non_commercial_contact(name="Giełda transportowa TIMOCOM")

    def test_name_soft_pass_pl_spedycja_not_legacy_gu(self):
        # Soft-pass: izba + spedycja + Sp. z o.o. → firma, nie instytucja
        assert not is_non_commercial_name(
            "Izba Partner Spedycja Sp. z o.o."
        )
        # Stary soft-pass DE GU usunięty — sam Generalunternehmer + GmbH = non-commercial
        assert is_non_commercial_name("Müller Generalunternehmer GmbH")
        assert is_non_commercial_name("Generalunternehmer Filialbau")

    def test_short_name_geo_pl_without_legal_form(self):
        # ≤3 słowa, bez Sp. z o.o., geo z BUNDESLAND_CONFIG → portal/miasto
        assert is_non_commercial_name("Transport Warszawa")
        assert is_non_commercial_name("Firma Kraków")
        assert is_non_commercial_name("Leipzig Gewerbe")
        # Z formą prawną — nie ten tor (firma)
        assert not is_non_commercial_name("Trans Spedycja Sp. z o.o.")

    def test_accepts_gmbh_with_own_domain(self):
        assert is_valid_commercial_company_contact(
            email="info@sus-bau.de",
            url="https://sus-bau.de",
            name="SuS Bau GmbH",
        )

    def test_accepts_pl_sp_zoo(self):
        assert is_valid_commercial_company_contact(
            email="biuro@trans-spedycja.pl",
            url="https://trans-spedycja.pl",
            name="Trans Spedycja Sp. z o.o.",
        )

    def test_accepts_pl_sa(self):
        assert is_valid_commercial_company_contact(
            email="kontakt@firma-sa.pl",
            url="https://firma-sa.pl",
            name="Logistyka Polska S.A.",
        )

    def test_accepts_pl_domain_heuristic_without_legal_form(self):
        # Nazwa bez Sp. z o.o., ale domena maila z „spedycja” / „transport”
        assert is_valid_commercial_company_contact(
            email="biuro@nord-spedycja.pl",
            url="https://inna-domena.pl",
            name="Nord Partner",
        )
        assert is_valid_commercial_company_contact(
            email="biuro@abc-transport.pl",
            url="https://inna-domena.pl",
            name="ABC Partner",
        )


class TestFilterCommercialEmails:
    def test_deduplicates_and_filters(self):
        raw = [
            "info@firma.de",
            "info@firma.de",
            "info@leipzig.de",
            "kontakt@bau-gmbh.de",
        ]
        out = filter_commercial_emails(raw)
        assert out == ["info@firma.de", "kontakt@bau-gmbh.de"]

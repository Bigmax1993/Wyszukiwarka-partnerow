# -*- coding: utf-8 -*-
"""Testy jednostkowe: commercial_contact_filter."""
from __future__ import annotations

import pytest

from commercial_contact_filter import (
    filter_commercial_emails,
    is_junk_scraped_email,
    is_non_commercial_contact,
    is_non_commercial_email,
    is_valid_commercial_company_contact,
)

pytestmark = pytest.mark.unit


class TestNonCommercialEmail:
    def test_rejects_city_domain(self):
        assert is_non_commercial_email("info@leipzig.de")

    def test_accepts_company_domain(self):
        assert not is_non_commercial_email("office@bau-gmbh.de")


class TestJunkScrapedEmail:
    def test_rejects_cookie_banner(self):
        assert is_junk_scraped_email("akzeptieren@cookie-banner.de")

    def test_accepts_normal_email(self):
        assert not is_junk_scraped_email("kontakt@firma-gmbh.de")


class TestCommercialContact:
    def test_rejects_institution_name(self):
        assert is_non_commercial_contact(name="Stadt Leipzig, Dezernat Wirtschaft")

    def test_accepts_gmbh_with_own_domain(self):
        assert is_valid_commercial_company_contact(
            email="info@sus-bau.de",
            url="https://sus-bau.de",
            name="SuS Bau GmbH",
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

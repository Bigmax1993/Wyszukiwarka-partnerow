# -*- coding: utf-8 -*-
"""Testy jednostkowe: pl_fas_spedycja_scraper pod kampanię PL FAS."""
from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import pl_fas_spedycja_scraper as scraper
from fas_spedycja_inquiry_email_pl import FAS_MUST_KEEP_RATE_LINE, FAS_WEBSITE

pytestmark = pytest.mark.unit


class TestPlFasEmailDefaults:
    def test_lang_and_custom_template_defaults(self):
        assert scraper.CUSTOM_EMAIL_LANG == "pl"
        assert scraper.USE_CUSTOM_EMAIL_TEMPLATE is True
        assert scraper.SERPER_COUNTRY == "pl"
        assert scraper.SERPER_LANGUAGE == "pl"
        assert "Forwarding Assistant" in scraper.CUSTOM_EMAIL_DRAFT
        assert FAS_MUST_KEEP_RATE_LINE in scraper.CUSTOM_EMAIL_DRAFT
        assert scraper.EMAIL_SUBJECT_TEMPLATE.startswith("Maksym / Forwarding Assistant")
        assert FAS_WEBSITE in scraper.EMAIL_SIGNATURE
        assert scraper.FIXED_EMAIL_SUBJECT_DE == scraper.FIXED_EMAIL_SUBJECT_PL

    def test_inquiry_context_is_pl_segments(self):
        assert "Polska" in scraper.INQUIRY_REGION_PL
        assert "ftl" in scraper.INQUIRY_SEGMENTS_PL
        assert scraper.INQUIRY_REGION_DE == scraper.INQUIRY_REGION_PL
        assert scraper.RETAIL_CHAINS_DE == scraper.INQUIRY_SEGMENTS_PL


class TestPlFasEmailAliases:
    def test_send_and_attachment_aliases(self):
        assert scraper.send_email_pl_fas is scraper.send_email_de_gu
        assert (
            scraper.get_email_attachments_pl_fas
            is scraper.get_email_attachments_de_gu
        )

    def test_assemble_fallback_injects_company(self):
        body = scraper._assemble_inquiry_email_body("Trans Spedycja Sp. z o.o.")
        assert "Trans Spedycja Sp. z o.o." in body
        assert FAS_MUST_KEEP_RATE_LINE in body
        assert FAS_WEBSITE in body

    def test_generate_email_content_fallback_without_api(self):
        log = logging.getLogger("test_pl_fas_mail")
        with patch(
            "email_custom_template.inquiry_try_custom",
            side_effect=RuntimeError("brak API"),
        ):
            subject, body = scraper.generate_email_content(
                "Trans Spedycja Sp. z o.o.",
                log,
                city_name="Głogów",
            )
        assert "Forwarding Assistant" in subject
        assert FAS_MUST_KEEP_RATE_LINE in body
        assert "Trans Spedycja" in body

    def test_generate_email_content_keeps_rate_line_from_claude(self):
        log = logging.getLogger("test_pl_fas_mail")
        claude_body = (
            "Cześć,\n\nTu Claude.\n\n"
            f"{FAS_MUST_KEEP_RATE_LINE}\n\n"
            "Pozdrawiam\nMaksym Swinczak\nswinczakdata.pl\n+48 516 513 965"
        )
        with patch(
            "email_custom_template.inquiry_try_custom",
            return_value=("Temat FAS test", claude_body),
        ):
            subject, body = scraper.generate_email_content("Firma X", log)
        assert subject == "Temat FAS test"
        assert FAS_MUST_KEEP_RATE_LINE in body
        assert "swinczakdata.pl" in body

    def test_sanitize_sender_name_default_fas(self):
        assert scraper.sanitize_sender_name("") == (
            "Maksym Swinczak, Forwarding Assistant"
        )
        assert "Forwarding Assistant" in scraper.sanitize_sender_name("   ")


class TestSerperBadDomainsPl:
    def test_pl_junk_present_de_retail_absent(self):
        bad = scraper.SERPER_BAD_DOMAINS
        assert "panoramafirm.pl" in bad
        assert "gus.gov.pl" in bad
        assert "pracuj.pl" in bad
        assert "raben-group" in bad
        assert "aldi-sued.de" not in bad
        assert "ibau.de" not in bad
        assert "filialfinder" not in bad

    def test_score_penalizes_panorama_and_big3pl(self):
        good = scraper.score_serper_candidate(
            "https://trans-spedycja.pl",
            "Spedycja FTL",
            "firma spedycyjna",
        )
        panorama = scraper.score_serper_candidate(
            "https://panoramafirm.pl/firma/x",
            "katalog",
            "spedycja",
        )
        raben = scraper.score_serper_candidate(
            "https://www.raben-group.com",
            "Raben",
            "logistyka",
        )
        assert good > panorama
        assert good > raben
        assert panorama < 0
        assert raben < 0


class TestIcpFlagsAndLegalForms:
    def test_named_chain_means_segments_not_aldi(self):
        assert scraper.REQUIRE_NAMED_RETAIL_CHAIN is True
        assert scraper.REQUIRE_SMALL_FIRM is True
        text = "Firma spedycyjna FTL LTL Europa flota trasy"
        chains = scraper.detect_retail_chains_in_text(text)
        assert "ftl" in chains
        assert "aldi" not in chains

    def test_company_legal_form_pl(self):
        assert scraper._company_name_has_legal_form("Trans Spedycja Sp. z o.o.")
        assert scraper._company_name_has_legal_form("Logistyka Polska S.A.")
        assert scraper._company_name_has_legal_form("Kultbau GmbH")

    def test_page_mentions_ftl_ok_ladenbau_rejected(self):
        ok, chains, _ = scraper.page_mentions_retail_store_projects(
            "Firma spedycyjna. Transport drogowy FTL LTL Europa. Realizacje, flota."
        )
        assert ok
        assert "ftl" in chains
        bad, _, _ = scraper.page_mentions_retail_store_projects(
            "Ladenbau Filialbau Neubau Gewerbe bez spedycji"
        )
        assert not bad

    def test_excel_export_row_pl_columns(self):
        rows = scraper.build_export_rows(
            [
                {
                    "nazwa": "Trans Spedycja Sp. z o.o.",
                    "company_name_clean": "Trans Spedycja Sp. z o.o.",
                    "url": "https://trans-spedycja.pl",
                    "www": "https://trans-spedycja.pl",
                    "email_target": "biuro@trans-spedycja.pl",
                    "retail_verified": True,
                    "is_gu": True,
                    "is_small_firm": True,
                    "gu_marker": "spedycja",
                    "bundesland": "Dolnoslaskie",
                    "page_snippet": "Firma spedycyjna FTL LTL",
                    "retail_chains_found": "ftl, ltl",
                }
            ]
        )
        assert len(rows) == 1
        row = rows[0]
        assert "Województwo" in row
        assert "Segmenty" in row or "Spedycja" in row
        assert row.get("E-mail") == "biuro@trans-spedycja.pl"


class TestApplyGuExtrasIcpFromJson:
    def test_extras_toggle_small_firm_off(self):
        mod = SimpleNamespace(
            REQUIRE_NAMED_RETAIL_CHAIN=True,
            REQUIRE_SMALL_FIRM=True,
            REQUIRE_WEBSITE_RETAIL_VERIFICATION=True,
            _pl_spedycja_filter=None,
        )
        scraper.apply_gu_run_config_extras(
            mod,
            {
                "require_named_retail_chain": False,
                "require_small_firm": False,
            },
        )
        assert mod.REQUIRE_NAMED_RETAIL_CHAIN is False
        assert mod.REQUIRE_SMALL_FIRM is False


class TestGeoPlFas:
    def test_center_and_bbox_are_poland(self):
        assert 49.0 <= scraper.REGION_CENTER_LAT <= 55.0
        assert 14.0 <= scraper.REGION_CENTER_LON <= 25.0
        assert scraper._coords_in_pl_bbox(
            scraper.REGION_CENTER_LAT, scraper.REGION_CENTER_LON
        )
        assert scraper.PL_BBOX_LAT_MIN == scraper.DE_DE_BBOX_LAT_MIN

    def test_foreign_tld_excludes_de_keeps_pl(self):
        assert ".pl" not in scraper._FOREIGN_TLD_SUFFIXES
        assert ".de" in scraper._FOREIGN_TLD_SUFFIXES

    def test_poland_candidate_accepts_pl_rejects_de(self):
        assert scraper.is_poland_pl_candidate(
            "https://trans-spedycja.pl/oferta", "Spedycja FTL", "Głogów"
        )
        assert not scraper.is_poland_pl_candidate(
            "https://mueller-bau.de/kontakt", "GmbH", "München Bayern"
        )
        assert scraper.is_poland_pl_candidate is scraper.is_germany_de_candidate

    def test_no_mfg_inquiry_import(self):
        assert not hasattr(scraper, "FIXED_GU_INQUIRY_DE")

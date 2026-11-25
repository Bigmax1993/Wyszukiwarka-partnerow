# Test: Kontakte tylko z e-mailem i telefonem.
from __future__ import annotations

import pl_fas_spedycja_scraper as scraper


def test_flags_require_email_and_phone_for_excel():
    assert scraper.EXPORT_PIPELINE_ROWS_WITHOUT_EMAIL is False
    assert scraper.EXPORT_PIPELINE_ROWS_WITHOUT_PHONE is False


def test_build_export_rows_skips_without_email_or_phone():
    rows = scraper.build_export_rows(
        [
            {
                "nazwa": "Bez Maila Sp. z o.o.",
                "company_name_clean": "Bez Maila Sp. z o.o.",
                "url": "https://bez-maila.pl",
                "www": "https://bez-maila.pl",
                "email_target": "",
                "telefon": "+48 71 111 22 33",
                "retail_verified": True,
                "is_gu": True,
                "is_small_firm": True,
                "page_snippet": "Firma spedycyjna FTL LTL",
                "retail_chains_found": "ftl",
            },
            {
                "nazwa": "Bez Telefonu Sp. z o.o.",
                "company_name_clean": "Bez Telefonu Sp. z o.o.",
                "url": "https://bez-tel.pl",
                "www": "https://bez-tel.pl",
                "email_target": "biuro@bez-tel.pl",
                "telefon": "",
                "retail_verified": True,
                "is_gu": True,
                "is_small_firm": True,
                "page_snippet": "Firma spedycyjna FTL LTL",
                "retail_chains_found": "ftl",
            },
            {
                "nazwa": "Pelny Kontakt Sp. z o.o.",
                "company_name_clean": "Pelny Kontakt Sp. z o.o.",
                "url": "https://pelny-kontakt.pl",
                "www": "https://pelny-kontakt.pl",
                "email_target": "biuro@pelny-kontakt.pl",
                "telefon": "+48 71 123 45 67",
                "retail_verified": True,
                "is_gu": True,
                "is_small_firm": True,
                "page_snippet": "Firma spedycyjna FTL LTL",
                "retail_chains_found": "ftl",
            },
        ]
    )
    assert len(rows) == 1
    assert rows[0]["E-mail"] == "biuro@pelny-kontakt.pl"
    assert scraper._excel_phone_ok(rows[0]["Telefon"])
    assert rows[0]["Nazwa firmy"] == "Pelny Kontakt Sp. z o.o."


def test_maps_needs_enrich_still_eligible_for_json_gate():
    """Maps Faza A używa eligibility do JSON — bez maila OK w cache."""
    row = {
        "nazwa": "Maps Firma Sp. z o.o.",
        "url": "https://maps-firma.pl",
        "discovery_source": "google_maps",
        "gap_status": scraper.GAP_STATUS_NEEDS_ENRICH,
        "maps_url": "https://maps.google.com/?cid=1",
        "email_target": "",
    }
    assert scraper.is_row_eligible_for_excel_export(row) is True
    assert scraper.build_export_rows([row]) == []


def test_row_from_cache_promotes_emails_found_to_excel():
    info = {
        "company_name": "Relon Logistics Sp. z o.o.",
        "official_website": "https://relon.pl",
        "email_target": "",
        "emails_found": "kontakt@relon.pl, payments@relon.pl",
        "phones_found": "+48 76 862 70 70",
        "retail_verified": True,
        "is_small_firm": True,
        "is_gu": True,
        "retail_chains_found": "ftl",
        "page_snippet": "spedycja FTL LTL",
    }
    row = scraper.row_from_cache_contact("https://relon.pl", info)
    assert row is not None
    assert "@" in (row.get("email_target") or "")
    exported = scraper.build_export_rows([row])
    assert len(exported) == 1
    assert "@" in exported[0]["E-mail"]
    assert scraper._excel_phone_ok(exported[0]["Telefon"])

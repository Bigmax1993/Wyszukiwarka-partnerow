# -*- coding: utf-8 -*-
"""Testy Fazy B — gap_fill_serper."""
from __future__ import annotations

from datetime import datetime, timedelta

from gap_fill_serper import (
    GAP_STATUS_ENRICHED,
    GAP_STATUS_NEEDS_ENRICH,
    GAP_STATUS_STILL_GAP,
    build_gap_fill_queries,
    contact_has_gap,
    extract_city_hint,
    filter_queries_outside_ttl,
    find_contact_key_by_domain,
    iter_gap_contacts,
    merge_enrichment_into_contact,
    should_attempt_gap_fill,
    store_gap_fill_result,
)


def test_contact_has_gap_no_email():
    assert contact_has_gap(
        {
            "company_name": "Relon",
            "official_website": "https://relon.pl/",
            "email_target": "",
        }
    )


def test_contact_has_gap_maps_only_www():
    assert contact_has_gap(
        {
            "company_name": "Olimpia",
            "official_website": "",
            "maps_url": "https://www.google.com/maps/place/X",
            "email_target": "",
            "telefon": "123",
        }
    )


def test_contact_no_gap_when_email_and_www():
    assert not contact_has_gap(
        {
            "company_name": "Relon",
            "official_website": "https://relon.pl/",
            "email_target": "a@relon.pl",
            "telefon": "",
        }
    )


def test_extract_city_from_postal_and_term():
    assert extract_city_hint({"full_address": "Smolna 19, 67-200 Głogów"}) == "Głogów"
    assert (
        extract_city_hint({"discovery_search_term": "firma spedycyjna Głogów LTL"})
        == "Głogów"
    )


def test_build_gap_fill_queries_includes_city():
    qs = build_gap_fill_queries(
        {
            "company_name": "Relon Logistics Sp. z o.o.",
            "full_address": "Smolna 19, 67-200 Głogów",
        }
    )
    assert len(qs) == 2
    assert "Relon" in qs[0] and "Głogów" in qs[0] and "spedycja" in qs[0]
    assert "firma spedycyjna" in qs[1]


def test_iter_gap_contacts_prefers_needs_enrich():
    contacts = {
        "https://a.pl": {
            "company_name": "A",
            "gap_status": GAP_STATUS_STILL_GAP,
            "email_target": "",
            "official_website": "https://a.pl",
            "enriched_at": "2000-01-01T00:00:00",
        },
        "https://b.pl": {
            "company_name": "B Relon",
            "gap_status": GAP_STATUS_NEEDS_ENRICH,
            "discovery_source": "google_maps",
            "email_target": "",
            "official_website": "https://b.pl",
        },
    }
    keys = [k for k, _ in iter_gap_contacts(contacts)]
    assert keys[0] == "https://b.pl"


def test_merge_sets_enriched_when_email_found():
    info = {
        "company_name": "Relon",
        "gap_status": GAP_STATUS_NEEDS_ENRICH,
        "official_website": "",
        "email_target": "",
        "discovery_source": "google_maps",
    }
    enriched = {
        "email_target": "kontakt@relon.pl",
        "official_website": "https://relon.pl/",
        "phones_found": "123",
        "retail_verified": True,
    }
    out = merge_enrichment_into_contact(
        info, enriched, queries=["Relon Głogów spedycja"], website="https://relon.pl/"
    )
    assert out["gap_status"] == GAP_STATUS_ENRICHED
    assert out["email_target"] == "kontakt@relon.pl"
    assert out["serper_gap_queries"] == ["Relon Głogów spedycja"]
    assert out["enriched_at"]


def test_merge_still_gap_without_email_or_www():
    info = {"company_name": "X", "gap_status": GAP_STATUS_NEEDS_ENRICH}
    out = merge_enrichment_into_contact(info, {}, queries=["X spedycja"], website="")
    assert out["gap_status"] == GAP_STATUS_STILL_GAP


def test_query_ttl_skips_same_queries():
    info = {
        "company_name": "Relon Logistics",
        "full_address": "67-200 Głogów",
        "gap_status": GAP_STATUS_STILL_GAP,
        "email_target": "",
        "official_website": "",
        "enriched_at": datetime.now().isoformat(),
        "serper_gap_queries": [
            "Relon Logistics Głogów spedycja",
            "Relon Logistics Głogów firma spedycyjna",
        ],
    }
    qs = build_gap_fill_queries(info)
    fresh = filter_queries_outside_ttl(info, qs)
    assert fresh == []
    assert not should_attempt_gap_fill(info)


def test_query_ttl_allows_retry_after_expiry():
    info = {
        "company_name": "Relon Logistics",
        "full_address": "67-200 Głogów",
        "gap_status": GAP_STATUS_STILL_GAP,
        "email_target": "",
        "official_website": "",
        "enriched_at": (datetime.now() - timedelta(days=10)).isoformat(),
        "serper_gap_queries": ["Relon Logistics Głogów spedycja"],
    }
    assert should_attempt_gap_fill(info)
    fresh = filter_queries_outside_ttl(info, build_gap_fill_queries(info))
    assert len(fresh) == 2


def test_store_merges_into_existing_domain_no_duplicate():
    import pl_fas_spedycja_scraper as s

    contacts = {
        "https://relon.pl": {
            "company_name": "Relon Logistics",
            "official_website": "https://relon.pl",
            "email_target": "",
            "gap_status": GAP_STATUS_NEEDS_ENRICH,
        },
        "https://www.google.com/maps/place/Relon": {
            "company_name": "Relon Logistics Sp. z o.o.",
            "maps_url": "https://www.google.com/maps/place/Relon",
            "official_website": "",
            "email_target": "",
            "gap_status": GAP_STATUS_NEEDS_ENRICH,
            "discovery_source": "google_maps",
        },
    }
    updated = {
        "company_name": "Relon Logistics Sp. z o.o.",
        "official_website": "https://relon.pl/",
        "email_target": "kontakt@relon.pl",
        "telefon": "123",
        "gap_status": GAP_STATUS_ENRICHED,
        "serper_gap_queries": ["Relon Głogów spedycja"],
        "enriched_at": datetime.now().isoformat(),
        "maps_url": "https://www.google.com/maps/place/Relon",
    }
    owner = find_contact_key_by_domain(
        contacts,
        "https://relon.pl/",
        scraper_mod=s,
        exclude_key="https://www.google.com/maps/place/Relon",
    )
    assert owner == "https://relon.pl"
    target = store_gap_fill_result(
        contacts,
        "https://www.google.com/maps/place/Relon",
        updated,
        scraper_mod=s,
    )
    assert target == "https://relon.pl"
    assert contacts["https://relon.pl"]["email_target"] == "kontakt@relon.pl"
    assert contacts["https://www.google.com/maps/place/Relon"]["merged_into"] == (
        "https://relon.pl"
    )
    # nie powstał trzeci klucz domeny
    assert "https://relon.pl/" not in contacts

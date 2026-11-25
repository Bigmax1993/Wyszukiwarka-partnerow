# -*- coding: utf-8 -*-
"""Testy google_maps_scraper + mapowanie do wierszy discovery."""
from __future__ import annotations

from google_maps_scraper import maps_hits_to_discovery_rows, _maps_search_url


def test_maps_search_url_encodes_query():
    url = _maps_search_url("firma spedycyjna Głogów")
    assert url.startswith("https://www.google.com/maps/search/")
    assert "hl=pl" in url
    assert "G" in url or "%C5%82" in url or "glog" in url.lower() or "G%C5%82og" in url


def test_maps_hits_to_discovery_rows_prefers_website():
    hits = [
        {
            "name": "Relon Logistics Sp. z o.o.",
            "address": "Smolna 19, Głogów",
            "phone": "+48 736 318 412",
            "website": "https://relon.pl/",
            "maps_url": "https://www.google.com/maps/place/Relon",
            "rating": "4.8",
            "reviews": "126",
        },
        {
            "name": "OLIMPIA TRANSPORT",
            "address": "Piastowska 5",
            "phone": "",
            "website": "",
            "maps_url": "https://www.google.com/maps/place/Olimpia",
        },
        {"name": "", "website": "https://x.pl", "maps_url": ""},
    ]
    rows = maps_hits_to_discovery_rows("firma spedycyjna Głogów", hits)
    assert len(rows) == 2
    assert rows[0]["url"] == "https://relon.pl/"
    assert rows[0]["official_website"] == "https://relon.pl/"
    assert rows[0]["discovery_source"] == "google_maps"
    assert rows[0]["gap_status"] == "needs_enrich"
    assert rows[0]["telefon"].startswith("+48")
    assert rows[1]["url"].startswith("https://www.google.com/maps/")
    assert rows[1]["official_website"] == ""
    assert rows[1]["nazwa"] == "OLIMPIA TRANSPORT"
    assert rows[1]["gap_status"] == "needs_enrich"


def test_maps_phase_a_contact_builder():
    import pl_fas_spedycja_scraper as s

    row = {
        "nazwa": "Relon Logistics Sp. z o.o.",
        "company_name_raw": "Relon Logistics Sp. z o.o.",
        "official_website": "https://relon.pl/",
        "maps_url": "https://www.google.com/maps/place/Relon",
        "full_address": "Smolna 19, Głogów",
        "telefon": "+48 736 318 412",
        "fraza": "firma spedycyjna Głogów",
        "discovery_source": "google_maps",
        "gap_status": "needs_enrich",
    }
    contact = s._build_maps_phase_a_contact(row, discovery_wojewodztwo="Dolnoslaskie")
    assert contact["gap_status"] == s.GAP_STATUS_NEEDS_ENRICH
    assert contact["discovery_source"] == "google_maps"
    assert contact["email_target"] == ""
    assert contact["email_status"] == s.MAPS_PHASE_A_EMAIL_STATUS
    assert contact["official_website"] == "https://relon.pl/"
    assert contact["maps_url"].startswith("https://www.google.com/maps/")
    assert contact["telefon"].startswith("+48")
    assert s._maps_phase_a_contact_key(row) in (
        "https://relon.pl",
        "https://relon.pl/",
    )

# Test: coerce_cleanup_result_1to1 dopasowuje cały rekord do walidacji.
from __future__ import annotations

import pl_fas_spedycja_scraper as scraper


def test_coerce_picks_valid_phone_email_website_and_drops_junk_name():
    row = {
        "nazwa": "Best Performance Logistics Sp. z o.o.",
        "phones_found": "0000525946, +48222501247",
        "emails_found": "noreply@mail.com, pdziekan@bestperf.com",
        "official_website": "https://www.bestperf.com/kontakt",
        "retail_chains_found": "ftl, aldi, ltl",
        "bundesland": "",
        "adres": "ul. Testowa 1, 00-001 Warszawa",
    }
    parsed = {
        "company_name_clean": "Best Performance Logistics Sp. z o.o.",
        "address": "ul. Testowa 1, 00-001 Warszawa",
        "phone": "05-11-2026",
        "email": "noreply@mail.com",
        "website": "https://www.bestperf.com/kontakt",
        "bundesland": "NotAState",
        "handelsketten": "ftl, aldi, ltl",
        "url": "https://www.bestperf.com/kontakt",
    }
    out = scraper.coerce_cleanup_result_1to1(
        parsed,
        row=row,
        company_raw=row["nazwa"],
        address_raw=row["adres"],
        phone_raw=row["phones_found"],
        email_raw=row["emails_found"],
        website_raw=row["official_website"],
        segments_raw=row["retail_chains_found"],
    )
    assert "Best Performance" in out["company_name_clean"]
    assert scraper._excel_phone_ok(out["phone"])
    assert out["email"] == "pdziekan@bestperf.com"
    assert out["website"].startswith("https://")
    assert "kontakt" not in out["website"].rstrip("/").split("/")[-1] or out[
        "website"
    ].endswith("bestperf.com") or "bestperf.com" in out["website"]
    assert "aldi" not in out["handelsketten"]
    assert "ftl" in out["handelsketten"]
    assert scraper._excel_email_ok(out["email"])


def test_parse_cleanup_includes_email():
    from claude_row_cleanup import parse_claude_row_cleanup_response

    data = parse_claude_row_cleanup_response(
        '{"company_name_clean":"X Sp. z o.o.","address":"","phone":"+48 22 111 22 33",'
        '"email":"biuro@x.pl","website":"https://x.pl","bundesland":"Mazowieckie",'
        '"handelsketten":"ftl","url":"https://x.pl"}'
    )
    assert data["email"] == "biuro@x.pl"
    assert data["phone"].startswith("+48")

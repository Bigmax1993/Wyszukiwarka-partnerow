# Test: pick_best_pl_phone wybiera prawdziwy +48 ze śmieciowego bloba.
from __future__ import annotations

import pl_fas_spedycja_scraper as scraper


def test_pick_best_skips_date_and_zeros():
    raw = "05-11-2026, 0000081253, +48 327 935 935, 06 011"
    picked = scraper.pick_best_pl_phone(raw)
    assert picked
    assert scraper._excel_phone_ok(picked)
    digits = "".join(ch for ch in picked if ch.isdigit())
    assert "327935935" in digits or digits.endswith("327935935") or "48327935935" in digits


def test_pick_best_prefers_plus48_buried_in_blob():
    raw = "0000525946, 0/1393229, +48222501247, 05 138 970"
    picked = scraper.pick_best_pl_phone(raw)
    assert picked
    assert scraper._excel_phone_ok(picked)
    digits = "".join(ch for ch in picked if ch.isdigit())
    assert digits.startswith("48") or len(digits.lstrip("0")) >= 9


def test_has_phone_gap_fill_uses_pick_best():
    import gap_fill_serper as gap

    info = {
        "email_target": "biuro@example.pl",
        "phones_found": "05-11-2026, 0000081253, +48 327 935 935",
        "official_website": "https://example.pl",
    }
    assert gap.has_email(info)
    assert gap.has_phone(info)
    assert gap.contact_has_gap(info) is False


def test_build_export_rows_picks_buried_phone():
    rows = scraper.build_export_rows(
        [
            {
                "nazwa": "Blob Phone Sp. z o.o.",
                "company_name_clean": "Blob Phone Sp. z o.o.",
                "url": "https://blob-phone.pl",
                "www": "https://blob-phone.pl",
                "email_target": "biuro@blob-phone.pl",
                "phones_found": "05-11-2026, 0000081253, +48 327 935 935",
                "telefon": "",
                "retail_verified": True,
                "is_gu": True,
                "is_small_firm": True,
                "page_snippet": "Firma spedycyjna FTL LTL",
                "retail_chains_found": "ftl",
            }
        ]
    )
    assert len(rows) == 1
    assert scraper._excel_phone_ok(rows[0]["Telefon"])

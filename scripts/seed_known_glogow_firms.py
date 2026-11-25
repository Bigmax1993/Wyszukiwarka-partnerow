# -*- coding: utf-8 -*-
"""
Seed znanych firm z Głogowa (Antrans, Arra Group) do cache + Excel Kontakte.

  python scripts/seed_known_glogow_firms.py
  python scripts/seed_known_glogow_firms.py --campaign-dir /opt/bots/Wyszukiwarka-partnerow
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SEED_FIRMS = [
    {
        "key": "https://antrans.eu",
        "company_name": "Antrans Sp. z o.o. Sp. k.",
        "official_website": "https://antrans.eu/",
        "full_address": "Transportowa 6, 67-200 Głogów, Polska",
        "city": "Głogów",
        "email_target": "antrans@antrans.eu",
        "emails_found": "antrans@antrans.eu, biuro@antrans.eu",
        "telefon": "+48 695 950 300",
        "phones_found": "+48 695 950 300, +48 76 832 00 20",
        "discovery_search_term": "Antrans Głogów",
    },
    {
        "key": "https://www.arra-group.com",
        "company_name": "Arra Group Sp. z o.o.",
        "official_website": "https://www.arra-group.com/",
        "full_address": "ul. Piastowska 5, 67-200 Głogów, Polska",
        "city": "Głogów",
        "email_target": "salesPL@arra-group.com",
        "emails_found": "salesPL@arra-group.com, salespl@arra-group.com",
        "telefon": "+48 535 507 071",
        "phones_found": "+48 535 507 071, +48 509 345 476",
        "discovery_search_term": "Arra Group Głogów",
    },
]


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def build_contact(seed: dict) -> dict:
    name = seed["company_name"]
    return {
        "company_name": name,
        "company_name_raw": name,
        "company_name_clean": name,
        "official_website": seed["official_website"],
        "www": seed["official_website"],
        "full_address": seed["full_address"],
        "city": seed["city"],
        "miasto": seed["city"],
        "email_target": seed["email_target"],
        "emails_found": seed["emails_found"],
        "email_status": "seeded",
        "telefon": seed["telefon"],
        "phones_found": seed["phones_found"],
        "discovery_source": "manual_seed",
        "discovery_search_term": seed["discovery_search_term"],
        "gap_status": "enriched",
        "is_gu": True,
        "gu_marker": "spedycja",
        "retail_verified": True,
        "verification_reason": "manual_seed:znana firma transportowa/spedycja Głogów",
        "seeded_at": _now(),
        "page_snippet": (
            f"{name} spedycja transport FTL Głogów {seed['full_address']} "
            f"{seed['telefon']}"
        ),
        "serper_title": name,
        "serper_snippet": f"{name} spedycja transport {seed['full_address']}",
        "bundesland": "Dolnoslaskie",
        "wojewodztwo": "Dolnoslaskie",
        "discovery_wojewodztwo": "Dolnoslaskie",
    }


def _upsert_kontakte_xlsx(xlsx: Path, seeds: list[dict]) -> None:
    import pandas as pd
    from openpyxl import load_workbook

    if not xlsx.is_file():
        raise SystemExit(f"Brak Excela: {xlsx}")

    df = pd.read_excel(xlsx, sheet_name="Kontakte")
    # normalize columns expected by export
    col_map = {
        "Nazwa firmy": "Nazwa firmy",
        "Adres": "Adres",
        "Województwo": "Województwo",
        "Miasto": "Miasto",
        "Telefon": "Telefon",
        "E-mail": "E-mail",
        "Strona www": "Strona www",
        "URL": "URL",
    }
    for c in col_map:
        if c not in df.columns:
            df[c] = ""

    def _key(row) -> str:
        return str(row.get("URL") or row.get("Strona www") or "").strip().rstrip("/").lower()

    by_url = {}
    for _, row in df.iterrows():
        k = _key(row)
        if k:
            by_url[k] = row.to_dict()

    for seed in seeds:
        k = seed["key"].rstrip("/").lower()
        by_url[k] = {
            **(by_url.get(k) or {}),
            "Nazwa firmy": seed["company_name"],
            "Adres": seed["full_address"],
            "Województwo": "Dolnośląskie",
            "Miasto": seed["city"],
            "Telefon": seed["telefon"],
            "E-mail": seed["email_target"],
            "Strona www": seed["official_website"],
            "URL": seed["key"],
            "WWW sprawdzone": "Tak",
            "Spedycja": "Tak",
            "Status": "seed",
        }

    out = pd.DataFrame(list(by_url.values()))
    # preserve column order from original where possible
    ordered = [c for c in df.columns if c in out.columns] + [
        c for c in out.columns if c not in df.columns
    ]
    out = out[ordered]

    wb = load_workbook(xlsx)
    if "Kontakte" in wb.sheetnames:
        ws = wb["Kontakte"]
        wb.remove(ws)
    # write via pandas to a temp sheet then... simpler: use ExcelWriter mode append
    wb.save(xlsx)
    wb.close()

    with pd.ExcelWriter(
        xlsx, engine="openpyxl", mode="a", if_sheet_exists="replace"
    ) as writer:
        out.to_excel(writer, sheet_name="Kontakte", index=False)
    print(f"excel Kontakte upsert: {len(seeds)} firm, sheet rows={len(out)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-dir", type=Path, default=ROOT)
    parser.add_argument("--skip-excel", action="store_true")
    args = parser.parse_args(argv)

    camp = args.campaign_dir.resolve()
    sys.path.insert(0, str(camp))
    import os

    os.chdir(camp)
    os.environ.setdefault("KANBUD_DATA_DIR", str(camp))

    import pl_fas_spedycja_scraper as s

    logger = s.setup_logging()
    cache = s.load_cache(logger)
    contacts = cache.setdefault("contacts", {})
    added = []
    updated = []
    for seed in SEED_FIRMS:
        key = seed["key"]
        info = build_contact(seed)
        if key in contacts and isinstance(contacts[key], dict):
            existing = contacts[key]
            existing.update(info)
            contacts[key] = existing
            updated.append(key)
        else:
            contacts[key] = info
            added.append(key)

    s.save_cache(cache, logger)
    contacts = cache.get("contacts") or {}
    print(f"cache: added={len(added)} updated={len(updated)}")
    for seed in SEED_FIRMS:
        u = seed["key"]
        info = contacts.get(u) or {}
        print(
            " ",
            u,
            "→",
            info.get("company_name") or "MISSING_AFTER_PURGE",
            info.get("email_target") or "",
        )

    if not args.skip_excel:
        present = [s for s in SEED_FIRMS if s["key"] in contacts]
        if present:
            _upsert_kontakte_xlsx(Path(s.OUTPUT_FILE), present)
        else:
            print("SKIP excel — seed nie przetrwał purge cache")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

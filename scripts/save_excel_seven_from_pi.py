# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Moduł (skrypt CLI, jednorazowy): scripts/save_excel_seven_from_pi — zapis 7 firm do Excela z artefaktu piątkowego discovery.
#
# CO ROBI: składa 7 wierszy: firmy z istniejącego Excela (arkusz Kontakte) oraz firmy wskazane w _EXTRA_CACHE_URLS z cache JSON, które wypadają przy ostrych
#   filtrach eksportu; zapisuje je do lokalnego Excela (Info, Kontakte, Wojewodztwa) i aktualizuje cache.
# ROLA W PIPELINE: ręczna operacja ops po discovery (etap „cache/Excel”); wiele nazw kolumn (GU, Kleinunternehmen, WWW_geprueft) i język "de" to pozostałości po kampanii DE.
# ZALEŻNOŚCI: pl_fas_spedycja_scraper (jako scraper), libs.scraper_email_replies (ReplySyncConfig, write_excel_with_reply_styles), stdlib json, logging, sys, pathlib.
# WEJŚCIE: lokalny cache i Excel kampanii. WYJŚCIE: nadpisany Excel (scraper.OUTPUT_FILE), zapis cache, wydruk nazw 7 firm, kod 0.
# ============================================================
"""
Zapis 7 firm do Excel z artefaktu piątkowego discovery (pl-spedycja-wyniki-pi).

5 firm z arkusza Kontakte + 2 z cache JSON (Gropp bg-hd.de, Münch+Muench),
które wypadają przy ostrych filtrach eksportu (sieć „dm” poza whitelistą).
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIBS = ROOT / "libs"
for _p in (ROOT, LIBS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from libs.scraper_email_replies import ReplySyncConfig, write_excel_with_reply_styles  # noqa: E402

import pl_fas_spedycja_scraper as scraper  # noqa: E402

# Dwie firmy z piątkowego cache, których nie ma w xlsx po filtrach.
_EXTRA_CACHE_URLS = (
    "https://bg-hd.de",
    "https://muenchundmuench.com",
)


# >>> OPIS FUNKCJI: funkcja _contact_to_pipeline_row
# Cel: zmapować kontakt z cache na wiersz pipeline (eksport 7 firm). Parametry: place_url (str); info (dict). Zwraca: dict po scraper.normalize_row_company_name (nazwa, www, e-mail, telefon, adres,
# bundesland, flagi retail_verified/is_gu/is_small_firm — tu domyślnie False, status e-maila). Efekty uboczne/błędy: brak własnych.
def _contact_to_pipeline_row(place_url: str, info: dict) -> dict:
    """Zmapuj kontakt cache → wiersz pipeline (eksport 7 firm)."""
    name = (
        info.get("company_name_clean")
        or info.get("company_name")
        or info.get("company_name_raw")
        or ""
    ).strip()
    email = (info.get("email_target") or "").strip()
    if not email:
        found = [
            x.strip()
            for x in (info.get("emails_found") or "").split(",")
            if x.strip() and "@" in x
        ]
        email = found[0] if found else ""
    phone = (info.get("phones_found") or "").strip()
    if "," in phone:
        phone = phone.split(",", 1)[0].strip()
    return scraper.normalize_row_company_name(
        {
            "url": place_url,
            "www": info.get("official_website") or place_url,
            "official_website": info.get("official_website") or place_url,
            "nazwa": name,
            "company_name_clean": name,
            "company_name_raw": info.get("company_name_raw") or name,
            "email_target": email,
            "emails_found": info.get("emails_found") or "",
            "telefon": phone,
            "phones_found": info.get("phones_found") or phone,
            "full_address": info.get("full_address") or "",
            "adres": info.get("full_address") or "",
            "bundesland": info.get("bundesland") or "",
            "retail_verified": bool(info.get("retail_verified")),
            "verification_reason": (info.get("verification_reason") or "").strip(),
            "page_snippet": (info.get("page_snippet") or "").strip(),
            "retail_chains_found": (info.get("retail_chains_found") or "").strip(),
            "is_gu": bool(info.get("is_gu")),
            "is_small_firm": bool(info.get("is_small_firm")),
            "gu_marker": (info.get("gu_marker") or "").strip(),
            "email_status": (info.get("email_status") or "").strip(),
        }
    )


# >>> OPIS FUNKCJI: funkcja _pipeline_row_to_export
# Cel: zamienić wiersz pipeline na kolumny Excela. Parametry: row (dict). Zwraca: dict — kolumny z scraper.row_to_excel_kontakte_columns oraz WWW_geprueft, Kleinunternehmen, GU, GU_Marker (ja/nein)
# i Status. Efekty uboczne/błędy: brak własnych.
def _pipeline_row_to_export(row: dict) -> dict:
    """Wiersz pipeline → kolumny Excela (ops eksport 7 firm)."""
    email = (row.get("email_target") or "").strip()
    if not email:
        found = [
            x.strip()
            for x in (row.get("emails_found") or "").split(",")
            if x.strip() and "@" in x
        ]
        if found:
            email, _ = scraper.pick_best_email_for_inquiry(
                found, row.get("official_website") or row.get("www") or ""
            )
    table = scraper.row_to_excel_kontakte_columns(row, email)
    return {
        **table,
        "WWW_geprueft": "ja" if row.get("retail_verified") else "nein",
        "Kleinunternehmen": "ja" if row.get("is_small_firm") else "nein",
        "GU": "ja" if row.get("is_gu") or scraper._row_has_gu_signal(row) else "nein",
        "GU_Marker": (row.get("gu_marker") or "").strip(),
        "Status": scraper._excel_status_label(row),
    }


# >>> OPIS FUNKCJI: funkcja build_seven_rows
# Cel: złożyć dokładnie 7 wierszy do zapisu. Parametry: logger. Zwraca: (rows[:7], cache) — wiersze z istniejącego Excela uzupełnione/nadpisane wpisami z _EXTRA_CACHE_URLS.
# Efekty uboczne: wczytanie cache i Excela, scraper.sync_pipeline_rows_to_contacts_cache, ostrzeżenia o brakujących kontaktach.
# Błędy: SystemExit, gdy po złożeniu jest mniej niż 7 firm.
def build_seven_rows(logger: logging.Logger) -> tuple[list[dict], dict]:
    """Złóż 7 wierszy: Excel + 2 firmy z cache spoza ostrych filtrów."""
    cache = scraper.load_cache(logger)
    rows, _ = scraper.load_existing_output(scraper.OUTPUT_FILE, logger)
    by_url = scraper.index_all_rows_by_url(rows)
    contacts = cache.get("contacts") or {}

    for place_url in _EXTRA_CACHE_URLS:
        info = contacts.get(place_url)
        if not isinstance(info, dict):
            logger.warning("Brak kontaktu w cache: %s", place_url)
            continue
        row = _contact_to_pipeline_row(place_url, info)
        url = (row.get("url") or place_url).strip()
        if url in by_url:
            by_url[url].update(row)
        else:
            rows.append(row)
            by_url[url] = row

    scraper.sync_pipeline_rows_to_contacts_cache(rows, cache)

    if len(rows) < 7:
        raise SystemExit(
            f"Za malo firm do zapisu: {len(rows)} (oczekiwano 7). "
            "Uruchom na artefakcie pl-spedycja-wyniki-pi z piatku."
        )

    return rows[:7], cache


# >>> OPIS FUNKCJI: funkcja main
# Cel: CLI zapisujące 7 firm do lokalnego Excela. Parametry: brak. Zwraca: int 0.
# Efekty uboczne: nadpisuje scraper.OUTPUT_FILE (arkusze Info, Kontakte, Wojewodztwa; lang="de", campaign_id="pl_spedycja"), zapisuje cache, drukuje listę nazw.
# Błędy: SystemExit z build_seven_rows; błędy zapisu propagują się.
def main() -> int:
    """CLI: zapisz 7 firm z artefaktu pi do Excela lokalnego."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger("excel_seven")

    rows, cache = build_seven_rows(logger)
    export_rows = [_pipeline_row_to_export(r) for r in rows]
    state_rows = scraper.build_bundesland_rows(rows)

    cfg = ReplySyncConfig(
        cache_path=scraper.CACHE_FILE,
        xlsx_path=scraper.OUTPUT_FILE,
        lang="de",
        campaign_id="pl_spedycja",
    )
    write_excel_with_reply_styles(
        scraper.OUTPUT_FILE,
        {
            "Info": scraper.build_excel_info_sheet_rows(),
            "Kontakte": export_rows,
            "Wojewodztwa": state_rows,
        },
        cache,
        cfg,
        logger,
    )
    scraper.save_cache(cache, logger)

    names = [r.get("Nazwa firmy") or "" for r in export_rows]
    print(f"Zapisano {len(export_rows)} firm w {scraper.OUTPUT_FILE}:")
    for i, name in enumerate(names, 1):
        print(f"  {i}. {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

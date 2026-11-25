# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Moduł (skrypt CLI): scripts/export_week_discovery_all_to_excel — scalenie artefaktów discovery z kilku dni do jednego Excela.
#
# CO ROBI
#   Pobiera (gh run download) artefakty "pl-spedycja-wyniki-pi" dla podanych run ID, scala wpisy contacts z cache JSON (z próbą odzysku przy uszkodzonym JSON),
#   mapuje je na wiersze pipeline, a następnie zapisuje WSZYSTKIE firmy do Excela (arkusze Info, Kontakte, Wojewodztwa) bez ostrych filtrów eksportu
#   (wpisy bez e-maila lub pominięte też trafiają do arkusza).
# ROLA W PIPELINE: raport tygodniowy po cyklu discovery (etap „cache/Excel”). Uruchamiany ręcznie lub w CI.
# ZALEŻNOŚCI: pl_fas_spedycja_scraper (jako scraper — normalizacja wierszy, kolumny Excela, cache), pl_spedycja_filter.get_discovery_wojewodztwo,
#   libs.scraper_email_replies (ReplySyncConfig, write_excel_with_reply_styles), recover_pi_cache_contacts, GitHub CLI (gh), stdlib.
# WEJŚCIE: --run-ids (wymagane), --repo, --label, --output. WYJŚCIE: plik Excel, zaktualizowany lokalny cache, kod wyjścia i podsumowanie na stdout.
# ============================================================
"""
Scal artefakty pl-spedycja-wyniki-pi z kilku dni discovery i zapisz WSZYSTKIE firmy z cache do Excela.

Pomija ostre filtry eksportu (skipped / bez maila też trafiają do arkusza).
"""
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIBS = ROOT / "libs"
SCRIPTS = ROOT / "scripts"
for _p in (ROOT, LIBS, SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from recover_pi_cache_contacts import recover_contacts_from_cache_file  # noqa: E402

from libs.scraper_email_replies import ReplySyncConfig, write_excel_with_reply_styles  # noqa: E402
from pl_spedycja_filter import get_discovery_wojewodztwo  # noqa: E402

import pl_fas_spedycja_scraper as scraper  # noqa: E402


# >>> OPIS FUNKCJI: funkcja _contact_to_pipeline_row
# Cel: zmapować wpis cache contacts na wiersz pipeline scrapera. Parametry: place_url (str); info (dict) — dane kontaktu z cache.
# Zwraca: dict wiersza (po scraper.normalize_row_company_name) — nazwa, www, e-mail (email_target lub pierwszy z emails_found), pierwszy telefon, adres,
# województwo (bundesland / get_discovery_wojewodztwo), flagi weryfikacji (retail_verified, is_gu, is_small_firm domyślnie True), powód weryfikacji, status e-maila.
# Efekty uboczne/błędy: brak własnych (czysta transformacja).
def _contact_to_pipeline_row(place_url: str, info: dict) -> dict:
    """Zmapuj wpis cache contacts → wiersz pipeline scrapera."""
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
            "bundesland": (
                info.get("bundesland")
                or get_discovery_wojewodztwo(info)
                or ""
            ),
            "discovery_wojewodztwo": get_discovery_wojewodztwo(info),
            "retail_verified": bool(info.get("retail_verified")),
            "verification_reason": (info.get("verification_reason") or "").strip(),
            "page_snippet": (info.get("page_snippet") or "").strip(),
            "retail_chains_found": (info.get("retail_chains_found") or "").strip(),
            "is_gu": bool(info.get("is_gu")),
            "is_small_firm": bool(info.get("is_small_firm", True)),
            "gu_marker": (info.get("gu_marker") or "").strip(),
            "email_status": (info.get("email_status") or "").strip(),
        }
    )


# >>> OPIS FUNKCJI: funkcja _pipeline_row_to_export
# Cel: zamienić wiersz pipeline na wiersz arkusza Kontakte. Parametry: row (dict).
# Zwraca: dict — kolumny z scraper.row_to_excel_kontakte_columns plus „WWW sprawdzone”, „Spedycja”, „Status” i „Weryfikacja” (powód do 200 znaków); e-mail wybrany przez
# scraper.pick_best_email_for_inquiry, gdy brak email_target. Efekty uboczne/błędy: brak własnych.
def _pipeline_row_to_export(row: dict) -> dict:
    """Wiersz pipeline → kolumny arkusza Kontakte (eksport tygodnia)."""
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
    reason = (row.get("verification_reason") or "").strip()
    return {
        **table,
        "WWW sprawdzone": scraper._excel_yes_no(bool(row.get("retail_verified"))),
        "Spedycja": scraper._excel_yes_no(
            bool(row.get("is_gu") or scraper._row_has_gu_signal(row))
        ),
        "Status": scraper._excel_status_label(row),
        "Weryfikacja": reason[:200] if reason else "",
    }


# >>> OPIS FUNKCJI: funkcja _load_cache_file
# Cel: wczytać plik cache JSON. Parametry: path (Path). Zwraca: dict. Efekty uboczne: odczyt UTF-8. Błędy: JSONDecodeError/OSError propagują się.
def _load_cache_file(path: Path) -> dict:
    """Wczytaj plik cache JSON (utf-8)."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# >>> OPIS FUNKCJI: funkcja _download_pi_artifact
# Cel: pobrać artefakt "pl-spedycja-wyniki-pi" z GitHub Actions. Parametry: run_id (str); dest (Path) — katalog docelowy; repo (keyword-only, str).
# Zwraca: Path do Wyniki/pl_spedycja_cache.json albo None, gdy pobranie zawiodło lub brak pliku. Efekty uboczne: tworzy katalog, uruchamia "gh run download", log warning.
# Błędy: kod wyjścia gh != 0 → warning i None.
def _download_pi_artifact(run_id: str, dest: Path, *, repo: str) -> Path | None:
    """Pobierz artefakt pl-spedycja-wyniki-pi; zwróć ścieżkę cache lub None."""
    dest.mkdir(parents=True, exist_ok=True)
    cmd = [
        "gh",
        "run",
        "download",
        str(run_id),
        "-R",
        repo,
        "-n",
        "pl-spedycja-wyniki-pi",
        "-D",
        str(dest),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        logging.warning("Pomijam run %s: %s", run_id, (proc.stderr or proc.stdout).strip())
        return None
    cache_path = dest / "Wyniki" / "pl_spedycja_cache.json"
    return cache_path if cache_path.is_file() else None


# >>> OPIS FUNKCJI: funkcja merge_contacts_from_run_ids
# Cel: scalić contacts z wielu runów discovery. Parametry: run_ids (list[str]); repo (keyword-only, str); skip_corrupt (keyword-only, bool, True).
# Zwraca: (merged: dict[url → info], loaded: list[run_id]) — późniejszy run nadpisuje wpis tego samego URL. Efekty uboczne: pobiera artefakty do katalogów tymczasowych, logi.
# Błędy: uszkodzony JSON → próba odzysku (recover_contacts_from_cache_file) przy skip_corrupt=True, inaczej wyjątek; runy bez artefaktu pomijane.
def merge_contacts_from_run_ids(
    run_ids: list[str],
    *,
    repo: str,
    skip_corrupt: bool = True,
) -> tuple[dict, list[str]]:
    """Scal contacts z wielu runów pi; zwraca (merged, lista załadowanych run_id)."""
    merged: dict[str, dict] = {}
    loaded: list[str] = []
    for run_id in run_ids:
        run_id = run_id.strip()
        if not run_id:
            continue
        with tempfile.TemporaryDirectory(prefix=f"gu-pi-{run_id}-") as tmp:
            cache_path = _download_pi_artifact(run_id, Path(tmp), repo=repo)
            if not cache_path:
                continue
            try:
                cache = _load_cache_file(cache_path)
                contacts = cache.get("contacts") or {}
            except json.JSONDecodeError as exc:
                if skip_corrupt:
                    logging.warning(
                        "run %s: uszkodzony JSON (%s) — probuje odzysku contacts",
                        run_id,
                        exc,
                    )
                    contacts = recover_contacts_from_cache_file(cache_path)
                else:
                    raise
            if not isinstance(contacts, dict):
                continue
            for url, info in contacts.items():
                if isinstance(info, dict):
                    merged[url] = info
            loaded.append(run_id)
            logging.info(
                "run %s: +%s kontaktow (lacznie %s)", run_id, len(contacts), len(merged)
            )
    return merged, loaded


# >>> OPIS FUNKCJI: funkcja export_merged_contacts
# Cel: zbudować wiersze pipeline i cache z scalonych kontaktów (bez ostrych filtrów). Parametry: contacts (dict); label (keyword-only, str) — etykieta tygodnia.
# Zwraca: (rows: list[dict], cache: dict) — wiersze posortowane po nazwie i URL (pomijane bez nazwy i URL); cache z contacts i week_export_meta.
# Efekty uboczne: scraper.sync_pipeline_rows_to_contacts_cache, log. Błędy: SystemExit("Brak firm do eksportu po scaleniu cache.") gdy nic do eksportu.
def export_merged_contacts(
    contacts: dict[str, dict],
    *,
    label: str = "",
) -> tuple[list[dict], dict]:
    """Zbuduj wiersze pipeline + cache z scalonych kontaktów (bez ostrych filtrów)."""
    logger = logging.getLogger("week_export")
    cache = scraper._empty_cache()
    cache["contacts"] = dict(contacts)
    rows = []
    for place_url, info in contacts.items():
        if not isinstance(info, dict):
            continue
        row = _contact_to_pipeline_row(place_url, info)
        name = (row.get("nazwa") or "").strip()
        url = (row.get("url") or "").strip()
        if not name and not url:
            continue
        rows.append(row)
    rows.sort(key=lambda r: ((r.get("nazwa") or "").lower(), r.get("url") or ""))
    if not rows:
        raise SystemExit("Brak firm do eksportu po scaleniu cache.")
    scraper.sync_pipeline_rows_to_contacts_cache(rows, cache)
    if label:
        cache.setdefault("week_export_meta", {})["label"] = label
        cache["week_export_meta"]["exported_rows"] = len(rows)
    logger.info("Eksport tygodnia: %s unikalnych firm", len(rows))
    return rows, cache


# >>> OPIS FUNKCJI: funkcja write_excel
# Cel: zapisać Excel (Info, Kontakte, Wojewodztwa) i zaktualizować lokalny cache. Parametry: rows (list[dict]); cache (dict); logger; output (Path|None — domyślnie scraper.OUTPUT_FILE).
# Zwraca: Path zapisanego pliku. Efekty uboczne: tworzy katalog, zapis xlsx (write_excel_with_reply_styles, lang="pl", campaign_id="pl_spedycja"), scraper.save_cache.
# Błędy: propagowane.
def write_excel(rows: list[dict], cache: dict, logger: logging.Logger, output: Path | None = None) -> Path:
    """Zapisz Excel Kontakte/Wojewodztwa i zaktualizuj cache lokalny."""
    export_rows = [_pipeline_row_to_export(r) for r in rows]
    state_rows = scraper.build_bundesland_rows(rows)
    out = output or scraper.OUTPUT_FILE
    out.parent.mkdir(parents=True, exist_ok=True)
    cfg = ReplySyncConfig(
        cache_path=scraper.CACHE_FILE,
        xlsx_path=out,
        lang="pl",
        campaign_id="pl_spedycja",
    )
    write_excel_with_reply_styles(
        out,
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
    return out


# >>> OPIS FUNKCJI: funkcja main
# Cel: CLI scalające artefakty i zapisujące Excel. Parametry: brak (argparse: --run-ids, --repo, --label, --output). Zwraca: int 0 po sukcesie.
# Efekty uboczne: pobieranie artefaktów, zapis Excela i cache, wydruk podsumowania. Błędy: SystemExit, gdy nie udało się pobrać żadnego artefaktu lub brak firm.
def main() -> int:
    """CLI: scal artefakty pi z tygodnia i wyeksportuj wszystkie firmy do Excela."""
    parser = argparse.ArgumentParser(
        description="Scal pi z tygodnia discovery i zapisz wszystkie firmy do Excela"
    )
    parser.add_argument(
        "--run-ids",
        required=True,
        help="Lista run ID (pl-spedycja-wyniki-pi), po przecinku",
    )
    parser.add_argument(
        "--repo",
        default="Bigmax1993/Wyszukiwarka-partnerow",
        help="GitHub repo (owner/name)",
    )
    parser.add_argument(
        "--label",
        default="",
        help="Etykieta tygodnia (np. 2026-06-15_2026-06-21)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Sciezka docelowego Excela (domyslnie Wyniki/pl_spedycja_kontakte.xlsx)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger("week_export")

    run_ids = [x.strip() for x in args.run_ids.split(",") if x.strip()]
    contacts, loaded = merge_contacts_from_run_ids(run_ids, repo=args.repo)
    if not loaded:
        raise SystemExit("Nie udalo sie pobrac zadnego artefaktu pi.")
    rows, cache = export_merged_contacts(contacts, label=args.label)
    out = write_excel(rows, cache, logger, output=args.output)

    with_email = sum(1 for r in rows if (r.get("email_target") or "").strip())
    print(
        f"Zapisano {len(rows)} firm ({with_email} z e-mailem) -> {out}\n"
        f"Zrodlo: run IDs {', '.join(loaded)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

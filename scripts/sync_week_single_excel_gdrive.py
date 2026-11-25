# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Moduł (skrypt CLI, jednorazowy): scripts/sync_week_single_excel_gdrive — jeden plik Excela tygodnia discovery na Google Drive.
#
# CO ROBI: scala artefakty discovery (run ID), zapisuje lokalny Excel o nazwie <prefiks kontakte>_<etykieta tygodnia>.xlsx, a następnie (o ile Drive nie jest wyłączony i nie podano
#   --dry-run) usuwa z folderu Drive stare pliki Excela z prefiksem kontakte i wysyła nowy plik jako jedyną kopię.
# ROLA W PIPELINE: ręczny krok porządkujący wyniki tygodnia na Drive (po discovery).
# ZALEŻNOŚCI: export_week_discovery_all_to_excel (scalanie i zapis), gdrive_upload_wyniki (poświadczenia, Drive API, upload), recover_pi_cache_contacts, pl_spedycja_data_paths (ID folderu), scraper_env.
# WEJŚCIE: --run-ids, --repo, --week-label, --folder-id, --dry-run. WYJŚCIE: lokalny Excel, zmiany na Drive, kod 0 lub SystemExit przy braku artefaktów.
# UWAGA: operacja kasująca na Drive — działa tylko przy DISABLE_GOOGLE_DRIVE=0.
# ============================================================
"""
Jednorazowy sync tygodnia discovery: jeden plik Excel na Google Drive, usuniecie starych kopii.

Uzycie (GHA lub lokalnie z OAuth):
  python scripts/sync_week_single_excel_gdrive.py \\
    --run-ids "27533750486,27638016924,27787280147,27837533068" \\
    --week-label "2026-06-15_2026-06-21"
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for _p in (ROOT, SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from pl_spedycja_data_paths import GOOGLE_DRIVE_FAS_FOLDER_ID  # noqa: E402
import export_week_discovery_all_to_excel as week_export  # noqa: E402
import gdrive_upload_wyniki as gdrive  # noqa: E402
from recover_pi_cache_contacts import recover_contacts_from_cache_file  # noqa: E402

_KONTAKTE_PREFIX = "pl_spedycja_kontakte"


# >>> OPIS FUNKCJI: funkcja _list_kontakte_xlsx
# Cel: wylistować pliki xlsx z prefiksem kontakte w folderze Drive. Parametry: service; folder_id (str). Zwraca: list[dict] (id, name) z paginacją (pageSize=100).
# Efekty uboczne: zapytania list do API. Błędy: propagowane.
def _list_kontakte_xlsx(service, folder_id: str) -> list[dict]:
    """Lista plików .xlsx kontakte w folderze Drive."""
    q = (
        f"'{folder_id}' in parents and trashed = false and "
        f"mimeType = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' and "
        f"name contains '{_KONTAKTE_PREFIX}'"
    )
    files: list[dict] = []
    page_token = None
    while True:
        res = (
            service.files()
            .list(
                q=q,
                fields="nextPageToken, files(id,name)",
                pageSize=100,
                pageToken=page_token,
                corpora="allDrives",
                **gdrive._LIST_OPTS,
            )
            .execute()
        )
        files.extend(res.get("files") or [])
        page_token = res.get("nextPageToken")
        if not page_token:
            break
    return files


# >>> OPIS FUNKCJI: funkcja _delete_drive_files
# Cel: usunąć wskazane pliki z Drive. Parametry: service; files (list[dict] z id/name). Zwraca: int — liczba usuniętych plików (wpisy bez id pomijane).
# Efekty uboczne: TRWAŁE usunięcie plików przez API, wydruk nazw. Błędy: wyjątki API propagują się.
def _delete_drive_files(service, files: list[dict]) -> int:
    """Usuń wskazane pliki Drive; zwróć liczbę skasowanych."""
    n = 0
    for f in files:
        fid = f.get("id")
        name = f.get("name") or fid
        if not fid:
            continue
        service.files().delete(fileId=fid, **gdrive._DRIVE_API_OPTS).execute()
        print(f"  Usunieto: {name}")
        n += 1
    return n


# >>> OPIS FUNKCJI: funkcja main
# Cel: CLI synchronizujące jeden Excel tygodnia. Parametry: brak (argparse: --run-ids wymagane, --repo, --week-label, --folder-id, --dry-run). Zwraca: int 0 (także w trybie dry-run lub NO-OP przy wyłączonym Drive).
# Efekty uboczne: pobranie artefaktów, zapis Excela w Wyniki/, na Drive: usunięcie starych kopii i upload nowego pliku (bez wersjonowania datą).
# Błędy: SystemExit, gdy nie pobrano żadnego artefaktu; błąd odczytu scraper_env łapany (fallback na env DISABLE_GOOGLE_DRIVE); błędy API propagują się.
def main() -> int:
    """CLI: jeden Excel tygodnia na Drive (usuwa stare kopie kontakte)."""
    parser = argparse.ArgumentParser(
        description="Jeden Excel z tygodnia discovery na Drive (usuwa stare kopie kontakte)"
    )
    parser.add_argument("--run-ids", required=True)
    parser.add_argument("--repo", default="Bigmax1993/Wyszukiwarka-partnerow")
    parser.add_argument("--week-label", default="2026-06-15_2026-06-21")
    parser.add_argument(
        "--folder-id",
        default=os.environ.get("GDRIVE_FOLDER_ID", GOOGLE_DRIVE_FAS_FOLDER_ID),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Tylko eksport lokalny, bez Drive",
    )
    args = parser.parse_args()

    import logging

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger("week_single_sync")

    try:
        from scraper_env import is_google_drive_disabled

        drive_off = is_google_drive_disabled()
    except Exception:
        raw = (os.environ.get("DISABLE_GOOGLE_DRIVE") or "1").strip().lower()
        drive_off = raw not in ("0", "false", "no", "off")

    excel_name = f"{_KONTAKTE_PREFIX}_{args.week_label}.xlsx"
    wyniki = ROOT / "Wyniki"
    wyniki.mkdir(parents=True, exist_ok=True)
    output = wyniki / excel_name

    run_ids = [x.strip() for x in args.run_ids.split(",") if x.strip()]
    contacts, loaded = week_export.merge_contacts_from_run_ids(run_ids, repo=args.repo)
    if not loaded:
        raise SystemExit("Nie udalo sie pobrac zadnego artefaktu pi.")
    rows, cache = week_export.export_merged_contacts(contacts, label=args.week_label)
    week_export.write_excel(rows, cache, logger, output=output)

    with_email = sum(1 for r in rows if (r.get("email_target") or "").strip())
    print(f"Excel lokalny: {output} ({len(rows)} firm, {with_email} z e-mailem)")

    if args.dry_run or drive_off:
        if drive_off and not args.dry_run:
            print(
                "[NO-OP] Google Drive wyłączony (DISABLE_GOOGLE_DRIVE=1) — "
                "zostawiam tylko Excel lokalny."
            )
        return 0

    creds, use_oauth = gdrive._load_credentials()
    service, MediaFileUpload = gdrive._drive_service(creds)
    folder_id = gdrive._resolve_upload_folder(service, args.folder_id, use_oauth=use_oauth)

    old_files = _list_kontakte_xlsx(service, folder_id)
    if old_files:
        print(f"Usuwam {len(old_files)} starych plikow Excel ({_KONTAKTE_PREFIX}*) z Drive:")
        _delete_drive_files(service, old_files)
    else:
        print("Brak starych plikow Excel do usuniecia.")

    print(f"Upload: {excel_name}")
    gdrive._upload_file(service, MediaFileUpload, output, folder_id, version_xlsx=False)
    print(
        f"Gotowe: 1 plik na Drive ({len(rows)} firm).\n"
        f"https://drive.google.com/drive/folders/{folder_id}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

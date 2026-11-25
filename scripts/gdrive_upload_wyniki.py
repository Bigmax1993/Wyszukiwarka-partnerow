# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Moduł (skrypt CLI): scripts/gdrive_upload_wyniki — upload plików z Wyniki/ (oraz opcjonalnie wyslane/) na Google Drive.
#
# CO ROBI
#   Ładuje poświadczenia (preferowany OAuth użytkownika z GDRIVE_OAUTH_*, w drugiej kolejności konto usługowe
#   z GDRIVE_SERVICE_ACCOUNT_JSON/FILE, opcjonalnie delegacja DWD), ustala folder docelowy (OAuth / Shared Drive /
#   impersonacja), wysyła pliki płasko do folderu Excela, a katalog wyslane/ do podfolderu "wyslane". Pliki .json i .log
#   (cache, logi) NIE są uploadowane. Arkusze .xlsx są domyślnie wersjonowane datą (GDRIVE_VERSION_XLSX=1): powstaje plik
#   z sufiksem _RRRR-MM-DD_GGMM oraz aktualna kopia bez daty.
#
# ROLA W PIPELINE: ostatni krok publikacji wyników (po discovery/backfill) w GitHub Actions lub lokalnie. Cały moduł jest
#   NO-OP, gdy DISABLE_GOOGLE_DRIVE jest włączone (domyślnie włączone — patrz scraper_env.is_google_drive_disabled).
#
# ZALEŻNOŚCI: pl_spedycja_data_paths (resolve_data_root, wyniki_dir, wyslane_dir, ID folderu Drive), scraper_env (kill switch),
#   google-auth / google-api-python-client (importowane leniwie), stdlib argparse, json, mimetypes, os, sys, datetime, pathlib.
# WEJŚCIE: argumenty CLI --campaign-dir, --folder-id oraz zmienne środowiskowe GDRIVE_*. WYJŚCIE: kod wyjścia (0 sukces/NO-OP,
#   1 gdy nie było plików), komunikaty na stdout; funkcje pomocnicze zwracają id plików/folderów lub liczniki.
# BŁĘDY: brakujące/niepoprawne poświadczenia kończą proces przez SystemExit z czytelnym komunikatem.
# ============================================================
"""
Upload folderu Wyniki/ (+ opcjonalnie wyslane/) do Google Drive.

Cache (.json) i logi (.log) NIE są uploadowane — zostają w artefaktach GitHub Actions.

Konto usługowe nie ma własnej przestrzeni dyskowej — pliki muszą trafić na
Shared Drive (dysk zespołowy) albo upload w imieniu użytkownika (delegacja DWD).

Zmienne:
  GDRIVE_SERVICE_ACCOUNT_JSON / GDRIVE_SERVICE_ACCOUNT_FILE
  GDRIVE_FOLDER_ID — folder końcowego Excela (domyślnie 1bRCAqle6BS46YEw0fScq4P095LsJUSgL)
  GDRIVE_SHARED_DRIVE_ID — opcjonalnie ID dysku współdzielonego (auto-wykrywanie, jeśli puste)
  GDRIVE_IMPERSONATE_EMAIL — opcjonalnie e-mail użytkownika Workspace (domain-wide delegation)
  GDRIVE_VERSION_XLSX — 1 (domyślnie): każdy .xlsx jako nowy plik z datą, bez nadpisywania
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIBS = ROOT / "libs"
for _p in (ROOT, LIBS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from pl_spedycja_data_paths import (  # noqa: E402
    GOOGLE_DRIVE_FAS_FOLDER_ID,
    resolve_data_root,
    wyniki_dir,
    wyslane_dir,
)

# Pełny dostęp do Drive (wymagany dla Shared Drive i nadpisywania plików).
SCOPES = ("https://www.googleapis.com/auth/drive",)

_DRIVE_API_OPTS = {
    "supportsAllDrives": True,
    "supportsTeamDrives": True,
}
_LIST_OPTS = {
    **_DRIVE_API_OPTS,
    "includeItemsFromAllDrives": True,
}

_GU_FOLDER_NAME = "PL Spedycja Wyniki"

# Cache (.json) i logi zostają w artefaktach GitHub — nie na Drive.
_GDRIVE_SKIP_SUFFIXES = frozenset({".json", ".log"})


# >>> OPIS FUNKCJI: funkcja _skip_gdrive_upload
# Cel: zdecydować, czy pominąć plik przy uploadzie. Parametry: path (Path). Zwraca: bool — True dla rozszerzeń z _GDRIVE_SKIP_SUFFIXES
# (cache .json, logi .log — zostają jako artefakty GHA). Efekty uboczne/błędy: brak.
def _skip_gdrive_upload(path: Path) -> bool:
    """True = nie uploaduj (cache .json / logi — tylko artefakt GHA)."""
    return path.suffix.lower() in _GDRIVE_SKIP_SUFFIXES


# >>> OPIS FUNKCJI: funkcja _gdrive_version_xlsx_enabled
# Cel: sprawdzić, czy Excel ma być wysyłany jako nowy plik z datą. Parametry: brak. Zwraca: bool — zmienna GDRIVE_VERSION_XLSX
# (domyślnie włączona; wyłączają ją 0/false/no/off). Efekty uboczne/błędy: brak.
def _gdrive_version_xlsx_enabled() -> bool:
    """Czy Excel ma iść jako nowy plik z datą (GDRIVE_VERSION_XLSX, domyślnie ON)."""
    raw = (os.environ.get("GDRIVE_VERSION_XLSX") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


# >>> OPIS FUNKCJI: funkcja _upload_stamp
# Cel: znacznik czasu do nazw wersjonowanych plików. Parametry: brak. Zwraca: str "RRRR-MM-DD_GGMM" w strefie SCRAPER_TIMEZONE
# (domyślnie Europe/Warsaw). Błędy: przy błędzie strefy/braku zoneinfo — czas lokalny OS (wyjątek łapany).
def _upload_stamp() -> str:
    """Znacznik czasu Europe/Warsaw do nazw wersjonowanych .xlsx."""
    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(os.environ.get("SCRAPER_TIMEZONE", "Europe/Warsaw"))
        return datetime.now(tz).strftime("%Y-%m-%d_%H%M")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d_%H%M")


# >>> OPIS FUNKCJI: funkcja versioned_xlsx_upload_name
# Cel: zbudować nazwę wersjonowaną pliku xlsx. Parametry: filename (str); stamp (keyword-only, str|None — domyślnie _upload_stamp()).
# Zwraca: str — np. pl_spedycja_kontakte.xlsx → pl_spedycja_kontakte_2026-06-08_1405.xlsx; dla plików innych niż .xlsx sama nazwa.
# Efekty uboczne/błędy: brak.
def versioned_xlsx_upload_name(filename: str, *, stamp: str | None = None) -> str:
    """pl_spedycja_kontakte.xlsx → pl_spedycja_kontakte_2026-06-08_1405.xlsx"""
    path = Path(filename)
    if path.suffix.lower() != ".xlsx":
        return path.name
    tag = stamp or _upload_stamp()
    return f"{path.stem}_{tag}{path.suffix}"


# >>> OPIS FUNKCJI: funkcja _load_oauth_credentials
# Cel: wczytać poświadczenia OAuth użytkownika. Parametry: brak. Zwraca: obiekt Credentials (odświeżony refresh tokenem) albo None, gdy
# brak GDRIVE_OAUTH_REFRESH_TOKEN. Efekty uboczne: żądanie odświeżenia tokenu do Google, import bibliotek google-auth.
# Błędy: SystemExit przy braku GDRIVE_OAUTH_CLIENT_ID/SECRET lub biblioteki google-auth.
def _load_oauth_credentials():
    """OAuth użytkownika z env GDRIVE_OAUTH_* albo None gdy brak refresh tokena."""
    refresh = (os.environ.get("GDRIVE_OAUTH_REFRESH_TOKEN") or "").strip()
    if not refresh:
        return None
    client_id = (os.environ.get("GDRIVE_OAUTH_CLIENT_ID") or "").strip()
    client_secret = (os.environ.get("GDRIVE_OAUTH_CLIENT_SECRET") or "").strip()
    if not client_id or not client_secret:
        raise SystemExit(
            "Ustaw GDRIVE_OAUTH_CLIENT_ID i GDRIVE_OAUTH_CLIENT_SECRET "
            "(uruchom scripts/gdrive_oauth_setup.py)."
        )
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except ImportError as e:
        raise SystemExit("pip install google-auth\n" + str(e)) from e

    creds = Credentials(
        token=None,
        refresh_token=refresh,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=list(SCOPES),
    )
    creds.refresh(Request())
    return creds


# >>> OPIS FUNKCJI: funkcja _load_service_account_credentials
# Cel: wczytać poświadczenia konta usługowego (JSON z env lub plik) i opcjonalnie włączyć delegację DWD. Parametry: brak.
# Zwraca: obiekt Credentials (z subject, jeśli ustawiono GDRIVE_IMPERSONATE_EMAIL). Efekty uboczne: wypisuje informację o delegacji.
# Błędy: SystemExit — brak biblioteki, wartość wyglądająca jak klucz API (AIza…), niepoprawny JSON, JSON niebędący kluczem konta usługowego
# lub brak źródła poświadczeń.
def _load_service_account_credentials():
    """Credentials konta usługowego (JSON env / plik) + opcjonalna delegacja DWD."""
    try:
        from google.oauth2 import service_account
    except ImportError as e:
        raise SystemExit(
            "Zainstaluj: pip install google-api-python-client google-auth\n" + str(e)
        ) from e

    raw = (os.environ.get("GDRIVE_SERVICE_ACCOUNT_JSON") or "").strip()
    path = (os.environ.get("GDRIVE_SERVICE_ACCOUNT_FILE") or "").strip()
    if raw:
        if raw.startswith("AIza"):
            raise SystemExit(
                "GDRIVE_SERVICE_ACCOUNT_JSON wyglada na klucz API (AIza...). "
                "Wklej caly plik JSON z Konta uslugi -> Klucze (type=service_account)."
            )
        try:
            info = json.loads(raw)
        except json.JSONDecodeError as e:
            raise SystemExit(
                f"GDRIVE_SERVICE_ACCOUNT_JSON nie jest poprawnym JSON: {e}. "
                "W GitHub Secrets wklej cala tresc pobranego pliku .json."
            ) from e
        if info.get("type") != "service_account" or not info.get("client_email"):
            raise SystemExit(
                "JSON musi byc kluczem konta uslugowego (type=service_account, client_email)."
            )
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    elif path and Path(path).is_file():
        creds = service_account.Credentials.from_service_account_file(path, scopes=SCOPES)
    else:
        raise SystemExit(
            "Ustaw GDRIVE_SERVICE_ACCOUNT_JSON (treść) lub GDRIVE_SERVICE_ACCOUNT_FILE (ścieżka)."
        )

    impersonate = (os.environ.get("GDRIVE_IMPERSONATE_EMAIL") or "").strip()
    if impersonate:
        creds = creds.with_subject(impersonate)
        print(f"Delegacja DWD: upload w imieniu {impersonate}")
    return creds


# >>> OPIS FUNKCJI: funkcja _load_credentials
# Cel: wybrać metodę uwierzytelnienia. Parametry: brak. Zwraca: (creds, use_oauth: bool) — OAuth, jeśli skonfigurowany, inaczej konto usługowe.
# Efekty uboczne: komunikaty na stdout. Błędy: propagowane (SystemExit) z funkcji ładujących.
def _load_credentials():
    """Preferuj OAuth; fallback = service account. Zwraca (creds, use_oauth)."""
    oauth = _load_oauth_credentials()
    if oauth is not None:
        print("OAuth: upload na Twoj Dysk Google (folder udostepniony uzytkownikowi)")
        return oauth, True
    return _load_service_account_credentials(), False


# >>> OPIS FUNKCJI: funkcja _drive_service
# Cel: zbudować klienta Google Drive API v3. Parametry: creds. Zwraca: (service, MediaFileUpload) — klient oraz klasa do uploadu.
# Efekty uboczne: leniwy import googleapiclient. Błędy: ImportError, gdy brak biblioteki.
def _drive_service(creds):
    """Zbuduj klienta Drive API v3 oraz klasę MediaFileUpload."""
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    return service, MediaFileUpload


# >>> OPIS FUNKCJI: funkcja _folder_metadata
# Cel: pobrać metadane folderu Drive. Parametry: service; folder_id (str). Zwraca: dict (id, name, driveId, mimeType, parents).
# Efekty uboczne: wywołanie API. Błędy: wyjątki API propagują się.
def _folder_metadata(service, folder_id: str) -> dict:
    """Metadane folderu Drive (id, name, driveId, …)."""
    return (
        service.files()
        .get(
            fileId=folder_id,
            fields="id,name,driveId,mimeType,parents",
            **_DRIVE_API_OPTS,
        )
        .execute()
    )


# >>> OPIS FUNKCJI: funkcja _list_shared_drives
# Cel: wylistować dyski współdzielone dostępne dla poświadczeń. Parametry: service. Zwraca: list[dict] (id, name), z paginacją.
# Efekty uboczne: wywołania API. Błędy: propagowane.
def _list_shared_drives(service) -> list[dict]:
    """Lista Shared Drives dostępnych dla bieżących credentials."""
    drives: list[dict] = []
    page_token = None
    while True:
        res = (
            service.drives()
            .list(pageSize=100, pageToken=page_token, fields="nextPageToken,drives(id,name)")
            .execute()
        )
        drives.extend(res.get("drives") or [])
        page_token = res.get("nextPageToken")
        if not page_token:
            break
    return drives


# >>> OPIS FUNKCJI: funkcja _find_folder_in_parent
# Cel: znaleźć podfolder o nazwie w folderze nadrzędnym. Parametry: service; parent_id (str); name (str; apostrofy escapowane).
# Zwraca: str|None — id pierwszego pasującego, nieusuniętego folderu. Efekty uboczne: zapytanie list API. Błędy: propagowane.
def _find_folder_in_parent(service, parent_id: str, name: str) -> str | None:
    """Znajdź ID podfolderu o danej nazwie w parent_id (lub None)."""
    safe_name = name.replace("'", "\\'")
    q = (
        f"'{parent_id}' in parents and name = '{safe_name}' "
        f"and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    res = (
        service.files()
        .list(q=q, fields="files(id)", pageSize=1, corpora="allDrives", **_LIST_OPTS)
        .execute()
    )
    files = res.get("files") or []
    return files[0]["id"] if files else None


# >>> OPIS FUNKCJI: funkcja _create_folder
# Cel: utworzyć folder na Drive. Parametry: service; parent_id (str); name (str); drive_id (keyword-only, str|None) — dla Shared Drive.
# Zwraca: str — id nowego folderu. Efekty uboczne: tworzenie folderu przez API. Błędy: propagowane.
def _create_folder(service, parent_id: str, name: str, *, drive_id: str | None = None) -> str:
    """Utwórz folder w parent_id; zwróć nowe file id."""
    meta: dict = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    if drive_id:
        meta["driveId"] = drive_id
    created = service.files().create(body=meta, fields="id", **_DRIVE_API_OPTS).execute()
    return created["id"]


# >>> OPIS FUNKCJI: funkcja _resolve_shared_drive_upload_folder
# Cel: ustalić folder docelowy na Shared Drive. Parametry: service; preferred_folder_id (str).
# Zwraca: (folder_id, shared_drive_id) — preferowany folder, jeśli już leży na Shared Drive; inaczej folder o nazwie _GU_FOLDER_NAME (istniejący
# lub nowo utworzony) w wybranym dysku (GDRIVE_SHARED_DRIVE_ID albo pierwszy dostępny).
# Efekty uboczne: komunikaty, ewentualne utworzenie folderu. Błędy: SystemExit, gdy konto nie widzi żadnego Shared Drive.
def _resolve_shared_drive_upload_folder(service, preferred_folder_id: str) -> tuple[str, str]:
    """
    Zwraca (folder_id, shared_drive_id) do uploadu na Shared Drive.
    """
    configured_drive = (os.environ.get("GDRIVE_SHARED_DRIVE_ID") or "").strip()
    drives = _list_shared_drives(service)
    if configured_drive:
        drive_ids = {d["id"] for d in drives}
        if configured_drive not in drive_ids and drives:
            print(
                f"Uwaga: GDRIVE_SHARED_DRIVE_ID={configured_drive} niedostepny; "
                f"uzywam {drives[0]['name']}"
            )
            shared_drive_id = drives[0]["id"]
        elif configured_drive in drive_ids or not drives:
            shared_drive_id = configured_drive
        else:
            raise SystemExit(
                "Brak dostepnych Shared Drives dla konta uslugowego. "
                "Dodaj je jako czlonka dysku wspoldzielonego (Content manager)."
            )
    elif drives:
        shared_drive_id = drives[0]["id"]
        print(f"Shared Drive: {drives[0].get('name', shared_drive_id)}")
    else:
        raise SystemExit(
            "Konto uslugowe nie widzi zadnego Shared Drive.\n"
            "Najprosciej: uruchom na PC  python scripts/gdrive_oauth_setup.py\n"
            "(OAuth na Twoj folder — bez Shared Drive).\n"
            "Albo: dysk wspoldzielony + e-mail konta uslugowego jako Content manager."
        )

    try:
        meta = _folder_metadata(service, preferred_folder_id)
        if meta.get("driveId"):
            print(f"Folder docelowy jest na Shared Drive: {meta.get('name', preferred_folder_id)}")
            return preferred_folder_id, meta["driveId"]
    except Exception:
        pass

    existing = _find_folder_in_parent(service, shared_drive_id, _GU_FOLDER_NAME)
    if existing:
        print(f"Uzywam folderu na Shared Drive: {_GU_FOLDER_NAME} ({existing})")
        return existing, shared_drive_id

    created = _create_folder(
        service, shared_drive_id, _GU_FOLDER_NAME, drive_id=shared_drive_id
    )
    print(f"Utworzono folder na Shared Drive: {_GU_FOLDER_NAME} ({created})")
    return created, shared_drive_id


# >>> OPIS FUNKCJI: funkcja _resolve_upload_folder
# Cel: wybrać folder, do którego można uploadować. Parametry: service; folder_id (str); use_oauth (keyword-only, bool).
# Zwraca: str — folder_id przy OAuth, przy folderze na Shared Drive albo przy delegacji DWD; w przeciwnym razie folder z
# _resolve_shared_drive_upload_folder. Efekty uboczne: komunikaty. Błędy: odczyt metadanych jest łapany (komunikat); dalsze błędy — propagowane.
def _resolve_upload_folder(service, folder_id: str, *, use_oauth: bool) -> str:
    """Ustal folder, do którego można uploadować (OAuth / Shared Drive / impersonacja)."""
    if use_oauth:
        print(f"OAuth -> folder {folder_id}")
        return folder_id
    try:
        meta = _folder_metadata(service, folder_id)
        if meta.get("driveId"):
            print(f"Upload na Shared Drive (folder: {meta.get('name', folder_id)})")
            return folder_id
    except Exception as exc:
        print(f"Nie mozna odczytac folderu {folder_id}: {exc}")

    if (os.environ.get("GDRIVE_IMPERSONATE_EMAIL") or "").strip():
        print(f"Upload przez delegacje do folderu {folder_id}")
        return folder_id

    print(
        "Folder jest na 'Moim dysku' — konto uslugowe nie moze tam zapisywac plikow. "
        "Przelaczam na Shared Drive..."
    )
    upload_id, _drive = _resolve_shared_drive_upload_folder(service, folder_id)
    return upload_id


# >>> OPIS FUNKCJI: funkcja _find_or_create_folder
# Cel: zwrócić id istniejącego podfolderu lub utworzyć go. Parametry: service; parent_id (str); name (str).
# Zwraca: str — id folderu. Efekty uboczne: ewentualne utworzenie folderu. Błędy: propagowane.
def _find_or_create_folder(service, parent_id: str, name: str) -> str:
    """Zwróć istniejący podfolder lub utwórz nowy."""
    existing = _find_folder_in_parent(service, parent_id, name)
    if existing:
        return existing
    return _create_folder(service, parent_id, name)


# >>> OPIS FUNKCJI: funkcja _upload_file
# Cel: wysłać plik lokalny do folderu Drive. Parametry: service; MediaFileUpload (klasa); local (Path); parent_id (str);
# version_xlsx (keyword-only, bool|None — domyślnie wg GDRIVE_VERSION_XLSX).
# Zwraca: str — id pliku. Zachowanie: .xlsx z wersjonowaniem zawsze tworzy NOWY plik z datą w nazwie; w pozostałych przypadkach aktualizuje istniejący
# plik o tej samej nazwie albo tworzy nowy (upload wznawialny, MIME zgadywany).
# Efekty uboczne: upload przez API. Błędy: propagowane.
def _upload_file(
    service,
    MediaFileUpload,
    local: Path,
    parent_id: str,
    *,
    version_xlsx: bool | None = None,
) -> str:
    """Upload pliku lokalnego do folderu Drive; zwraca file id."""
    mime, _ = mimetypes.guess_type(str(local))
    media = MediaFileUpload(str(local), mimetype=mime or "application/octet-stream", resumable=True)
    use_version = _gdrive_version_xlsx_enabled() if version_xlsx is None else version_xlsx
    drive_name = (
        versioned_xlsx_upload_name(local.name)
        if use_version and local.suffix.lower() == ".xlsx"
        else local.name
    )
    if use_version and local.suffix.lower() == ".xlsx":
        body = {"name": drive_name, "parents": [parent_id]}
        created = (
            service.files()
            .create(body=body, media_body=media, fields="id", **_DRIVE_API_OPTS)
            .execute()
        )
        return created["id"]

    safe_name = drive_name.replace("'", "\\'")
    q = f"'{parent_id}' in parents and name = '{safe_name}' and trashed = false"
    existing = (
        service.files()
        .list(q=q, fields="files(id)", pageSize=1, corpora="allDrives", **_LIST_OPTS)
        .execute()
        .get("files")
        or []
    )
    body = {"name": drive_name, "parents": [parent_id]}
    if existing:
        fid = existing[0]["id"]
        service.files().update(fileId=fid, media_body=media, **_DRIVE_API_OPTS).execute()
        return fid
    created = service.files().create(body=body, media_body=media, fields="id", **_DRIVE_API_OPTS).execute()
    return created["id"]


# >>> OPIS FUNKCJI: funkcja upload_files_flat
# Cel: wysłać wszystkie pliki z katalogu lokalnego bezpośrednio do folderu Drive. Parametry: service; MediaFileUpload; local_dir (Path); drive_parent_id (str).
# Zwraca: int — liczba wysłanych plików (0, gdy katalog nie istnieje). Pliki .json/.log pomijane; dla .xlsx (wersjonowanie włączone) wysyłane są dwie wersje:
# z datą i aktualna bez daty (liczone jako jeden plik). Efekty uboczne: upload, wypisywanie OK/SKIP. Błędy: propagowane.
def upload_files_flat(service, MediaFileUpload, local_dir: Path, drive_parent_id: str) -> int:
    """Upload plików z katalogu lokalnego bezpośrednio do drive_parent_id."""
    if not local_dir.is_dir():
        return 0
    count = 0
    for p in sorted(local_dir.iterdir()):
        if not p.is_file():
            continue
        if _skip_gdrive_upload(p):
            print(f"  SKIP {p.name} (tylko GitHub artefakt)")
            continue
        if p.suffix.lower() == ".xlsx" and _gdrive_version_xlsx_enabled():
            dated = versioned_xlsx_upload_name(p.name)
            _upload_file(service, MediaFileUpload, p, drive_parent_id, version_xlsx=True)
            print(f"  OK {dated}")
            _upload_file(service, MediaFileUpload, p, drive_parent_id, version_xlsx=False)
            print(f"  OK {p.name} (aktualny)")
            count += 1
            continue
        _upload_file(service, MediaFileUpload, p, drive_parent_id)
        print(f"  OK {p.name}")
        count += 1
    return count


# >>> OPIS FUNKCJI: funkcja upload_folder_named
# Cel: wysłać pliki katalogu lokalnego do podfolderu na Drive. Parametry: service; MediaFileUpload; local_dir (Path); drive_parent_id (str); drive_name (str).
# Zwraca: int — liczba wysłanych plików (0, gdy katalog nie istnieje). Efekty uboczne: znajduje/tworzy podfolder, upload, komunikaty; pliki .json/.log pomijane. Błędy: propagowane.
def upload_folder_named(
    service, MediaFileUpload, local_dir: Path, drive_parent_id: str, drive_name: str
) -> int:
    """Upload lokalnego katalogu do podfolderu drive_name na Drive."""
    if not local_dir.is_dir():
        return 0
    sub_id = _find_or_create_folder(service, drive_parent_id, drive_name)
    count = 0
    for p in sorted(local_dir.iterdir()):
        if not p.is_file():
            continue
        if _skip_gdrive_upload(p):
            print(f"  SKIP {drive_name}/{p.name} (tylko GitHub artefakt)")
            continue
        uploaded_as = (
            versioned_xlsx_upload_name(p.name)
            if _gdrive_version_xlsx_enabled() and p.suffix.lower() == ".xlsx"
            else p.name
        )
        _upload_file(service, MediaFileUpload, p, sub_id)
        print(f"  OK {drive_name}/{uploaded_as}")
        count += 1
    return count


# >>> OPIS FUNKCJI: funkcja main
# Cel: wejście CLI skryptu. Parametry: brak (argumenty z argparse: --campaign-dir, --folder-id). Zwraca: int — 0 po uploadzie lub w trybie NO-OP
# (DISABLE_GOOGLE_DRIVE włączone), 1 gdy nie było plików do wysłania.
# Efekty uboczne: uwierzytelnienie, upload plików z Wyniki/ i wyslane/, komunikaty na stdout z linkiem do folderu.
# Błędy: SystemExit z funkcji pomocniczych (poświadczenia); błąd odczytu scraper_env jest łapany (wtedy flaga czytana bezpośrednio z env).
def main() -> int:
    """CLI: upload Wyniki/ (+ opcjonalnie wyslane/) na Google Drive."""
    parser = argparse.ArgumentParser(description="Upload Wyniki do Google Drive")
    parser.add_argument(
        "--campaign-dir",
        type=Path,
        default=ROOT,
        help="Katalog kampanii (do resolve_data_root)",
    )
    parser.add_argument(
        "--folder-id",
        default=os.environ.get("GDRIVE_FOLDER_ID", GOOGLE_DRIVE_FAS_FOLDER_ID),
    )
    args = parser.parse_args()

    try:
        from scraper_env import is_google_drive_disabled

        drive_off = is_google_drive_disabled()
    except Exception:
        raw = (os.environ.get("DISABLE_GOOGLE_DRIVE") or "1").strip().lower()
        drive_off = raw not in ("0", "false", "no", "off")
    if drive_off:
        print(
            "[NO-OP] Google Drive wyłączony (DISABLE_GOOGLE_DRIVE=1). "
            "Wyniki zostają lokalnie / w artefaktach GHA. "
            "Rollback: DISABLE_GOOGLE_DRIVE=0"
        )
        return 0

    creds, use_oauth = _load_credentials()
    service, MediaFileUpload = _drive_service(creds)
    data_root = resolve_data_root(args.campaign_dir)
    upload_folder_id = _resolve_upload_folder(service, args.folder_id, use_oauth=use_oauth)

    total = 0
    w = wyniki_dir(data_root)
    if w.is_dir():
        print(f"Upload plikow z {w} -> Drive {upload_folder_id}")
        total += upload_files_flat(service, MediaFileUpload, w, upload_folder_id)
    s = wyslane_dir(data_root)
    if s.is_dir():
        print(f"Upload {s} -> Drive/wyslane/")
        total += upload_folder_named(service, MediaFileUpload, s, upload_folder_id, "wyslane")

    if total == 0:
        print(
            "Brak plikow do wyslania (puste Wyniki/). "
            "Uruchom najpierw pipeline discovery/backfill/send."
        )
        return 1

    print(
        f"Zakonczono. Plikow: {total}. Folder: "
        f"https://drive.google.com/drive/folders/{upload_folder_id}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

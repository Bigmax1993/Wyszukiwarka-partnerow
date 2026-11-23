# -*- coding: utf-8 -*-
"""
Stałe załączniki do maili B2B (kampania PL FAS / spedycja).

=============================================================================
PO CO TEN MODUŁ
=============================================================================
Przed SMTP scrapera (`pl_fas_spedycja_scraper.get_email_attachments_pl_fas`)
musi być lokalny PPTX. Ten moduł:

  1) szuka pliku lokalnie (env → cache ``Wyniki/`` → ``assets/campaign/``),
  2) gdy brak — pobiera z Google Drive (OAuth GHA / service account).

Shimy: ``fas_email_attachment``, ``mfg_gu_email_attachment``.

=============================================================================
DWA PLIKI B2B
=============================================================================
1) Oferta kampanii::

     https://drive.google.com/file/d/1t6m-M49t4w0RuLzc8rWebwjldLUMMRW3/view?usp=drive_link
     lokalnie: ``FAS_zalacznik_kampania.pptx``

2) Dodatkowa prezentacja (zawsze dołączana obok oferty)::

     https://drive.google.com/file/d/164qbEQOTyO8VTgfZr2wtIVTY-zttk6u7/view?usp=drive_link
     lokalnie: ``FAS_prezentacja.pptx``

Publiczne API: ``ensure_fas_email_attachments`` (lista) albo
``ensure_fas_email_attachment(..., extra=…)`` (jeden plik).
Aliasy ``resolve_mfg_*`` / ``ensure_mfg_*`` / ``_download_slides_pptx`` —
dla starego kodu; nie usuwać bez aktualizacji workflowów.
"""
from __future__ import annotations

import io
import logging
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# EMAIL_ATTACHMENT_DRIVE_FILE_ID / _URL  (plik 1 — oferta)
# ---------------------------------------------------------------------------
# PO CO: kanoniczne ID oferty FAS na Drive; URL do logów / docs / błędów SMTP.
# CZYTA: download, export CLI, scraper (komunikat braku załącznika), testy.
EMAIL_ATTACHMENT_DRIVE_FILE_ID = "1t6m-M49t4w0RuLzc8rWebwjldLUMMRW3"
EMAIL_ATTACHMENT_DRIVE_URL = (
    f"https://drive.google.com/file/d/{EMAIL_ATTACHMENT_DRIVE_FILE_ID}/view?usp=drive_link"
)

# ---------------------------------------------------------------------------
# EMAIL_ATTACHMENT_EXTRA_*  (plik 2 — prezentacja)
# ---------------------------------------------------------------------------
# PO CO: druga prezentacja w każdym mailu B2B obok oferty.
# ENV:   FAS_EMAIL_ATTACHMENT_EXTRA_PATH (lokalny override).
# CZYTA: ensure_fas_email_attachments, export_fas_email_attachment.py, GHA send.
EMAIL_ATTACHMENT_EXTRA_DRIVE_FILE_ID = "164qbEQOTyO8VTgfZr2wtIVTY-zttk6u7"
EMAIL_ATTACHMENT_EXTRA_DRIVE_URL = (
    f"https://drive.google.com/file/d/{EMAIL_ATTACHMENT_EXTRA_DRIVE_FILE_ID}/view?usp=drive_link"
)

# Domyślne nazwy lokalne (Drive może mieć inną nazwę — cache i tak używa tych stałych).
ATTACHMENT_FILENAME = "FAS_zalacznik_kampania.pptx"
ATTACHMENT_EXTRA_FILENAME = "FAS_prezentacja.pptx"

# Scope OAuth / SA — ten sam co gdrive_oauth_setup.py (refresh token na GHA).
DRIVE_READONLY_SCOPES = ("https://www.googleapis.com/auth/drive",)
PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
GOOGLE_SLIDES_MIME = "application/vnd.google-apps.presentation"

# Aliasy legacy (stare skrypty / workflowy mówiły „Slides” = oferta).
GOOGLE_SLIDES_PRESENTATION_ID = EMAIL_ATTACHMENT_DRIVE_FILE_ID
GOOGLE_SLIDES_URL = EMAIL_ATTACHMENT_DRIVE_URL


def _env_attachment_path(*, extra: bool = False) -> Path | None:
    """
    Odczyt ścieżki załącznika z zmiennych środowiskowych (gdy plik istnieje).

    =====================================================================
    PO CO
    =====================================================================
    Pozwala nadpisać Drive/cache lokalną ścieżką (GHA ``FAS_EMAIL_ATTACHMENT_*``,
    PC deweloperski) bez zmiany kodu i bez wołania API.

    =====================================================================
    PRZEBIEG
    =====================================================================
    1. Wybierz klucze env wg ``extra``.
    2. Dla każdego niepustego klucza: ``Path.expanduser()``, sprawdź ``is_file()``.
    3. Pierwszy istniejący plik wygrywa; brak → ``None``.

    =====================================================================
    ARGUMENTY
    =====================================================================
    ``extra``
        ``False`` → ``FAS_EMAIL_ATTACHMENT_PATH``, potem legacy
        ``MFG_EMAIL_ATTACHMENT_PATH`` (tylko oferta).
        ``True``  → wyłącznie ``FAS_EMAIL_ATTACHMENT_EXTRA_PATH`` (prezentacja).

    =====================================================================
    ZWRACA
    =====================================================================
    ``Path`` do istniejącego pliku albo ``None`` (pusty env / plik nie istnieje).
    """
    keys = (
        ("FAS_EMAIL_ATTACHMENT_EXTRA_PATH",)
        if extra
        else ("FAS_EMAIL_ATTACHMENT_PATH", "MFG_EMAIL_ATTACHMENT_PATH")
    )
    for key in keys:
        raw = (os.environ.get(key) or "").strip()
        if not raw:
            continue
        p = Path(raw).expanduser()
        if p.is_file():
            return p
    return None


def _cache_attachment_path(campaign_dir: Path, filename: str | None = None) -> Path:
    """
    Buduje ścieżkę cache załącznika w lokalnym ``Wyniki/``.

    =====================================================================
    PO CO
    =====================================================================
    Po pobraniu z Drive plik ląduje tu (nie w folderze Excela na Drive),
    żeby kolejne maile SMTP nie wołały API ponownie. Cache JSON/log
    kampanii też żyje w ``Wyniki/`` — spójny lokalny root.

    =====================================================================
    PRZEBIEG
    =====================================================================
    1. ``resolve_data_root(campaign_dir)`` (``KANBUD_DATA_DIR`` lub repo).
    2. ``wyniki_dir(root) / filename``.

    =====================================================================
    ARGUMENTY
    =====================================================================
    ``campaign_dir``
        Katalog kampanii / repo (bazowy do ``resolve_data_root``).
    ``filename``
        Nazwa pliku; domyślnie ``ATTACHMENT_FILENAME`` (oferta).
        Dla prezentacji podaj ``ATTACHMENT_EXTRA_FILENAME``.

    =====================================================================
    ZWRACA
    =====================================================================
    ``Path`` np. ``<data_root>/Wyniki/FAS_zalacznik_kampania.pptx``
    (katalog może jeszcze nie istnieć — tworzy go download).
    """
    from pl_spedycja_data_paths import resolve_data_root, wyniki_dir

    root = resolve_data_root(campaign_dir)
    return wyniki_dir(root) / (filename or ATTACHMENT_FILENAME)


def _load_drive_readonly_credentials():
    """
    Ładuje credentials Google Drive (odczyt) do pobrania załączników.

    =====================================================================
    PO CO
    =====================================================================
    Jedna ścieżka auth dla GHA (OAuth refresh token) i lokalnie
    (service account JSON). Bez credentials download zwraca ``False``.

    =====================================================================
    PRZEBIEG / KOLEJNOŚĆ
    =====================================================================
    1. OAuth Desktop / GHA: ``GDRIVE_OAUTH_REFRESH_TOKEN`` +
       ``GDRIVE_OAUTH_CLIENT_ID`` + ``GDRIVE_OAUTH_CLIENT_SECRET``
       → ``Credentials`` + ``refresh()``.
    2. Konto usługowe: ``GDRIVE_SERVICE_ACCOUNT_JSON`` (treść JSON)
       albo ``GDRIVE_SERVICE_ACCOUNT_FILE`` (ścieżka do pliku).
    3. Brak biblioteki Google / brak env / nieudany refresh → ``None``.

    =====================================================================
    ZWRACA
    =====================================================================
    Obiekt credentials Google albo ``None``.
    """
    refresh = (os.environ.get("GDRIVE_OAUTH_REFRESH_TOKEN") or "").strip()
    client_id = (os.environ.get("GDRIVE_OAUTH_CLIENT_ID") or "").strip()
    client_secret = (os.environ.get("GDRIVE_OAUTH_CLIENT_SECRET") or "").strip()
    if refresh and client_id and client_secret:
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
        except ImportError:
            return None
        creds = Credentials(
            token=None,
            refresh_token=refresh,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=list(DRIVE_READONLY_SCOPES),
        )
        creds.refresh(Request())
        return creds

    import json

    try:
        from google.oauth2 import service_account
    except ImportError:
        return None

    raw = (os.environ.get("GDRIVE_SERVICE_ACCOUNT_JSON") or "").strip()
    path = (os.environ.get("GDRIVE_SERVICE_ACCOUNT_FILE") or "").strip()
    if raw:
        info = json.loads(raw)
        return service_account.Credentials.from_service_account_info(
            info, scopes=DRIVE_READONLY_SCOPES
        )
    if path and Path(path).is_file():
        return service_account.Credentials.from_service_account_file(
            path, scopes=DRIVE_READONLY_SCOPES
        )
    return None


def _drive_download_to_buffer(service, file_id: str, mime_type: str) -> io.BytesIO:
    """
    Pobiera bajty pliku z Drive API do bufora w pamięci.

    =====================================================================
    PO CO
    =====================================================================
    Jedno miejsce na różnicę MIME: natywne Google Slides wymaga
    ``export_media`` → PPTX; zwykły plik PPTX/PDF → ``get_media``.

    =====================================================================
    PRZEBIEG
    =====================================================================
    1. Jeśli ``mime_type == GOOGLE_SLIDES_MIME`` → eksport do ``PPTX_MIME``.
    2. Inaczej → ``files().get_media``.
    3. ``MediaIoBaseDownload`` chunkami do ``BytesIO``, ``seek(0)``.

    =====================================================================
    ARGUMENTY
    =====================================================================
    ``service``
        Klient ``googleapiclient`` Drive v3 (już z credentials).
    ``file_id``
        ID pliku na Drive (oferta albo prezentacja).
    ``mime_type``
        MIME z metadanych; steruje export vs get_media.

    =====================================================================
    ZWRACA
    =====================================================================
    ``io.BytesIO`` na początku bufora — gotowy do ``write_bytes`` / zapisu.
    """
    from googleapiclient.http import MediaIoBaseDownload

    if mime_type == GOOGLE_SLIDES_MIME:
        request = service.files().export_media(fileId=file_id, mimeType=PPTX_MIME)
    else:
        request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _status, done = downloader.next_chunk()
    buffer.seek(0)
    return buffer


def _download_attachment_pptx(
    dest: Path,
    logger: logging.Logger | None = None,
    *,
    file_id: str | None = None,
    drive_url: str | None = None,
) -> bool:
    """
    Pobiera załącznik FAS z Drive i zapisuje pod ``dest``.

    =====================================================================
    PO CO
    =====================================================================
    Używane gdy lokalnie nie ma env/cache/assets — GHA export CLI,
    pierwszy run na maszynie z credentials, albo ``ensure_*`` po miss resolve.

    =====================================================================
    PRZEBIEG
    =====================================================================
    1. Kill-switch ``DISABLE_GOOGLE_DRIVE`` (domyślnie ON = brak Drive)
       → ``False`` (export CLI ustawia ``0`` przed pobraniem).
    2. Import ``googleapiclient`` + credentials.
    3. ``files().get`` metadane (mime, name) → ``_drive_download_to_buffer``.
    4. Zapis ``dest.write_bytes``; sukces gdy plik > ~1 KB.

    =====================================================================
    ARGUMENTY
    =====================================================================
    ``dest``
        Docelowa ścieżka lokalna (zwykle cache w ``Wyniki/`` lub assets).
    ``logger``
        Opcjonalny logger (info / warning / error).
    ``file_id``
        ID Drive; domyślnie oferta (``EMAIL_ATTACHMENT_DRIVE_FILE_ID``).
        Prezentacja: ``EMAIL_ATTACHMENT_EXTRA_DRIVE_FILE_ID``.
    ``drive_url``
        URL do komunikatów błędów; domyślnie URL oferty.

    =====================================================================
    ZWRACA
    =====================================================================
    ``True`` gdy plik istnieje i ma sensowny rozmiar; inaczej ``False``.
    """
    try:
        from scraper_env import is_google_drive_disabled

        if is_google_drive_disabled():
            if logger:
                logger.info(
                    "DISABLE_GOOGLE_DRIVE=1 — pomijam pobranie załącznika z Drive "
                    "(użyj lokalnego assets/campaign lub FAS_EMAIL_ATTACHMENT_PATH)."
                )
            return False
    except Exception:
        raw = (os.environ.get("DISABLE_GOOGLE_DRIVE") or "1").strip().lower()
        if raw not in ("0", "false", "no", "off"):
            return False

    try:
        from googleapiclient.discovery import build
    except ImportError:
        if logger:
            logger.warning(
                "Brak google-api-python-client — nie pobrano załącznika z Drive."
            )
        return False

    creds = _load_drive_readonly_credentials()
    if creds is None:
        return False

    fid = (file_id or EMAIL_ATTACHMENT_DRIVE_FILE_ID).strip()
    url = (drive_url or EMAIL_ATTACHMENT_DRIVE_URL).strip()

    dest.parent.mkdir(parents=True, exist_ok=True)
    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    try:
        meta = (
            service.files()
            .get(fileId=fid, fields="mimeType,name", supportsAllDrives=True)
            .execute()
        )
        mime_type = str(meta.get("mimeType") or "")
        drive_name = (meta.get("name") or "").strip()
        if logger:
            logger.info("Drive załącznik: %s (mime=%s)", drive_name or fid, mime_type)
        buffer = _drive_download_to_buffer(service, fid, mime_type)
    except Exception as exc:
        if logger:
            logger.error(
                "Pobranie załącznika %s nieudane (%s). Udostępnij plik kontu OAuth "
                "lub konto usługi (GDRIVE_OAUTH_* / GDRIVE_SERVICE_ACCOUNT_JSON). "
                "URL: %s",
                fid,
                exc,
                url,
            )
        return False
    dest.write_bytes(buffer.getvalue())
    if logger:
        logger.info(
            "Pobrano załącznik z Drive → %s (%.1f MB)",
            dest,
            dest.stat().st_size / (1024 * 1024),
        )
    return dest.is_file() and dest.stat().st_size > 1000


def resolve_fas_email_attachment(
    campaign_dir: Path,
    *,
    extra: bool = False,
) -> Path | None:
    """
    Szuka lokalnego załącznika FAS — **bez** wołania Drive API.

    =====================================================================
    PO CO
    =====================================================================
    Szybka ścieżka przed SMTP: jeśli plik już jest lokalnie, nie ruszamy
    sieci. Ścieżki MFG (Referenzliste / Fliesenboden) celowo usunięte.

    =====================================================================
    PRZEBIEG (HOT PATH)
    =====================================================================
    1. env (``_env_attachment_path``) — GHA / override.
    2. cache ``Wyniki/<filename>`` (rozmiar > 1 KB).
    3. bundled ``assets/campaign/<filename>``.
    4. brak → ``None`` (wtedy ``ensure_*`` może spróbować Drive).

    =====================================================================
    ARGUMENTY
    =====================================================================
    ``campaign_dir``
        Katalog kampanii (zwykle root repo / ``CAMPAIGN_DIR`` scrapera).
    ``extra``
        ``False`` → oferta (plik 1); ``True`` → prezentacja (plik 2).

    =====================================================================
    ZWRACA
    =====================================================================
    ``Path`` do istniejącego pliku albo ``None``.
    """
    filename = ATTACHMENT_EXTRA_FILENAME if extra else ATTACHMENT_FILENAME
    env_p = _env_attachment_path(extra=extra)
    if env_p:
        return env_p
    cache_p = _cache_attachment_path(campaign_dir, filename)
    if cache_p.is_file() and cache_p.stat().st_size > 1000:
        return cache_p
    bundled = Path(campaign_dir) / "assets" / "campaign" / filename
    if bundled.is_file():
        return bundled
    return None


def ensure_fas_email_attachment(
    campaign_dir: Path,
    logger: logging.Logger | None = None,
    *,
    extra: bool = False,
) -> Path | None:
    """
    Gwarantuje **jeden** lokalny załącznik FAS — resolve, a gdy brak: Drive.

    =====================================================================
    PO CO
    =====================================================================
    Publiczne API dla pojedynczego pliku (oferta **lub** prezentacja).
    Scraper zwykle woła ``ensure_fas_email_attachments`` (oba naraz).

    =====================================================================
    PRZEBIEG
    =====================================================================
    1. ``resolve_fas_email_attachment(..., extra=…)`` — jeśli OK, zwróć.
    2. Dobierz ``file_id`` / URL / nazwę cache wg ``extra``.
    3. ``_download_attachment_pptx`` do ``Wyniki/``.
    4. Przy fail: log error + ``None``.

    =====================================================================
    ARGUMENTY
    =====================================================================
    ``campaign_dir``
        Katalog kampanii.
    ``logger``
        Opcjonalny logger scrapera / CLI.
    ``extra``
        ``False`` → oferta; ``True`` → dodatkowa prezentacja.

    =====================================================================
    ZWRACA
    =====================================================================
    ``Path`` do lokalnego PPTX albo ``None``.
    """
    existing = resolve_fas_email_attachment(campaign_dir, extra=extra)
    if existing:
        return existing

    filename = ATTACHMENT_EXTRA_FILENAME if extra else ATTACHMENT_FILENAME
    file_id = (
        EMAIL_ATTACHMENT_EXTRA_DRIVE_FILE_ID
        if extra
        else EMAIL_ATTACHMENT_DRIVE_FILE_ID
    )
    drive_url = (
        EMAIL_ATTACHMENT_EXTRA_DRIVE_URL if extra else EMAIL_ATTACHMENT_DRIVE_URL
    )
    cache_p = _cache_attachment_path(campaign_dir, filename)
    if _download_attachment_pptx(
        cache_p, logger, file_id=file_id, drive_url=drive_url
    ):
        return cache_p

    if logger:
        logger.error(
            "Brak załącznika%s. Udostępnij plik Drive %s kontu Google "
            "lub ustaw FAS_EMAIL_ATTACHMENT%s_PATH / plik w assets/campaign.",
            " (prezentacja)" if extra else "",
            drive_url,
            "_EXTRA" if extra else "",
        )
    return None


def ensure_fas_email_attachments(
    campaign_dir: Path,
    logger: logging.Logger | None = None,
) -> list[Path]:
    """
    Lokalne załączniki B2B: **oferta + prezentacja** (kolejność stała).

    =====================================================================
    PO CO
    =====================================================================
    Kanoniczne API dla scrapera przed SMTP — oba pliki w jednym wywołaniu.
    GHA send ustawia ``FAS_EMAIL_ATTACHMENT_PATH`` / ``_EXTRA_PATH`` po eksporcie.

    =====================================================================
    PRZEBIEG
    =====================================================================
    1. ``ensure_fas_email_attachment(..., extra=False)`` — oferta (wymagana
       do wysyłki; scraper odrzuca mail gdy lista pusta).
    2. ``ensure_fas_email_attachment(..., extra=True)`` — prezentacja.
    3. Brak prezentacji przy istniejącej ofercie → ``warning``, lista i tak
       zawiera tylko ofertę (mail może iść z jednym PPTX).

    =====================================================================
    ARGUMENTY
    =====================================================================
    ``campaign_dir``
        Katalog kampanii / repo.
    ``logger``
        Opcjonalny logger (warning przy braku prezentacji).

    =====================================================================
    ZWRACA
    =====================================================================
    Lista ``Path`` (0–2): najpierw oferta, potem prezentacja.
    Pusta lista = brak oferty (SMTP scrapera zwróci błąd).
    """
    out: list[Path] = []
    primary = ensure_fas_email_attachment(campaign_dir, logger, extra=False)
    if primary and primary.is_file():
        out.append(primary)
    extra = ensure_fas_email_attachment(campaign_dir, logger, extra=True)
    if extra and extra.is_file():
        out.append(extra)
    elif logger and primary:
        logger.warning(
            "Brak drugiej prezentacji (%s) — wysyłka tylko z ofertą.",
            EMAIL_ATTACHMENT_EXTRA_DRIVE_URL,
        )
    return out


# ---------------------------------------------------------------------------
# Aliasy legacy (stare importy / skrypty MFG / nazewnictwo „Slides”).
# Nie usuwać bez aktualizacji workflowów i testów.
# ---------------------------------------------------------------------------
resolve_mfg_email_attachment = resolve_fas_email_attachment
ensure_mfg_email_attachment = ensure_fas_email_attachment
_download_slides_pptx = _download_attachment_pptx

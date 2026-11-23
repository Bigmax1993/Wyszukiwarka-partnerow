# -*- coding: utf-8 -*-
"""
Testy API live: Gmail (SMTP/IMAP) oraz Google Drive (folder Excela + załącznik).

Co robi ten plik
----------------
Sprawdza na żywo, że sekrety z `.env` / GitHub Secrets działają:

- Gmail: logowanie SMTP (raport Excel) i IMAP (archiwum) — **bez** ``sendmail``
- Drive: odczyt metadanych folderu końcowego Excela i pliku-załącznika B2B —
  **bez** uploadu i **bez** pobierania treści

Bez sekretów testy robią ``pytest.skip`` (nie failują CI bez kluczy).
Marker: ``api_live`` (+ ``integration``). Uruchomienie::

  python -m pytest tests/integration/test_gmail_gdrive_api.py -m api_live -v
"""
from __future__ import annotations

import json
import os
import smtplib
import ssl
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.api_live]

ROOT = Path(__file__).resolve().parents[2]


def _env(key: str) -> str:
    """
    Odczyt zmiennej środowiskowej jako obcięty string.

    Pusty / brak klucza → ``\"\"`` (caller decyduje o skip).
    Nie ładuje `.env` sam — robi to ``scraper_env`` przy imporcie.
    """
    return (os.environ.get(key) or "").strip()


def _load_drive_credentials():
    """
    Buduje credentials Google Drive do testów odczytu metadanych.

    Kolejność:
      1. OAuth Desktop — ``GDRIVE_OAUTH_REFRESH_TOKEN`` + CLIENT_ID/SECRET
         (ten sam zestaw co upload Excela na GHA nd 09:00),
      2. konto usługowe — ``GDRIVE_SERVICE_ACCOUNT_JSON`` lub ``_FILE``,
         opcjonalnie ``GDRIVE_IMPERSONATE_EMAIL`` (DWD).

    Zwraca ``(creds, \"oauth\"|\"service_account\")`` albo ``(None, None)``
    gdy brak sekretów — wtedy test robi ``skip``, nie ``SystemExit``
    (w przeciwieństwie do skryptów produkcyjnych uploadu).
    """
    refresh = _env("GDRIVE_OAUTH_REFRESH_TOKEN")
    client_id = _env("GDRIVE_OAUTH_CLIENT_ID")
    client_secret = _env("GDRIVE_OAUTH_CLIENT_SECRET")
    if refresh and client_id and client_secret:
        pytest.importorskip("google.oauth2.credentials")
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        creds = Credentials(
            token=None,
            refresh_token=refresh,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=["https://www.googleapis.com/auth/drive"],
        )
        creds.refresh(Request())
        return creds, "oauth"

    raw = _env("GDRIVE_SERVICE_ACCOUNT_JSON")
    path = _env("GDRIVE_SERVICE_ACCOUNT_FILE")
    if not raw and path and Path(path).is_file():
        raw = Path(path).read_text(encoding="utf-8")
    if not raw:
        return None, None

    pytest.importorskip("google.oauth2.service_account")
    from google.oauth2 import service_account

    info = json.loads(raw)
    if info.get("type") != "service_account":
        pytest.skip("GDRIVE_SERVICE_ACCOUNT_JSON nie jest kontem usługowym")
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive"]
    )
    impersonate = _env("GDRIVE_IMPERSONATE_EMAIL")
    if impersonate:
        creds = creds.with_subject(impersonate)
    return creds, "service_account"


def _drive_service(creds):
    """
    Klient Google Drive API v3 z podanymi credentials.

    ``cache_discovery=False`` — unika zapisu discovery cache na CI.
    Brak ``googleapiclient`` → skip przez ``importorskip``.
    """
    pytest.importorskip("googleapiclient.discovery")
    from googleapiclient.discovery import build

    return build("drive", "v3", credentials=creds, cache_discovery=False)


# --- Gmail -----------------------------------------------------------------


@pytest.mark.api_live
def test_gmail_smtp_login():
    """
    Live: logowanie do SMTP (Gmail / inny host z env) — bez wysyłki wiadomości.

    Po co: raport Excel nd 09:00 i przyszłe maile B2B wymagają działającego
    ``MAIL_USER`` + hasła aplikacji. Test kończy się na ``login()``;
    nie woła ``sendmail``, więc nic nie trafia do skrzynki odbiorcy.

    Skip gdy brak user/hasła albo nie da się ustalić hosta SMTP.
    Port: ``SMTP_PORT`` (domyślnie 587 + STARTTLS) albo SSL przy 465.
    """
    from mail_transport import get_smtp_host
    from scraper_env import get_mail_password, get_mail_user

    user = (get_mail_user() or "").strip()
    password = (get_mail_password() or "").strip()
    if not user or not password:
        pytest.skip("Brak MAIL_USER / MAIL_PASSWORD (lub GMAIL_*)")

    host = get_smtp_host() or (
        "smtp.gmail.com" if "@gmail.com" in user.lower() else ""
    )
    if not host:
        pytest.skip("Brak SMTP_HOST i adres nie jest Gmail")

    port = int(_env("SMTP_PORT") or "587")
    use_ssl = (_env("SMTP_SSL") or "").lower() in ("1", "true", "yes", "on") or port == 465

    if use_ssl:
        with smtplib.SMTP_SSL(host, port, timeout=30) as smtp:
            smtp.ehlo()
            smtp.login(user, password)
    else:
        context = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
            smtp.login(user, password)


@pytest.mark.api_live
def test_gmail_imap_login():
    """
    Live: logowanie IMAP — bez listowania / odczytu wiadomości.

    Po co: archiwum ``wyslane/`` i sync odpowiedzi (gdy włączone) idą przez IMAP.
    Wystarczy ``login`` → ``OK``. Skip bez credentials lub hosta.
    """
    import imaplib

    from mail_transport import get_imap_host
    from scraper_env import get_mail_password, get_mail_user

    user = (get_mail_user() or "").strip()
    password = (get_mail_password() or "").strip()
    if not user or not password:
        pytest.skip("Brak MAIL_USER / MAIL_PASSWORD (lub GMAIL_*)")

    host = get_imap_host() or (
        "imap.gmail.com" if "@gmail.com" in user.lower() else ""
    )
    if not host:
        pytest.skip("Brak IMAP_HOST")

    port = int(_env("IMAP_PORT") or "993")
    with imaplib.IMAP4_SSL(host, port) as mail:
        typ, _data = mail.login(user, password)
        assert typ == "OK"


# --- Google Drive ----------------------------------------------------------


@pytest.mark.api_live
def test_gdrive_excel_folder_readable():
    """
    Live: konto Drive widzi folder końcowego Excela kontaktów.

    ID: ``GDRIVE_FOLDER_ID`` z env albo default
    ``pl_spedycja_data_paths.GOOGLE_DRIVE_FAS_FOLDER_ID`` (``1bRCAq…``).

    Sprawdza ``files.get`` → mime = folder, niepusta nazwa.
    Nie listuje zawartości i nic nie uploaduje.
    Skip bez OAuth / konta usługowego.
    """
    from pl_spedycja_data_paths import GOOGLE_DRIVE_FAS_FOLDER_ID

    folder_id = _env("GDRIVE_FOLDER_ID") or GOOGLE_DRIVE_FAS_FOLDER_ID
    if not folder_id:
        pytest.skip("Brak GDRIVE_FOLDER_ID")

    creds, mode = _load_drive_credentials()
    if creds is None:
        pytest.skip(
            "Brak GDRIVE_OAUTH_* lub GDRIVE_SERVICE_ACCOUNT_JSON/_FILE"
        )

    service = _drive_service(creds)
    meta = (
        service.files()
        .get(
            fileId=folder_id,
            fields="id,name,mimeType",
            supportsAllDrives=True,
        )
        .execute()
    )
    assert meta.get("id") == folder_id
    assert meta.get("mimeType") == "application/vnd.google-apps.folder"
    assert (meta.get("name") or "").strip()
    assert mode in ("oauth", "service_account")


@pytest.mark.api_live
def test_gdrive_email_attachment_file_readable():
    """
    Live: konto Drive widzi plik-załącznik maila B2B (FAS).

    ID z ``pl_fas_email_attachment.EMAIL_ATTACHMENT_DRIVE_FILE_ID``
    (``1t6m-M49…``). Tylko metadane (nazwa, mime, size) — bez ``get_media``,
    żeby nie ściągać dużego PPTX/PDF w CI.

    Assert: to nie jest folder. Skip bez credentials Drive.
    """
    from pl_fas_email_attachment import EMAIL_ATTACHMENT_DRIVE_FILE_ID

    file_id = EMAIL_ATTACHMENT_DRIVE_FILE_ID
    creds, _mode = _load_drive_credentials()
    if creds is None:
        pytest.skip(
            "Brak GDRIVE_OAUTH_* lub GDRIVE_SERVICE_ACCOUNT_JSON/_FILE"
        )

    service = _drive_service(creds)
    meta = (
        service.files()
        .get(
            fileId=file_id,
            fields="id,name,mimeType,size",
            supportsAllDrives=True,
        )
        .execute()
    )
    assert meta.get("id") == file_id
    assert (meta.get("name") or "").strip()
    mime = (meta.get("mimeType") or "").strip()
    assert mime
    # Plik binarny albo Google Docs/Slides — byle nie folder
    assert mime != "application/vnd.google-apps.folder"

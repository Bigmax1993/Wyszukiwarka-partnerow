# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Moduł: libs/scraper_env — jedno miejsce odczytu zmiennych środowiskowych i flag „kill-switch”.
#
# CO ROBI
#   Definiuje nazwy zmiennych (ENV_*: klucze Serper/Anthropic, dane SMTP/IMAP, Cc/Bcc, katalog danych,
#   adres raportu Excel), ładuje plik .env (libs/.env) przy imporcie (bez nadpisywania już ustawionych
#   zmiennych), udostępnia get_env_value (proces → cache → PowerShell User → Machine na Windows)
#   oraz gettery kluczy/poczty i flagi: is_contractor_emails_disabled, is_google_drive_disabled,
#   is_excel_report_email_disabled. Flagi DISABLE_CONTRACTOR_EMAILS i DISABLE_GOOGLE_DRIVE są
#   domyślnie WŁĄCZONE (funkcje wyłączone; rollback = ustawić 0), DISABLE_EXCEL_REPORT_EMAIL domyślnie wyłączona.
#
# ROLA W PIPELINE
#   Bramka konfiguracji dla wszystkich etapów: discovery (klucz Serper), Claude (klucz Anthropic),
#   e-mail B2B (kill switch + dane SMTP), raport Excel na adres wewnętrzny, Google Drive.
#
# ZALEŻNOŚCI: os, subprocess, pathlib oraz polish_text.configure_utf8_environment (import w module).
# STAN GLOBALNY: _DOTENV_LOADED, _WINDOWS_ENV_CACHE (cache odczytów z rejestru/PowerShell),
#   _LEGACY_ENV_ALIASES (GMAIL_* → MAIL_*).
# BEZPIECZEŃSTWO: check_env_status zwraca tylko informację „ustawiona/nie”, nigdy wartości sekretów.
# Uwaga: docstring pliku zawiera zniekształcone znaki (mojibake) — pozostawiono bez zmian.
# ============================================================
"""
Wsp├│lne nazwy zmiennych ┼Ťrodowiskowych (identyczne jak w PowerShell User/Machine).

Ustawienie na sta┼ée (PowerShell):
  [System.Environment]::SetEnvironmentVariable("SERPER_API_KEY", "...", "User")
  [System.Environment]::SetEnvironmentVariable("MAIL_USER", "twoj@domena.pl", "User")
  [System.Environment]::SetEnvironmentVariable("MAIL_PASSWORD", "...", "User")
  [System.Environment]::SetEnvironmentVariable("SMTP_HOST", "serwer.home.pl", "User")
  [System.Environment]::SetEnvironmentVariable("IMAP_HOST", "serwer.home.pl", "User")
  # Opcjonalnie (stare nazwy nadal dzia┼éaj─ů): GMAIL_USER, GMAIL_APP_PASSWORD, GMAIL_SENDER_NAME
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

_DOTENV_LOADED = False


# >>> OPIS FUNKCJI: funkcja _load_dotenv_file
# Cel: jednorazowo wczytać plik .env z katalogu libs/ do os.environ. Parametry: brak. Zwraca: None.
# Efekty uboczne: ustawia zmienne tylko wtedy, gdy ich jeszcze nie ma w os.environ; pomija puste linie,
# komentarze (#) i linie bez "="; zdejmuje cudzysłowy z wartości; ustawia globalne _DOTENV_LOADED.
# Błędy: OSError przy czytaniu pliku jest łapany i ignorowany; brak pliku .env = brak działania.
def _load_dotenv_file() -> None:
    """┼üaduje .env z katalogu projektu (nie commituj .env z kluczami)."""
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    _DOTENV_LOADED = True
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.is_file():
        return
    try:
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
    except OSError:
        pass


_load_dotenv_file()

# --- Nazwy 1:1 z PowerShell ([Environment]::SetEnvironmentVariable(..., "User")) ---
ENV_SERPER_API_KEY = "SERPER_API_KEY"
ENV_MAIL_USER = "MAIL_USER"
ENV_MAIL_PASSWORD = "MAIL_PASSWORD"
ENV_MAIL_SENDER_NAME = "MAIL_SENDER_NAME"
ENV_SMTP_HOST = "SMTP_HOST"
ENV_SMTP_PORT = "SMTP_PORT"
ENV_SMTP_SSL = "SMTP_SSL"
ENV_IMAP_HOST = "IMAP_HOST"
ENV_IMAP_PORT = "IMAP_PORT"
ENV_IMAP_SSL = "IMAP_SSL"
ENV_MAIL_BCC = "MAIL_BCC"
ENV_MAIL_CC = "MAIL_CC"
ENV_MAIL_ARCHIVE_IMAP = "MAIL_ARCHIVE_IMAP"
# Kompatybilno┼Ť─ç wsteczna (Gmail lub stare instalacje)
ENV_GMAIL_USER = "GMAIL_USER"
ENV_GMAIL_APP_PASSWORD = "GMAIL_APP_PASSWORD"
ENV_GMAIL_SENDER_NAME = "GMAIL_SENDER_NAME"
ENV_ANTHROPIC_API_KEY = "ANTHROPIC_API_KEY"
ENV_CLAUDE_MODEL = "CLAUDE_MODEL"
ENV_CLAUDE_MODEL_VERIFY = "CLAUDE_MODEL_VERIFY"
ENV_CLAUDE_MODEL_FAST = "CLAUDE_MODEL_FAST"
ENV_KANBUD_DATA_DIR = "KANBUD_DATA_DIR"
ENV_EXCEL_REPORT_TO = "EXCEL_REPORT_TO"
DEFAULT_EXCEL_REPORT_TO = "svinchak1993@gmail.com"

# Opcjonalne (tylko niekt├│re skrypty)
ENV_ENABLE_GEO_DISTANCE_PLZ_FILTER = "ENABLE_GEO_DISTANCE_PLZ_FILTER"
ENV_MAX_DISTANCE_KM_FROM_ANCHOR = "MAX_DISTANCE_KM_FROM_ANCHOR"
ENV_SERPER_SHUFFLE_TERMS = "SERPER_SHUFFLE_TERMS"
ENV_EMAIL_MX_CHECK = "EMAIL_MX_CHECK"

# Kill-switches (domyślnie włączone = wyłączone funkcje; rollback: ustaw na 0)
ENV_DISABLE_CONTRACTOR_EMAILS = "DISABLE_CONTRACTOR_EMAILS"
ENV_DISABLE_GOOGLE_DRIVE = "DISABLE_GOOGLE_DRIVE"
ENV_DISABLE_EXCEL_REPORT_EMAIL = "DISABLE_EXCEL_REPORT_EMAIL"

REQUIRED_FOR_EMAIL = (ENV_MAIL_USER, ENV_MAIL_PASSWORD)
REQUIRED_FOR_SERPER = (ENV_SERPER_API_KEY,)


# >>> OPIS FUNKCJI: funkcja _env_flag_default_on
# Cel: odczytać flagę, która domyślnie jest WŁĄCZONA. Parametry: name (str) — nazwa zmiennej.
# Zwraca: bool — False tylko dla wartości 0/false/no/off (bez wielkości liter); brak zmiennej = True.
# Efekty uboczne: odczyt os.getenv. Błędy: brak.
def _env_flag_default_on(name: str) -> bool:
    """True gdy flaga włączona (domyślnie 1). Wyłącz: 0 / false / no / off."""
    raw = (os.getenv(name) if os.getenv(name) is not None else "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


# >>> OPIS FUNKCJI: funkcja _env_flag_default_off
# Cel: odczytać flagę, która domyślnie jest WYŁĄCZONA. Parametry: name (str).
# Zwraca: bool — True tylko dla 1/true/yes/on; brak zmiennej = False. Efekty uboczne/błędy: brak.
def _env_flag_default_off(name: str) -> bool:
    """True gdy flaga włączona (domyślnie 0 = flaga off). Włącz: 1 / true / yes / on."""
    raw = (os.getenv(name) if os.getenv(name) is not None else "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


# >>> OPIS FUNKCJI: funkcja is_contractor_emails_disabled
# Cel: kill switch wysyłki maili B2B do kontrahentów (DISABLE_CONTRACTOR_EMAILS). Parametry: brak.
# Zwraca: bool — domyślnie True (wysyłka wyłączona); False dopiero po ustawieniu zmiennej na 0/false/no/off.
# Efekty uboczne/błędy: brak (dry-run treści nadal możliwy).
def is_contractor_emails_disabled() -> bool:
    """ZERO maili B2B do kontrahentów (SMTP/yagmail). Dry-run treści nadal OK."""
    return _env_flag_default_on(ENV_DISABLE_CONTRACTOR_EMAILS)


# >>> OPIS FUNKCJI: funkcja is_google_drive_disabled
# Cel: kill switch integracji Google Drive (DISABLE_GOOGLE_DRIVE) — brak upload/sync/download. Parametry: brak.
# Zwraca: bool — domyślnie True (wyłączone). Efekty uboczne/błędy: brak.
def is_google_drive_disabled() -> bool:
    """ZERO upload/sync/download przez Google Drive API oraz ścieżek Drive for desktop."""
    return _env_flag_default_on(ENV_DISABLE_GOOGLE_DRIVE)


# >>> OPIS FUNKCJI: funkcja is_excel_report_email_disabled
# Cel: sprawdzić, czy wyłączono wewnętrzny raport Excel e-mailem (DISABLE_EXCEL_REPORT_EMAIL). Parametry: brak.
# Zwraca: bool — domyślnie False (raport WŁĄCZONY; odbiorca EXCEL_REPORT_TO). Efekty uboczne/błędy: brak.
def is_excel_report_email_disabled() -> bool:
    """Raport wewnętrzny Excel (jeden odbiorca EXCEL_REPORT_TO). Domyślnie WŁĄCZONY."""
    return _env_flag_default_off(ENV_DISABLE_EXCEL_REPORT_EMAIL)

_WINDOWS_ENV_CACHE: dict[str, str] = {}
_LEGACY_ENV_ALIASES = {
    ENV_GMAIL_USER: ENV_MAIL_USER,
    ENV_GMAIL_APP_PASSWORD: ENV_MAIL_PASSWORD,
    ENV_GMAIL_SENDER_NAME: ENV_MAIL_SENDER_NAME,
}


# >>> OPIS FUNKCJI: funkcja get_env_value
# Cel: odczytać zmienną środowiskową z kilku źródeł. Parametry: name (str); default (str, "").
# Zwraca: str — pierwsza niepusta wartość (po strip) w kolejności: os.environ[name], alias legacy
# (GMAIL_* → MAIL_*), cache procesu, a na Windows PowerShell [Environment]::GetEnvironmentVariable
# dla zakresów User i Machine; w ostatniej kolejności default.
# Efekty uboczne: na Windows uruchamia subprocess powershell (stderr wyciszony); wartość znaleziona w
# rejestrze trafia do cache i os.environ (setdefault). Błędy: wyjątki subprocess są łapane (continue).
def get_env_value(name: str, default: str = "") -> str:
    """Odczyt zmiennej: proces Ôćĺ cache Ôćĺ PowerShell User Ôćĺ PowerShell Machine."""
    val = os.getenv(name)
    if val:
        return val.strip()
    alias = _LEGACY_ENV_ALIASES.get(name)
    if alias:
        alias_val = os.getenv(alias)
        if alias_val:
            return alias_val.strip()
    if name in _WINDOWS_ENV_CACHE:
        return _WINDOWS_ENV_CACHE[name]
    if os.name == "nt":
        for scope in ("User", "Machine"):
            try:
                cmd = (
                    f"[Environment]::GetEnvironmentVariable('{name}','{scope}')"
                )
                out = subprocess.check_output(
                    ["powershell", "-NoProfile", "-Command", cmd],
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    stderr=subprocess.DEVNULL,
                )
                val = (out or "").strip()
                if val:
                    _WINDOWS_ENV_CACHE[name] = val
                    os.environ.setdefault(name, val)
                    return val
            except Exception:
                continue
    return (default or "").strip()


# >>> OPIS FUNKCJI: funkcja get_serper_api_key
# Cel: klucz API Serper. Parametry: brak. Zwraca: str — SERPER_API_KEY lub "". Efekty uboczne/błędy: jak get_env_value.
def get_serper_api_key() -> str:
    return get_env_value(ENV_SERPER_API_KEY)


# >>> OPIS FUNKCJI: funkcja get_anthropic_api_key
# Cel: klucz API Anthropic (Claude). Parametry: brak. Zwraca: str — ANTHROPIC_API_KEY lub "".
# Efekty uboczne/błędy: jak get_env_value.
def get_anthropic_api_key() -> str:
    return get_env_value(ENV_ANTHROPIC_API_KEY)


# >>> OPIS FUNKCJI: funkcja get_excel_report_to
# Cel: adres odbiorcy raportu Excel. Parametry: brak. Zwraca: str — EXCEL_REPORT_TO lub DEFAULT_EXCEL_REPORT_TO.
# Efekty uboczne/błędy: jak get_env_value.
def get_excel_report_to() -> str:
    return get_env_value(ENV_EXCEL_REPORT_TO) or DEFAULT_EXCEL_REPORT_TO


# >>> OPIS FUNKCJI: funkcja get_mail_user
# Cel: login skrzynki do SMTP/IMAP. Parametry: brak. Zwraca: str — MAIL_USER, a gdy pusty GMAIL_USER (legacy).
# Efekty uboczne/błędy: jak get_env_value.
def get_mail_user() -> str:
    return get_env_value(ENV_MAIL_USER) or get_env_value(ENV_GMAIL_USER)


# >>> OPIS FUNKCJI: funkcja get_mail_password
# Cel: hasło skrzynki. Parametry: brak. Zwraca: str — MAIL_PASSWORD, a gdy pusty GMAIL_APP_PASSWORD.
# Efekty uboczne/błędy: jak get_env_value. Uwaga: wartość sekretna — nie logować.
def get_mail_password() -> str:
    return get_env_value(ENV_MAIL_PASSWORD) or get_env_value(ENV_GMAIL_APP_PASSWORD)


# >>> OPIS FUNKCJI: funkcja get_mail_sender_name
# Cel: nazwa nadawcy w polu From. Parametry: brak. Zwraca: str — MAIL_SENDER_NAME, a gdy pusty GMAIL_SENDER_NAME.
# Efekty uboczne/błędy: jak get_env_value.
def get_mail_sender_name() -> str:
    return get_env_value(ENV_MAIL_SENDER_NAME) or get_env_value(ENV_GMAIL_SENDER_NAME)


# >>> OPIS FUNKCJI: funkcja get_gmail_user
# Cel: alias zgodności wstecznej dla get_mail_user. Parametry: brak. Zwraca: str. Efekty uboczne/błędy: jak get_mail_user.
def get_gmail_user() -> str:
    return get_mail_user()


# >>> OPIS FUNKCJI: funkcja get_gmail_app_password
# Cel: alias zgodności wstecznej dla get_mail_password. Parametry: brak. Zwraca: str (sekret). Efekty uboczne/błędy: jak get_mail_password.
def get_gmail_app_password() -> str:
    return get_mail_password()


# >>> OPIS FUNKCJI: funkcja get_gmail_sender_name
# Cel: alias zgodności wstecznej dla get_mail_sender_name. Parametry: brak. Zwraca: str. Efekty uboczne/błędy: jak get_mail_sender_name.
def get_gmail_sender_name() -> str:
    return get_mail_sender_name()


# >>> OPIS FUNKCJI: funkcja check_env_status
# Cel: sprawdzić, które ważne zmienne są ustawione, bez ujawniania wartości. Parametry: brak.
# Zwraca: dict[str, bool] — nazwa zmiennej → czy ma niepustą wartość (Serper, dane poczty, SMTP/IMAP, Anthropic, modele Claude).
# Efekty uboczne: odczyty get_env_value (na Windows mogą uruchamiać PowerShell). Błędy: brak.
def check_env_status() -> dict[str, bool]:
    """Kt├│re zmienne s─ů ustawione (bez ujawniania warto┼Ťci)."""
    all_names = (
        ENV_SERPER_API_KEY,
        ENV_MAIL_USER,
        ENV_MAIL_PASSWORD,
        ENV_MAIL_SENDER_NAME,
        ENV_SMTP_HOST,
        ENV_IMAP_HOST,
        ENV_GMAIL_USER,
        ENV_GMAIL_APP_PASSWORD,
        ENV_GMAIL_SENDER_NAME,
        ENV_ANTHROPIC_API_KEY,
        ENV_CLAUDE_MODEL,
        ENV_CLAUDE_MODEL_VERIFY,
        ENV_CLAUDE_MODEL_FAST,
    )
    return {n: bool(get_env_value(n)) for n in all_names}


# UTF-8 / polskie znaki ÔÇö od razu przy imporcie modu┼éu wsp├│lnego
from polish_text import configure_utf8_environment

configure_utf8_environment()

# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Moduł: libs/scraper_email_replies — synchronizacja odpowiedzi e-mail (IMAP), ceny z maili i PDF, przypomnienia i kolumny CRM w Excelu.
#
# CO ROBI
#   Skanuje skrzynkę IMAP (BODY.PEEK), dopasowuje odpowiedzi do kontaktów z cache (po adresie email_target lub domenie firmowej),
#   klasyfikuje je (oferta / pytania / bez ceny / auto-odpowiedź / bounce), wyciąga kwoty z treści i PDF (natywnie lub OCR),
#   wylicza „Zadzwoń?” i flagi interwencji, buduje treść przypomnień (max 2 na kontakt, PL/DE oraz wariant DE+FR z cytatem
#   poprzedniego maila) i zapisuje Excel z kolumnami CRM oraz kolorowaniem wierszy.
#
# ROLA W PIPELINE
#   Warstwa Excela i obsługi odpowiedzi. Z głównego scrapera PL FAS (pl_fas_spedycja_scraper) używane są: REPLY_EXPORT_COLUMNS, ReplySyncConfig,
#   mark_email_sent, merge_export_row i write_excel_with_reply_styles (zapis Excela z kolumnami CRM); skrypty export_week_discovery_all_to_excel.py
#   i save_excel_seven_from_pi.py używają ReplySyncConfig + write_excel_with_reply_styles. Pozostała część (skan IMAP, przypomnienia, presety
#   kampanii PL/DE/CH, stopki Kanbud/MFG, kotwice relacji transportu) to wspólny kod legacy z kampanii Kanbud/MFG. Wysyłka B2B jest
#   domyślnie wyłączona kill-switchem DISABLE_CONTRACTOR_EMAILS.
#
# ZALEŻNOŚCI
#   polish_text (configure_utf8_environment, normalize_row_dict, normalize_unicode_text, sanitize_special_text), scraper_env
#   (dane Gmail/IMAP), mail_transport (get_imap_host, send_smtp_email); leniwie: email_journal, project_config, email_reply_intelligence
#   (moduł spoza repozytorium), pandas/openpyxl (Excel), PyMuPDF/pypdf/pdf2image/pytesseract (PDF/OCR).
#   Przy imporcie wywołuje configure_utf8_environment().
#
# WEJŚCIE / WYJŚCIE
#   Wejście: cache kampanii (dict z kluczem contacts), ReplySyncConfig, wiadomości IMAP. Wyjście: zmodyfikowany cache (pola reply_*, price_*,
#   reminder_*, call_needed…), listy kandydatów do przypomnień, pliki cache JSON i Excel.
# STAŁE: DEFAULT_NO_REPLY_HOURS=3, REMINDER_1_HOURS_AFTER_SENT=3, REMINDER_2_HOURS_AFTER_FIRST=2, MAX_REMINDERS_PER_CONTACT=2,
#   okno wysyłki SEND_WINDOW_START/END = 8–18, wzorce cen PRICE_PATTERNS, wskazówki auto-odpowiedzi/bounce/pytań (PL/DE).
# ============================================================
"""
Wspólny moduł: synchronizacja odpowiedzi Gmail (IMAP), wyciąganie cen (mail + PDF),
kolumny CRM w Excelu, czerwone wiersze gdy brak odpowiedzi po X godzinach.
"""
from __future__ import annotations

import email
import imaplib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path
from typing import Any

import random
import time

from polish_text import (
    configure_utf8_environment,
    normalize_row_dict,
    normalize_unicode_text,
    sanitize_special_text,
)
from scraper_env import (
    ENV_GMAIL_APP_PASSWORD,
    ENV_GMAIL_SENDER_NAME,
    ENV_GMAIL_USER,
    get_env_value,
    get_gmail_app_password,
    get_gmail_user,
)
from mail_transport import get_imap_host, send_smtp_email

configure_utf8_environment()

# --- Konfiguracja domyślna ---
DEFAULT_NO_REPLY_HOURS = 3.0
DEFAULT_IMAP_FULL_SCAN_DAYS = 120
DEFAULT_REMINDER_MIN_HOURS = 3.0
REMINDER_1_HOURS_AFTER_SENT = 3.0
REMINDER_2_HOURS_AFTER_FIRST = 2.0
MAX_REMINDERS_PER_CONTACT = 2
REMINDER_SEND_DELAY_MIN = 22
REMINDER_SEND_DELAY_MAX = 58
SEND_WINDOW_START = 8
SEND_WINDOW_END = 18

SIGNATURE_PL = (
    "Z poważaniem,\n\n"
    "Maksym Swinczak\n"
    "Kanbud Sp. z o.o.\n"
    "tel. +49 1522 3655 399"
)
# W stopce przypomnień DE pozostaje MFG (kampanie niemieckie)
SIGNATURE_DE = (
    "Mit freundlichen Grüßen\n"
    "Maksym Swinczak – MFG Modernerfliesenboden\n"
    "Tel.: +49 152 23655399\n"
    "Web: mfg-fliesen.de"
)
RED_FILL_RGB = "FFFFC7CE"
YELLOW_FILL_RGB = "FFFFFF99"

REPLY_EXPORT_COLUMNS = [
    "Status maila",
    "Wysłano",
    "Odpowiedź",
    "Status odpowiedzi",
    "Wymaga interwencji",
    "Odczytane (Twoja reakcja)",
    "Cena",
    "Waluta",
    "Opis",
    "Ceny (wszystkie)",
    "Źródło ceny",
    "Zadzwoń?",
]

ORANGE_FILL_RGB = "FFFFE699"

# Kotwice relacji (transport PL) — dopasowanie cen w tekście/OCR
TRANSPORT_RELATION_ANCHORS_PL = [
    ("rel_1", ("etoy", "1163", "szwajcar", " ch")),
    ("rel_2", ("saalfeld", "07318", "rewe", "niemiec", " de")),
    ("rel_3", ("opole", "odra", "cementownia")),
]

AUTO_REPLY_HINTS = (
    "automatic reply",
    "auto-reply",
    "autoreply",
    "out of office",
    "poza biurem",
    "nieobecno",
    "abwesenheit",
    "automatische antwort",
    "automatyczna odpowied",
    "urlaub",
    "vacation",
)

BOUNCE_HINTS = (
    "mail delivery failed",
    "undelivered",
    "undeliverable",
    "delivery status notification",
    "nie dostarczono",
    "mailbox unavailable",
    "user unknown",
)

QUESTION_HINTS_PL = (
    "proszę o",
    "prosze o",
    "czy ",
    "jaki nip",
    "jaki numer",
    "nie mamy w systemie",
    "proszę doprecyzować",
    "prosze doprecyzowac",
    "która firma",
    "ktora firma",
    "doprecyzow",
    "jakie dane",
)

QUESTION_HINTS_DE = (
    "bitte um",
    "können sie",
    "koennen sie",
    "welche",
    "ust-id",
    "steuernummer",
    "nicht im system",
    "rückfrage",
    "rueckfrage",
    "bitte teilen",
)

PRICE_PATTERNS = [
    re.compile(
        r"(?P<val>\d{1,3}(?:[\s\u00a0.]?\d{3})*(?:[.,]\d{1,2})?)\s*(?P<cur>zł|zl|PLN|EUR|€|CHF)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?P<cur>EUR|€|PLN|zł|zl|CHF)\s*(?P<val>\d{1,3}(?:[\s\u00a0.]?\d{3})*(?:[.,]\d{1,2})?)",
        re.IGNORECASE,
    ),
]

# Stopka firmowa / rejestrowa — nie jest wyceną transportu
FALSE_PRICE_SNIPPET_HINTS = (
    "kapitał zakładowy",
    "kapital zakladowy",
    "share capital",
    "registered capital",
    " w całości wpłacony",
    " w calosci wplacony",
    "krs ",
    "regon ",
    "nip ",
    "bdo ",
    "sąd rejonowy",
    "sad rejonowy",
)

POSITIVE_PRICE_SNIPPET_HINTS = (
    "stawka",
    "wycen",
    "cena",
    "oferta",
    "koszt",
    "eur/",
    "€/",
    "pln/",
    "za ton",
    "za transport",
    "relacja",
    "ftl",
    "all-in",
    "fracht",
    "preis",
    "angebot",
)


# >>> OPIS FUNKCJI: klasa ReplySyncConfig
# Klasa danych (dataclass) — konfiguracja jednej synchronizacji odpowiedzi:
#   cache_path, xlsx_path (Path) — pliki cache JSON i Excela kampanii; lang ("pl"/"de") — język etykiet;
#   campaign_id (str) — identyfikator kampanii do dziennika; no_reply_hours (float, domyślnie 3.0) — po ilu godzinach
#   bez odpowiedzi kontakt jest oznaczany „Zadzwoń?”; relation_anchors — kotwice relacji (domyślnie
#   TRANSPORT_RELATION_ANCHORS_PL); imap_days_back (int, 14) — zakres skanu IMAP; main_sheet_names — arkusze główne;
#   email_column ("E-mail") — nazwa kolumny z adresem. Brak logiki — tylko kontener danych.
@dataclass
class ReplySyncConfig:
    cache_path: Path
    xlsx_path: Path
    lang: str = "pl"
    campaign_id: str = ""
    no_reply_hours: float = DEFAULT_NO_REPLY_HOURS
    relation_anchors: list[tuple[str, tuple[str, ...]]] = field(
        default_factory=lambda: list(TRANSPORT_RELATION_ANCHORS_PL)
    )
    imap_days_back: int = 14
    main_sheet_names: tuple[str, ...] = ("Kontakte", "Kontakty", "Baza firm")
    email_column: str = "E-mail"


UNKNOWN_COMPANY_LABEL_PL = "Nieznana firma"
UNKNOWN_COMPANY_LABEL_DE = "Unbekanntes Unternehmen"
UNKNOWN_COMPANY_LABELS = (UNKNOWN_COMPANY_LABEL_PL, UNKNOWN_COMPANY_LABEL_DE)
_UNKNOWN_LABELS_LOWER = {label.lower() for label in UNKNOWN_COMPANY_LABELS}

EXPORT_NAME_COLUMNS = (
    "Nazwa firmy",
    "Firma",
    "Nazwa Firmy",
    "Firmenname",
    "nazwa",
    "company_name_clean",
)


# >>> OPIS FUNKCJI: funkcja is_unknown_company_name
# Cel: sprawdzić, czy nazwa to etykieta „firma nieznana”. Parametry: name (str). Zwraca: bool — True, gdy po strip/lower
# jest równa "nieznana firma" lub "unbekanntes unternehmen". Efekty uboczne/błędy: brak.
def is_unknown_company_name(name: str) -> bool:
    return (name or "").strip().lower() in _UNKNOWN_LABELS_LOWER


# >>> OPIS FUNKCJI: funkcja export_row_company_name
# Cel: wyciągnąć nazwę firmy z wiersza eksportu. Parametry: row (dict). Zwraca: str — pierwsza niepusta wartość z kolumn
# EXPORT_NAME_COLUMNS (Nazwa firmy, Firma, Firmenname, nazwa, company_name_clean) lub "". Efekty uboczne/błędy: brak.
def export_row_company_name(row: dict) -> str:
    for key in EXPORT_NAME_COLUMNS:
        val = row.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


# >>> OPIS FUNKCJI: funkcja is_unknown_company_row
# Cel: czy wiersz eksportu dotyczy „nieznanej firmy”. Parametry: row (dict). Zwraca: bool
# (is_unknown_company_name(export_row_company_name(row))). Efekty uboczne/błędy: brak.
def is_unknown_company_row(row: dict) -> bool:
    return is_unknown_company_name(export_row_company_name(row))


# >>> OPIS FUNKCJI: funkcja should_skip_scraper_row
# Cel: pominąć wpisy „Nieznana firma” bez adresu www. Parametry: row (dict) — z kluczami company_name_clean/nazwa i url.
# Zwraca: bool — True, gdy nazwa jest nieznana i url pusty. Efekty uboczne/błędy: brak.
def should_skip_scraper_row(row: dict) -> bool:
    """Pomija puste wpisy „Nieznana firma” / „Unbekanntes Unternehmen” bez URL."""
    name = (row.get("company_name_clean") or row.get("nazwa") or "").strip()
    if not is_unknown_company_name(name):
        return False
    return not (row.get("url") or "").strip()


# >>> OPIS FUNKCJI: funkcja filter_unknown_company_rows
# Cel: usunąć z listy wiersze „nieznanych firm”. Parametry: rows (list[dict]). Zwraca: nowa lista bez takich wierszy.
# Efekty uboczne/błędy: brak (oryginał niezmieniany).
def filter_unknown_company_rows(rows: list[dict]) -> list[dict]:
    return [r for r in rows if not is_unknown_company_row(r)]


# >>> OPIS FUNKCJI: funkcja purge_unknown_from_cache
# Cel: wyczyścić cache z wpisów „Nieznana firma / Unbekanntes Unternehmen”. Parametry: cache (dict, mutowany) — sekcje
# contacts, claude_row_enrichment i gemini_row_enrichment (legacy).
# Zwraca: int — liczba usuniętych wpisów (klucz zaczyna się od etykiety lub nazwa jest nieznana).
# Efekty uboczne: usuwa klucze z cache. Błędy: sekcje niebędące dict są pomijane.
def purge_unknown_from_cache(cache: dict) -> int:
    """Usuwa wpisy „Nieznana firma” / „Unbekanntes Unternehmen” z cache."""
    removed = 0
    for section in ("contacts", "claude_row_enrichment", "gemini_row_enrichment"):
        bucket = cache.get(section)
        if not isinstance(bucket, dict):
            continue
        drop_keys = []
        for key, info in bucket.items():
            if not isinstance(info, dict):
                continue
            name = (
                info.get("company_name_clean")
                or info.get("company_name")
                or info.get("nazwa")
                or ""
            ).strip()
            key_low = str(key).lower()
            key_is_unknown = any(
                key_low.startswith(label.lower()) for label in UNKNOWN_COMPANY_LABELS
            )
            if key_is_unknown or is_unknown_company_name(name):
                drop_keys.append(key)
        for key in drop_keys:
            bucket.pop(key, None)
            removed += 1
    return removed


# >>> OPIS FUNKCJI: funkcja normalize_email
# Cel: sprowadzić adres do postaci porównywalnej. Parametry: addr (str) — także "Imię <adres>".
# Zwraca: str — czysty adres małymi literami (parseaddr) lub "" dla pustego. Efekty uboczne/błędy: brak.
def normalize_email(addr: str) -> str:
    if not addr:
        return ""
    _, bare = parseaddr(addr)
    return (bare or addr).strip().lower()


# >>> OPIS FUNKCJI: funkcja email_domain
# Cel: wyciągnąć domenę z adresu. Parametry: addr (str). Zwraca: str — część po "@" (po normalizacji) lub "".
# Efekty uboczne/błędy: brak.
def email_domain(addr: str) -> str:
    em = normalize_email(addr)
    if "@" in em:
        return em.split("@", 1)[1]
    return ""


# Domeny współdzielone — dopasowanie po domenie dawało jedną odpowiedź setkom firm (gmail.com itd.)
GENERIC_EMAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "wp.pl",
        "o2.pl",
        "op.pl",
        "interia.pl",
        "onet.pl",
        "poczta.onet.pl",
        "vp.pl",
        "outlook.com",
        "hotmail.com",
        "live.com",
        "yahoo.com",
        "yahoo.pl",
        "icloud.com",
        "protonmail.com",
        "proton.me",
        "gmx.de",
        "gmx.net",
        "web.de",
        "t-online.de",
        "aol.com",
        "mail.com",
        "spoko.pl",
        "autograf.pl",
        "go2.pl",
    }
)

REPLY_SYNC_FIELD_KEYS = (
    "reply_at",
    "reply_from",
    "reply_subject",
    "reply_status",
    "has_reply",
    "reply_body_snippet",
    "reply_description",
    "price_main",
    "price_currency",
    "prices_all",
    "price_source",
    "price_rel",
    "price_evidence",
    "needs_human_review",
    "extraction_method",
    "extraction_version",
    "reply_matched_by",
    "requires_intervention",
    "imap_uid",
)


# >>> OPIS FUNKCJI: funkcja is_generic_email_domain
# Cel: rozpoznać domeny ogólnodostępne (gmail, wp itp. z GENERIC_EMAIL_DOMAINS), po których nie wolno dopasowywać firmy.
# Parametry: domain (str). Zwraca: bool — True dla pustej domeny, dokładnego dopasowania lub poddomeny z listy.
# Efekty uboczne/błędy: brak.
def is_generic_email_domain(domain: str) -> bool:
    d = (domain or "").strip().lower()
    if not d:
        return True
    if d in GENERIC_EMAIL_DOMAINS:
        return True
    return any(d == g or d.endswith("." + g) for g in GENERIC_EMAIL_DOMAINS)


# >>> OPIS FUNKCJI: funkcja mark_email_sent
# Cel: zapisać w kontakcie fakt wysłania zapytania. Parametry: contact (dict, mutowany); subject (str);
# body (keyword-only, str); lang (str, "pl"); campaign_id (str); relation_labels (list[str]|None).
# Zwraca: None. Efekty uboczne: ustawia email_sent_at (ISO, sekundy), email_subject_sent, opcjonalnie email_body_sent,
# email_lang, campaign_id, relation_labels. Błędy: brak.
def mark_email_sent(
    contact: dict,
    subject: str,
    *,
    body: str = "",
    lang: str = "pl",
    campaign_id: str = "",
    relation_labels: list[str] | None = None,
) -> None:
    contact["email_sent_at"] = datetime.now().isoformat(timespec="seconds")
    contact["email_subject_sent"] = (subject or "").strip()
    if body and str(body).strip():
        contact["email_body_sent"] = str(body).strip()
    contact["email_lang"] = lang
    if campaign_id:
        contact["campaign_id"] = campaign_id
    if relation_labels:
        contact["relation_labels"] = relation_labels


# >>> OPIS FUNKCJI: funkcja build_email_lookup
# Cel: zbudować indeksy odwrotne do dopasowania odpowiedzi do kontaktów. Parametry: cache (dict) — używa cache["contacts"].
# Zwraca: (by_email, by_domain): adres docelowy (email_target) → [place_url] oraz domena firmowa (nie ogólnodostępna) → [place_url].
# Efekty uboczne/błędy: brak (wpisy niebędące dict pomijane).
def build_email_lookup(cache: dict) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Adres docelowy wysyłki (email_target) -> [place_url]; domena firmowa (nie gmail/wp) -> [place_url]."""
    by_email: dict[str, list[str]] = {}
    by_domain: dict[str, list[str]] = {}
    contacts = cache.get("contacts") or {}
    for place_url, info in contacts.items():
        if not isinstance(info, dict):
            continue
        target = normalize_email(info.get("email_target") or "")
        if not target:
            continue
        by_email.setdefault(target, [])
        if place_url not in by_email[target]:
            by_email[target].append(place_url)
        dom = email_domain(target)
        if dom and not is_generic_email_domain(dom):
            by_domain.setdefault(dom, [])
            if place_url not in by_domain[dom]:
                by_domain[dom].append(place_url)
    return by_email, by_domain


# >>> OPIS FUNKCJI: funkcja _filter_urls_for_incoming_reply
# Cel: zawęzić kandydatów do kontaktów, do których faktycznie wysłano mail na ten adres. Parametry: cache (dict);
# urls (list[str]); from_em (str, znormalizowany nadawca odpowiedzi). Zwraca: list[str] — tylko place_url z email_target == from_em
# i ustawionym email_sent_at. Efekty uboczne/błędy: brak.
def _filter_urls_for_incoming_reply(cache: dict, urls: list[str], from_em: str) -> list[str]:
    """Tylko kontakty, na które faktycznie wysłano mail (email_target + email_sent_at)."""
    contacts = cache.get("contacts") or {}
    matched: list[str] = []
    for place_url in urls:
        info = contacts.get(place_url)
        if not isinstance(info, dict):
            continue
        if normalize_email(info.get("email_target") or "") != from_em:
            continue
        if not info.get("email_sent_at"):
            continue
        matched.append(place_url)
    return matched


# >>> OPIS FUNKCJI: funkcja pick_best_place_url_for_reply
# Cel: wybrać jeden kontakt dla odpowiedzi, gdy pasuje kilka. Parametry: cache (dict); urls (list[str]); msg_dt (datetime) — data maila.
# Zwraca: str|None — jedyny kandydat; przy wielu: ten z najpóźniejszym email_sent_at nie późniejszym niż msg_dt+5 min; w razie braku —
# pierwszy z listy; None dla pustej listy. Efekty uboczne: brak. Błędy: niepoprawne daty są pomijane (ValueError).
def pick_best_place_url_for_reply(
    cache: dict, urls: list[str], msg_dt: datetime
) -> str | None:
    """Jeden wiersz na odpowiedź — najbliższa wysyłka przed datą maila."""
    if not urls:
        return None
    if len(urls) == 1:
        return urls[0]
    contacts = cache.get("contacts") or {}
    best_url: str | None = None
    best_sent: datetime | None = None
    for place_url in urls:
        info = contacts.get(place_url)
        if not isinstance(info, dict):
            continue
        raw = info.get("email_sent_at")
        if not raw:
            continue
        try:
            sent_at = datetime.fromisoformat(str(raw).replace("Z", ""))
        except ValueError:
            continue
        if sent_at > msg_dt + timedelta(minutes=5):
            continue
        if best_sent is None or sent_at > best_sent:
            best_sent = sent_at
            best_url = place_url
    return best_url or urls[0]


# >>> OPIS FUNKCJI: funkcja resolve_place_urls
# Cel: znaleźć kontakty (place_url) pasujące do adresu nadawcy odpowiedzi. Parametry: from_addr (str); by_email, by_domain (dict z
# build_email_lookup); cache (dict|None) — jeśli podany, dodatkowo filtruje do kontaktów z wysłanym mailem.
# Zwraca: list[str] — dopasowanie po dokładnym adresie, a w drugiej kolejności po domenie firmowej (tylko gdy jednoznaczne);
# [] gdy brak. Efekty uboczne/błędy: brak.
def resolve_place_urls(
    from_addr: str,
    by_email: dict,
    by_domain: dict,
    cache: dict | None = None,
) -> list[str]:
    em = normalize_email(from_addr)
    if not em:
        return []
    urls: list[str] = []
    if em in by_email:
        urls = list(by_email[em])
    else:
        dom = email_domain(em)
        if dom and not is_generic_email_domain(dom) and dom in by_domain:
            candidates = list(by_domain[dom])
            if len(candidates) == 1:
                urls = candidates
    if not urls:
        return []
    if cache is not None:
        return _filter_urls_for_incoming_reply(cache, urls, em)
    return urls


# >>> OPIS FUNKCJI: funkcja clear_reply_fields
# Cel: wyzerować pola odpowiedzi kontaktu. Parametry: contact (dict, mutowany). Zwraca: None.
# Efekty uboczne: usuwa klucze REPLY_SYNC_FIELD_KEYS i user_read_at, ustawia has_reply=False. Błędy: brak.
def clear_reply_fields(contact: dict) -> None:
    for key in REPLY_SYNC_FIELD_KEYS:
        contact.pop(key, None)
    contact["has_reply"] = False
    contact.pop("user_read_at", None)


# >>> OPIS FUNKCJI: funkcja repair_misassigned_replies
# Cel: usunąć odpowiedzi przypisane do złego kontaktu (np. po wspólnej domenie gmail.com). Parametry: cache (dict, mutowany);
# logger (Logger|None). Zwraca: int — liczba wyczyszczonych kontaktów (reply_from różny od email_target).
# Efekty uboczne: clear_reply_fields na kontaktach, log info. Błędy: brak.
def repair_misassigned_replies(cache: dict, logger: logging.Logger | None = None) -> int:
    """Usuwa odpowiedzi przypisane do złego kontaktu (np. fan-out po gmail.com)."""
    cleared = 0
    for _url, info in (cache.get("contacts") or {}).items():
        if not isinstance(info, dict):
            continue
        if not info.get("reply_at"):
            continue
        reply_from = normalize_email(info.get("reply_from") or "")
        target = normalize_email(info.get("email_target") or "")
        if not reply_from:
            continue
        if target and reply_from == target:
            continue
        clear_reply_fields(info)
        cleared += 1
    if cleared and logger:
        logger.info(f"Usunięto błędnie przypisane odpowiedzi: {cleared}")
    return cleared


# >>> OPIS FUNKCJI: funkcja decode_mime_header
# Cel: zdekodować nagłówek MIME (np. =?UTF-8?...?=) do tekstu. Parametry: value (str|None). Zwraca: str — połączone fragmenty
# po decode_header (błędne bajty → znak zastępczy) i normalize_unicode_text; "" dla pustego. Efekty uboczne/błędy: brak.
def decode_mime_header(value: str | None) -> str:
    if not value:
        return ""
    parts = []
    for chunk, enc in decode_header(value):
        if isinstance(chunk, bytes):
            parts.append(chunk.decode(enc or "utf-8", errors="replace"))
        else:
            parts.append(str(chunk))
    return normalize_unicode_text("".join(parts).strip())


# >>> OPIS FUNKCJI: funkcja html_to_text
# Cel: uprościć HTML maila do zwykłego tekstu. Parametry: html (str). Zwraca: str — bez script/style, <br> i </p> jako nowe linie,
# pozostałe tagi usunięte, encje podstawowe odkodowane, białe znaki zredukowane. Efekty uboczne/błędy: brak.
def html_to_text(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape_basic(text)
    return " ".join(text.split())


# >>> OPIS FUNKCJI: funkcja unescape_basic
# Cel: odkodować cztery podstawowe encje HTML. Parametry: s (str). Zwraca: str — &nbsp;, &amp;, &lt;, &gt; zamienione na znaki.
# Efekty uboczne/błędy: brak.
def unescape_basic(s: str) -> str:
    return (
        s.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
    )


# >>> OPIS FUNKCJI: funkcja get_message_body
# Cel: wyciągnąć czytelną treść wiadomości e-mail. Parametry: msg (email.message.Message). Zwraca: str — preferuje części
# text/plain, w razie braku text/html (przez html_to_text); pomija załączniki; "" gdy brak treści. Wynik przechodzi przez
# normalize_unicode_text. Efekty uboczne: brak. Błędy: błędy dekodowania zestawu znaków → fallback na UTF-8 (errors="replace").
def get_message_body(msg: email.message.Message) -> str:
    plain_parts: list[str] = []
    html_parts: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = (part.get_content_type() or "").lower()
            disp = str(part.get("Content-Disposition") or "").lower()
            if "attachment" in disp:
                continue
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            charset = part.get_content_charset() or "utf-8"
            try:
                text = payload.decode(charset, errors="replace")
            except Exception:
                text = payload.decode("utf-8", errors="replace")
            if ctype == "text/plain":
                plain_parts.append(text)
            elif ctype == "text/html":
                html_parts.append(text)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            try:
                text = payload.decode(charset, errors="replace")
            except Exception:
                text = payload.decode("utf-8", errors="replace")
            if (msg.get_content_type() or "").lower() == "text/html":
                html_parts.append(text)
            else:
                plain_parts.append(text)
    if plain_parts:
        return normalize_unicode_text("\n".join(plain_parts).strip())
    if html_parts:
        return normalize_unicode_text(html_to_text("\n".join(html_parts)))
    return ""


# >>> OPIS FUNKCJI: funkcja iter_pdf_attachments
# Cel: wyłuskać załączniki PDF z wiadomości. Parametry: msg (Message). Zwraca: generator krotek (nazwa_pliku, bajty) dla części będących
# PDF-em (po nazwie .pdf lub typie application/pdf; domyślna nazwa "attachment.pdf"). Efekty uboczne/błędy: brak.
def iter_pdf_attachments(msg: email.message.Message):
    for part in msg.walk():
        disp = str(part.get("Content-Disposition") or "").lower()
        fname = part.get_filename() or ""
        ctype = (part.get_content_type() or "").lower()
        if "attachment" not in disp and not fname.lower().endswith(".pdf"):
            if ctype != "application/pdf":
                continue
        if not (fname.lower().endswith(".pdf") or ctype == "application/pdf"):
            continue
        payload = part.get_payload(decode=True)
        if payload:
            yield fname or "attachment.pdf", payload


# >>> OPIS FUNKCJI: funkcja extract_text_from_pdf_bytes
# Cel: odczytać tekst z PDF-a (natywnie, a w razie potrzeby OCR). Parametry: data (bytes); logger.
# Zwraca: (tekst, źródło) — "pdf_text" gdy natywny tekst >= 40 znaków; "pdf_ocr" gdy OCR >= 20 znaków; inaczej "empty".
# Efekty uboczne: opcjonalny OCR (zależności zewnętrzne). Błędy: obsługiwane w _pdf_native_text/_pdf_ocr_text (zwracają "").
def extract_text_from_pdf_bytes(data: bytes, logger: logging.Logger) -> tuple[str, str]:
    """Zwraca (tekst, źródło: pdf_text|pdf_ocr|empty)."""
    text = _pdf_native_text(data)
    if len(text.strip()) >= 40:
        return text, "pdf_text"
    ocr_text = _pdf_ocr_text(data, logger)
    if len(ocr_text.strip()) >= 20:
        return ocr_text, "pdf_ocr"
    return text or ocr_text, "empty"


# >>> OPIS FUNKCJI: funkcja _pdf_native_text
# Cel: wyciągnąć tekst z PDF bez OCR. Parametry: data (bytes). Zwraca: str — próba PyMuPDF (fitz), potem pypdf; "" przy niepowodzeniu.
# Efekty uboczne: leniwe importy bibliotek. Błędy: wszystkie wyjątki łapane (przejście do następnego silnika / "").
def _pdf_native_text(data: bytes) -> str:
    try:
        import fitz  # PyMuPDF  # pyright: ignore[reportMissingImports]

        doc = fitz.open(stream=data, filetype="pdf")
        parts = [page.get_text() for page in doc]
        doc.close()
        return "\n".join(parts)
    except Exception:
        pass
    try:
        from pypdf import PdfReader  # pyright: ignore[reportMissingImports]
        import io

        reader = PdfReader(io.BytesIO(data))
        parts = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        return "\n".join(parts)
    except Exception:
        return ""


# >>> OPIS FUNKCJI: funkcja _pdf_ocr_text
# Cel: rozpoznać tekst ze zeskanowanego PDF (OCR). Parametry: data (bytes); logger. Zwraca: str — tekst z pytesseract
# (język pol+deu+eng, 300 dpi) lub "". Efekty uboczne: konwersja stron na obrazy (pdf2image), log info o pominięciu.
# Błędy: brak bibliotek lub błąd OCR są łapane → log info + "".
def _pdf_ocr_text(data: bytes, logger: logging.Logger) -> str:
    try:
        import io

        import pytesseract  # pyright: ignore[reportMissingImports]
        from pdf2image import convert_from_bytes  # pyright: ignore[reportMissingImports]

        images = convert_from_bytes(data, dpi=300)
        lang = "pol+deu+eng"
        chunks = [pytesseract.image_to_string(img, lang=lang) for img in images]
        return "\n".join(chunks)
    except Exception as e:
        logger.info(f"OCR PDF pominięty (brak pdf2image/pytesseract?): {e}")
        return ""


# >>> OPIS FUNKCJI: funkcja parse_message_date
# Cel: odczytać datę wiadomości. Parametry: msg (Message). Zwraca: datetime|None — bez strefy czasowej (tzinfo usuwane bez
# przeliczenia); None gdy brak lub błędny nagłówek Date. Efekty uboczne: brak. Błędy: łapane → None.
def parse_message_date(msg: email.message.Message) -> datetime | None:
    raw = msg.get("Date")
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo:
            return dt.replace(tzinfo=None)
        return dt
    except Exception:
        return None


# >>> OPIS FUNKCJI: funkcja classify_reply_text
# Cel: wstępnie sklasyfikować treść odpowiedzi. Parametry: text (str); lang (str, nieużywany w logice).
# Zwraca: str — "bounce", "auto_reply", "replied_with_price", "replied_questions" lub "replied_no_price" (kolejność reguł jak w kodzie).
# Efekty uboczne: brak. Błędy: brak.
def classify_reply_text(text: str, lang: str = "pl") -> str:
    low = (text or "").lower()
    if any(h in low for h in BOUNCE_HINTS):
        return "bounce"
    if any(h in low for h in AUTO_REPLY_HINTS):
        return "auto_reply"
    prices = extract_price_candidates(text)
    if prices:
        return "replied_with_price"
    q_hints = list(QUESTION_HINTS_PL)
    q_hints.extend(QUESTION_HINTS_DE)
    if "?" in text and any(h in low for h in q_hints):
        return "replied_questions"
    if any(h in low for h in q_hints):
        return "replied_questions"
    if len(low.strip()) > 30:
        return "replied_no_price"
    return "replied_no_price"


# >>> OPIS FUNKCJI: funkcja _parse_amount
# Cel: sparsować kwotę zapisaną w formacie PL/DE/EN. Parametry: val (str) — np. "1 234,56" lub "1.234,56".
# Zwraca: float|None — wartość w zakresie 5…9 999 999; None dla pustego, niepoprawnego lub spoza zakresu.
# Efekty uboczne: brak. Błędy: ValueError łapany → None.
def _parse_amount(val: str) -> float | None:
    s = (val or "").strip().replace("\u00a0", " ").replace(" ", "")
    if not s:
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            s = parts[0].replace(".", "") + "." + parts[1]
        else:
            s = s.replace(",", "")
    else:
        s = s.replace(".", "") if s.count(".") > 1 else s
    try:
        v = float(s)
        if 5 <= v <= 9_999_999:
            return v
    except ValueError:
        pass
    return None


# >>> OPIS FUNKCJI: funkcja _normalize_currency
# Cel: ujednolicić oznaczenie waluty. Parametry: cur (str). Zwraca: str — wielkie litery; "€"/"EURO" → "EUR", "ZŁ"/"ZL" → "PLN".
# Efekty uboczne/błędy: brak.
def _normalize_currency(cur: str) -> str:
    c = (cur or "").strip().upper()
    if c in ("€", "EURO"):
        return "EUR"
    if c in ("ZŁ", "ZL"):
        return "PLN"
    return c


# >>> OPIS FUNKCJI: funkcja extract_price_candidates
# Cel: znaleźć w tekście kandydatów na cenę (PRICE_PATTERNS: kwota+waluta lub waluta+kwota; zł, PLN, EUR, €, CHF).
# Parametry: text (str). Zwraca: list[dict] z kluczami value (float), currency, snippet (±80 znaków) i relation_key
# (dopasowanie kotwicy relacji lub ""); duplikaty (kwota, waluta) pomijane, a kwoty tuż po stopce rejestrowej
# (kapitał zakładowy, KRS, NIP…) odrzucane. Efekty uboczne/błędy: brak.
def extract_price_candidates(text: str) -> list[dict]:
    found: list[dict] = []
    seen: set[tuple[float, str]] = set()
    body = text or ""
    for pat in PRICE_PATTERNS:
        for m in pat.finditer(body):
            if _is_false_price_context(body, m.start("val")):
                continue
            val = _parse_amount(m.group("val"))
            cur = _normalize_currency(m.group("cur"))
            if val is None or not cur:
                continue
            key = (round(val, 2), cur)
            if key in seen:
                continue
            seen.add(key)
            start = max(0, m.start() - 80)
            end = min(len(text), m.end() + 80)
            snippet = " ".join(text[start:end].split())
            rel_key = _match_relation(snippet.lower())
            found.append(
                {
                    "value": val,
                    "currency": cur,
                    "snippet": snippet,
                    "relation_key": rel_key,
                }
            )
    return found


# >>> OPIS FUNKCJI: funkcja _match_relation
# Cel: przypisać fragment tekstu do relacji transportowej. Parametry: snippet_low (str, lower). Zwraca: str — klucz relacji
# (rel_1/rel_2/rel_3) z pierwszej pasującej kotwicy TRANSPORT_RELATION_ANCHORS_PL lub "". Efekty uboczne/błędy: brak.
def _match_relation(snippet_low: str) -> str:
    for rel_key, anchors in TRANSPORT_RELATION_ANCHORS_PL:
        if any(a in snippet_low for a in anchors):
            return rel_key
    return ""


# >>> OPIS FUNKCJI: funkcja _is_false_price_context
# Cel: wykluczyć kwoty ze stopki rejestrowej. Parametry: text (str); match_start (int) — pozycja początku kwoty.
# Zwraca: bool — True, gdy w 45 znakach przed kwotą występuje fraza z FALSE_PRICE_SNIPPET_HINTS. Efekty uboczne/błędy: brak.
def _is_false_price_context(text: str, match_start: int) -> bool:
    """Stopka rejestrowa tuż przed kwotą (np. kapitał zakładowy 603.060,00 zł)."""
    before = (text or "")[max(0, match_start - 45) : match_start].lower()
    return any(h in before for h in FALSE_PRICE_SNIPPET_HINTS)


# >>> OPIS FUNKCJI: funkcja _price_candidate_score
# Cel: ocenić kandydata na cenę główną. Parametry: p (dict z extract_price_candidates). Zwraca: krotkę (score, flaga relacji,
# -wartość): +100 za relację, +50 za słowa pozytywne (stawka, oferta…), +20 dla kwot 50–50 000, -80 dla > 100 000.
# Efekty uboczne/błędy: brak.
def _price_candidate_score(p: dict) -> tuple[int, int, float]:
    """Wyższy = lepszy kandydat (nie największa liczba w stopce)."""
    sn = (p.get("snippet") or "").lower()
    score = 0
    if p.get("relation_key"):
        score += 100
    if any(h in sn for h in POSITIVE_PRICE_SNIPPET_HINTS):
        score += 50
    val = float(p.get("value") or 0)
    if 50 <= val <= 50_000:
        score += 20
    elif val > 100_000:
        score -= 80
    return (score, 1 if p.get("relation_key") else 0, -val)


# >>> OPIS FUNKCJI: funkcja _pick_main_price
# Cel: wybrać najlepszego kandydata na cenę. Parametry: candidates (list[dict]). Zwraca: dict|None — max wg _price_candidate_score;
# None dla pustej listy. Efekty uboczne/błędy: brak.
def _pick_main_price(candidates: list[dict]) -> dict | None:
    if not candidates:
        return None
    return max(candidates, key=_price_candidate_score)


# >>> OPIS FUNKCJI: funkcja merge_price_extractions
# Cel: połączyć ceny z treści maila i PDF w jeden wynik. Parametry: body_prices, pdf_prices (list[dict]); pdf_source (str).
# Zwraca: dict z kluczami price_main, price_currency, prices_all (do 8, "; "), reply_description (snippet ≤ 400 znaków),
# price_source ("mail"/"mail+pdf"/źródło PDF) i price_rel (relacja → "kwota waluta"); pusty zestaw pól dla braku cen.
# Efekty uboczne/błędy: brak.
def merge_price_extractions(
    body_prices: list[dict], pdf_prices: list[dict], pdf_source: str
) -> dict[str, Any]:
    all_p = body_prices + pdf_prices
    if not all_p:
        return {
            "price_main": "",
            "price_currency": "",
            "prices_all": "",
            "reply_description": "",
            "price_source": "",
            "price_rel": {},
        }
    main = _pick_main_price(all_p)
    if not main:
        return {
            "price_main": "",
            "price_currency": "",
            "prices_all": "",
            "reply_description": "",
            "price_source": "",
            "price_rel": {},
        }
    rel_map: dict[str, str] = {}
    for p in all_p:
        rk = p.get("relation_key") or ""
        if rk and rk not in rel_map:
            rel_map[rk] = f"{p['value']:.2f} {p['currency']}"
    parts = [f"{p['value']:.2f} {p['currency']}" for p in all_p[:8]]
    source = "mail"
    if pdf_prices and body_prices:
        source = "mail+pdf"
    elif pdf_prices:
        source = pdf_source or "pdf"
    desc = main.get("snippet", "")[:400]
    return {
        "price_main": f"{main['value']:.2f}",
        "price_currency": main["currency"],
        "prices_all": "; ".join(parts),
        "reply_description": desc,
        "price_source": source,
        "price_rel": rel_map,
    }


# >>> OPIS FUNKCJI: funkcja is_sent_status
# Cel: czy status maila to "sent". Parametry: status (str). Zwraca: bool. Efekty uboczne/błędy: brak.
def is_sent_status(status: str) -> bool:
    return str(status or "").strip().lower() == "sent"


# >>> OPIS FUNKCJI: funkcja has_meaningful_reply
# Cel: czy odpowiedź jest merytoryczna. Parametry: reply_status (str). Zwraca: bool — False dla pustego, auto_reply i bounce;
# True dla statusów zaczynających się od "replied". Efekty uboczne/błędy: brak.
def has_meaningful_reply(reply_status: str) -> bool:
    rs = (reply_status or "").strip().lower()
    if rs in ("auto_reply", "bounce", ""):
        return False
    return rs.startswith("replied")


# >>> OPIS FUNKCJI: funkcja contact_has_any_reply
# Cel: czy kontakt ma jakąkolwiek wiadomość zwrotną (także auto-odpowiedź lub bounce) — wtedy bez przypomnienia.
# Parametry: contact (dict). Zwraca: bool — True, gdy ustawione reply_at, reply_from, niepusty fragment treści, has_reply lub reply_status.
# Efekty uboczne/błędy: brak.
def contact_has_any_reply(contact: dict) -> bool:
    """Jakakolwiek wiadomość zwrotna (także auto-odpowiedź, bounce) — bez przypomnienia."""
    if contact.get("reply_at"):
        return True
    if contact.get("reply_from"):
        return True
    if (contact.get("reply_body_snippet") or "").strip():
        return True
    if contact.get("has_reply"):
        return True
    return bool((contact.get("reply_status") or "").strip())


# >>> OPIS FUNKCJI: funkcja requires_user_intervention
# Cel: czy odpowiedź wymaga reakcji użytkownika. Parametry: reply_status (str); body_text (str). Zwraca: bool — True dla
# replied_questions i bounce oraz dla replied_no_price z pytaniem ("?" i słowa z QUESTION_HINTS_PL/DE). Efekty uboczne/błędy: brak.
def requires_user_intervention(reply_status: str, body_text: str = "") -> bool:
    """Mail wymaga Twojej odpowiedzi (pytania, bounce, doprecyzowanie)."""
    rs = (reply_status or "").strip().lower()
    if rs in ("replied_questions", "bounce"):
        return True
    if rs == "replied_no_price":
        low = (body_text or "").lower()
        if "?" in (body_text or "") and any(h in low for h in QUESTION_HINTS_PL + QUESTION_HINTS_DE):
            return True
    return False


# >>> OPIS FUNKCJI: funkcja is_user_marked_read
# Cel: czy użytkownik oznaczył odpowiedź jako przeczytaną. Parametry: contact (dict). Zwraca: bool (user_marked_read). Efekty uboczne/błędy: brak.
def is_user_marked_read(contact: dict) -> bool:
    return bool(contact.get("user_marked_read"))


# >>> OPIS FUNKCJI: funkcja update_intervention_flags
# Cel: zaktualizować flagi interwencji w kontakcie. Parametry: contact (dict, mutowany); reply_status (str); body_text (str).
# Zwraca: None. Efekty uboczne: ustawia requires_intervention, intervention_status ("nieodczytane"/"odczytane"/"") i user_marked_read=False
# dla nowej interwencji. Błędy: brak.
def update_intervention_flags(contact: dict, reply_status: str, body_text: str) -> None:
    needs = requires_user_intervention(reply_status, body_text)
    contact["requires_intervention"] = needs
    if needs and not is_user_marked_read(contact):
        contact["user_marked_read"] = False
        contact["intervention_status"] = "nieodczytane"
    elif needs and is_user_marked_read(contact):
        contact["intervention_status"] = "odczytane"
    else:
        contact["intervention_status"] = ""


# >>> OPIS FUNKCJI: funkcja compute_call_needed
# Cel: ocenić, czy trzeba zadzwonić do firmy (brak odpowiedzi po X godzinach). Parametry: contact (dict); no_reply_hours (float).
# Zwraca: bool — True tylko gdy status "sent", brak merytorycznej odpowiedzi, znany email_sent_at, bieżąca godzina mieści się w oknie
# SEND_WINDOW_START–END (8–18) i minęło >= no_reply_hours. Efekty uboczne: brak. Błędy: niepoprawna data → False.
def compute_call_needed(contact: dict, no_reply_hours: float) -> bool:
    if not is_sent_status(contact.get("email_status", "")):
        return False
    if has_meaningful_reply(contact.get("reply_status", "")):
        return False
    if contact.get("has_reply"):
        return False
    sent_raw = contact.get("email_sent_at") or ""
    if not sent_raw:
        return False
    try:
        sent_at = datetime.fromisoformat(sent_raw.replace("Z", ""))
    except ValueError:
        return False
    now = datetime.now()
    if not (SEND_WINDOW_START <= now.hour < SEND_WINDOW_END):
        return False
    return (now - sent_at) >= timedelta(hours=float(no_reply_hours))


# >>> OPIS FUNKCJI: funkcja reply_status_label
# Cel: etykieta statusu odpowiedzi do Excela. Parametry: status (str); lang (str, "pl"/"de"). Zwraca: str — np. Oferta/Pytania/Bez ceny/Auto/Bounce
# (PL) lub Angebot/Rückfrage/Kein Preis (DE); dla nieznanego statusu sam status. Efekty uboczne/błędy: brak.
def reply_status_label(status: str, lang: str = "pl") -> str:
    m = {
        "replied_with_price": "Oferta",
        "replied_questions": "Pytania",
        "replied_no_price": "Bez ceny",
        "auto_reply": "Auto",
        "bounce": "Bounce",
    }
    if lang == "de":
        m = {
            "replied_with_price": "Angebot",
            "replied_questions": "Rückfrage",
            "replied_no_price": "Kein Preis",
            "auto_reply": "Auto",
            "bounce": "Bounce",
        }
    return m.get((status or "").strip().lower(), status or "")


# >>> OPIS FUNKCJI: funkcja export_columns_from_contact
# Cel: zbudować kolumny CRM (REPLY_EXPORT_COLUMNS) dla wiersza Excela. Parametry: contact (dict); lang (str).
# Zwraca: dict[str,str] — Status maila, Wysłano, Odpowiedź (Tak/Nie lub Ja/Nein), Status odpowiedzi, Wymaga interwencji, Odczytane,
# Cena, Waluta, Opis (do 500 znaków), Ceny (wszystkie), Źródło ceny, Zadzwoń?, a także Cena rel. 1–3.
# Efekty uboczne: brak. Błędy: brak.
def export_columns_from_contact(contact: dict, lang: str = "pl") -> dict[str, str]:
    sent = (contact.get("email_sent_at") or "")[:19].replace("T", " ")
    reply_at = (contact.get("reply_at") or "")[:19].replace("T", " ")
    rs = (contact.get("reply_status") or "").strip()
    has_r = "Tak" if has_meaningful_reply(rs) or contact.get("has_reply") else "Nie"
    if lang == "de":
        has_r = "Ja" if has_r == "Tak" else "Nein"
    call = contact.get("call_needed")
    if call is None:
        call = compute_call_needed(contact, DEFAULT_NO_REPLY_HOURS)
    call_l = "TAK" if call else ""
    rel_prices = contact.get("price_rel") or {}
    desc = (contact.get("reply_description") or "").strip()
    if isinstance(rel_prices, dict) and rel_prices:
        rel_txt = "; ".join(f"{k}: {v}" for k, v in rel_prices.items())
        if rel_txt:
            desc = (desc + " | " + rel_txt).strip(" |")
    needs_int = bool(contact.get("requires_intervention"))
    if lang == "de":
        int_lbl = "JA" if needs_int else ""
        read_lbl = (
            "Ja"
            if is_user_marked_read(contact)
            else ("Nein" if needs_int else "")
        )
    else:
        int_lbl = "TAK" if needs_int else ""
        read_lbl = (
            "Tak"
            if is_user_marked_read(contact)
            else ("Nie" if needs_int else "")
        )
    row = {
        "Status maila": (contact.get("email_status") or "").strip(),
        "Wysłano": sent,
        "Odpowiedź": has_r,
        "Status odpowiedzi": reply_status_label(rs, lang) if rs else "",
        "Wymaga interwencji": int_lbl,
        "Odczytane (Twoja reakcja)": read_lbl,
        "Cena": (contact.get("price_main") or "").strip(),
        "Waluta": (contact.get("price_currency") or "").strip(),
        "Opis": sanitize_special_text(desc)[:500],
        "Ceny (wszystkie)": (contact.get("prices_all") or "").strip(),
        "Źródło ceny": (contact.get("price_source") or "").strip(),
        "Zadzwoń?": call_l,
    }
    anchors = contact.get("relation_labels") or []
    if not anchors and rel_prices:
        anchors = ["Rel. 1", "Rel. 2", "Rel. 3"]
    for i, rk in enumerate(("rel_1", "rel_2", "rel_3"), start=1):
        col = f"Cena rel. {i}"
        if isinstance(rel_prices, dict):
            row[col] = rel_prices.get(rk, "")
        else:
            row[col] = ""
    return row


# >>> OPIS FUNKCJI: funkcja get_contact_for_email
# Cel: znaleźć kontakt po adresie e-mail. Parametry: cache (dict); email_addr (str). Zwraca: dict|None — pierwszy dopasowany wpis
# z cache["contacts"] (przez build_email_lookup i resolve_place_urls). Efekty uboczne/błędy: brak.
def get_contact_for_email(cache: dict, email_addr: str) -> dict | None:
    em = normalize_email(email_addr)
    if not em:
        return None
    by_email, by_domain = build_email_lookup(cache)
    urls = resolve_place_urls(em, by_email, by_domain, cache)
    if not urls:
        return None
    return (cache.get("contacts") or {}).get(urls[0])


# >>> OPIS FUNKCJI: funkcja find_contact_by_export_email
# Cel: alias — znajduje kontakt po adresie z kolumny E-mail eksportu. Parametry: cache (dict); email_col_value (str).
# Zwraca: dict|None (get_contact_for_email). Efekty uboczne/błędy: brak.
def find_contact_by_export_email(cache: dict, email_col_value: str) -> dict | None:
    return get_contact_for_email(cache, email_col_value)


# >>> OPIS FUNKCJI: funkcja apply_reply_to_contact
# Cel: zapisać w kontakcie dane odebranej odpowiedzi wraz z analizą (status, ceny, opis). Parametry (keyword-only poza contact):
# contact (dict, mutowany); reply_at (datetime); reply_from, reply_subject, reply_status, body_text, pdf_text, pdf_source (str);
# lang (str); gemini_cache (dict|None) — cache analizy (nazwa legacy); matched_by (str, "email").
# Zwraca: None. Efekty uboczne: ustawia reply_*, has_reply, price_*, call_needed i flagi interwencji; korzysta z modułu
# email_reply_intelligence (analyze_incoming_reply, strip_quoted_reply) — moduł NIE jest częścią tego repozytorium (import leniwy).
# Błędy: ImportError, gdy email_reply_intelligence jest niedostępny; inne wyjątki propagują się.
def apply_reply_to_contact(
    contact: dict,
    *,
    reply_at: datetime,
    reply_from: str,
    reply_subject: str,
    reply_status: str,
    body_text: str,
    pdf_text: str,
    pdf_source: str,
    lang: str,
    gemini_cache: dict | None = None,
    matched_by: str = "email",
) -> None:
    from email_reply_intelligence import analyze_incoming_reply, strip_quoted_reply

    contact["reply_at"] = reply_at.isoformat(timespec="seconds")
    contact["reply_from"] = normalize_email(reply_from)
    contact["reply_subject"] = (reply_subject or "")[:500]
    contact["reply_matched_by"] = matched_by
    body_clean = strip_quoted_reply(body_text)
    contact["reply_body_snippet"] = (body_clean or body_text or "")[:2000]

    analyzed = analyze_incoming_reply(
        contact=contact,
        from_email=normalize_email(reply_from),
        subject=reply_subject or "",
        body_text=body_text,
        pdf_text=pdf_text,
        pdf_source=pdf_source,
        lang=lang,
        gemini_cache=gemini_cache,
    )
    reply_status = analyzed.get("reply_status") or reply_status
    contact["reply_status"] = reply_status
    contact["has_reply"] = has_meaningful_reply(reply_status)

    for key in (
        "price_main",
        "price_currency",
        "prices_all",
        "price_source",
        "price_rel",
        "reply_description",
        "price_evidence",
        "needs_human_review",
        "extraction_method",
        "extraction_version",
    ):
        if key in analyzed:
            contact[key] = analyzed[key]
    if not contact.get("price_source"):
        contact["price_source"] = "mail" if pdf_text else "mail"
    if reply_status == "replied_questions" and not contact.get("price_main"):
        q = analyzed.get("questions_text") or ""
        contact["reply_description"] = (q or body_clean or "")[:500]
    contact["call_needed"] = compute_call_needed(contact, DEFAULT_NO_REPLY_HOURS)
    update_intervention_flags(contact, reply_status, body_clean or body_text)


# >>> OPIS FUNKCJI: funkcja fetch_imap_messages
# Cel: pobrać wiadomości z INBOX od podanej daty (BODY.PEEK — bez oznaczania jako przeczytane). Parametry: logger; since (datetime);
# mark_intervention_unread (keyword-only, bool, nieużywany w treści). Zwraca: list[(numer_wiadomości: bytes, Message)].
# Efekty uboczne: połączenie IMAP SSL, login, wpisy do email_journal (błędy dziennika ignorowane), logowanie, logout w finally.
# Błędy: RuntimeError przy braku MAIL_USER/MAIL_PASSWORD lub IMAP_HOST; błędy IMAP propagują się (po logout).
def fetch_imap_messages(
    logger: logging.Logger,
    since: datetime,
    *,
    mark_intervention_unread: bool = True,
) -> list[tuple[bytes, email.message.Message]]:
    user = get_gmail_user()
    password = get_gmail_app_password()
    imap_host = get_imap_host()
    if not (user and password):
        raise RuntimeError("Brak MAIL_USER / MAIL_PASSWORD (lub GMAIL_*) w zmiennych środowiskowych.")
    if not imap_host:
        raise RuntimeError("Brak IMAP_HOST w zmiennych środowiskowych.")

    messages: list[tuple[bytes, email.message.Message]] = []
    try:
        from email_journal import log_imap_scan_start

        log_imap_scan_start(since)
    except Exception:
        pass
    logger.info(f"IMAP: skan INBOX od {since.strftime('%Y-%m-%d')}…")
    since_str = since.strftime("%d-%b-%Y")
    mail = imaplib.IMAP4_SSL(imap_host)
    try:
        mail.login(user, password)
        mail.select("INBOX")
        typ, data = mail.search(None, f'(SINCE "{since_str}")')
        if typ != "OK" or not data or not data[0]:
            logger.info("IMAP: brak nowych wiadomości w zakresie.")
            return []
        for num in data[0].split():
            typ2, msg_data = mail.fetch(num, "(BODY.PEEK[])")
            if typ2 != "OK" or not msg_data:
                continue
            for part in msg_data:
                if isinstance(part, tuple) and len(part) > 1:
                    msg = email.message_from_bytes(part[1])
                    messages.append((num, msg))
        logger.info(
            f"IMAP: pobrano {len(messages)} wiadomości "
            f"(BODY.PEEK — skan nie oznacza maili jako przeczytane w Gmail)."
        )
        try:
            from email_journal import log_imap_scan_end

            log_imap_scan_end(len(messages))
        except Exception:
            pass
    finally:
        try:
            mail.logout()
        except Exception:
            pass
    return messages


# >>> OPIS FUNKCJI: funkcja normalize_imap_items
# Cel: ujednolicić listę wiadomości do krotek (uid, Message). Parametry: messages (list) — krotki lub same obiekty Message.
# Zwraca: list[(bytes, Message)] — dla samych Message uid = b"". Efekty uboczne/błędy: brak.
def normalize_imap_items(
    messages: list,
) -> list[tuple[bytes, email.message.Message]]:
    items: list[tuple[bytes, email.message.Message]] = []
    for item in messages or []:
        if isinstance(item, tuple) and len(item) >= 2:
            items.append((item[0], item[1]))
        else:
            items.append((b"", item))
    return items


# >>> OPIS FUNKCJI: funkcja mark_imap_messages_unread
# Cel: oznaczyć wiadomości w skrzynce jako nieprzeczytane (usunięcie flagi \\Seen). Parametry: logger; uids (list[bytes]).
# Zwraca: int — liczba pomyślnie oznaczonych (0 gdy pusta lista lub brak konfiguracji).
# Efekty uboczne: połączenie IMAP, STORE -FLAGS, logowanie. Błędy: wyjątki per wiadomość łapane (debug); logout w finally.
def mark_imap_messages_unread(logger: logging.Logger, uids: list[bytes]) -> int:
    """Oznacza wiadomości w Gmail jako nieprzeczytane (usuwa flagę \\Seen)."""
    if not uids:
        return 0
    user = get_gmail_user()
    password = get_gmail_app_password()
    imap_host = get_imap_host()
    if not (user and password and imap_host):
        logger.warning("Brak konfiguracji IMAP do oznaczenia wiadomości jako nieprzeczytane.")
        return 0
    mail = imaplib.IMAP4_SSL(imap_host)
    marked = 0
    try:
        mail.login(user, password)
        mail.select("INBOX")
        for uid in uids:
            try:
                typ, _ = mail.store(uid, "-FLAGS", "\\Seen")
                if typ == "OK":
                    marked += 1
            except Exception as e:
                logger.debug(f"IMAP store {uid}: {e}")
        logger.info(f"IMAP: oznaczono jako nieprzeczytane: {marked}/{len(uids)}")
    finally:
        try:
            mail.logout()
        except Exception:
            pass
    return marked


# >>> OPIS FUNKCJI: funkcja _imap_since_for_cache
# Cel: wyznaczyć datę początkową skanu IMAP. Parametry: cache (dict); config (ReplySyncConfig); full_inbox_scan (bool).
# Zwraca: datetime — przy pełnym skanie teraz minus imap_days_back; inaczej cache["email_sync_last_at"], a przy braku/błędzie
# — teraz minus imap_days_back. Efekty uboczne: brak. Błędy: ValueError daty łapany.
def _imap_since_for_cache(
    cache: dict, config: ReplySyncConfig, full_inbox_scan: bool
) -> datetime:
    if full_inbox_scan:
        return datetime.now() - timedelta(days=config.imap_days_back)
    since_raw = cache.get("email_sync_last_at")
    if since_raw:
        try:
            return datetime.fromisoformat(str(since_raw).replace("Z", ""))
        except ValueError:
            pass
    return datetime.now() - timedelta(days=config.imap_days_back)


# >>> OPIS FUNKCJI: funkcja sync_replies_from_messages
# Cel: przypisać odebrane maile do kontaktów w cache i zaktualizować dane odpowiedzi. Parametry: messages (list); cache (dict, mutowany);
# config (ReplySyncConfig); logger; since (datetime); force_refresh (keyword-only, bool) — przetwarzaj także starsze/już zapisane odpowiedzi.
# Zwraca: (updated: int, uids_mark_unread: list[bytes]) — liczba zaktualizowanych kontaktów i UID-y do oznaczenia jako nieprzeczytane.
# Efekty uboczne: naprawa błędnych przypisań, odczyt PDF/OCR, apply_reply_to_contact, wpisy do email_journal, przeliczenie call_needed,
# zapis cache["email_sync_last_at"]. Błędy: pojedyncze niepoprawne daty pomijane; błędy analizy odpowiedzi propagują się.
def sync_replies_from_messages(
    messages: list,
    cache: dict,
    config: ReplySyncConfig,
    logger: logging.Logger,
    since: datetime,
    *,
    force_refresh: bool = False,
) -> tuple[int, list[bytes]]:
    repair_misassigned_replies(cache, logger)
    by_email, by_domain = build_email_lookup(cache)
    contacts = cache.setdefault("contacts", {})
    claude_cache = cache.setdefault("claude_reply_extractions", {})
    if not claude_cache and isinstance(cache.get("gemini_reply_extractions"), dict):
        claude_cache.update(cache.get("gemini_reply_extractions") or {})
    updated = 0
    uids_mark_unread: list[bytes] = []
    our_email = normalize_email(get_gmail_user())
    campaign = config.campaign_id or ""

    for imap_uid, msg in normalize_imap_items(messages):
        msg_dt = parse_message_date(msg) or datetime.now()
        if msg_dt < since - timedelta(days=1):
            continue
        from_hdr = decode_mime_header(msg.get("From"))
        from_em = normalize_email(from_hdr)
        if not from_em or from_em == our_email:
            continue

        place_urls = resolve_place_urls(from_em, by_email, by_domain, cache)
        if not place_urls:
            continue

        subject = decode_mime_header(msg.get("Subject"))
        body = get_message_body(msg)
        pdf_text = ""
        pdf_source = ""
        for fname, payload in iter_pdf_attachments(msg):
            logger.info(f"PDF z maila: {fname}")
            pdf_text, pdf_source = extract_text_from_pdf_bytes(payload, logger)
            if pdf_text.strip():
                break

        place_url = pick_best_place_url_for_reply(cache, place_urls, msg_dt)
        if not place_url:
            continue
        contact = contacts.setdefault(place_url, {})
        sent_raw = contact.get("email_sent_at")
        if sent_raw:
            try:
                sent_at = datetime.fromisoformat(sent_raw.replace("Z", ""))
                if msg_dt < sent_at - timedelta(minutes=5):
                    continue
            except ValueError:
                pass
        if not force_refresh:
            prev_reply = contact.get("reply_at")
            if prev_reply:
                try:
                    if msg_dt <= datetime.fromisoformat(prev_reply.replace("Z", "")):
                        continue
                except ValueError:
                    pass

        apply_reply_to_contact(
            contact,
            reply_at=msg_dt,
            reply_from=from_em,
            reply_subject=subject,
            reply_status="",
            body_text=body,
            pdf_text=pdf_text,
            pdf_source=pdf_source,
            lang=config.lang,
            gemini_cache=claude_cache,
            matched_by="email",
        )
        company = (
            contact.get("company_name_clean")
            or contact.get("company_name")
            or from_em
        )
        reply_status = contact.get("reply_status") or ""
        logger.info(
            f"Mail od {from_em} → {company} ({reply_status}) — temat: {(subject or '')[:50]}"
        )
        try:
            from email_journal import log_mail_read

            log_mail_read(
                from_em,
                subject,
                matched=True,
                reply_status=reply_status,
                company=str(company),
                campaign=campaign,
            )
        except Exception:
            pass
        if imap_uid and contact.get("requires_intervention") and not is_user_marked_read(
            contact
        ):
            contact["imap_uid"] = (
                imap_uid.decode() if isinstance(imap_uid, bytes) else str(imap_uid)
            )
            uids_mark_unread.append(imap_uid)
        updated += 1

    for info in contacts.values():
        if isinstance(info, dict):
            if is_sent_status(info.get("email_status", "")):
                info["call_needed"] = compute_call_needed(info, config.no_reply_hours)
            if info.get("requires_intervention") and not is_user_marked_read(info):
                if not info.get("intervention_status"):
                    info["intervention_status"] = "nieodczytane"

    cache["email_sync_last_at"] = datetime.now().isoformat(timespec="seconds")
    try:
        from email_journal import log_sync_summary

        log_sync_summary(updated, campaign)
    except Exception:
        pass
    return updated, uids_mark_unread


# >>> OPIS FUNKCJI: funkcja sync_replies_to_cache
# Cel: pełna synchronizacja odpowiedzi (pobranie IMAP + przypisanie + opcjonalne oznaczenie jako nieprzeczytane). Parametry: cache (dict);
# config (ReplySyncConfig); logger; full_inbox_scan (False); prefetched_messages (list|None) — gotowe wiadomości; force_refresh (False);
# mark_gmail_unread (True). Zwraca: int — liczba zaktualizowanych kontaktów. Efekty uboczne: IMAP, modyfikacja cache.
# Błędy: wyjątki z fetch_imap_messages/sync_replies_from_messages propagują się.
def sync_replies_to_cache(
    cache: dict,
    config: ReplySyncConfig,
    logger: logging.Logger,
    *,
    full_inbox_scan: bool = False,
    prefetched_messages: list | None = None,
    force_refresh: bool = False,
    mark_gmail_unread: bool = True,
) -> int:
    since = _imap_since_for_cache(cache, config, full_inbox_scan)
    if prefetched_messages is None:
        prefetched_messages = fetch_imap_messages(logger, since)
    updated, uids = sync_replies_from_messages(
        prefetched_messages, cache, config, logger, since, force_refresh=force_refresh
    )
    if mark_gmail_unread and uids:
        mark_imap_messages_unread(logger, uids)
    return updated


# >>> OPIS FUNKCJI: funkcja get_all_campaign_presets
# Cel: zwrócić zakodowane presety wszystkich kampanii (PL, DE, CH): ścieżki cache i xlsx, język, campaign_id, arkusze.
# Parametry: base_dir (Path) — korzeń projektu. Zwraca: dict[str, dict] — klucze m.in. szczecin, warszawa, transport, saalfeld_*, kampania CH.
# Efekty uboczne: leniwy import project_config.switzerland_wyniki_dir; nie tworzy plików. Uwaga: to legacy GUI/Kanbud — nie obejmuje kampanii PL FAS.
# Błędy: ImportError, gdy project_config niedostępny.
def get_all_campaign_presets(base_dir: Path) -> dict[str, dict]:
    """Wszystkie kampanie PL + DE + CH (cache + xlsx)."""
    from project_config import switzerland_wyniki_dir

    base = Path(base_dir)
    ch_dir = switzerland_wyniki_dir()
    presets = {
        "szczecin": {
            "cache": base / "Wyniki_Szczecin" / "szczecin_piasek_cache.json",
            "xlsx": base / "Wyniki_Szczecin" / "szczecin_piasek_kontakte.xlsx",
            "lang": "pl",
            "campaign_id": "sand_szczecin",
            "sheets": ("Kontakte", "Wojewodztwa"),
            "main_sheets": ("Kontakte",),
        },
        "warszawa": {
            "cache": base / "Wyniki_Warszawa" / "warszawa_piasek_cache.json",
            "xlsx": base / "Wyniki_Warszawa" / "warszawa_piasek_kontakte.xlsx",
            "lang": "pl",
            "campaign_id": "sand_warszawa",
            "sheets": ("Kontakte", "Wojewodztwa"),
            "main_sheets": ("Kontakte",),
        },
        "transport": {
            "cache": base / "Wyniki_Transport_PL" / "poland_transport_cache.json",
            "xlsx": base / "Wyniki_Transport_PL" / "poland_transport_firmy.xlsx",
            "lang": "pl",
            "campaign_id": "transport_pl",
            "sheets": ("Kontakty", "Baza firm", "Wojewodztwa"),
            "main_sheets": ("Kontakty", "Baza firm"),
        },
        "saalfeld_sand": {
            "cache": base / "Wyniki_Saalfeld" / "saalfeld_sand_kies_cache.json",
            "xlsx": base / "Wyniki_Saalfeld" / "saalfeld_sand_kies_kontakte.xlsx",
            "lang": "de",
            "campaign_id": "sand_saalfeld_de",
            "sheets": ("Kontakte", "Bundeslaender"),
            "main_sheets": ("Kontakte",),
        },
        "saalfeld_beton": {
            "cache": base / "Wyniki_Saalfeld_Beton" / "saalfeld_betonwerk_cache.json",
            "xlsx": base / "Wyniki_Saalfeld_Beton" / "saalfeld_betonwerk_kontakte.xlsx",
            "lang": "de",
            "campaign_id": "beton_saalfeld_de",
            "sheets": ("Kontakte", "Bundeslaender"),
            "main_sheets": ("Kontakte",),
        },
        "saalfeld_baucontainer": {
            "cache": base / "Wyniki_Saalfeld_Baucontainer" / "saalfeld_baucontainer_cache.json",
            "xlsx": base / "Wyniki_Saalfeld_Baucontainer" / "saalfeld_baucontainer_kontakte.xlsx",
            "lang": "de",
            "campaign_id": "baucontainer_saalfeld_de",
            "sheets": ("Kontakte", "Bundeslaender"),
            "main_sheets": ("Kontakte",),
        },
        "saalfeld_radlader": {
            "cache": base / "Wyniki_Saalfeld_Radlader" / "saalfeld_radlader_cache.json",
            "xlsx": base / "Wyniki_Saalfeld_Radlader" / "saalfeld_radlader_kontakte.xlsx",
            "lang": "de",
            "campaign_id": "radlader_saalfeld_de",
            "sheets": ("Kontakte", "Bundeslaender"),
            "main_sheets": ("Kontakte",),
        },
    }
    ch_presets = {
        "switzerland_sand": {
            "cache": ch_dir / "switzerland_sand_gravel_cache.json",
            "xlsx": ch_dir / "switzerland_sand_gravel_contacts.xlsx",
            "lang": "de",
            "campaign_id": "sand_switzerland_ch",
            "sheets": ("Kontakte", "Kanton"),
            "main_sheets": ("Kontakte",),
        },
        "switzerland_hotels": {
            "cache": ch_dir / "switzerland_hotels_cache.json",
            "xlsx": ch_dir / "switzerland_hotels_contacts.xlsx",
            "lang": "de",
            "campaign_id": "hotels_switzerland_ch",
            "sheets": ("Kontakte",),
            "main_sheets": ("Kontakte",),
        },
    }
    for key, preset in ch_presets.items():
        if preset["cache"].is_file() or preset["xlsx"].is_file():
            presets[key] = preset
    return presets


# >>> OPIS FUNKCJI: funkcja preset_to_config
# Cel: zamienić preset kampanii na ReplySyncConfig. Parametry: preset (dict); no_reply_hours (float); imap_days (int).
# Zwraca: ReplySyncConfig (cache_path, xlsx_path, lang, campaign_id, no_reply_hours, imap_days_back, main_sheet_names).
# Efekty uboczne: brak. Błędy: KeyError, gdy preset nie ma cache/xlsx.
def preset_to_config(preset: dict, no_reply_hours: float, imap_days: int) -> ReplySyncConfig:
    return ReplySyncConfig(
        cache_path=Path(preset["cache"]),
        xlsx_path=Path(preset["xlsx"]),
        lang=preset.get("lang", "pl"),
        campaign_id=preset.get("campaign_id", ""),
        no_reply_hours=no_reply_hours,
        imap_days_back=imap_days,
        main_sheet_names=tuple(preset.get("main_sheets", preset.get("sheets", ("Kontakte",)))),
    )


# >>> OPIS FUNKCJI: funkcja sanitize_sender_name
# Cel: oczyścić nazwę nadawcy z nowych linii. Parametry: name (str). Zwraca: str — pojedyncze spacje. Efekty uboczne/błędy: brak.
def sanitize_sender_name(name: str) -> str:
    return " ".join((name or "").replace("\n", " ").split()).strip()


# >>> OPIS FUNKCJI: funkcja send_email_gmail
# Cel: wysłać przypomnienie przez wspólny transport SMTP (wrapper zgodności). Parametry: to_email, subject, body (str); logger;
# mail_type (keyword-only, "wiadomość"); campaign (keyword-only). Zwraca: (ok, info) — przy sukcesie info = "reminder_sent", inaczej komunikat błędu.
# Efekty uboczne: ustawia MAIL_SENDER_NAME z GMAIL_SENDER_NAME (setdefault), wysyłka przez mail_transport.send_smtp_email (tytuł i treść po sanitizacji).
# Błędy: błędy wysyłki zwracane jako (False, tekst) przez send_smtp_email.
def send_email_gmail(
    to_email: str,
    subject: str,
    body: str,
    logger: logging.Logger,
    *,
    mail_type: str = "wiadomość",
    campaign: str = "",
) -> tuple[bool, str]:
    sender_name = sanitize_sender_name(get_env_value(ENV_GMAIL_SENDER_NAME))
    if sender_name and not get_env_value("MAIL_SENDER_NAME"):
        try:
            import os

            os.environ.setdefault("MAIL_SENDER_NAME", sender_name)
        except Exception:
            pass
    ok, info = send_smtp_email(
        to_email,
        sanitize_special_text(subject),
        sanitize_special_text(body),
        logger,
        mail_type=mail_type,
        campaign=campaign,
    )
    return ok, ("reminder_sent" if ok else info)


# >>> OPIS FUNKCJI: funkcja _parse_sent_at
# Cel: odczytać datę wysłania zapytania. Parametry: contact (dict). Zwraca: datetime|None z email_sent_at (ISO, "Z" usuwane); None dla braku/błędu.
# Efekty uboczne: brak. Błędy: ValueError łapany.
def _parse_sent_at(contact: dict) -> datetime | None:
    raw = contact.get("email_sent_at") or ""
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", ""))
    except ValueError:
        return None


# >>> OPIS FUNKCJI: funkcja _parse_dt
# Cel: sparsować tekst ISO do datetime. Parametry: raw (str|None). Zwraca: datetime|None (None dla pustego/niepoprawnego).
# Efekty uboczne: brak. Błędy: ValueError łapany.
def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", ""))
    except ValueError:
        return None


# >>> OPIS FUNKCJI: funkcja reminder_count
# Cel: ile przypomnień wysłano (0–2). Parametry: contact (dict). Zwraca: int — z pola reminder_count (obcięte do 0..MAX_REMINDERS_PER_CONTACT),
# a gdy brak: 2 przy reminder_2_sent_at, 1 przy reminder_sent_at, inaczej 0. Efekty uboczne: brak. Błędy: niepoprawna liczba ignorowana.
def reminder_count(contact: dict) -> int:
    """Ile przypomnień już wysłano (0–2)."""
    raw = contact.get("reminder_count")
    if raw is not None and str(raw).strip() != "":
        try:
            return max(0, min(int(raw), MAX_REMINDERS_PER_CONTACT))
        except (TypeError, ValueError):
            pass
    if contact.get("reminder_2_sent_at"):
        return 2
    if contact.get("reminder_sent_at"):
        return 1
    return 0


# >>> OPIS FUNKCJI: funkcja get_pending_reminder_number
# Cel: ustalić, które przypomnienie jest należne. Parametry: contact (dict); first_after_hours, second_after_hours (keyword-only, float|None;
# domyślnie 3 h po zapytaniu i 2 h po pierwszym przypomnieniu). Zwraca: int|None — 1 lub 2; None, gdy kontakt ma jakąkolwiek odpowiedź,
# brak email_target, osiągnięto limit 2, status nie jest "sent" (dla pierwszego) lub nie minął wymagany czas. Efekty uboczne/błędy: brak.
def get_pending_reminder_number(
    contact: dict,
    *,
    first_after_hours: float | None = None,
    second_after_hours: float | None = None,
) -> int | None:
    """
    1 = pierwsze przypomnienie (min. 3 h po zapytaniu),
    2 = drugie (min. 2 h po pierwszym), max 2 łącznie na email_target.
  """
    if first_after_hours is None:
        first_after_hours = REMINDER_1_HOURS_AFTER_SENT
    if second_after_hours is None:
        second_after_hours = REMINDER_2_HOURS_AFTER_FIRST

    if contact_has_any_reply(contact):
        return None
    if not (contact.get("email_target") or "").strip():
        return None

    count = reminder_count(contact)
    if count >= MAX_REMINDERS_PER_CONTACT:
        return None

    now = datetime.now()

    if count == 0:
        if str(contact.get("email_status") or "").strip().lower() != "sent":
            return None
        sent_at = _parse_sent_at(contact)
        if not sent_at:
            return None
        if now - sent_at < timedelta(hours=float(first_after_hours)):
            return None
        return 1

    if count == 1:
        first_at = _parse_dt(contact.get("reminder_sent_at"))
        if not first_at:
            return None
        if now - first_at < timedelta(hours=float(second_after_hours)):
            return None
        return 2

    return None


# >>> OPIS FUNKCJI: funkcja needs_reminder
# Cel: czy wysłać kolejne przypomnienie. Parametry: contact (dict); min_hours (float|None, domyślnie DEFAULT_REMINDER_MIN_HOURS).
# Zwraca: bool (get_pending_reminder_number is not None). Efekty uboczne/błędy: brak.
def needs_reminder(contact: dict, min_hours: float | None = None) -> bool:
    """True jeśli należy wysłać kolejne przypomnienie (1. lub 2.)."""
    if min_hours is None:
        min_hours = DEFAULT_REMINDER_MIN_HOURS
    pending = get_pending_reminder_number(contact, first_after_hours=min_hours)
    return pending is not None


# >>> OPIS FUNKCJI: funkcja mark_reminder_sent
# Cel: zapisać wysłanie przypomnienia nr 1 lub 2. Parametry: contact (dict, mutowany); which (int). Zwraca: None.
# Efekty uboczne: ustawia reminder_sent_at/reminder_2_sent_at, reminder_count, reminder_status (sent_1/sent_2) i email_status
# (reminder_sent/reminders_complete). Błędy: ValueError("which must be 1 or 2") dla innych wartości.
def mark_reminder_sent(contact: dict, which: int) -> None:
    """Zapisuje wysłanie przypomnienia 1 lub 2 (nie więcej niż 2 łącznie)."""
    which = int(which)
    if which not in (1, 2):
        raise ValueError("which must be 1 or 2")
    now = datetime.now().isoformat(timespec="seconds")
    if which == 1:
        contact["reminder_sent_at"] = now
        contact["reminder_count"] = 1
        contact["reminder_status"] = "sent_1"
        contact["email_status"] = "reminder_sent"
    else:
        contact["reminder_2_sent_at"] = now
        contact["reminder_count"] = 2
        contact["reminder_status"] = "sent_2"
        contact["email_status"] = "reminders_complete"


SIGNATURE_START_PATTERNS = (
    r"(?i)^z\s+poważaniem",
    r"(?i)^z\s+powazaniem",
    r"(?i)^pozdrawiam\b",
    r"(?i)^mit\s+freundlichen\s+gr",
    r"(?i)^freundliche\s+gr",
    r"(?i)^beste\s+gr",
    r"(?i)^viele\s+gr",
)


# >>> OPIS FUNKCJI: funkcja get_original_email_body
# Cel: pobrać treść pierwszego wysłanego maila (do stopki i cytatu). Parametry: contact (dict). Zwraca: str — email_body_sent albo email_body, "" gdy brak.
# Efekty uboczne/błędy: brak.
def get_original_email_body(contact: dict) -> str:
    """Treść pierwszego wysłanego maila (do stopki i cytatu)."""
    for key in ("email_body_sent", "email_body"):
        raw = (contact.get(key) or "").strip()
        if raw:
            return raw
    return ""


# >>> OPIS FUNKCJI: funkcja split_body_and_signature
# Cel: rozdzielić treść i stopkę maila. Parametry: body (str). Zwraca: (treść_główna, stopka) — podział przy pierwszej linii pasującej
# do SIGNATURE_START_PATTERNS; bez dopasowania (treść, ""). Efekty uboczne/błędy: brak.
def split_body_and_signature(body: str) -> tuple[str, str]:
    """Rozdziela treść główną i stopkę (od linii z pozdrowieniem)."""
    text = (body or "").strip()
    if not text:
        return "", ""
    lines = text.splitlines()
    sig_idx: int | None = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        for pat in SIGNATURE_START_PATTERNS:
            if re.match(pat, stripped):
                sig_idx = i
                break
        if sig_idx is not None:
            break
    if sig_idx is None:
        return text, ""
    main = "\n".join(lines[:sig_idx]).strip()
    signature = "\n".join(lines[sig_idx:]).strip()
    return main, signature


# >>> OPIS FUNKCJI: funkcja _format_sent_datetime
# Cel: sformatować datę wysłania do "YYYY-MM-DD HH:MM". Parametry: sent_raw (str). Zwraca: str — "" dla pustego; dla niepoprawnej daty
# pierwsze 16 znaków z "T" zamienionym na spację. Efekty uboczne: brak. Błędy: ValueError łapany.
def _format_sent_datetime(sent_raw: str) -> str:
    if not sent_raw:
        return ""
    try:
        dt = datetime.fromisoformat(str(sent_raw).replace("Z", ""))
        return dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return sent_raw[:16].replace("T", " ")


# >>> OPIS FUNKCJI: funkcja _reply_subject
# Cel: zbudować temat przypomnienia z prefiksem "Re:". Parametry: original_subject (str); lang (str); company (str).
# Zwraca: str — oryginalny temat bez prefiksów Re:/Odp:/Aw: poprzedzony "Re: "; przy pustym temacie domyślny ("Re: Preisanfrage – firma" dla DE
# lub "Re: zapytanie ofertowe – firma"). Efekty uboczne/błędy: brak.
def _reply_subject(original_subject: str, lang: str, company: str) -> str:
    subj = (original_subject or "").strip()
    while subj:
        low = subj.lower()
        if low.startswith("re:"):
            subj = subj[3:].strip()
        elif low.startswith("odp:"):
            subj = subj[4:].strip()
        elif low.startswith("aw:"):
            subj = subj[3:].strip()
        else:
            break
    if subj:
        return f"Re: {subj}"
    if lang == "de":
        return f"Re: Preisanfrage – {company}"
    return f"Re: zapytanie ofertowe – {company}"


# >>> OPIS FUNKCJI: funkcja _is_mfg_signature_text
# Cel: wykryć stopkę dawnej firmy MFG w tekście. Parametry: text (str). Zwraca: bool — True, gdy zawiera znaczniki MFG (mfg modernerfliesenboden, mfg-fliesen…).
# Efekty uboczne/błędy: brak.
def _is_mfg_signature_text(text: str) -> bool:
    low = (text or "").lower()
    return any(
        x in low
        for x in (
            "mfg modernerfliesenboden",
            "mfg-fliesen",
            "mfg fliesen",
            "– mfg",
            "- mfg",
        )
    )


# >>> OPIS FUNKCJI: funkcja normalize_signature_for_pl
# Cel: dopasować stopkę przypomnień dla firm PL (stopka Kanbud, nie MFG). Parametry: signature (str).
# Zwraca: str — SIGNATURE_PL, gdy brak stopki lub jest MFG bez Kanbud; stopka bez zmian, gdy zawiera "kanbud"; w pozostałych przypadkach
# linie MFG są podmieniane na dane Kanbud. Efekty uboczne/błędy: brak. Uwaga: dane kontaktowe są zakodowane na stałe (legacy).
def normalize_signature_for_pl(signature: str) -> str:
    """Przypomnienia do firm PL — stopka Kanbud, nie MFG."""
    sig = (signature or "").strip()
    if not sig or _is_mfg_signature_text(sig):
        return SIGNATURE_PL
    if "kanbud" in sig.lower():
        return sig
    # Zamiana linii firmowej MFG na Kanbud, zachowaj resztę jeśli sensowna
    lines = sig.splitlines()
    out: list[str] = []
    for line in lines:
        if _is_mfg_signature_text(line):
            if "Kanbud" not in "\n".join(out):
                out.extend(["Maksym Swinczak", "Kanbud Sp. z o.o.", "tel. +49 1522 3655 399"])
            continue
        if "mfg-fliesen" in line.lower() or line.strip().lower().startswith("www:"):
            continue
        out.append(line)
    merged = "\n".join(out).strip()
    return merged if merged and "kanbud" in merged.lower() else SIGNATURE_PL


# >>> OPIS FUNKCJI: funkcja _reminder_from_line
# Cel: wiersz "Od/Von" w cytowanym poprzednim mailu. Parametry: lang (str). Zwraca: str — dla DE "Nazwa <adres>" (z GMAIL_SENDER_NAME);
# dla PL "Maksym Swinczak, Kanbud Sp. z o.o. <adres>" (lub bez adresu). Efekty uboczne: odczyt env. Błędy: brak.
def _reminder_from_line(lang: str) -> str:
    sender = get_gmail_user() or get_env_value(ENV_GMAIL_USER) or ""
    if lang == "de":
        sender_name = sanitize_sender_name(get_env_value(ENV_GMAIL_SENDER_NAME))
        if sender_name and sender:
            return f"{sender_name} <{sender}>"
        return sender or sender_name or ""
    # PL: zawsze Kanbud w nagłówku cytatu (nie nazwa nadawcy z Gmail/MFG)
    if sender:
        return f"Maksym Swinczak, Kanbud Sp. z o.o. <{sender}>"
    return "Maksym Swinczak, Kanbud Sp. z o.o."


# >>> OPIS FUNKCJI: funkcja format_quoted_previous_email
# Cel: zbudować blok cytatu poprzedniego maila (nagłówek + treść z prefiksem "> "). Parametry: original_body, original_subject, sent_at_raw (str);
# lang (str, "de" → niemieckie etykiety, inaczej polskie). Zwraca: str — "" gdy brak oryginalnej treści. Efekty uboczne/błędy: brak.
def format_quoted_previous_email(
    original_body: str,
    original_subject: str,
    sent_at_raw: str,
    lang: str,
) -> str:
    """Blok historii poprzedniego maila (jak w odpowiedzi w wątku)."""
    if not (original_body or "").strip():
        return ""
    from_line = _reminder_from_line(lang)
    sent_fmt = _format_sent_datetime(sent_at_raw)

    if lang == "de":
        header = "--- Ursprüngliche Nachricht ---\n"
        if sent_fmt:
            header += f"Datum: {sent_fmt}\n"
        header += f"Betreff: {original_subject or '(ohne Betreff)'}\n"
        if from_line:
            header += f"Von: {from_line}\n"
    else:
        header = "--- Poprzednia wiadomość ---\n"
        if sent_fmt:
            header += f"Data: {sent_fmt}\n"
        header += f"Temat: {original_subject or '(brak tematu)'}\n"
        if from_line:
            header += f"Od: {from_line}\n"

    quoted = "\n".join(
        f"> {line}" if line.strip() else ">" for line in original_body.splitlines()
    )
    return f"{header}\n{quoted}"


# >>> OPIS FUNKCJI: funkcja build_reminder_email
# Cel: zbudować temat i treść przypomnienia (1. lub 2.) z cytatem pierwotnej wiadomości. Parametry: contact (dict); lang (str, "pl"/"de");
# reminder_number (keyword-only, int, 1) — >= 2 oznacza ponaglenie. Zwraca: (subject, body) — wstęp w języku, stopka z oryginału
# (PL: znormalizowana; DE: SIGNATURE_DE gdy brak) oraz cytat. Efekty uboczne/błędy: brak.
def build_reminder_email(
    contact: dict, lang: str, *, reminder_number: int = 1
) -> tuple[str, str]:
    company = (
        contact.get("company_name_clean")
        or contact.get("company_name")
        or contact.get("nazwa")
        or "Firma"
    ).strip()
    orig_subj = (contact.get("email_subject_sent") or contact.get("email_subject") or "").strip()
    orig_body = get_original_email_body(contact)
    sent_raw = contact.get("email_sent_at") or ""
    sent_date = sent_raw[:10] if sent_raw else ""

    _main, signature = split_body_and_signature(orig_body)
    if lang == "de":
        if not signature:
            signature = SIGNATURE_DE
    else:
        signature = normalize_signature_for_pl(signature)

    subject = _reply_subject(orig_subj, lang, company)

    if reminder_number >= 2:
        if lang == "de":
            intro = (
                f"Guten Tag,\n\n"
                f"ich möchte unsere Anfrage"
                f"{f' vom {sent_date}' if sent_date else ''} "
                f"noch einmal kurz ansprechen — bisher haben wir leider keine "
                f"Rückmeldung erhalten. Wären Sie so freundlich, uns zeitnah zu antworten?"
            )
        else:
            intro = (
                f"Dzień dobry,\n\n"
                f"ponownie przypominam o naszym zapytaniu ofertowym"
                f"{f' z dnia {sent_date}' if sent_date else ''} — "
                f"niestety nie otrzymaliśmy jeszcze odpowiedzi. "
                f"Będę wdzięczny za krótką informację lub wycenę."
            )
    elif lang == "de":
        intro = (
            f"Guten Tag,\n\n"
            f"ich erlaube mir, unsere Anfrage"
            f"{f' vom {sent_date}' if sent_date else ''} "
            f"freundlich in Erinnerung zu rufen. Könnten Sie uns bitte kurz "
            f"rückmelden oder ein unverbindliches Angebot zusenden?"
        )
    else:
        intro = (
            f"Dzień dobry,\n\n"
            f"uprzejmie przypominam o naszym zapytaniu ofertowym"
            f"{f' z dnia {sent_date}' if sent_date else ''}. "
            f"Będę wdzięczny za krótką informację zwrotną lub wycenę."
        )

    quoted = format_quoted_previous_email(orig_body, orig_subj, sent_raw, lang)
    parts = [intro, signature]
    if quoted:
        parts.append(quoted)
    body = "\n\n".join(p for p in parts if p.strip())
    return subject, body


BILINGUAL_REMINDER_SEPARATOR = "\n\n──────────\n\n"


# >>> OPIS FUNKCJI: funkcja backfill_email_sent_metadata
# Cel: uzupełnić brakujące pola po wysłaniu zapytania (stare wpisy cache). Parametry: cache (dict, mutowany); logger (Logger|None).
# Zwraca: int — liczba zaktualizowanych kontaktów. Efekty uboczne: kopiuje email_subject→email_subject_sent, email_body→email_body_sent,
# a przy znanym email_sent_at i treści ustawia email_status="sent" (poza statusami duplicate_/deferred_/suppressed_ i już wysłanymi); log info.
# Błędy: wpisy niebędące dict pomijane.
def backfill_email_sent_metadata(cache: dict, logger: logging.Logger | None = None) -> int:
    """Uzupełnia brakujące pola po wysłaniu zapytania (stare wpisy cache)."""
    updated = 0
    contacts = cache.get("contacts") or {}
    for _url, info in contacts.items():
        if not isinstance(info, dict):
            continue
        changed = False
        if not (info.get("email_subject_sent") or "").strip():
            subj = (info.get("email_subject") or "").strip()
            if subj:
                info["email_subject_sent"] = subj
                changed = True
        if not (info.get("email_body_sent") or "").strip():
            body = (info.get("email_body") or "").strip()
            if body:
                info["email_body_sent"] = body
                changed = True
        status = str(info.get("email_status") or "").strip().lower()
        has_sent_at = bool((info.get("email_sent_at") or "").strip())
        has_body = bool(
            (info.get("email_body_sent") or info.get("email_body") or "").strip()
        )
        if has_sent_at and has_body and status not in (
            "sent",
            "reminder_sent",
            "reminders_complete",
        ):
            if not status.startswith(("duplicate_", "deferred_", "suppressed_")):
                info["email_status"] = "sent"
                changed = True
        if changed:
            updated += 1
    if logger and updated:
        logger.info(
            "backfill_email_sent_metadata: zaktualizowano %s kontakt(ów)", updated
        )
    return updated


# >>> OPIS FUNKCJI: funkcja _reminder_intro_fr
# Cel: francuski wstęp przypomnienia (część dwujęzyczna DE/FR). Parametry: contact (dict); reminder_number (keyword-only, int).
# Zwraca: str — tekst grzecznościowy (inny dla 1. i 2. przypomnienia, z datą wysłania, jeśli znana). Efekty uboczne/błędy: brak.
def _reminder_intro_fr(contact: dict, *, reminder_number: int) -> str:
    sent_raw = contact.get("email_sent_at") or ""
    sent_date = sent_raw[:10] if sent_raw else ""
    date_bit = f" du {sent_date}" if sent_date else ""
    if reminder_number >= 2:
        return (
            f"Bonjour,\n\n"
            f"je me permets de relancer notre demande{date_bit} — "
            f"nous n'avons pas encore reçu de retour. "
            f"Pourriez-vous nous répondre prochainement ?"
        )
    return (
        f"Bonjour,\n\n"
        f"je me permets de relancer notre demande{date_bit}. "
        f"Pourriez-vous nous répondre ou nous envoyer une offre sans engagement ?"
    )


# >>> OPIS FUNKCJI: funkcja _build_bilingual_reminder_email_de_fr
# Cel: zbudować dwujęzyczne (DE + FR) przypomnienie. Parametry: contact (dict); reminder_number (keyword-only, int, 1).
# Zwraca: (subject, body) — treść DE, separator BILINGUAL_REMINDER_SEPARATOR, część FR, stopka i cytat. Efekty uboczne/błędy: brak.
def _build_bilingual_reminder_email_de_fr(
    contact: dict, *, reminder_number: int = 1
) -> tuple[str, str]:
    orig_subj = (
        contact.get("email_subject_sent") or contact.get("email_subject") or ""
    ).strip()
    orig_body = get_original_email_body(contact)
    sent_raw = contact.get("email_sent_at") or ""
    subject, body_de = build_reminder_email(contact, "de", reminder_number=reminder_number)
    intro_fr = _reminder_intro_fr(contact, reminder_number=reminder_number)
    quoted = format_quoted_previous_email(orig_body, orig_subj, sent_raw, "de")
    main_de, signature = split_body_and_signature(body_de)
    parts = [
        main_de,
        BILINGUAL_REMINDER_SEPARATOR,
        f"Madame, Monsieur,\n\n{intro_fr}",
        signature,
    ]
    if quoted:
        parts.append(quoted)
    body = "\n\n".join(p for p in parts if p and str(p).strip())
    return subject, body


# >>> OPIS FUNKCJI: funkcja build_reminder_email_for_preset
# Cel: wybrać wariant przypomnienia zależnie od presetu. Parametry: contact (dict); preset (dict) — lang oraz flaga bilingual_reminder_de_fr;
# reminder_number (keyword-only, int, 1). Zwraca: (subject, body) — dwujęzyczne DE/FR albo jednojęzyczne (build_reminder_email).
# Efekty uboczne/błędy: brak.
def build_reminder_email_for_preset(
    contact: dict,
    preset: dict,
    *,
    reminder_number: int = 1,
) -> tuple[str, str]:
    lang = str(preset.get("lang") or "pl").strip().lower()
    if preset.get("bilingual_reminder_de_fr"):
        return _build_bilingual_reminder_email_de_fr(
            contact, reminder_number=reminder_number
        )
    return build_reminder_email(contact, lang, reminder_number=reminder_number)


# >>> OPIS FUNKCJI: funkcja _latest_inbound_from_target
# Cel: znaleźć najnowszą wiadomość od adresata zapytania po dacie wysłania. Parametry: contact (dict); messages (list); our_email (str).
# Zwraca: (datetime, Message)|None — wiadomość od email_target (nie od nas), nie wcześniejsza niż wysyłka-5 min; None gdy brak. Efekty uboczne/błędy: brak.
def _latest_inbound_from_target(
    contact: dict,
    messages: list,
    our_email: str,
) -> tuple[datetime, email.message.Message] | None:
    """Najnowsza wiadomość od email_target po dacie wysłania zapytania."""
    target = normalize_email(contact.get("email_target") or "")
    if not target:
        return None
    sent_at = _parse_sent_at(contact)
    if not sent_at:
        return None
    best_dt: datetime | None = None
    best_msg: email.message.Message | None = None
    for _uid, msg in normalize_imap_items(messages):
        from_em = normalize_email(decode_mime_header(msg.get("From")))
        if not from_em or from_em != target or from_em == our_email:
            continue
        msg_dt = parse_message_date(msg) or datetime.now()
        if msg_dt < sent_at - timedelta(minutes=5):
            continue
        if best_dt is None or msg_dt > best_dt:
            best_dt = msg_dt
            best_msg = msg
    if best_dt is None or best_msg is None:
        return None
    return best_dt, best_msg


# >>> OPIS FUNKCJI: funkcja verify_contact_reply_from_imap
# Cel: sprawdzić w pobranych wiadomościach, czy kontakt odpisał, i zapisać odpowiedź. Parametry: contact (dict, mutowany); config (ReplySyncConfig);
# messages (list); logger (Logger|None); cache (dict|None) — cache analiz odpowiedzi. Zwraca: bool — True, gdy kontakt ma jakąkolwiek odpowiedź
# (nowo znalezioną lub wcześniejszą). Efekty uboczne: odczyt załączników PDF, apply_reply_to_contact, logowanie. Błędy: jak apply_reply_to_contact.
def verify_contact_reply_from_imap(
    contact: dict,
    config: ReplySyncConfig,
    messages: list,
    logger: logging.Logger | None = None,
    *,
    cache: dict | None = None,
) -> bool:
    """Sprawdza skrzynkę dla tego samego adresata (email_target). Zwraca True jeśli jest odpowiedź."""
    our_email = normalize_email(get_gmail_user())
    found = _latest_inbound_from_target(contact, messages, our_email)
    if not found:
        return contact_has_any_reply(contact)
    msg_dt, msg = found
    prev_reply = contact.get("reply_at")
    if prev_reply:
        try:
            prev_dt = datetime.fromisoformat(str(prev_reply).replace("Z", ""))
            if msg_dt <= prev_dt:
                return contact_has_any_reply(contact)
        except ValueError:
            pass
    subject = decode_mime_header(msg.get("Subject"))
    body = get_message_body(msg)
    pdf_text = ""
    pdf_source = ""
    for fname, payload in iter_pdf_attachments(msg):
        if logger:
            logger.info(f"Weryfikacja PDF ({contact.get('email_target')}): {fname}")
        pdf_text, pdf_source = extract_text_from_pdf_bytes(payload, logger)
        if pdf_text.strip():
            break
    claude_cache = None
    if cache is not None:
        claude_cache = cache.setdefault("claude_reply_extractions", {})
        if not claude_cache and isinstance(cache.get("gemini_reply_extractions"), dict):
            claude_cache.update(cache.get("gemini_reply_extractions") or {})
    apply_reply_to_contact(
        contact,
        reply_at=msg_dt,
        reply_from=normalize_email(decode_mime_header(msg.get("From"))),
        reply_subject=subject,
        reply_status="",
        body_text=body,
        pdf_text=pdf_text,
        pdf_source=pdf_source,
        lang=config.lang,
        gemini_cache=claude_cache,
        matched_by="email",
    )
    if logger:
        logger.info(
            f"Weryfikacja IMAP: odpowiedź od {contact.get('email_target')} "
            f"({contact.get('reply_status')})"
        )
    return True


# >>> OPIS FUNKCJI: funkcja verify_sent_contacts_from_imap
# Cel: zweryfikować odpowiedzi dla wszystkich kontaktów ze statusem "sent". Parametry: cache (dict); config; messages (list); logger.
# Zwraca: int — liczba kontaktów, które dopiero teraz uzyskały odpowiedź. Efekty uboczne: modyfikacja kontaktów (verify_contact_reply_from_imap). Błędy: propagowane.
def verify_sent_contacts_from_imap(
    cache: dict,
    config: ReplySyncConfig,
    messages: list,
    logger: logging.Logger | None = None,
) -> int:
    """Dla każdego kontaktu ze statusem sent — weryfikacja odpowiedzi od email_target."""
    updated = 0
    for _url, info in (cache.get("contacts") or {}).items():
        if not isinstance(info, dict):
            continue
        if not is_sent_status(info.get("email_status", "")):
            continue
        if not (info.get("email_target") or "").strip():
            continue
        had = contact_has_any_reply(info)
        verify_contact_reply_from_imap(info, config, messages, logger, cache=cache)
        if contact_has_any_reply(info) and not had:
            updated += 1
    return updated


# >>> OPIS FUNKCJI: funkcja iter_reminder_candidates
# Cel: zwrócić kontakty, którym należy wysłać przypomnienie. Parametry: cache (dict); min_hours (float|None); messages (list|None) i config
# (ReplySyncConfig|None) — gdy oba podane, najpierw weryfikacja odpowiedzi przez IMAP; logger.
# Zwraca: list[(place_url, contact, email_target)] spełniające needs_reminder. Efekty uboczne: możliwa modyfikacja kontaktów przy weryfikacji. Błędy: propagowane.
def iter_reminder_candidates(
    cache: dict,
    min_hours: float | None = None,
    *,
    messages: list | None = None,
    config: ReplySyncConfig | None = None,
    logger: logging.Logger | None = None,
) -> list[tuple[str, dict, str]]:
    """[(place_url, contact, email_target), ...] — po weryfikacji IMAP jeśli podano messages."""
    if min_hours is None:
        min_hours = DEFAULT_REMINDER_MIN_HOURS
    if messages is not None and config is not None:
        verify_sent_contacts_from_imap(cache, config, messages, logger)
    out = []
    contacts = cache.get("contacts") or {}
    for place_url, info in contacts.items():
        if not isinstance(info, dict):
            continue
        target = (info.get("email_target") or "").strip()
        if not target:
            continue
        if needs_reminder(info, min_hours):
            out.append((place_url, info, target))
    return out


# >>> OPIS FUNKCJI: funkcja sleep_between_reminder_sends
# Cel: losowa pauza między wysyłkami przypomnień (22–58 s) — ograniczenie ryzyka oznaczenia jako spam. Parametry: logger; to_email (str).
# Zwraca: None. Efekty uboczne: BLOKUJĄCY time.sleep, log info. Błędy: brak.
def sleep_between_reminder_sends(logger: logging.Logger, to_email: str) -> None:
    delay = round(random.uniform(REMINDER_SEND_DELAY_MIN, REMINDER_SEND_DELAY_MAX), 1)
    logger.info(f"Pauza {delay}s przed kolejnym mailem (po {to_email})")
    time.sleep(delay)


# >>> OPIS FUNKCJI: funkcja load_cache
# Cel: wczytać cache JSON kampanii. Parametry: path (Path). Zwraca: dict — zawartość pliku lub {"contacts": {}} gdy plik nie istnieje.
# Efekty uboczne: odczyt pliku UTF-8. Błędy: JSONDecodeError/OSError propagują się.
def load_cache(path: Path) -> dict:
    if not path.exists():
        return {"contacts": {}}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# >>> OPIS FUNKCJI: funkcja save_cache
# Cel: zapisać cache JSON. Parametry: path (Path); cache (dict). Zwraca: None. Efekty uboczne: tworzy katalog nadrzędny i nadpisuje plik
# (UTF-8, ensure_ascii=False, wcięcie 2) — zapis nieatomowy. Błędy: OSError/TypeError propagują się.
def save_cache(path: Path, cache: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


# >>> OPIS FUNKCJI: funkcja write_excel_with_reply_styles
# Cel: zapisać Excel z kolumnami CRM i kolorowaniem wierszy. Parametry: path (Path); sheets (dict[str, list[dict]]) — arkusz → wiersze;
# cache (dict); config (ReplySyncConfig); logger. Zwraca: None.
# Efekty uboczne: nadpisuje plik xlsx (pandas + openpyxl, importy leniwe); wiersze „nieznanych firm” są pomijane; kolumny odpowiedzi z kontaktu
# (dopasowanie po adresie e-mail) są dopisywane; kolor: czerwony — „zadzwoń”, pomarańczowy — nieodczytana interwencja, żółty — pytania.
# Błędy: brak pandas/openpyxl lub błąd zapisu propagują się.
def write_excel_with_reply_styles(
    path: Path,
    sheets: dict[str, list[dict]],
    cache: dict,
    config: ReplySyncConfig,
    logger: logging.Logger,
) -> None:
    import pandas as pd  # pyright: ignore[reportMissingImports]
    from openpyxl.styles import PatternFill  # pyright: ignore[reportMissingImports]

    path.parent.mkdir(parents=True, exist_ok=True)
    red_fill = PatternFill(start_color=RED_FILL_RGB, end_color=RED_FILL_RGB, fill_type="solid")
    yellow_fill = PatternFill(
        start_color=YELLOW_FILL_RGB, end_color=YELLOW_FILL_RGB, fill_type="solid"
    )
    orange_fill = PatternFill(
        start_color=ORANGE_FILL_RGB, end_color=ORANGE_FILL_RGB, fill_type="solid"
    )

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for sheet_name, rows in sheets.items():
            rows = filter_unknown_company_rows(rows or [])
            if not rows:
                pd.DataFrame().to_excel(writer, index=False, sheet_name=sheet_name)
                continue
            enriched = []
            for row in rows:
                r = normalize_row_dict(dict(row))
                em = (r.get(config.email_column) or r.get("E-mail") or "").strip()
                contact = find_contact_by_export_email(cache, em) if em else None
                if contact:
                    extra = export_columns_from_contact(contact, config.lang)
                    for k, v in extra.items():
                        if k not in r or not str(r.get(k, "")).strip():
                            r[k] = v
                        elif k in REPLY_EXPORT_COLUMNS:
                            r[k] = v
                    r["_call_needed"] = compute_call_needed(contact, config.no_reply_hours)
                    r["_intervention_unread"] = bool(
                        contact.get("requires_intervention")
                    ) and not is_user_marked_read(contact)
                    r["_reply_questions"] = (
                        contact.get("reply_status") == "replied_questions"
                    )
                else:
                    r["_call_needed"] = False
                    r["_intervention_unread"] = False
                    r["_reply_questions"] = False
                enriched.append(r)
            df = pd.DataFrame(enriched)
            meta_cols = [c for c in df.columns if c.startswith("_")]
            df_export = df.drop(columns=meta_cols, errors="ignore")
            df_export.to_excel(writer, index=False, sheet_name=sheet_name)
            ws = writer.sheets[sheet_name]
            call_flags = df["_call_needed"].tolist() if "_call_needed" in df.columns else []
            int_flags = (
                df["_intervention_unread"].tolist()
                if "_intervention_unread" in df.columns
                else []
            )
            q_flags = df["_reply_questions"].tolist() if "_reply_questions" in df.columns else []
            for row_idx, (call, intervention, quest) in enumerate(
                zip(call_flags, int_flags, q_flags), start=2
            ):
                fill = None
                if call:
                    fill = red_fill
                elif intervention:
                    fill = orange_fill
                elif quest:
                    fill = yellow_fill
                if fill:
                    for col_idx in range(1, ws.max_column + 1):
                        ws.cell(row=row_idx, column=col_idx).fill = fill

    logger.info(f"Zapisano Excel ze stylami: {path}")


# >>> OPIS FUNKCJI: funkcja merge_export_row
# Cel: wzbogacić wiersz eksportu o kolumny CRM z cache. Parametry: base (dict); cache (dict); email_value (str); lang (str, "pl").
# Zwraca: dict — kopia base z kolumnami z export_columns_from_contact, jeśli znaleziono kontakt. Efekty uboczne/błędy: brak.
def merge_export_row(base: dict, cache: dict, email_value: str, lang: str = "pl") -> dict:
    row = dict(base)
    contact = find_contact_by_export_email(cache, email_value)
    if contact:
        row.update(export_columns_from_contact(contact, lang))
    return row

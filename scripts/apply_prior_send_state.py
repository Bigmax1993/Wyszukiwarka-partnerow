# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Moduł (skrypt CLI): scripts/apply_prior_send_state — przeniesienie stanu wysyłek między plikami cache.
#
# CO ROBI: z cache poprzedniej wysyłki (--prior-cache) kopiuje do cache docelowego (--target-cache; domyślnie Wyniki/pl_spedycja_cache.json) informacje o wysłanych
#   mailach: ustawia email_status="sent" dla kontaktów pasujących po adresie, kluczu nazwy firmy lub domenie oraz scala liczniki/blokady
#   (email_suppression, email_sent_targets, email_daily, email_domain_daily). Cel: uniknąć podwójnych maili do tych samych firm po scaleniu cache tygodnia.
# ROLA W PIPELINE: krok pomocniczy przed ponowną wysyłką B2B (etap „optional B2B email”).
# ZALEŻNOŚCI: pl_fas_spedycja_scraper (scraper.CACHE_FILE, scraper.save_cache), stdlib argparse, json, logging, re, sys, pathlib.
# WEJŚCIE: dwa pliki cache JSON. WYJŚCIE: nadpisany cache docelowy, komunikat z liczbą oznaczonych kontaktów, kod 0.
# ============================================================
"""
Przenies status wysylek (sent, suppression, dzienne liczniki) z poprzedniego cache
do scalonego cache tygodnia — unika podwojnych maili do tych samych firm.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pl_fas_spedycja_scraper as scraper  # noqa: E402


# >>> OPIS FUNKCJI: funkcja _norm_name
# Cel: znormalizować nazwę firmy do porównań. Parametry: name (str). Zwraca: str — małe litery, tylko [a-z0-9] rozdzielone spacjami (znaki spoza ASCII są usuwane).
# Efekty uboczne/błędy: brak.
def _norm_name(name: str) -> str:
    """Normalizuj nazwę firmy do porównania (lowercase, alfanum)."""
    s = (name or "").lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# >>> OPIS FUNKCJI: funkcja _company_key
# Cel: wyliczyć klucz firmy z pól nazwy. Parametry: info (dict) — company_name_clean / company_name / company_name_raw. Zwraca: str — _norm_name, max 80 znaków ("" gdy brak nazwy).
# Efekty uboczne/błędy: brak.
def _company_key(info: dict) -> str:
    """Klucz firmy z pól company_name_* (max 80 znaków)."""
    name = (
        info.get("company_name_clean")
        or info.get("company_name")
        or info.get("company_name_raw")
        or ""
    )
    return _norm_name(name)[:80]


# >>> OPIS FUNKCJI: funkcja _domain_from_info
# Cel: wyłuskać domenę firmy. Parametry: info (dict); place_url (str). Zwraca: str — host z place_url lub official_website (bez schematu, ścieżki i "www."); "" dla pustego URL oraz dla northdata.de.
# Efekty uboczne/błędy: brak.
def _domain_from_info(info: dict, place_url: str = "") -> str:
    """Host domeny z URL/www (bez www.; pomija northdata)."""
    url = (place_url or info.get("official_website") or "").strip().lower()
    if not url:
        return ""
    host = re.sub(r"^https?://", "", url).split("/")[0]
    if host.startswith("www."):
        host = host[4:]
    if host in ("northdata.de", "www.northdata.de"):
        return ""
    return host


# >>> OPIS FUNKCJI: funkcja merge_sent_state
# Cel: przenieść status „wysłano” z cache źródłowego do docelowego. Parametry: target (dict, mutowany); source (dict); logger.
# Zwraca: int — liczba kontaktów w target oznaczonych jako sent (dopasowanie po adresie email_target, kluczu nazwy lub domenie z wysłanych w source).
# Efekty uboczne: nadpisuje email_status="sent" w target, scala sekcje email_suppression/email_sent_targets/email_daily/email_domain_daily (wartości ze source nadpisują), log info.
# Błędy: gdy contacts nie są dict — zwraca 0; brak własnych wyjątków.
def merge_sent_state(target: dict, source: dict, logger: logging.Logger) -> int:
    """Zwraca liczbe kontaktow oznaczonych jako sent w target."""
    src_contacts = source.get("contacts") or {}
    tgt_contacts = target.setdefault("contacts", {})
    if not isinstance(src_contacts, dict) or not isinstance(tgt_contacts, dict):
        return 0

    sent_emails: set[str] = set()
    sent_keys: set[str] = set()
    sent_domains: set[str] = set()
    for _url, info in src_contacts.items():
        if not isinstance(info, dict):
            continue
        if (info.get("email_status") or "").strip().lower() != "sent":
            continue
        em = (info.get("email_target") or "").strip().lower()
        if em:
            sent_emails.add(em)
        key = _company_key(info)
        if key:
            sent_keys.add(key)
        dom = _domain_from_info(info, _url)
        if dom:
            sent_domains.add(dom)

    for bucket in ("email_suppression", "email_sent_targets", "email_daily", "email_domain_daily"):
        src_val = source.get(bucket)
        if isinstance(src_val, dict) and src_val:
            merged = target.setdefault(bucket, {})
            if isinstance(merged, dict):
                for k, v in src_val.items():
                    merged[k] = v

    marked = 0
    for place_url, info in tgt_contacts.items():
        if not isinstance(info, dict):
            continue
        em = (info.get("email_target") or "").strip().lower()
        key = _company_key(info)
        dom = _domain_from_info(info, place_url)
        if em and em in sent_emails:
            info["email_status"] = "sent"
            marked += 1
            continue
        if key and key in sent_keys:
            info["email_status"] = "sent"
            marked += 1
            continue
        if dom and dom in sent_domains:
            info["email_status"] = "sent"
            marked += 1

    if marked:
        logger.info("Oznaczono %s kontaktow jako sent (z poprzedniego cache)", marked)
    return marked


# >>> OPIS FUNKCJI: funkcja main
# Cel: CLI przenoszące stan wysyłek między plikami cache. Parametry: brak (argparse: --prior-cache wymagany, --target-cache). Zwraca: int 0.
# Efekty uboczne: odczyt obu plików JSON, zapis target przez scraper.save_cache, komunikat na stdout. Błędy: brak pliku/niepoprawny JSON propagują się wyjątkiem.
def main() -> int:
    """CLI: przenieś status sent/suppression z prior cache do target cache."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--prior-cache",
        type=Path,
        required=True,
        help="Sciezka do cache z ostatniej wysylki (pl-spedycja-wyniki-tue)",
    )
    parser.add_argument(
        "--target-cache",
        type=Path,
        default=scraper.CACHE_FILE,
        help="Cache docelowy (domyslnie Wyniki/pl_spedycja_cache.json)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger("apply_prior_send")

    with open(args.prior_cache, encoding="utf-8") as f:
        source = json.load(f)
    with open(args.target_cache, encoding="utf-8") as f:
        target = json.load(f)

    n = merge_sent_state(target, source, logger)
    scraper.save_cache(target, logger)
    print(f"Zapisano cache: {args.target_cache} (sent przeniesione: {n})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

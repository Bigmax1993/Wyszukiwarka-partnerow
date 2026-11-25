# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Moduł (skrypt CLI): scripts/analyze_mail_jobs — podgląd firm kwalifikujących się do wysyłki z aktualnego cache.
#
# CO ROBI: buduje listę „mail jobs” z cache (scraper.build_email_jobs_from_cache_json) i wypisuje ją oraz wszystkie kontakty z e-mailem wraz ze statusem i flagą weryfikacji.
# ROLA W PIPELINE: diagnostyka przed etapem wysyłki B2B (nic nie wysyła i nie zapisuje).
# ZALEŻNOŚCI: pl_fas_spedycja_scraper (jako scraper), stdlib argparse, logging, sys, pathlib. WEJŚCIE: opcja --force-resend. WYJŚCIE: wydruk na stdout, kod 0.
# ============================================================
"""Podglad firm kwalifikujacych sie do wysylki z aktualnego cache."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pl_fas_spedycja_scraper as scraper  # noqa: E402


# >>> OPIS FUNKCJI: funkcja main
# Cel: wypisać podgląd kwalifikacji do wysyłki. Parametry: brak (argparse: --force-resend). Zwraca: int 0.
# Efekty uboczne: odczyt cache, wydruk liczby contacts i jobów oraz listy kontaktów z e-mailem (status, rv=T/F dla retail_verified). Nie modyfikuje cache.
# Błędy: wyjątki z odczytu cache propagują się.
def main() -> int:
    """CLI: wypisz joby mailowe z cache (podgląd kwalifikacji do wysyłki)."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-resend", action="store_true")
    args = parser.parse_args()

    logger = logging.getLogger("analyze_mail_jobs")
    jobs = scraper.build_email_jobs_from_cache_json(logger, force_resend=args.force_resend)
    cache = scraper.load_cache(logger)
    contacts = cache.get("contacts") or {}

    print(f"Contacts w cache: {len(contacts)}")
    print(f"Mail jobs gotowych do wysylki: {len(jobs)}")
    for job in jobs:
        print(
            f"  -> {job.get('email_target')} | "
            f"{(job.get('company_name') or '')[:55]}"
        )

    print("\nWszystkie kontakty z e-mailem:")
    for _url, info in sorted(
        contacts.items(),
        key=lambda x: ((x[1] or {}).get("company_name") or "").lower(),
    ):
        if not isinstance(info, dict):
            continue
        em = (info.get("email_target") or "").strip()
        if not em:
            continue
        st = (info.get("email_status") or "").strip()
        rv = "T" if info.get("retail_verified") else "F"
        name = (info.get("company_name") or "")[:45]
        print(f"  {em:38} {st:28} rv={rv} | {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

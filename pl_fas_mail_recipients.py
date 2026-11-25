# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Uzupełnienie opisu modułu pl_fas_mail_recipients (komentarz dodatkowy do docstringa).
#   Wejście: adres To oraz opcjonalny ciąg Cc z MAIL_CC; wyjście: list[str] adresów Cc.
#   Zależności: mail_transport.merge_mail_cc_recipients (import leniwy wewnątrz funkcji, aby brak
#   libs/ nie psuł importu modułu). Błędy są wyciszane (zwrot []), więc wysyłka nigdy nie pada
#   z powodu samego scalania Cc. Alias merge_mfg_campaign_cc wskazuje na tę samą funkcję.
# ============================================================
"""
Cc odbiorców kampanii PL FAS / spedycja.

=============================================================================
PO CO TEN MODUŁ
=============================================================================
Widoczna kopia (Cc) przy wysyłce zapytania:

  1. Zawsze ``FAS_OFFICE_CC_EMAIL`` (``svinchak1993@gmail.com``) —
     zamiast starego MFG ``office@mfg-fliesen.de`` (odpięte).
  2. Dodatkowo adresy z ``MAIL_CC`` w ``.env`` (opcjonalnie).

Merge przez ``mail_transport.merge_mail_cc_recipients`` (bez duplikatu
względem ``To:``).

Wywołujący: ``pl_fas_spedycja_scraper`` (ścieżka SMTP kontrahenta).
"""
from __future__ import annotations

# Biuro / kopia kampanii PL FAS (zastępuje office@mfg-fliesen.de).
FAS_OFFICE_CC_EMAIL = "svinchak1993@gmail.com"


def merge_fas_campaign_cc(to_email: str, extra_env_cc: str = "") -> list[str]:
    """
    Lista adresów Cc: ``FAS_OFFICE_CC_EMAIL`` + opcjonalne ``MAIL_CC``.

    Przebieg
    --------
    1. Złóż ``FAS_OFFICE_CC_EMAIL`` z ``extra_env_cc`` (zwykle ``MAIL_CC``).
    2. ``merge_mail_cc_recipients`` — dedupe, bez powtórzenia ``to_email``.
    3. Błąd importu / merge → ``[]``.

    Stare biuro MFG **nie** jest dodawane.
    """
    parts = [FAS_OFFICE_CC_EMAIL]
    extra = (extra_env_cc or "").strip()
    if extra:
        parts.append(extra)
    combined = ",".join(parts)
    try:
        from mail_transport import merge_mail_cc_recipients

        return merge_mail_cc_recipients(to_email, combined)
    except Exception:
        return []


# Alias nazwy legacy (importy / testy pod starą funkcją).
merge_mfg_campaign_cc = merge_fas_campaign_cc

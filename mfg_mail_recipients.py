# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Moduł: mfg_mail_recipients — SHIM legacy do pl_fas_mail_recipients.
#
# CO ROBI: reeksportuje FAS_OFFICE_CC_EMAIL, merge_fas_campaign_cc i alias merge_mfg_campaign_cc,
#   a stałą historyczną MFG_OFFICE_CC_EMAIL ustawia na adres FAS (NIE na dawne office@mfg-fliesen.de).
# ROLA W PIPELINE: ustalanie odbiorców Cc przy wysyłce zapytań do kontrahentów (obecnie wysyłka
#   jest wyłączona kill-switchem DISABLE_CONTRACTOR_EMAILS, ale kod pozostaje).
# ZALEŻNOŚCI: pl_fas_mail_recipients. Funkcji własnych brak.
# ============================================================
"""
Shim legacy: ``mfg_mail_recipients`` → ``pl_fas_mail_recipients``.

``office@mfg-fliesen.de`` odpięte. Cc biura = ``FAS_OFFICE_CC_EMAIL``
(``svinchak1993@gmail.com``).

Nowy kod::

  from pl_fas_mail_recipients import merge_fas_campaign_cc, FAS_OFFICE_CC_EMAIL
"""
from __future__ import annotations

from pl_fas_mail_recipients import (  # noqa: F401
    FAS_OFFICE_CC_EMAIL,
    merge_fas_campaign_cc,
    merge_mfg_campaign_cc,
)

# Legacy nazwa stałej — wskazuje na skrzynkę FAS, nie MFG.
MFG_OFFICE_CC_EMAIL = FAS_OFFICE_CC_EMAIL

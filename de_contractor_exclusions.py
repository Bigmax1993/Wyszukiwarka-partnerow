# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Moduł: de_contractor_exclusions — SHIM zgodności wstecznej.
#
# CO ROBI: re-eksportuje bloklistę kontrahentów z pl_fas_contractor_exclusions
#   (EXCLUDED_NAME_MARKERS, EXCLUDED_EMAIL_DOMAINS_EXACT, EXCLUDED_DOMAIN_FRAGMENTS,
#   is_excluded_kontrahent, contact_info_excluded), żeby stary import
#   `from de_contractor_exclusions import ...` nadal działał po adaptacji kampanii do PL FAS.
#
# ROLA W PIPELINE: filtr higieniczny („nie zbieraj / nie eksportuj / nie mailuj”) — logika w
#   pl_fas_contractor_exclusions.py.
# ZALEŻNOŚCI: pl_fas_contractor_exclusions. Funkcji własnych brak; nic nie zwraca poza reeksportami.
# ============================================================
"""
Shim legacy: ``de_contractor_exclusions`` → ``pl_fas_contractor_exclusions``.

Bloklista kontrahentów PL FAS (MFG/DE GU = higiena). Nowy kod::

  from pl_fas_contractor_exclusions import is_excluded_kontrahent
"""
from __future__ import annotations

from pl_fas_contractor_exclusions import *  # noqa: F403
from pl_fas_contractor_exclusions import (  # noqa: F401
    EXCLUDED_DOMAIN_FRAGMENTS,
    EXCLUDED_EMAIL_DOMAINS_EXACT,
    EXCLUDED_NAME_MARKERS,
    contact_info_excluded,
    is_excluded_kontrahent,
)

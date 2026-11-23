# -*- coding: utf-8 -*-
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

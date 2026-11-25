# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Moduł: mfg_gu_email_attachment — SHIM legacy do pl_fas_email_attachment.
#
# CO ROBI: zachowuje starą nazwę modułu (kampania MFG/GU) i przekierowuje wszystkie symbole
#   (ATTACHMENT_FILENAME, ATTACHMENT_EXTRA_FILENAME, ID/URL Drive, ensure_*/resolve_* — także aliasy
#   mfg) do pl_fas_email_attachment.
# ROLA W PIPELINE: tylko kompatybilność importów; załączniki do maili B2B obsługuje moduł docelowy.
# ZALEŻNOŚCI: pl_fas_email_attachment. Funkcji własnych brak.
# ============================================================
"""
Shim legacy: ``mfg_gu_email_attachment`` → ``pl_fas_email_attachment``.

Nowy kod::

  from pl_fas_email_attachment import ensure_fas_email_attachment
"""
from __future__ import annotations

from pl_fas_email_attachment import *  # noqa: F403
from pl_fas_email_attachment import (  # noqa: F401
    ATTACHMENT_EXTRA_FILENAME,
    ATTACHMENT_FILENAME,
    EMAIL_ATTACHMENT_DRIVE_FILE_ID,
    EMAIL_ATTACHMENT_DRIVE_URL,
    EMAIL_ATTACHMENT_EXTRA_DRIVE_FILE_ID,
    EMAIL_ATTACHMENT_EXTRA_DRIVE_URL,
    ensure_fas_email_attachment,
    ensure_fas_email_attachments,
    ensure_mfg_email_attachment,
    resolve_fas_email_attachment,
    resolve_mfg_email_attachment,
)

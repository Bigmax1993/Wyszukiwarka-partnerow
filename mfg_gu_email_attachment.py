# -*- coding: utf-8 -*-
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

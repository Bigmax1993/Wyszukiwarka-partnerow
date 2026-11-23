# -*- coding: utf-8 -*-
from __future__ import annotations

from fas_spedycja_inquiry_email_pl import (
    FAS_EMAIL_SUBJECT_PL,
    FAS_MUST_KEEP_RATE_LINE,
    FAS_PHONE,
    FAS_SENDER_NAME,
    FAS_WEBSITE,
    FIXED_FAS_INQUIRY_PL,
    build_fas_inquiry_fallback_pl,
)


def test_fas_draft_has_required_blocks():
    body = FIXED_FAS_INQUIRY_PL
    assert "Cześć" in body
    assert "Znam ten ból" in body
    assert FAS_MUST_KEEP_RATE_LINE in body
    assert FAS_SENDER_NAME in body
    assert FAS_WEBSITE in body
    assert FAS_PHONE in body
    assert "Maksym / Forwarding Assistant" in FAS_EMAIL_SUBJECT_PL


def test_fas_fallback_injects_company():
    body = build_fas_inquiry_fallback_pl("Trans Spedycja Sp. z o.o.")
    assert "Trans Spedycja Sp. z o.o." in body
    assert FAS_MUST_KEEP_RATE_LINE in body

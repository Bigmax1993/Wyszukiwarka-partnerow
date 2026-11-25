# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# MODUŁ TESTOWY: tests/unit/test_fas_spedycja_inquiry_email_pl.py
# CO ROBI: testy szablonu zapytania FAS (fas_spedycja_inquiry_email_pl): wymagane bloki i podstawienie nazwy firmy.
# ROLA W PIPELINE: chroni treść outreach (zdanie o stawce, podpis, www, telefon).
# ZALEŻNOŚCI: fas_spedycja_inquiry_email_pl (stałe i funkcja fallback).
# WEJŚCIE/WYJŚCIE: Moduł nie przyjmuje argumentów CLI; pytest/unittest odkrywa i uruchamia testy; nic nie zwraca (wynik = zielone/czerwone testy).
# ============================================================
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


# >>> OPIS FUNKCJI: funkcja test_fas_draft_has_required_blocks
# Test: szkic maila zawiera powitanie, 'Znam ten ból', zdanie o stawce, podpis, www i telefon; temat zaczyna się od 'Maksym / Forwarding Assistant'.
# Parametry: brak (funkcja pytest). Zwraca: None (wynik = przejście lub błąd testu).
# Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
def test_fas_draft_has_required_blocks():
    body = FIXED_FAS_INQUIRY_PL
    assert "Cześć" in body
    assert "Znam ten ból" in body
    assert FAS_MUST_KEEP_RATE_LINE in body
    assert FAS_SENDER_NAME in body
    assert FAS_WEBSITE in body
    assert FAS_PHONE in body
    assert "Maksym / Forwarding Assistant" in FAS_EMAIL_SUBJECT_PL


# >>> OPIS FUNKCJI: funkcja test_fas_fallback_injects_company
# Test: fallback wstawia nazwę firmy i zachowuje zdanie o stawce.
# Parametry: brak (funkcja pytest). Zwraca: None (wynik = przejście lub błąd testu).
# Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
def test_fas_fallback_injects_company():
    body = build_fas_inquiry_fallback_pl("Trans Spedycja Sp. z o.o.")
    assert "Trans Spedycja Sp. z o.o." in body
    assert FAS_MUST_KEEP_RATE_LINE in body

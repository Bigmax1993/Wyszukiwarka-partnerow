# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# MODUŁ TESTOWY: tests/unit/test_kill_switches.py
# CO ROBI: testy przełączników bezpieczeństwa (kill switches) w scraper_env: DISABLE_CONTRACTOR_EMAILS, DISABLE_GOOGLE_DRIVE, DISABLE_EXCEL_REPORT_EMAIL.
# ROLA W PIPELINE: gwarantuje domyślne bezpieczne zachowanie: maile B2B i Drive wyłączone, raport Excel włączony.
# ZALEŻNOŚCI: unittest, unittest.mock.patch.dict, scraper_env.
# WEJŚCIE/WYJŚCIE: Moduł nie przyjmuje argumentów CLI; pytest/unittest odkrywa i uruchamia testy; nic nie zwraca (wynik = zielone/czerwone testy).
# ============================================================
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
LIBS = ROOT / "libs"
for p in (str(LIBS), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import scraper_env  # noqa: E402


# >>> OPIS FUNKCJI: klasa KillSwitchFlagsTest
# Grupa testów: flagi kill-switch.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class KillSwitchFlagsTest(unittest.TestCase):
    # >>> OPIS FUNKCJI: funkcja KillSwitchFlagsTest.test_contractor_emails_disabled_by_default
    # Test: bez zmiennej env wysyłka do kontrahentów jest wyłączona.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: patch.dict na os.environ. Błędy: AssertionError przy niespełnionej asercji.
    def test_contractor_emails_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DISABLE_CONTRACTOR_EMAILS", None)
            self.assertTrue(scraper_env.is_contractor_emails_disabled())

    # >>> OPIS FUNKCJI: funkcja KillSwitchFlagsTest.test_contractor_emails_enabled_with_zero
    # Test: DISABLE_CONTRACTOR_EMAILS=0 włącza wysyłkę.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: patch.dict na os.environ. Błędy: AssertionError przy niespełnionej asercji.
    def test_contractor_emails_enabled_with_zero(self):
        with patch.dict(os.environ, {"DISABLE_CONTRACTOR_EMAILS": "0"}, clear=False):
            self.assertFalse(scraper_env.is_contractor_emails_disabled())

    # >>> OPIS FUNKCJI: funkcja KillSwitchFlagsTest.test_google_drive_disabled_by_default
    # Test: bez zmiennej Google Drive jest wyłączony.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: patch.dict na os.environ. Błędy: AssertionError przy niespełnionej asercji.
    def test_google_drive_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DISABLE_GOOGLE_DRIVE", None)
            self.assertTrue(scraper_env.is_google_drive_disabled())

    # >>> OPIS FUNKCJI: funkcja KillSwitchFlagsTest.test_google_drive_enabled_with_false
    # Test: DISABLE_GOOGLE_DRIVE=false włącza Drive.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: patch.dict na os.environ. Błędy: AssertionError przy niespełnionej asercji.
    def test_google_drive_enabled_with_false(self):
        with patch.dict(os.environ, {"DISABLE_GOOGLE_DRIVE": "false"}, clear=False):
            self.assertFalse(scraper_env.is_google_drive_disabled())

    # >>> OPIS FUNKCJI: funkcja KillSwitchFlagsTest.test_excel_report_enabled_by_default
    # Test: raport Excel mailem jest domyślnie włączony.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: patch.dict na os.environ. Błędy: AssertionError przy niespełnionej asercji.
    def test_excel_report_enabled_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DISABLE_EXCEL_REPORT_EMAIL", None)
            self.assertFalse(scraper_env.is_excel_report_email_disabled())

    # >>> OPIS FUNKCJI: funkcja KillSwitchFlagsTest.test_excel_report_disabled_with_one
    # Test: DISABLE_EXCEL_REPORT_EMAIL=1 wyłącza raport.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: patch.dict na os.environ. Błędy: AssertionError przy niespełnionej asercji.
    def test_excel_report_disabled_with_one(self):
        with patch.dict(os.environ, {"DISABLE_EXCEL_REPORT_EMAIL": "1"}, clear=False):
            self.assertTrue(scraper_env.is_excel_report_email_disabled())


if __name__ == "__main__":
    unittest.main()

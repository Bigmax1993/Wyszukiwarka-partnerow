# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# MODUŁ TESTOWY: tests/test_send_excel_gmail.py
# CO ROBI: testy skryptu wysyłki raportu Excel (domyślny odbiorca, temat i treść maila).
# ROLA W PIPELINE: chroni scripts/send_excel_gmail.py używany przez GitHub Actions.
# ZALEŻNOŚCI: unittest, unittest.mock, scripts.send_excel_gmail, scraper_env.
# WEJŚCIE/WYJŚCIE: Moduł nie przyjmuje argumentów CLI; pytest/unittest odkrywa i uruchamia testy; nic nie zwraca (wynik = zielone/czerwone testy).
# ============================================================
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import send_excel_gmail as mailer
from scraper_env import DEFAULT_EXCEL_REPORT_TO


# >>> OPIS FUNKCJI: klasa SendExcelGmailTest
# Grupa testów: temat, treść i odbiorca raportu.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class SendExcelGmailTest(unittest.TestCase):
    # >>> OPIS FUNKCJI: funkcja SendExcelGmailTest.test_default_recipient
    # Test: bez zmiennych środowiskowych odbiorcą jest DEFAULT_EXCEL_REPORT_TO.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: patch.dict na os.environ. Błędy: AssertionError przy niespełnionej asercji.
    def test_default_recipient(self):
        with patch.dict("os.environ", {}, clear=False):
            import scraper_env

            scraper_env._DOTENV_LOADED = True
            self.assertEqual(
                scraper_env.get_excel_report_to(), DEFAULT_EXCEL_REPORT_TO
            )

    # >>> OPIS FUNKCJI: funkcja SendExcelGmailTest.test_build_email_subject_contains_filename
    # Test: temat maila zawiera 'PL FAS Kontakte Excel' i nazwę pliku.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_build_email_subject_contains_filename(self):
        path = Path("pl_spedycja_kontakte.xlsx")
        subject = mailer.build_email_subject(path)
        self.assertIn("PL FAS Kontakte Excel", subject)
        self.assertIn(path.name, subject)

    # >>> OPIS FUNKCJI: funkcja SendExcelGmailTest.test_build_email_body_pl_fas
    # Test: treść maila jest po polsku (PL FAS / spedycja drogowa), nie zawiera 'Generalunternehmer' i podaje nazwę pliku.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: patch Path.stat (rozmiar pliku). Błędy: AssertionError przy niespełnionej asercji.
    def test_build_email_body_pl_fas(self):
        path = Path("pl_spedycja_kontakte.xlsx")
        with patch.object(Path, "stat") as st:
            st.return_value.st_size = 2048
            body = mailer.build_email_body(path, 3)
        self.assertIn("PL FAS / spedycja drogowa", body)
        self.assertNotIn("Generalunternehmer", body)
        self.assertIn(path.name, body)


if __name__ == "__main__":
    unittest.main()

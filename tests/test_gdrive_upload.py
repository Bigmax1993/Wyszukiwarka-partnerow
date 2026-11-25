# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# MODUŁ TESTOWY: tests/test_gdrive_upload.py
# CO ROBI: testy nazewnictwa wersjonowanego XLSX i listy plików pomijanych przy uploadzie na Google Drive.
# ROLA W PIPELINE: chroni zachowanie scripts/gdrive_upload_wyniki.py (wersjonowanie nazwy, brak uploadu cache/logów).
# ZALEŻNOŚCI: unittest, scripts.gdrive_upload_wyniki (funkcje nazewnicze i _skip_gdrive_upload).
# WEJŚCIE/WYJŚCIE: Moduł nie przyjmuje argumentów CLI; pytest/unittest odkrywa i uruchamia testy; nic nie zwraca (wynik = zielone/czerwone testy).
# ============================================================
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.gdrive_upload_wyniki import (  # noqa: E402
    _skip_gdrive_upload,
    versioned_xlsx_upload_name,
)


# >>> OPIS FUNKCJI: klasa GdriveVersionedXlsxTest
# Grupa testów: nazewnictwo i filtr plików uploadu na Drive.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class GdriveVersionedXlsxTest(unittest.TestCase):
    # >>> OPIS FUNKCJI: funkcja GdriveVersionedXlsxTest.test_versions_kontakte_xlsx
    # Test: plik kontakte.xlsx dostaje nazwę z datą i godziną (np. pl_spedycja_kontakte_2026-06-08_1405.xlsx).
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_versions_kontakte_xlsx(self):
        name = versioned_xlsx_upload_name(
            "pl_spedycja_kontakte.xlsx", stamp="2026-06-08_1405"
        )
        self.assertEqual(name, "pl_spedycja_kontakte_2026-06-08_1405.xlsx")

    # >>> OPIS FUNKCJI: funkcja GdriveVersionedXlsxTest.test_non_xlsx_unchanged
    # Test: pliki inne niż xlsx zachowują nazwę.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_non_xlsx_unchanged(self):
        self.assertEqual(
            versioned_xlsx_upload_name("pl_spedycja_cache.json", stamp="x"),
            "pl_spedycja_cache.json",
        )

    # >>> OPIS FUNKCJI: funkcja GdriveVersionedXlsxTest.test_cache_and_log_skipped_from_drive
    # Test: cache JSON i log są pomijane przy uploadzie, a xlsx nie.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_cache_and_log_skipped_from_drive(self):
        self.assertTrue(_skip_gdrive_upload(Path("pl_spedycja_cache.json")))
        self.assertTrue(_skip_gdrive_upload(Path("pl_spedycja_scraper.log")))
        self.assertFalse(_skip_gdrive_upload(Path("pl_spedycja_kontakte.xlsx")))


if __name__ == "__main__":
    unittest.main()

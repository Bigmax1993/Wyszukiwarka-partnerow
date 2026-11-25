# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# MODUŁ TESTOWY: tests/test_excel_append.py
# CO ROBI: testy scalania wierszy Excela w trybie append (bez kasowania istniejących wierszy).
# ROLA W PIPELINE: chroni kumulację tygodniową pliku Excel (merge_export_rows_append, merge_pipeline_rows, export_row_dedupe_key).
# ZALEŻNOŚCI: unittest, pl_fas_spedycja_scraper (jako scraper).
# WEJŚCIE/WYJŚCIE: Moduł nie przyjmuje argumentów CLI; pytest/unittest odkrywa i uruchamia testy; nic nie zwraca (wynik = zielone/czerwone testy).
# ============================================================
"""Testy append Excel ÔÇö merge bez kasowania istniej─ůcych wierszy."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pl_fas_spedycja_scraper as scraper


# >>> OPIS FUNKCJI: klasa ExcelAppendMergeTest
# Grupa testów: scalanie wierszy Excela/pipeline.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class ExcelAppendMergeTest(unittest.TestCase):
    # >>> OPIS FUNKCJI: funkcja ExcelAppendMergeTest.test_merge_export_rows_appends_new_and_updates_existing
    # Test: nowy wiersz jest dopisywany, istniejący aktualizowany (telefon), a ręczna kolumna odpowiedzi jest zachowana; liczniki appended=1, updated=1.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_merge_export_rows_appends_new_and_updates_existing(self):
        existing = [
            {
                "Nazwa firmy": "Alt GmbH",
                "URL": "https://alt.de",
                "E-mail": "alt@alt.de",
                "Odpowied┼║": "tak",
            }
        ]
        incoming = [
            {
                "Nazwa firmy": "Alt GmbH neu",
                "URL": "https://alt.de",
                "E-mail": "alt@alt.de",
                "Telefon": "+49111",
            },
            {
                "Nazwa firmy": "Neu GmbH",
                "URL": "https://neu.de",
                "E-mail": "neu@neu.de",
            },
        ]
        merged, appended, updated = scraper.merge_export_rows_append(
            existing, incoming, logger=None
        )
        self.assertEqual(len(merged), 2)
        self.assertEqual(appended, 1)
        self.assertEqual(updated, 1)
        by_url = {r["URL"]: r for r in merged}
        self.assertEqual(by_url["https://alt.de"]["Telefon"], "+49111")
        self.assertEqual(by_url["https://alt.de"]["Odpowied┼║"], "tak")
        self.assertEqual(by_url["https://neu.de"]["Nazwa firmy"], "Neu GmbH")

    # >>> OPIS FUNKCJI: funkcja ExcelAppendMergeTest.test_merge_pipeline_rows_keeps_excel_only_rows
    # Test: merge_pipeline_rows zachowuje wiersze występujące tylko w Excelu i dodaje wiersze z cache.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_merge_pipeline_rows_keeps_excel_only_rows(self):
        existing = [{"url": "https://excel-only.de", "nazwa": "Excel Only"}]
        incoming = [{"url": "https://cache.de", "nazwa": "From Cache"}]
        merged = scraper.merge_pipeline_rows(existing, incoming)
        urls = {r["url"] for r in merged}
        self.assertEqual(urls, {"https://excel-only.de", "https://cache.de"})

    # >>> OPIS FUNKCJI: funkcja ExcelAppendMergeTest.test_export_row_dedupe_key_prefers_email
    # Test: klucz deduplikacji preferuje e-mail ('email:a@b.de').
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_export_row_dedupe_key_prefers_email(self):
        key = scraper.export_row_dedupe_key(
            {"E-mail": "a@b.de", "URL": "https://x.de", "Nazwa firmy": "X"}
        )
        self.assertEqual(key, "email:a@b.de")


if __name__ == "__main__":
    unittest.main()

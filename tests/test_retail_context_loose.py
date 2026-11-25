# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# MODUŁ TESTOWY: tests/test_retail_context_loose.py
# CO ROBI: testy łagodnej kwalifikacji kontekstu (has_retail_context_without_named_chain).
# ROLA W PIPELINE: bramka 'kontekst bez nazwanego segmentu' w filtrze ICP.
# ZALEŻNOŚCI: unittest, pl_spedycja_filter.
# WEJŚCIE/WYJŚCIE: Moduł nie przyjmuje argumentów CLI; pytest/unittest odkrywa i uruchamia testy; nic nie zwraca (wynik = zielone/czerwone testy).
# ============================================================
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pl_spedycja_filter import has_retail_context_without_named_chain


# >>> OPIS FUNKCJI: klasa RetailContextLooseTest
# Grupa testów: kontekst transportowy bez nazwanego segmentu.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class RetailContextLooseTest(unittest.TestCase):
    # >>> OPIS FUNKCJI: funkcja RetailContextLooseTest.test_accepts_spedycja_without_named_segment
    # Test: spedycja bez nazwanego segmentu jest akceptowana.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_accepts_spedycja_without_named_segment(self):
        text = (
            "Firma spedycyjna. Transport drogowy i organizacja przewozu. "
            "Logistyka na terenie Polski."
        )
        self.assertTrue(has_retail_context_without_named_chain(text))

    # >>> OPIS FUNKCJI: funkcja RetailContextLooseTest.test_accepts_dyspozytor_with_trade_context
    # Test: dyspozytor z kontekstem handlowym jest akceptowany.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_accepts_dyspozytor_with_trade_context(self):
        text = "Spedytor. Dyspozytor fracht — transport międzynarodowy."
        self.assertTrue(has_retail_context_without_named_chain(text))

    # >>> OPIS FUNKCJI: funkcja RetailContextLooseTest.test_rejects_irrelevant_role
    # Test: niepasująca rola jest odrzucana.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_rejects_irrelevant_role(self):
        text = "Agencja pracy — oferty pracy kierowca, kurs na prawo jazdy."
        self.assertFalse(has_retail_context_without_named_chain(text))

    # >>> OPIS FUNKCJI: funkcja RetailContextLooseTest.test_rejects_pure_construction
    # Test: czysta budowlanka jest odrzucana.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_rejects_pure_construction(self):
        text = "Bauunternehmen für Wohnungsbau und Bürosanierung."
        self.assertFalse(has_retail_context_without_named_chain(text))


if __name__ == "__main__":
    unittest.main(verbosity=2)

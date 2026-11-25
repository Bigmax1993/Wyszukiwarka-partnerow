# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# MODUŁ TESTOWY: tests/test_strict_gu_filter.py
# CO ROBI: smoke test filtra pl_spedycja_filter: segmenty, dowody, powody odrzucenia.
# ROLA W PIPELINE: podstawowa ochrona ICP spedycji.
# ZALEŻNOŚCI: unittest, pl_spedycja_filter.
# WEJŚCIE/WYJŚCIE: Moduł nie przyjmuje argumentów CLI; pytest/unittest odkrywa i uruchamia testy; nic nie zwraca (wynik = zielone/czerwone testy).
# ============================================================
"""Smoke unittest: pl_spedycja_filter (PL spedycja)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pl_spedycja_filter import (
    TRANSPORT_SEGMENT_MARKERS,
    debug_filter_decision,
    has_store_shell_build_evidence,
    is_interior_fitout_specialist,
    is_serper_only_pending_candidate,
    is_valid_retail_store_builder_contact,
    reject_reason,
)


# >>> OPIS FUNKCJI: klasa StrictGuFilterTest
# Grupa testów: podstawowe funkcje filtra ICP.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class StrictGuFilterTest(unittest.TestCase):
    # >>> OPIS FUNKCJI: funkcja StrictGuFilterTest.test_required_segments_whitelist
    # Test: lista segmentów TRANSPORT_SEGMENT_MARKERS zawiera ftl, ltl, fracht.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_required_segments_whitelist(self):
        self.assertTrue({"ftl", "ltl", "fracht"}.issubset(set(TRANSPORT_SEGMENT_MARKERS)))

    # >>> OPIS FUNKCJI: funkcja StrictGuFilterTest.test_store_shell_build_evidence
    # Test: has_store_shell_build_evidence rozpoznaje dowody oferty w tekście.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_store_shell_build_evidence(self):
        text = "Firma spedycyjna. Transport drogowy FTL. Fracht Europa."
        self.assertTrue(has_store_shell_build_evidence(text))

    # >>> OPIS FUNKCJI: funkcja StrictGuFilterTest.test_rejects_interior_without_shell
    # Test: tekst o kurierze/paczkach jest odrzucany z powodem kurier_paczka.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_rejects_interior_without_shell(self):
        text = "InPost — paczkomaty i kurier. Nadaj paczkę online."
        rejected, reason = is_interior_fitout_specialist(text)
        self.assertTrue(rejected)
        self.assertEqual(reason, "kurier_paczka")

    # >>> OPIS FUNKCJI: funkcja StrictGuFilterTest.test_accepts_spedycja_with_segment
    # Test: spedycja z segmentem nie jest odrzucana i ma dowody.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_accepts_spedycja_with_segment(self):
        text = (
            "Firma spedycyjna. Transport międzynarodowy. "
            "Spedycja FTL Polska Niemcy."
        )
        rejected, _ = is_interior_fitout_specialist(text)
        self.assertFalse(rejected)
        self.assertTrue(has_store_shell_build_evidence(text))

    # >>> OPIS FUNKCJI: funkcja StrictGuFilterTest.test_reject_reason_and_valid
    # Test: reject_reason zwraca 'courier' dla kuriera; poprawne kontakty przechodzą walidację.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_reject_reason_and_valid(self):
        self.assertEqual(reject_reason(text="kurier InPost paczka"), "courier")
        text = "Firma spedycyjna. Transport drogowy FTL."
        self.assertTrue(
            is_valid_retail_store_builder_contact(
                email="biuro@spedycja-example.pl",
                url="https://spedycja-example.pl",
                name="Spedycja Example",
                text=text,
            )
        )

    # >>> OPIS FUNKCJI: funkcja StrictGuFilterTest.test_serper_and_debug
    # Test: is_serper_only_pending_candidate akceptuje kandydata, a debug zwraca reject_reason=None i is_serper_candidate=True.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_serper_and_debug(self):
        kwargs = dict(
            email="biuro@spedycja-example.pl",
            url="https://spedycja-example.pl",
            name="Spedycja Example",
            text="Firma spedycyjna FTL Warszawa",
            search_term="spedycja FTL Warszawa",
        )
        self.assertTrue(is_serper_only_pending_candidate(**kwargs))
        d = debug_filter_decision(**kwargs)
        self.assertIsNone(d["reject_reason"])
        self.assertTrue(d["is_serper_candidate"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

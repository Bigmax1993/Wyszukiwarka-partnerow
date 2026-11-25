# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# MODUŁ TESTOWY: tests/test_scraper_runtime_limit.py
# CO ROBI: testy twardego limitu czasu runu (scraper_runtime_limit).
# ROLA W PIPELINE: gwarancja, że run zatrzymuje się po SCRAPER_MAX_RUNTIME_SECONDS i zapisuje postęp.
# ZALEŻNOŚCI: unittest, unittest.mock, scraper_runtime_limit.
# WEJŚCIE/WYJŚCIE: Moduł nie przyjmuje argumentów CLI; pytest/unittest odkrywa i uruchamia testy; nic nie zwraca (wynik = zielone/czerwone testy).
# ============================================================
import unittest
from unittest import mock

import scraper_runtime_limit as srl


# >>> OPIS FUNKCJI: klasa ScraperRuntimeLimitTest
# Grupa testów: limit czasu runu.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class ScraperRuntimeLimitTest(unittest.TestCase):
    # >>> OPIS FUNKCJI: funkcja ScraperRuntimeLimitTest.setUp
    # Przygotowanie testu: resetuje zegar limitu czasu modułu scraper_runtime_limit, żeby testy były niezależne. Parametry: self. Zwraca: None. Efekty uboczne: zmienia stan globalny modułu. Błędy: brak.
    def setUp(self):
        srl.reset_scraper_runtime_clock_for_tests()

    # >>> OPIS FUNKCJI: funkcja ScraperRuntimeLimitTest.test_no_limit_when_disabled
    # Test: limit 0 oznacza brak ograniczenia (is_scraper_runtime_limit_reached=False).
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: patch.object na stałej limitu. Błędy: AssertionError przy niespełnionej asercji.
    def test_no_limit_when_disabled(self):
        with mock.patch.object(srl, "SCRAPER_MAX_RUNTIME_SECONDS", 0):
            srl.start_scraper_runtime_clock()
            self.assertFalse(srl.is_scraper_runtime_limit_reached())

    # >>> OPIS FUNKCJI: funkcja ScraperRuntimeLimitTest.test_limit_reached_after_elapsed
    # Test: po upływie czasu (zegar podmieniony mockiem) limit jest osiągnięty.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: patch zegara i stałej limitu. Błędy: AssertionError przy niespełnionej asercji.
    def test_limit_reached_after_elapsed(self):
        with mock.patch.object(srl, "SCRAPER_MAX_RUNTIME_SECONDS", 600):
            with mock.patch(
                "scraper_runtime_limit.time.monotonic", side_effect=[100.0, 701.0]
            ):
                srl.start_scraper_runtime_clock()
                self.assertTrue(srl.is_scraper_runtime_limit_reached())

    # >>> OPIS FUNKCJI: funkcja ScraperRuntimeLimitTest.test_request_stop_logs
    # Test: request_stop_on_runtime_limit zwraca True i loguje komunikat 'Limit czasu scrapera' dokładnie raz.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: patch zegara; przechwycenie komunikatów. Błędy: AssertionError przy niespełnionej asercji.
    def test_request_stop_logs(self):
        with mock.patch.object(srl, "SCRAPER_MAX_RUNTIME_SECONDS", 1):
            with mock.patch(
                "scraper_runtime_limit.time.monotonic", side_effect=[0.0, 2.0]
            ):
                srl.start_scraper_runtime_clock()
                messages: list[str] = []
                self.assertTrue(
                    srl.request_stop_on_runtime_limit(
                        None, console_step_fn=messages.append
                    )
                )
                self.assertEqual(len(messages), 1)
                self.assertIn("Limit czasu scrapera", messages[0])


if __name__ == "__main__":
    unittest.main()

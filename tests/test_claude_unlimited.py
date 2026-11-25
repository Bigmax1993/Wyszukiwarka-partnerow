# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# MODUŁ TESTOWY: tests/test_claude_unlimited.py
# CO ROBI: testy trybu unlimited limitów Claude (domyślnie włączony) i trybu limitowanego z rezerwą.
# ROLA W PIPELINE: pilnuje semantyki limitów dziennych w claude_client wykorzystywanych w całym pipeline.
# ZALEŻNOŚCI: unittest, unittest.mock.patch, claude_client (configure_claude_limits, is_claude_unlimited, is_claude_limit_reached_today).
# WEJŚCIE/WYJŚCIE: Moduł nie przyjmuje argumentów CLI; pytest/unittest odkrywa i uruchamia testy; nic nie zwraca (wynik = zielone/czerwone testy).
# ============================================================
import unittest
from unittest.mock import patch

from claude_client import (
    configure_claude_limits,
    get_remaining_daily_claude_limit,
    is_claude_limit_reached_today,
    is_claude_unlimited,
)


# >>> OPIS FUNKCJI: klasa TestClaudeUnlimited
# Grupa testów: limity dzienne Claude.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestClaudeUnlimited(unittest.TestCase):
    # >>> OPIS FUNKCJI: funkcja TestClaudeUnlimited.tearDown
    # Sprzątanie po teście: przywraca domyślną konfigurację limitów Claude, aby testy nie wpływały na siebie. Parametry: self. Zwraca: None. Efekty uboczne: modyfikuje globalne ustawienia claude_client. Błędy: brak.
    def tearDown(self):
        configure_claude_limits(daily_limit=3000, reserve=1000, unlimited=True)

    # >>> OPIS FUNKCJI: funkcja TestClaudeUnlimited.test_default_is_unlimited
    # Test: domyślnie limit jest wyłączony: is_claude_limit_reached_today=False, pozostały budżet > 0.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: patch daty; brak sieci. Błędy: AssertionError przy niespełnionej asercji.
    def test_default_is_unlimited(self):
        configure_claude_limits(unlimited=True)
        self.assertTrue(is_claude_unlimited())
        cache = {"claude_daily": {"2099-01-01": 9999}}
        with patch("claude_client._campaign_today", return_value="2099-01-01"):
            self.assertFalse(is_claude_limit_reached_today(cache))
            _, used, remaining = get_remaining_daily_claude_limit(cache)
            self.assertEqual(used, 9999)
            self.assertGreater(remaining, 0)

    # >>> OPIS FUNKCJI: funkcja TestClaudeUnlimited.test_limited_mode_respects_reserve
    # Test: w trybie limitowanym limit jest osiągnięty po wykorzystaniu budżetu pomniejszonego o rezerwę.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: patch daty; zmienia globalną konfigurację limitów (przywracaną w tearDown). Błędy: AssertionError przy niespełnionej asercji.
    def test_limited_mode_respects_reserve(self):
        configure_claude_limits(daily_limit=100, reserve=10, unlimited=False)
        self.assertFalse(is_claude_unlimited())
        cache = {"claude_daily": {"2099-01-01": 95}}
        with patch("claude_client._campaign_today", return_value="2099-01-01"):
            self.assertTrue(is_claude_limit_reached_today(cache))


if __name__ == "__main__":
    unittest.main()

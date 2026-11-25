# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# MODUŁ TESTOWY: tests/test_discovery_run_state.py
# CO ROBI: test zapisu stanu runu discovery (record_discovery_run_state) w cache.
# ROLA W PIPELINE: chroni dane używane przez workflow GHA do oceny, czy discovery się powiodło (zużycie Serper, wyczerpanie).
# ZALEŻNOŚCI: unittest, discovery_run_state.record_discovery_run_state.
# WEJŚCIE/WYJŚCIE: Moduł nie przyjmuje argumentów CLI; pytest/unittest odkrywa i uruchamia testy; nic nie zwraca (wynik = zielone/czerwone testy).
# ============================================================
import unittest

from discovery_run_state import record_discovery_run_state


# >>> OPIS FUNKCJI: klasa DiscoveryRunStateTest
# Grupa testów: stan runu discovery.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class DiscoveryRunStateTest(unittest.TestCase):
    # >>> OPIS FUNKCJI: funkcja DiscoveryRunStateTest.test_record_state
    # Test: record_discovery_run_state zapisuje w cache['discovery_run_state'] zużycie Serper (500) i flagę wyczerpania (False).
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_record_state(self):
        cache: dict = {"serper_daily": {"2026-06-06": 500}}
        record_discovery_run_state(
            cache,
            all_rows=[],
            total_new_rows=50,
            serper_only=True,
            rotate_mode=False,
            campaign_today="2026-06-06",
            serper_daily_limit=3000,
            serper_discovery_reserve=1000,
            is_serper_unlimited=False,
            is_serper_limit_reached_today_fn=lambda c: False,
            is_serper_api_exhausted_fn=lambda c: False,
            discovery_target_reached_fn=lambda *a, **k: False,
        )
        self.assertEqual(cache["discovery_run_state"]["serper_used"], 500)
        self.assertFalse(cache["discovery_run_state"]["serper_exhausted"])


if __name__ == "__main__":
    unittest.main()

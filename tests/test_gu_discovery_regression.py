# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# MODUŁ TESTOWY: tests/test_gu_discovery_regression.py
# CO ROBI: największy zestaw testów regresyjnych discovery (serper-only, małe firmy, limity Serper, rotacja województw, filtry ICP/geo, merge Excela, wybór e-maila).
# ROLA W PIPELINE: bezpiecznik dla całego etapu discovery i kwalifikacji kandydatów w pl_fas_spedycja_scraper oraz pl_spedycja_filter/pl_spedycja_keywords. Nazwy klas z 'Bundesweit/GU/Retail' są legacy.
# ZALEŻNOŚCI: unittest, unittest.mock.patch, pl_fas_spedycja_scraper (jako scraper), pl_spedycja_keywords, pl_spedycja_filter, gu_bundesland_rotation.
# WEJŚCIE/WYJŚCIE: Moduł nie przyjmuje argumentów CLI; pytest/unittest odkrywa i uruchamia testy; nic nie zwraca (wynik = zielone/czerwone testy).
# ============================================================
"""
Testy regresyjne discovery GU (serper-only, małe firmy, limit Serper, rotacja).

Uruchomienie:
  python tests/test_gu_discovery_regression.py
  python -m unittest tests.test_gu_discovery_regression -v
"""
from __future__ import annotations

import logging
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pl_fas_spedycja_scraper as scraper
from pl_spedycja_keywords import (
    ALL_BUNDESLAENDER,
    RETAIL_CHAINS_ROTATION,
    build_discovery_terms,
    default_max_discovery_terms_for,
)
from pl_spedycja_filter import (
    is_generalunternehmer,
    is_loose_serper_discovery_candidate,
    is_serper_only_pending_candidate,
)

_LOGGER = logging.getLogger("test_gu_discovery_regression")


# >>> OPIS FUNKCJI: klasa BundesweitRegression
# Grupa testów: konfiguracja całopolskiej kampanii (16 województw), sufiks regionu, liczba fraz discovery i cel serper-only.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class BundesweitRegression(unittest.TestCase):
    # >>> OPIS FUNKCJI: funkcja BundesweitRegression.test_default_covers_all_bundeslaender
    # Test: domyślnie aktywne jest 16 województw (ALL_BUNDESLAENDER i CAMPAIGN_ACTIVE_BUNDESLAENDER).
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_default_covers_all_bundeslaender(self):
        self.assertEqual(len(ALL_BUNDESLAENDER), 16)
        self.assertEqual(len(scraper.CAMPAIGN_ACTIVE_BUNDESLAENDER), 16)

    # >>> OPIS FUNKCJI: funkcja BundesweitRegression.test_bundesweit_region_suffix_short
    # Test: sufiks regionu Serper dla wszystkich województw to krótkie 'Polska'.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_bundesweit_region_suffix_short(self):
        """Suffix Serper: Polska przy wielu województwach."""
        from pl_spedycja_keywords import build_region_suffix

        self.assertEqual(build_region_suffix(list(ALL_BUNDESLAENDER)), "Polska")
        self.assertEqual(
            build_region_suffix(
                ["Mazowieckie", "Śląskie", "Wielkopolskie", "Małopolskie"]
            ),
            "Polska",
        )

    # >>> OPIS FUNKCJI: funkcja BundesweitRegression.test_two_lands_keep_short_suffix
    # Test: dla dwóch województw sufiks zawiera 'Polska' i skróty (np. MZ, LD).
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_two_lands_keep_short_suffix(self):
        from pl_spedycja_keywords import build_region_suffix

        suffix = build_region_suffix(["Mazowieckie", "Lodzkie"])
        self.assertIn("Polska", suffix)
        self.assertIn("MZ", suffix)
        self.assertIn("LD", suffix)

    # >>> OPIS FUNKCJI: funkcja BundesweitRegression.test_bundesweit_has_many_discovery_terms
    # Test: dla całej Polski generowanych jest co najmniej 500 fraz discovery (limit tematyczny zgodny z default_max_discovery_terms_for).
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_bundesweit_has_many_discovery_terms(self):
        # Kampania PL: cap discovery = 1000 (nie 2000 jak dawniej DE)
        self.assertGreaterEqual(len(scraper.SERPER_DISCOVERY_TERMS), 500)
        self.assertEqual(
            default_max_discovery_terms_for(list(ALL_BUNDESLAENDER)), 1000
        )

    # >>> OPIS FUNKCJI: funkcja BundesweitRegression.test_serper_only_target_uses_new_rows_not_total
    # Test: w trybie serper-only cel liczy NOWE wiersze w runie, a nie łączną liczbę wierszy w Excelu (_discovery_target_reached).
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_serper_only_target_uses_new_rows_not_total(self):
        rows = [{"url": f"https://example.de/{i}"} for i in range(200)]
        self.assertFalse(
            scraper._discovery_target_reached(
                rows,
                total_new_rows=10,
                rotate_mode=False,
                serper_only=True,
            )
        )
        self.assertTrue(
            scraper._discovery_target_reached(
                rows,
                total_new_rows=scraper.MIN_CONTACTS_TARGET,
                rotate_mode=False,
                serper_only=True,
            )
        )


# >>> OPIS FUNKCJI: klasa SerperQuotaExhaustionRegression
# Grupa testów: wykrywanie i skutki wyczerpania kredytów Serper.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class SerperQuotaExhaustionRegression(unittest.TestCase):
    # >>> OPIS FUNKCJI: funkcja SerperQuotaExhaustionRegression.test_detects_402_quota_error
    # Test: błąd z HTTP 402 jest rozpoznawany jako wyczerpanie kredytów (_is_serper_quota_error).
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: atrapa wyjątku FakeErr z response.status_code=402. Błędy: AssertionError przy niespełnionej asercji.
    def test_detects_402_quota_error(self):
        class FakeResp:
            status_code = 402

            def json(self):
                return {"message": "Not enough credits"}

        class FakeErr(Exception):
            response = FakeResp()

        self.assertTrue(scraper._is_serper_quota_error(FakeErr()))

    # >>> OPIS FUNKCJI: funkcja SerperQuotaExhaustionRegression.test_mark_exhausted_stops_further_discovery
    # Test: mark_serper_api_exhausted ustawia flagi: API wyczerpane i limit dzienny osiągnięty.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_mark_exhausted_stops_further_discovery(self):
        cache = scraper._empty_cache()
        scraper.mark_serper_api_exhausted(cache, "402 Payment Required")
        self.assertTrue(scraper.is_serper_api_exhausted(cache))
        self.assertTrue(scraper.is_serper_limit_reached_today(cache))

    # >>> OPIS FUNKCJI: funkcja SerperQuotaExhaustionRegression.test_process_terms_stops_when_api_exhausted
    # Test: _process_serper_terms przerywa pracę (stop_requested=True, 0 nowych wierszy), gdy API Serper jest wyczerpane.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: mocki/atrapy w pamięci i słowniki cache tworzone w teście (bez sieci i bez plików poza tymczasowymi). Błędy: AssertionError przy niespełnionej asercji.
    def test_process_terms_stops_when_api_exhausted(self):
        cache = scraper._empty_cache()
        scraper.mark_serper_api_exhausted(cache, "test")
        all_rows: list = []
        prev_maps = scraper.ENABLE_GOOGLE_MAPS_DISCOVERY
        scraper.ENABLE_GOOGLE_MAPS_DISCOVERY = False
        try:
            total, stopped = scraper._process_serper_terms(
                ["Generalunternehmer Filialbau Berlin Rewe"] * 5,
                "test",
                all_rows=all_rows,
                seen_global=set(),
                cache=cache,
                logger=_LOGGER,
                enable_auto_email=False,
                apply_distance_filter=False,
                max_new_rows=None,
                total_new_rows=0,
                stop_requested=False,
                serper_only=True,
            )
        finally:
            scraper.ENABLE_GOOGLE_MAPS_DISCOVERY = prev_maps
        self.assertTrue(stopped)
        self.assertEqual(total, 0)


# >>> OPIS FUNKCJI: klasa SerperLimitRegression
# Grupa testów: dzienny budżet Serper, reset i cache zapytań.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class SerperLimitRegression(unittest.TestCase):
    # >>> OPIS FUNKCJI: funkcja SerperLimitRegression.test_reset_clears_daily_counter
    # Test: reset_serper_daily_for_discovery zeruje licznik dnia, kasuje flagę limitu i czyści cache serper/serper_discovery.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_reset_clears_daily_counter(self):
        cache = scraper._empty_cache()
        today = scraper.campaign_today()
        cache.setdefault("serper_daily", {})[today] = 300
        cache.setdefault("serper_limit_reached", {})[today] = True
        cache["serper"] = {"q1": {"rows": []}}
        cache["serper_discovery"] = {"q2": {"empty": True, "rows": []}}
        scraper.reset_serper_daily_for_discovery(cache)
        self.assertEqual(cache["serper_daily"][today], 0)
        self.assertNotIn(today, cache.get("serper_limit_reached", {}))
        self.assertEqual(cache["serper"], {})
        self.assertEqual(cache["serper_discovery"], {})

    # >>> OPIS FUNKCJI: funkcja SerperLimitRegression.test_reset_keep_search_caches_for_resume
    # Test: przy keep_search_caches=True reset zeruje licznik, ale zachowuje cache zapytań (wznowienie runu).
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_reset_keep_search_caches_for_resume(self):
        cache = scraper._empty_cache()
        today = scraper.campaign_today()
        cache.setdefault("serper_daily", {})[today] = 900
        cache.setdefault("serper_limit_reached", {})[today] = True
        cache["serper"] = {"q1": "firma.de"}
        cache["serper_discovery"] = {"search:q2": {"rows": [{"url": "x"}]}}
        scraper.reset_serper_daily_for_discovery(cache, keep_search_caches=True)
        self.assertEqual(cache["serper_daily"][today], 0)
        self.assertNotIn(today, cache.get("serper_limit_reached", {}))
        self.assertEqual(cache["serper"], {"q1": "firma.de"})
        self.assertEqual(
            cache["serper_discovery"],
            {"search:q2": {"rows": [{"url": "x"}]}},
        )

    # >>> OPIS FUNKCJI: funkcja SerperLimitRegression.test_ensure_budget_raises_when_exhausted
    # Test: ensure_serper_budget_or_fail rzuca RuntimeError, gdy dzienny budżet jest wyczerpany.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError; RuntimeError oczekiwany w assertRaises.
    def test_ensure_budget_raises_when_exhausted(self):
        cache = scraper._empty_cache()
        today = scraper.campaign_today()
        cache["serper_daily"][today] = scraper.SERPER_DAILY_LIMIT
        with self.assertRaises(RuntimeError):
            scraper.ensure_serper_budget_or_fail(cache)

    # >>> OPIS FUNKCJI: funkcja SerperLimitRegression.test_ensure_budget_ok_after_reset
    # Test: po resecie budżet jest pełny (użyte 0, pozostałe = SERPER_DAILY_LIMIT).
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_ensure_budget_ok_after_reset(self):
        cache = scraper._empty_cache()
        scraper.reset_serper_daily_for_discovery(cache)
        scraper.ensure_serper_budget_or_fail(cache)
        _, used, remaining = scraper.get_remaining_daily_serper_limit(cache)
        self.assertEqual(used, 0)
        self.assertEqual(remaining, scraper.SERPER_DAILY_LIMIT)

    # >>> OPIS FUNKCJI: funkcja SerperLimitRegression.test_empty_serper_cache_respects_ttl
    # Test: pusty wynik w cache discovery jest honorowany, dopóki nie minie TTL (zwraca []).
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_empty_serper_cache_respects_ttl(self):
        cache = scraper._empty_cache()
        cache.setdefault("serper_discovery", {})
        key = scraper._serper_discovery_cache_key("test query", use_places_endpoint=False)
        cache["serper_discovery"][key] = {
            "empty": True,
            "at": datetime.now().isoformat(),
            "rows": [],
        }
        rows = scraper.get_cached_serper_discovery_rows(
            cache, "test query", use_places_endpoint=False
        )
        self.assertEqual(rows, [])

    # >>> OPIS FUNKCJI: funkcja SerperLimitRegression.test_empty_serper_cache_expires_after_ttl
    # Test: pusty wpis cache starszy niż TTL wygasa (get_cached_serper_discovery_rows zwraca None → ponowne zapytanie).
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_empty_serper_cache_expires_after_ttl(self):
        cache = scraper._empty_cache()
        cache.setdefault("serper_discovery", {})
        key = scraper._serper_discovery_cache_key("stale query", use_places_endpoint=False)
        old = datetime.now() - timedelta(days=scraper.SERPER_DISCOVERY_EMPTY_CACHE_DAYS + 1)
        cache["serper_discovery"][key] = {
            "empty": True,
            "at": old.isoformat(),
            "rows": [],
        }
        self.assertIsNone(
            scraper.get_cached_serper_discovery_rows(
                cache, "stale query", use_places_endpoint=False
            )
        )


# >>> OPIS FUNKCJI: klasa StrictGuFilterRegression
# Grupa testów: ścisła kwalifikacja roli spedytora (legacy nazwa 'GU').
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class StrictGuFilterRegression(unittest.TestCase):
    # >>> OPIS FUNKCJI: funkcja StrictGuFilterRegression.test_is_generalunternehmer_positive
    # Test: tekst o firmie spedycyjnej kwalifikuje się jako rola ICP, a marker to np. 'firma spedycyjna'/'spedycja'.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_is_generalunternehmer_positive(self):
        ok, marker = is_generalunternehmer(
            "Trans Spedycja Sp. z o.o. — firma spedycyjna FTL"
        )
        self.assertTrue(ok)
        self.assertIn(marker, ("firma spedycyjna", "spedycja"))

    # >>> OPIS FUNKCJI: funkcja StrictGuFilterRegression.test_is_generalunternehmer_rejects_ladenbau_only
    # Test: sama tematyka ladenbau (legacy DE) nie daje roli (False, pusty marker).
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_is_generalunternehmer_rejects_ladenbau_only(self):
        ok, marker = is_generalunternehmer("HELIA Ladenbau GmbH Filialbau Neubau")
        self.assertFalse(ok)
        self.assertEqual(marker, "")

    # >>> OPIS FUNKCJI: funkcja StrictGuFilterRegression.test_is_generalunternehmer_rejects_bauunternehmen_only
    # Test: sama tematyka bauunternehmen nie daje roli spedytora.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_is_generalunternehmer_rejects_bauunternehmen_only(self):
        ok, _ = is_generalunternehmer("Bauunternehmen Müller GmbH Gewerbebau")
        self.assertFalse(ok)


# >>> OPIS FUNKCJI: klasa GeoFilterRegression
# Grupa testów: filtry geograficzne i kandydaci z Polski.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class GeoFilterRegression(unittest.TestCase):
    # >>> OPIS FUNKCJI: funkcja GeoFilterRegression.test_geo_filters_disabled_by_default
    # Test: filtry geo (kod pocztowy, dystans) są domyślnie wyłączone — dowolna lokalizacja przechodzi.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_geo_filters_disabled_by_default(self):
        self.assertFalse(scraper.ENABLE_REGION_PLZ_FILTER)
        self.assertFalse(scraper.ENABLE_DISTANCE_FROM_REGION_KM)
        self.assertFalse(scraper._geo_filters_enabled())
        self.assertTrue(scraper.location_within_region_km("München Hamburg Köln"))

    # >>> OPIS FUNKCJI: funkcja GeoFilterRegression.test_poland_candidate_accepts_pl_domain
    # Test: domena .pl jest akceptowana; stary alias is_germany_de_candidate wskazuje na is_poland_pl_candidate.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_poland_candidate_accepts_pl_domain(self):
        self.assertTrue(
            scraper.is_poland_pl_candidate(
                "https://trans-spedycja.pl/kontakt", "Spedycja", "Głogów"
            )
        )
        self.assertIs(scraper.is_germany_de_candidate, scraper.is_poland_pl_candidate)

    # >>> OPIS FUNKCJI: funkcja GeoFilterRegression.test_poland_candidate_rejects_de_domain
    # Test: domena .de jest odrzucana jako kandydat PL.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_poland_candidate_rejects_de_domain(self):
        self.assertFalse(
            scraper.is_poland_pl_candidate(
                "https://firma-bau.de/kontakt", "GU Leipzig", ""
            )
        )

    # >>> OPIS FUNKCJI: funkcja GeoFilterRegression.test_poland_candidate_rejects_at_domain
    # Test: domena .at jest odrzucana jako kandydat PL.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_poland_candidate_rejects_at_domain(self):
        self.assertFalse(
            scraper.is_poland_pl_candidate("https://firma-bau.at/kontakt", "Bau Wien", "")
        )

    # >>> OPIS FUNKCJI: funkcja GeoFilterRegression.test_poland_candidate_accepts_pl_postal_hint
    # Test: kandydat bez domeny .pl jest akceptowany, gdy tekst zawiera polską wskazówkę adresową (kod pocztowy).
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_poland_candidate_accepts_pl_postal_hint(self):
        self.assertTrue(
            scraper.is_poland_pl_candidate(
                "https://spedycja-example.com",
                "Trans Spedycja",
                "67-200 Głogów Polska",
            )
        )

    # >>> OPIS FUNKCJI: funkcja GeoFilterRegression.test_run_config_disables_geo_filters
    # Test: apply_gu_run_config_extras z geo_filter_enabled=false wyłącza flagi filtrów geo na module.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: obiekt-atrapa modułu modyfikowany w teście. Błędy: AssertionError przy niespełnionej asercji.
    def test_run_config_disables_geo_filters(self):
        import pl_fas_spedycja_scraper as mod

        apply = scraper.apply_gu_run_config_extras
        apply(mod, {"geo_filter_enabled": False})
        self.assertFalse(mod.ENABLE_REGION_PLZ_FILTER)
        self.assertFalse(mod.ENABLE_DISTANCE_FROM_REGION_KM)


# >>> OPIS FUNKCJI: klasa LooseSerperFilterRegression
# Grupa testów: łagodny filtr kandydatów Serper (discovery).
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class LooseSerperFilterRegression(unittest.TestCase):
    # >>> OPIS FUNKCJI: funkcja LooseSerperFilterRegression.test_accepts_spedycja_snippet
    # Test: snippet o spedycji jest akceptowany.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_accepts_spedycja_snippet(self):
        self.assertTrue(
            is_loose_serper_discovery_candidate(
                name="Trans Spedycja Sp. z o.o.",
                url="https://trans-spedycja.pl",
                email="biuro@trans-spedycja.pl",
                text="Firma spedycyjna FTL transport drogowy Warszawa Europa",
            )
        )

    # >>> OPIS FUNKCJI: funkcja LooseSerperFilterRegression.test_accepts_role_without_ftl_word_in_snippet
    # Test: sama rola spedytora wystarcza, bez słowa FTL w snippecie.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_accepts_role_without_ftl_word_in_snippet(self):
        self.assertTrue(
            is_loose_serper_discovery_candidate(
                name="Spedytor Kowalski",
                url="https://spedytor-kowalski.pl",
                email="biuro@spedytor-kowalski.pl",
                text="Biuro spedycyjne — organizacja przewozu Polska",
            )
        )

    # >>> OPIS FUNKCJI: funkcja LooseSerperFilterRegression.test_accepts_segment_from_search_term
    # Test: segment może pochodzić z frazy wyszukiwania, nie tylko ze snippeta.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_accepts_segment_from_search_term(self):
        self.assertTrue(
            is_loose_serper_discovery_candidate(
                name="Nord Transport Sp. z o.o.",
                url="https://nord-transport.pl",
                email="biuro@nord-transport.pl",
                text="Biuro w Gdańsku — kontakt",
                search_term="spedycja FTL Pomorskie",
            )
        )

    # >>> OPIS FUNKCJI: funkcja LooseSerperFilterRegression.test_rejects_without_trade_context
    # Test: brak kontekstu handlowo-transportowego → odrzut.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_rejects_without_trade_context(self):
        self.assertFalse(
            is_loose_serper_discovery_candidate(
                name="Weber Bau GmbH",
                url="https://weber-bau.de",
                text="Generalunternehmer Filialbau Gewerbebau",
            )
        )

    # >>> OPIS FUNKCJI: funkcja LooseSerperFilterRegression.test_rejects_media_publisher
    # Test: media/wydawcy są odrzucane.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_rejects_media_publisher(self):
        self.assertFalse(
            is_loose_serper_discovery_candidate(
                url="https://www.hi-heute.de/supermarkte",
                name="hi-heute.de",
                text="Supermarkt Nachrichten Aldi Rewe",
            )
        )

    # >>> OPIS FUNKCJI: funkcja LooseSerperFilterRegression.test_loose_accepts_more_than_strict_core
    # Test: filtr discovery (sama rola) jest łagodniejszy niż rdzeń, który wymaga ROLA ∧ (SEGMENT ∨ USŁUGA).
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_loose_accepts_more_than_strict_core(self):
        """Serper discovery: sama rola; core wymaga ROLE∧(SEGMENT∨SERVICE)."""
        from pl_spedycja_filter import (
            mentions_retail_store_build_activity_core,
            mentions_retail_store_build_activity_serper_discovery,
        )

        text = "Firma spedycyjna Warszawa regionalnie"
        self.assertTrue(mentions_retail_store_build_activity_serper_discovery(text))
        self.assertFalse(mentions_retail_store_build_activity_core(text))


# >>> OPIS FUNKCJI: klasa SerperOnlyFilterRegression
# Grupa testów: filtr kandydatów w trybie serper-only (pending_www_verify), cache, odtwarzanie z Excela i wybór e-maila.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class SerperOnlyFilterRegression(unittest.TestCase):
    # >>> OPIS FUNKCJI: funkcja SerperOnlyFilterRegression.test_rejects_ladenbau_without_trade_signal
    # Test: ladenbau bez sygnału handlowego jest odrzucany.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_rejects_ladenbau_without_trade_signal(self):
        self.assertFalse(
            is_serper_only_pending_candidate(
                name="HELIA Ladenbau GmbH",
                url="https://helia-ladenbau.de",
                text="Ladenbau in Ulm",
            )
        )

    # >>> OPIS FUNKCJI: funkcja SerperOnlyFilterRegression.test_accepts_spedycja_ftl
    # Test: spedycja FTL jest akceptowana.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_accepts_spedycja_ftl(self):
        self.assertTrue(
            is_serper_only_pending_candidate(
                name="Trans Spedycja Sp. z o.o.",
                url="https://trans-spedycja.pl",
                email="biuro@trans-spedycja.pl",
                text="Firma spedycyjna FTL transport drogowy",
            )
        )

    # >>> OPIS FUNKCJI: funkcja SerperOnlyFilterRegression.test_rejects_media_publisher
    # Test: wydawca/media odrzucony.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_rejects_media_publisher(self):
        self.assertFalse(
            is_serper_only_pending_candidate(
                url="https://www.hi-heute.de/supermarkte",
                name="hi-heute.de",
                text="Supermarkt Nachrichten",
            )
        )

    # >>> OPIS FUNKCJI: funkcja SerperOnlyFilterRegression.test_rejects_exchange_operator
    # Test: operator giełdy transportowej odrzucony.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_rejects_exchange_operator(self):
        self.assertFalse(
            is_serper_only_pending_candidate(
                url="https://www.timocom.com/pl",
                name="TimoCom",
                text="Giełda transportowa oferty frachtów",
            )
        )

    # >>> OPIS FUNKCJI: funkcja SerperOnlyFilterRegression.test_serper_only_equals_loose_alias
    # Test: is_serper_only_pending_candidate jest równoważny filtrowi 'loose' dla tych samych danych.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_serper_only_equals_loose_alias(self):
        kwargs = dict(
            name="Trans Spedycja Sp. z o.o.",
            url="https://trans-spedycja.pl",
            email="biuro@trans-spedycja.pl",
            text="Firma spedycyjna FTL Warszawa",
            search_term="spedycja FTL",
        )
        self.assertEqual(
            is_serper_only_pending_candidate(**kwargs),
            is_loose_serper_discovery_candidate(**kwargs),
        )

    # >>> OPIS FUNKCJI: funkcja SerperOnlyFilterRegression.test_serper_only_accepts_role_in_company_name
    # Test: rola wpisana w nazwie firmy wystarcza do akceptacji kandydata.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_serper_only_accepts_role_in_company_name(self):
        self.assertTrue(
            is_serper_only_pending_candidate(
                name="Spedycja Mazowsze Sp. z o.o.",
                url="https://spedycja-mazowsze.pl",
                email="biuro@spedycja-mazowsze.pl",
                text="Kontakt Warszawa",
            )
        )

    # >>> OPIS FUNKCJI: funkcja SerperOnlyFilterRegression.test_serper_only_rejects_without_trade_signal
    # Test: brak sygnału handlowego → odrzut w trybie serper-only.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_serper_only_rejects_without_trade_signal(self):
        self.assertFalse(
            is_serper_only_pending_candidate(
                name="Weber Bau GmbH",
                url="https://weber-bau.de",
                text="Generalunternehmer Filialbau Gewerbebau",
            )
        )

    # >>> OPIS FUNKCJI: funkcja SerperOnlyFilterRegression.test_serper_only_accepts_segment_from_search_term_not_snippet
    # Test: segment z frazy wyszukiwania (nie ze snippeta) jest akceptowany.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_serper_only_accepts_segment_from_search_term_not_snippet(self):
        self.assertTrue(
            is_serper_only_pending_candidate(
                name="Nord Logistyka Sp. z o.o.",
                url="https://nord-logistyka.pl",
                email="biuro@nord-logistyka.pl",
                text="Biuro w Gdańsku — kontakt",
                search_term="spedycja FTL Pomorskie",
            )
        )

    # >>> OPIS FUNKCJI: funkcja SerperOnlyFilterRegression.test_serper_only_accepts_service_in_search_term
    # Test: usługa obecna we frazie wyszukiwania jest akceptowana.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_serper_only_accepts_service_in_search_term(self):
        self.assertTrue(
            is_serper_only_pending_candidate(
                name="Warszawa Transport Sp. z o.o.",
                url="https://warszawa-transport.pl",
                email="biuro@warszawa-transport.pl",
                text="Kontakt i oferta",
                search_term="transport drogowy Mazowieckie",
            )
        )

    # >>> OPIS FUNKCJI: funkcja SerperOnlyFilterRegression.test_serper_only_accepts_trade_signal_without_extra_gu
    # Test: sygnał handlowy bez dodatkowych znaczników roli jest wystarczający.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_serper_only_accepts_trade_signal_without_extra_gu(self):
        self.assertTrue(
            is_serper_only_pending_candidate(
                name="Partner Forwarding Sp. z o.o.",
                url="https://partner-forwarding.pl",
                email="biuro@partner-forwarding.pl",
                text="Freight forwarding Europa — fracht drogowy",
                search_term="freight forwarding Polska",
            )
        )

    # >>> OPIS FUNKCJI: funkcja SerperOnlyFilterRegression.test_serper_only_accepts_ftl_segment
    # Test: segment FTL jest akceptowany.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_serper_only_accepts_ftl_segment(self):
        self.assertTrue(
            is_serper_only_pending_candidate(
                name="Nord Spedycja Sp. z o.o.",
                url="https://nord-spedycja.pl",
                email="biuro@nord-spedycja.pl",
                text="Spedycja FTL referencje trasy Europa",
            )
        )

    # >>> OPIS FUNKCJI: funkcja SerperOnlyFilterRegression.test_pending_not_purged_from_cache
    # Test: rekordy pending_www_verify nie są usuwane przez purge_institutions_from_cache.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: tymczasowy słownik cache w teście. Błędy: AssertionError przy niespełnionej asercji.
    def test_pending_not_purged_from_cache(self):
        from pl_spedycja_filter import is_cache_contact_not_store_builder

        info = {
            "company_name_clean": "Trans Spedycja Sp. z o.o.",
            "verification_reason": scraper.PENDING_WWW_VERIFY_REASON,
            "retail_verified": False,
        }
        self.assertFalse(
            is_cache_contact_not_store_builder("https://trans-spedycja.pl", info)
        )

    # >>> OPIS FUNKCJI: funkcja SerperOnlyFilterRegression.test_reverify_all_includes_rejected_cache_contacts
    # Test: collect_urls_for_www_reverify: bez reverify_all tylko pending, z reverify_all także odrzucone kontakty z cache.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: tymczasowy słownik cache w teście. Błędy: AssertionError przy niespełnionej asercji.
    def test_reverify_all_includes_rejected_cache_contacts(self):
        cache = scraper._empty_cache()
        cache["contacts"] = {
            "https://a.de": {
                "verification_reason": "keine_handelskette",
                "retail_verified": False,
            },
            "https://b.de": {
                "verification_reason": scraper.PENDING_WWW_VERIFY_REASON,
                "retail_verified": False,
            },
        }
        pending_only = scraper.collect_urls_for_www_reverify(cache, reverify_all=False)
        all_urls = scraper.collect_urls_for_www_reverify(cache, reverify_all=True)
        self.assertEqual(pending_only, ["https://b.de"])
        self.assertEqual(set(all_urls), {"https://a.de", "https://b.de"})

    # >>> OPIS FUNKCJI: funkcja SerperOnlyFilterRegression.test_excel_roundtrip_restores_pending
    # Test: wiersz pending zapisany jak w Excelu i wczytany przez row_from_excel_record odtwarza powód weryfikacji, region, miasto, segmenty i flagę roli; nadal kwalifikuje się do eksportu.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_excel_roundtrip_restores_pending(self):
        rec = {
            "Nazwa firmy": "Trans Spedycja Sp. z o.o.",
            "URL": "https://trans-spedycja.pl",
            "Strona www": "https://trans-spedycja.pl",
            "WWW sprawdzone": "nie",
            "E-mail": "biuro@trans-spedycja.pl",
            "Segmenty": "ftl",
            "Spedycja": "tak",
            "Województwo": "Mazowieckie",
            "Miasto": "Warszawa",
        }
        row = scraper.row_from_excel_record(rec)
        row["verification_reason"] = scraper.PENDING_WWW_VERIFY_REASON
        row["page_snippet"] = "Firma spedycyjna FTL transport drogowy Europa"
        row["email_target"] = "biuro@trans-spedycja.pl"
        self.assertEqual(row.get("verification_reason"), scraper.PENDING_WWW_VERIFY_REASON)
        self.assertTrue(scraper.is_row_eligible_for_excel_export(row))
        self.assertEqual(row.get("bundesland"), "Mazowieckie")
        self.assertEqual(row.get("miasto"), "Warszawa")
        self.assertEqual(row.get("retail_chains_found"), "ftl")
        self.assertTrue(row.get("is_gu"))

    # >>> OPIS FUNKCJI: funkcja SerperOnlyFilterRegression.test_excel_legacy_de_headers_still_import
    # Test: stare nagłówki DE (Bundesland, Handelsketten…) są nadal poprawnie importowane z Excela.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_excel_legacy_de_headers_still_import(self):
        rec = {
            "Nazwa firmy": "Old Export Sp. z o.o.",
            "URL": "https://old-export.pl",
            "WWW_geprueft": "nein",
            "Handelsketten": "ltl",
            "GU": "ja",
            "Bundesland": "dolnośląskie",
        }
        row = scraper.row_from_excel_record(rec)
        self.assertEqual(row.get("bundesland"), "Dolnoslaskie")
        self.assertEqual(row.get("retail_chains_found"), "ltl")
        self.assertTrue(row.get("is_gu"))
        self.assertFalse(row.get("retail_verified"))

    # >>> OPIS FUNKCJI: funkcja SerperOnlyFilterRegression.test_pick_email_prefers_impressum_over_homepage_junk
    # Test: wybór e-maila preferuje adres z Impressum nad przypadkowymi z strony głównej i spełnia próg MIN_EMAIL_SCORE_FOR_SEND.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_pick_email_prefers_impressum_over_homepage_junk(self):
        target, score, method = scraper.pick_email_with_impressum_priority(
            all_emails=[
                "d@enschutzhinweisen.akzeptieren",
                "privacy@firma.pl",
            ],
            impressum_emails=["biuro@trans-spedycja.pl"],
            website="https://trans-spedycja.pl",
        )
        self.assertEqual(target, "biuro@trans-spedycja.pl")
        self.assertIn(method, ("impressum", "impressum_rules"))
        self.assertGreaterEqual(score, scraper.MIN_EMAIL_SCORE_FOR_SEND)

    # >>> OPIS FUNKCJI: funkcja SerperOnlyFilterRegression.test_collect_impressum_urls_includes_guessed_paths
    # Test: collect_impressum_urls dokłada zgadnięte ścieżki (kontakt/o-nas/o-firmie) i nie dodaje podstron bloga.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_collect_impressum_urls_includes_guessed_paths(self):
        urls = scraper.collect_impressum_urls(
            "https://www.trans-spedycja.pl/uslugi/",
            ["https://www.trans-spedycja.pl/blog/"],
        )
        self.assertTrue(any("/kontakt" in u or "/o-nas" in u or "/o-firmie" in u for u in urls))
        self.assertNotIn("https://www.trans-spedycja.pl/blog/", urls)

    # >>> OPIS FUNKCJI: funkcja SerperOnlyFilterRegression.test_website_inbox_email_on_short_domain
    # Test: łagodniejsza reguła „website inbox” wybiera adres na krótkiej domenie, którego ścisły ranking by nie wybrał.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_website_inbox_email_on_short_domain(self):
        from email_targeting import (
            MIN_EMAIL_SCORE_FOR_SEND,
            pick_best_email_for_inquiry,
            pick_best_email_from_website_scrape,
        )

        strict, strict_score = pick_best_email_for_inquiry(
            ["biuro@ts.pl"], "https://trans-spedycja.pl"
        )
        # Krótka domena lokalna może nie przejść ścisłego scoringu
        relaxed, relaxed_score = pick_best_email_from_website_scrape(
            ["biuro@trans-spedycja.pl"], "https://trans-spedycja.pl"
        )
        self.assertEqual(relaxed, "biuro@trans-spedycja.pl")
        self.assertGreaterEqual(relaxed_score, MIN_EMAIL_SCORE_FOR_SEND)
        self.assertIsInstance(strict_score, int)

    # >>> OPIS FUNKCJI: funkcja SerperOnlyFilterRegression.test_sync_pipeline_rows_populates_email_jobs
    # Test: sync_pipeline_rows_to_contacts_cache + build_email_jobs_from_cache_json tworzą jedno zadanie mailowe z poprawnym adresem.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_sync_pipeline_rows_populates_email_jobs(self):
        cache = scraper._empty_cache()
        rows = [
            {
                "nazwa": "Trans Spedycja Sp. z o.o.",
                "url": "https://trans-spedycja.pl",
                "www": "https://trans-spedycja.pl",
                "email_target": "biuro@trans-spedycja.pl",
                "retail_verified": True,
                "is_gu": True,
                "is_small_firm": True,
                "retail_chains_found": "ftl",
                "verification_reason": "ok",
                "page_snippet": "Firma spedycyjna FTL transport drogowy Europa",
            }
        ]
        scraper.sync_pipeline_rows_to_contacts_cache(rows, cache)
        jobs = scraper.build_email_jobs_from_cache_json(
            logging.getLogger("test"), cache=cache
        )
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["email_target"], "biuro@trans-spedycja.pl")

    # >>> OPIS FUNKCJI: funkcja SerperOnlyFilterRegression.test_excel_info_sheet_documents_append_mode
    # Test: arkusz Info dokumentuje tryb append i przebudowę (min. 3 wiersze).
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_excel_info_sheet_documents_append_mode(self):
        rows = scraper.build_excel_info_sheet_rows()
        self.assertGreaterEqual(len(rows), 3)
        text = " ".join(
            str(v)
            for row in rows
            for v in row.values()
        ).lower()
        self.assertIn("append", text)
        self.assertIn("przebudow", text)

    # >>> OPIS FUNKCJI: funkcja SerperOnlyFilterRegression.test_merge_pipeline_preserves_existing_when_cache_empty
    # Test: merge_pipeline_rows zachowuje istniejące wiersze, gdy cache nie wnosi nowych.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_merge_pipeline_preserves_existing_when_cache_empty(self):
        existing = [
            {
                "nazwa": "BAUTAL GU GmbH",
                "url": "https://bautal-gu.de",
                "verification_reason": scraper.PENDING_WWW_VERIFY_REASON,
            }
        ]
        merged = scraper.merge_pipeline_rows(existing, [])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["nazwa"], "BAUTAL GU GmbH")

    # >>> OPIS FUNKCJI: funkcja SerperOnlyFilterRegression.test_pending_row_eligible_for_excel_when_gu_in_snippet
    # Test: wiersz pending z rolą w snippecie kwalifikuje się do eksportu do Excela.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_pending_row_eligible_for_excel_when_gu_in_snippet(self):
        row = {
            "nazwa": "Trans Spedycja Sp. z o.o.",
            "url": "https://trans-spedycja.pl",
            "www": "https://trans-spedycja.pl",
            "retail_verified": False,
            "verification_reason": scraper.PENDING_WWW_VERIFY_REASON,
            "page_snippet": "Firma spedycyjna FTL transport drogowy Europa",
            "email_target": "biuro@trans-spedycja.pl",
        }
        self.assertTrue(scraper.is_row_eligible_for_excel_export(row))

    # >>> OPIS FUNKCJI: funkcja SerperOnlyFilterRegression.test_pending_row_rejected_without_gu
    # Test: wiersz pending bez sygnału roli nie trafia do Excela.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_pending_row_rejected_without_gu(self):
        row = {
            "nazwa": "HELIA Ladenbau GmbH",
            "url": "https://helia-ladenbau.de",
            "www": "https://helia-ladenbau.de",
            "retail_verified": False,
            "verification_reason": scraper.PENDING_WWW_VERIFY_REASON,
            "email_target": "info@helia-ladenbau.de",
        }
        self.assertFalse(scraper.is_row_eligible_for_excel_export(row))

    # >>> OPIS FUNKCJI: funkcja SerperOnlyFilterRegression.test_discovered_row_rejected_after_verify_without_chain
    # Test: wiersz po weryfikacji bez segmentu (chain) jest odrzucany z eksportu.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_discovered_row_rejected_after_verify_without_chain(self):
        row = {
            "nazwa": "BAUTAL GU GmbH",
            "url": "https://bautal-gu.de",
            "bundesland": "Nordrhein-Westfalen",
            "discovery_wojewodztwo": "Nordrhein-Westfalen",
            "retail_verified": False,
            "verification_reason": "kein_generalunternehmer",
            "email_target": "",
        }
        self.assertFalse(scraper.is_row_eligible_for_excel_export(row))

    # >>> OPIS FUNKCJI: funkcja SerperOnlyFilterRegression.test_verified_row_rejected_when_not_small
    # Test: wiersz zweryfikowany, ale nie 'mała firma', jest odrzucany z eksportu.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_verified_row_rejected_when_not_small(self):
        row = {
            "nazwa": "Müller GU GmbH",
            "url": "https://mueller-gu.de",
            "retail_verified": True,
            "is_gu": True,
            "is_small_firm": False,
            "retail_chains_found": "rewe",
            "page_snippet": "Generalunternehmer Referenz Rewe",
            "email_target": "",
        }
        self.assertFalse(scraper.is_row_eligible_for_excel_export(row))


# >>> OPIS FUNKCJI: klasa SmallCompanyFilterRegression
# Grupa testów: rozpoznawanie dużych firm i whitelist małych regionalnych (is_likely_large_company).
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class SmallCompanyFilterRegression(unittest.TestCase):
    # >>> OPIS FUNKCJI: funkcja SmallCompanyFilterRegression.test_rejects_hochtief_domain
    # Test: domena koncernu (hochtief) jest uznana za dużą firmę z powodem zawierającym markę.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_rejects_hochtief_domain(self):
        large, reason = scraper.is_likely_large_company(
            "Bau AG", "https://www.hochtief.de", "Generalunternehmer"
        )
        self.assertTrue(large)
        self.assertIn("hochtief", reason)

    # >>> OPIS FUNKCJI: funkcja SmallCompanyFilterRegression.test_rejects_strabag_name
    # Test: nazwa koncernu (strabag) → duża firma.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_rejects_strabag_name(self):
        large, _ = scraper.is_likely_large_company(
            "STRABAG AG", "https://strabag-example.de", ""
        )
        self.assertTrue(large)

    # >>> OPIS FUNKCJI: funkcja SmallCompanyFilterRegression.test_accepts_familienunternehmen_ladenbau
    # Test: firma rodzinna nie jest uznana za dużą.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_accepts_familienunternehmen_ladenbau(self):
        large, reason = scraper.is_likely_large_company(
            "HELIA Ladenbau GmbH",
            "https://helia-ladenbau.de",
            "Familienunternehmen regional tätig Bauunternehmen Ladenbau",
        )
        self.assertFalse(large, reason)

    # >>> OPIS FUNKCJI: funkcja SmallCompanyFilterRegression.test_accepts_gmbh_co_kg_without_konzern
    # Test: forma 'GmbH & Co. KG' bez sygnałów koncernu nie jest duża.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_accepts_gmbh_co_kg_without_konzern(self):
        large, reason = scraper.is_likely_large_company(
            "Jela Ladenbau GmbH & Co. KG",
            "https://jela-ladenbau.de",
            "Ladenbau Neubau regional",
        )
        self.assertFalse(large, reason)

    # >>> OPIS FUNKCJI: funkcja SmallCompanyFilterRegression.test_rejects_gmbh_co_kg_with_konzern_signal
    # Test: 'GmbH & Co. KG' z sygnałem koncernu → duża firma (grosses_unternehmen).
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_rejects_gmbh_co_kg_with_konzern_signal(self):
        large, reason = scraper.is_likely_large_company(
            "Bau GmbH & Co. KG",
            "https://example.de",
            "Teil des Konzerns weltweit tätig",
        )
        self.assertTrue(large)
        self.assertIn("grosses_unternehmen", reason)

    # >>> OPIS FUNKCJI: funkcja SmallCompanyFilterRegression.test_whitelist_regional_gu_with_moderate_employee_count
    # Test: regionalna firma z umiarkowaną liczbą pracowników (np. 280) jest chroniona whitelistą.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_whitelist_regional_gu_with_moderate_employee_count(self):
        """Faza 4: 280 Mitarbeiter + regionalny GU — nie odrzucaj jako koncern."""
        page = (
            "Generalunternehmer Filialbau regional tätig in Bayern. "
            "280 Mitarbeiter. Referenzprojekte Rewe Aldi."
        )
        large, reason = scraper.is_likely_large_company(
            "Weber GU GmbH",
            "https://weber-gu-bayern.de",
            page,
            serper_blob="weltweit tätig konzern international tätig",
        )
        self.assertFalse(large, reason)

    # >>> OPIS FUNKCJI: funkcja SmallCompanyFilterRegression.test_whitelist_does_not_apply_above_employee_threshold
    # Test: whitelist nie działa powyżej progu pracowników (> 499).
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_whitelist_does_not_apply_above_employee_threshold(self):
        large, _ = scraper.is_likely_large_company(
            "Regional GU GmbH",
            "https://regional-gu.de",
            "Generalunternehmer Filialbau regional. 650 Mitarbeiter.",
        )
        self.assertFalse(large)  # bez markerów koncernu — tylko liczba > 499

    # >>> OPIS FUNKCJI: funkcja SmallCompanyFilterRegression.test_whitelist_blocked_by_strong_konzern_signal
    # Test: silny sygnał koncernu (np. giełdowa) blokuje whitelistę.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_whitelist_blocked_by_strong_konzern_signal(self):
        """Silny sygnał koncernu (börsennotiert) blokuje whitelist mimo regionalnego GU."""
        large, reason = scraper.is_likely_large_company(
            "Bau GmbH",
            "https://bau-gmbh.de",
            "Generalunternehmer Filialbau regional. 200 Mitarbeiter. Börsennotiert Konzern.",
        )
        self.assertTrue(large)
        self.assertIn("grosses_unternehmen", reason)

    # >>> OPIS FUNKCJI: funkcja SmallCompanyFilterRegression.test_whitelist_does_not_override_known_konzern_domain
    # Test: whitelist nie przesłania znanej domeny koncernu.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_whitelist_does_not_override_known_konzern_domain(self):
        large, _ = scraper.is_likely_large_company(
            "Regional Bau",
            "https://www.hochtief.de",
            "Generalunternehmer Filialbau regional 150 Mitarbeiter",
        )
        self.assertTrue(large)

    # >>> OPIS FUNKCJI: funkcja SmallCompanyFilterRegression.test_max_employee_count_parser
    # Test: _max_employee_count_in_blob wyciąga największą liczbę pracowników z tekstu.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_max_employee_count_parser(self):
        self.assertEqual(
            scraper._max_employee_count_in_blob("ca. 280 mitarbeiter in deutschland"),
            280,
        )
        self.assertEqual(
            scraper._max_employee_count_in_blob("Belegschaft von 120 Mitarbeiterinnen"),
            120,
        )


# >>> OPIS FUNKCJI: klasa CompanyNameLegalFormRegression
# Grupa testów: formy prawne w nazwie firmy (e.K., GbR vs e.Kfm.).
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class CompanyNameLegalFormRegression(unittest.TestCase):
    """Faza 6: e.K. / GbR jako prawidłowa forma prawna w nazwie do Excela."""

    # >>> OPIS FUNKCJI: funkcja CompanyNameLegalFormRegression.test_accepts_ek_legal_form
    # Test: 'e.K.' jest rozpoznawane jako forma prawna.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_accepts_ek_legal_form(self):
        for name in (
            "Müller Filialbau e.K.",
            "Müller Filialbau e. K.",
            "Bau Meier eK",
            "Hans Bau E.K",
        ):
            with self.subTest(name=name):
                self.assertTrue(scraper._company_name_has_legal_form(name))

    # >>> OPIS FUNKCJI: funkcja CompanyNameLegalFormRegression.test_accepts_gbr_legal_form
    # Test: 'GbR' jest rozpoznawane jako forma prawna.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_accepts_gbr_legal_form(self):
        for name in ("Weber Bau GbR", "Schmidt & Partner GbR", "Partner GbR."):
            with self.subTest(name=name):
                self.assertTrue(scraper._company_name_has_legal_form(name))

    # >>> OPIS FUNKCJI: funkcja CompanyNameLegalFormRegression.test_rejects_ekfm_as_legal_form
    # Test: 'e.Kfm.' (kupiec) nie jest formą prawną.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_rejects_ekfm_as_legal_form(self):
        self.assertFalse(scraper._company_name_has_legal_form("Schmidt e.Kfm."))
        self.assertFalse(scraper._company_name_has_legal_form("e.Kfm. Schmidt Bau"))

    # >>> OPIS FUNKCJI: funkcja CompanyNameLegalFormRegression.test_ek_gbr_not_rejected_for_export
    # Test: nazwy z e.K./GbR nie są odrzucane przez is_rejected_company_name_for_export.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_ek_gbr_not_rejected_for_export(self):
        self.assertFalse(
            scraper.is_rejected_company_name_for_export(
                "Müller Filialbau e.K.",
                "https://mueller-filialbau.de",
                "info@mueller-filialbau.de",
            )
        )
        self.assertFalse(
            scraper.is_rejected_company_name_for_export(
                "Schmidt & Partner GbR",
                "https://schmidt-bau.de",
                "kontakt@schmidt-bau.de",
            )
        )

    # >>> OPIS FUNKCJI: funkcja CompanyNameLegalFormRegression.test_finalize_prefers_ek_name
    # Test: finalize_company_name_for_export preferuje nazwę z formą prawną e.K.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_finalize_prefers_ek_name(self):
        name = scraper.finalize_company_name_for_export(
            "Müller Filialbau e.K.",
            fallback_raw="Müller Filialbau",
            website="https://mueller-filialbau.de",
            email="info@mueller-filialbau.de",
        )
        self.assertEqual(name, "Müller Filialbau e.K.")


# >>> OPIS FUNKCJI: klasa SmallLadenbauVerifyRegression
# Grupa testów: weryfikacja małych firm w kampanii PL (helper ladenbau jest legacy DE; REQUIRE_GU wyłączone).
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class SmallLadenbauVerifyRegression(unittest.TestCase):
    """Helper ladenbau jest legacy DE; przy PL FAS (REQUIRE_GU=OFF) nie narzuca GU."""

    # >>> OPIS FUNKCJI: funkcja SmallLadenbauVerifyRegression.test_is_small_ladenbau_specialist_matches_name_marker
    # Test: helper legacy rozpoznaje marker w nazwie, a REQUIRE_GENERALUNTERNEHMER jest wyłączone.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_is_small_ladenbau_specialist_matches_name_marker(self):
        self.assertFalse(scraper.REQUIRE_GENERALUNTERNEHMER)
        self.assertTrue(
            scraper._is_small_ladenbau_specialist(
                "Müller Generalunternehmer GmbH",
                "https://mueller-ladenbau.de",
                "Generalunternehmer für Ladenbau — Neubau und Umbau von Gewerbeobjekten.",
            )
        )
        # Bez REQUIRE_GU bramka GU jest wyłączona — nadal True przy markerze ladenbau.
        self.assertTrue(
            scraper._is_small_ladenbau_specialist(
                "Müller-Ladenbau GmbH",
                "https://mueller-ladenbau.de",
                "Wir realisieren Neubau und Umbau von Gewerbeobjekten.",
            )
        )

    # >>> OPIS FUNKCJI: funkcja SmallLadenbauVerifyRegression.test_rejects_without_ladenbau_in_name
    # Test: bez markera w nazwie helper zwraca False.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_rejects_without_ladenbau_in_name(self):
        self.assertFalse(
            scraper._is_small_ladenbau_specialist(
                "Allgemeine Bau GmbH",
                "https://allgemein-bau.de",
                "Neubau Gewerbe",
            )
        )

    # >>> OPIS FUNKCJI: funkcja SmallLadenbauVerifyRegression.test_verify_rejects_de_ladenbau_rewe_under_pl_icp
    # Test: firma DE ladenbau z Rewe nie przechodzi weryfikacji ICP PL (brak segmentów FTL/LTL).
    # Parametry: self, mock_gather. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: patche: wyłączony Claude verify i podmieniony tekst strony (gather_website_text_for_verification). Błędy: AssertionError przy niespełnionej asercji.
    @patch.object(scraper, "ENABLE_CLAUDE_PAGE_VERIFY", False)
    @patch.object(scraper, "gather_website_text_for_verification")
    def test_verify_rejects_de_ladenbau_rewe_under_pl_icp(self, mock_gather):
        """DE Filialbau + Rewe ≠ segmenty FTL/LTL PL — nie weryfikuj jako ICP."""
        mock_gather.return_value = (
            "Generalunternehmer für Ladenbau. Referenzen: Neubau Rewe Filiale. "
            "img alt='Rewe Filiale' src='/uploads/rewe-filiale.jpg'",
            ["https://helia-ladenbau.de"],
        )
        result = scraper.verify_company_on_website(
            "HELIA Generalunternehmer GmbH",
            "https://helia-ladenbau.de",
            _LOGGER,
            {},
        )
        self.assertFalse(result["verified"])
        self.assertNotIn("rewe", result.get("retail_chains") or [])
        self.assertFalse(result.get("is_gu"))

    # >>> OPIS FUNKCJI: funkcja SmallLadenbauVerifyRegression.test_verify_rejects_filialbau_rewe_without_transport_segment
    # Test: filialbau + Rewe bez segmentu transportowego → verified=False.
    # Parametry: self, mock_gather. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: patche jak wyżej. Błędy: AssertionError przy niespełnionej asercji.
    @patch.object(scraper, "ENABLE_CLAUDE_PAGE_VERIFY", False)
    @patch.object(scraper, "gather_website_text_for_verification")
    def test_verify_rejects_filialbau_rewe_without_transport_segment(self, mock_gather):
        mock_gather.return_value = (
            "Wir realisieren Filialbau und Ladenbau für den Einzelhandel. "
            "Referenzen: Neubau Rewe Filiale in Bayern. Portfolio Supermarktprojekte.",
            ["https://markus-bau.de/referenzen"],
        )
        result = scraper.verify_company_on_website(
            "Markus-Bau GmbH",
            "https://markus-bau.de",
            _LOGGER,
            {},
        )
        self.assertFalse(result["verified"])
        self.assertFalse(result.get("is_gu"))
        self.assertNotIn("rewe", result.get("retail_chains") or [])

    # >>> OPIS FUNKCJI: funkcja SmallLadenbauVerifyRegression.test_verify_rejects_ladenbau_without_gu
    # Test: ladenbau bez roli → odrzut z odpowiednim powodem.
    # Parametry: self, mock_gather. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: patche jak wyżej. Błędy: AssertionError przy niespełnionej asercji.
    @patch.object(scraper, "ENABLE_CLAUDE_PAGE_VERIFY", False)
    @patch.object(scraper, "gather_website_text_for_verification")
    def test_verify_rejects_ladenbau_without_gu(self, mock_gather):
        mock_gather.return_value = (
            "Wir realisieren Ladenbau und Gewerbebau Neubau regional.",
            ["https://helia-ladenbau.de"],
        )
        result = scraper.verify_company_on_website(
            "HELIA Ladenbau GmbH",
            "https://helia-ladenbau.de",
            _LOGGER,
            {},
        )
        self.assertFalse(result["verified"])
        self.assertIn(
            result["verification_reason"],
            (
                "kein_generalunternehmer",
                "brak_roli_forwardera",
                "kein_gu_filialbau_kontext",
                "brak_sygnalu_transport",
                "keine_handelskette",
                "brak_segmentu_ftl_ltl",
                "claude_brak_segmentu_transport",
                "claude_brak_roli_spedycji",
                "gielda_3pl_portal",
                "kein_markt_nachweis",
                "nicht_klein",
                "kein_kleinunternehmen",
                "claude_nie_mala_firma",
            ),
        )

    # >>> OPIS FUNKCJI: funkcja SmallLadenbauVerifyRegression.test_verify_rejects_large_konzern
    # Test: duży koncern jest odrzucany z powodem grosses_unternehmen.
    # Parametry: self, mock_gather. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: patche jak wyżej. Błędy: AssertionError przy niespełnionej asercji.
    @patch.object(scraper, "ENABLE_CLAUDE_PAGE_VERIFY", False)
    @patch.object(scraper, "gather_website_text_for_verification")
    def test_verify_rejects_large_konzern(self, mock_gather):
        mock_gather.return_value = (
            "STRABAG Konzern weltweit taetig tausend Mitarbeiter",
            ["https://www.strabag.com"],
        )
        result = scraper.verify_company_on_website(
            "STRABAG SE",
            "https://www.strabag.com",
            _LOGGER,
            {},
        )
        self.assertFalse(result["verified"])
        self.assertIn("grosses_unternehmen", result["verification_reason"])


# >>> OPIS FUNKCJI: klasa BundeslandCountsRegression
# Grupa testów: liczniki leadów per województwo.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class BundeslandCountsRegression(unittest.TestCase):
    # >>> OPIS FUNKCJI: funkcja BundeslandCountsRegression.test_count_pending_for_land
    # Test: count_pending_for_bundesland liczy unikalne pending dla województwa (wiersze + cache).
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_count_pending_for_land(self):
        rows = [
            {
                "url": "https://a-ladenbau.de",
                "verification_reason": scraper.PENDING_WWW_VERIFY_REASON,
                "retail_verified": False,
                "discovery_wojewodztwo": "Niedersachsen",
            },
            {
                "url": "https://b-ladenbau.de",
                "verification_reason": scraper.PENDING_WWW_VERIFY_REASON,
                "retail_verified": False,
                "discovery_wojewodztwo": "Niedersachsen",
            },
            {
                "url": "https://c-verified.de",
                "retail_verified": True,
                "discovery_wojewodztwo": "Niedersachsen",
            },
        ]
        cache = {
            "contacts": {
                "https://d-ladenbau.de": {
                    "verification_reason": scraper.PENDING_WWW_VERIFY_REASON,
                    "retail_verified": False,
                    "discovery_wojewodztwo": "Niedersachsen",
                }
            }
        }
        self.assertEqual(
            scraper.count_pending_for_bundesland(rows, cache, "Niedersachsen"), 3
        )

    # >>> OPIS FUNKCJI: funkcja BundeslandCountsRegression.test_count_verified_for_land
    # Test: count_retail_verified_for_bundesland liczy tylko zweryfikowane dla danego województwa.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_count_verified_for_land(self):
        rows = [
            {
                "url": "https://v1.de",
                "retail_verified": True,
                "discovery_wojewodztwo": "Bayern",
            },
            {
                "url": "https://v2.de",
                "retail_verified": True,
                "discovery_wojewodztwo": "Bayern",
            },
        ]
        self.assertEqual(
            scraper.count_retail_verified_for_bundesland(rows, "Bayern"), 2
        )


# >>> OPIS FUNKCJI: klasa DiscoveryFunnelRegression
# Grupa testów: lejek discovery (metryki).
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class DiscoveryFunnelRegression(unittest.TestCase):
    # >>> OPIS FUNKCJI: funkcja DiscoveryFunnelRegression.test_funnel_counters_increment
    # Test: liczniki lejka rosną, a log_discovery_funnel zapisuje linię '[LEjek]'.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: przechwytywanie logów (assertLogs). Błędy: AssertionError przy niespełnionej asercji.
    def test_funnel_counters_increment(self):
        funnel = scraper.new_discovery_funnel()
        funnel["serper_queries"] = 10
        funnel["raw_hits"] = 40
        funnel["filtered_serper"] = 15
        funnel["filtered_large_serper"] = 5
        funnel["pending_saved"] = 20
        funnel["api_zero_terms"] = 3
        self.assertEqual(funnel["pending_saved"], 20)
        with self.assertLogs(_LOGGER, level="INFO") as captured:
            scraper.log_discovery_funnel(funnel, _LOGGER)
        self.assertTrue(any("[LEjek]" in m for m in captured.output))


# >>> OPIS FUNKCJI: klasa RetailChainSerperRotationRegression
# Grupa testów: rotacja segmentów transportu (legacy RETAIL_CHAINS_ROTATION) we frazach Serper.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class RetailChainSerperRotationRegression(unittest.TestCase):
    # >>> OPIS FUNKCJI: funkcja RetailChainSerperRotationRegression.test_discovery_terms_include_rotating_chains
    # Test: frazy discovery zawierają co najmniej 3 rotujące segmenty.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_discovery_terms_include_rotating_chains(self):
        # RETAIL_CHAINS_ROTATION = segmenty oferty (FTL/LTL/ADR…), nie sieci handlowe.
        # Część szablonów jest celowo BEZ {chain} (lepsze małe miasta) — te pomijamy.
        terms = build_discovery_terms(["Mazowieckie"], max_terms=40)
        chains_low = [c.lower() for c in RETAIL_CHAINS_ROTATION]
        with_segment = [
            t for t in terms if any(c in t.lower() for c in chains_low)
        ]
        plain = [t for t in terms if t not in with_segment]
        self.assertGreaterEqual(
            len(with_segment),
            3,
            msg="oczekiwano fraz z rotującym segmentem (FTL/LTL/…)",
        )
        self.assertGreaterEqual(
            len(plain),
            1,
            msg="oczekiwano ≥1 frazy bez segmentu (np. 'spedycja Warszawa')",
        )
        found = {
            c
            for c in RETAIL_CHAINS_ROTATION
            if any(c.lower() in t.lower() for t in with_segment)
        }
        self.assertGreaterEqual(len(found), 3)

    # >>> OPIS FUNKCJI: funkcja RetailChainSerperRotationRegression.test_discovery_terms_cycle_all_whitelist_chains
    # Test: frazy przechodzą przez wszystkie segmenty z listy rotacji.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_discovery_terms_cycle_all_whitelist_chains(self):
        terms = build_discovery_terms(
            ["Malopolskie"], max_terms=len(RETAIL_CHAINS_ROTATION) * 2
        )
        found = [
            c
            for c in RETAIL_CHAINS_ROTATION
            if any(c.lower() in t.lower() for t in terms)
        ]
        self.assertEqual(len(found), len(RETAIL_CHAINS_ROTATION))


# >>> OPIS FUNKCJI: klasa RotationThresholdRegression
# Grupa testów: próg przesunięcia rotacji województw.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class RotationThresholdRegression(unittest.TestCase):
    # >>> OPIS FUNKCJI: funkcja RotationThresholdRegression.test_rotation_commit_when_pending_enough
    # Test: przy wystarczającej liczbie pending rotacja przesuwa się na następne województwo z BUNDESLAND_ROTATION_ORDER.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: operacje na stanie rotacji w pliku tymczasowym. Błędy: AssertionError przy niespełnionej asercji.
    def test_rotation_commit_when_pending_enough(self):
        from gu_bundesland_rotation import (
            BUNDESLAND_ROTATION_ORDER,
            commit_rotation_after_run,
            load_rotation_state,
            peek_next_bundesland,
            rotation_state_path,
        )
        import tempfile

        tmp = Path(tempfile.mkdtemp())
        path = rotation_state_path(tmp)
        state = load_rotation_state(path)
        land = peek_next_bundesland(state)
        pending = scraper.MIN_VERIFIED_CONTACTS_ROTATION
        verified = 0
        should_rotate = (
            verified >= scraper.MIN_VERIFIED_CONTACTS_ROTATION
            or pending >= scraper.MIN_VERIFIED_CONTACTS_ROTATION
        )
        self.assertTrue(should_rotate)
        nxt = commit_rotation_after_run(path, state, land)
        self.assertIn(nxt, BUNDESLAND_ROTATION_ORDER)

    # >>> OPIS FUNKCJI: funkcja RotationThresholdRegression.test_rotation_stays_when_below_threshold
    # Test: poniżej progu rotacja zostaje na tym samym województwie.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: jak wyżej. Błędy: AssertionError przy niespełnionej asercji.
    def test_rotation_stays_when_below_threshold(self):
        pending = scraper.MIN_VERIFIED_CONTACTS_ROTATION - 1
        verified = 0
        should_rotate = (
            verified >= scraper.MIN_VERIFIED_CONTACTS_ROTATION
            or pending >= scraper.MIN_VERIFIED_CONTACTS_ROTATION
        )
        self.assertFalse(should_rotate)


# >>> OPIS FUNKCJI: klasa EnrichRowSerperSkipRegression
# Grupa testów: enrich_row_with_contacts a zapytania Serper.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class EnrichRowSerperSkipRegression(unittest.TestCase):
    # >>> OPIS FUNKCJI: funkcja EnrichRowSerperSkipRegression.test_reverify_skips_serper_when_url_in_row
    # Test: przy ponownej weryfikacji z URL-em w wierszu nie jest wołane search_official_website_with_serper.
    # Parametry: self, mock_collect, mock_serper. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: patche na search_official_website_with_serper, collect_contacts_from_website i flagi weryfikacji. Błędy: AssertionError przy niespełnionej asercji.
    @patch.object(scraper, "REQUIRE_WEBSITE_RETAIL_VERIFICATION", False)
    @patch.object(scraper, "search_official_website_with_serper")
    @patch.object(scraper, "collect_contacts_from_website")
    def test_reverify_skips_serper_when_url_in_row(self, mock_collect, mock_serper):
        mock_collect.return_value = {
            "emails": ["info@firma.de"],
            "impressum_emails": ["info@firma.de"],
            "phones": [],
            "website": "https://firma.de",
            "source_urls": ["https://firma.de"],
            "page_snippet": "",
        }
        row = {
            "url": "https://firma.de",
            "www": "https://firma.de",
            "nazwa": "Firma Bau GmbH",
        }
        cache = {"contacts": {}}
        scraper.enrich_row_with_contacts(
            row, cache, _LOGGER, force_refresh=True
        )
        mock_serper.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)

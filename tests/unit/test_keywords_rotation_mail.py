# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# MODUŁ TESTOWY: tests/unit/test_keywords_rotation_mail.py
# CO ROBI: testy słów kluczowych PL (pl_spedycja_keywords), rotacji województw i wykrywania hosta SMTP (mail_transport).
# ROLA W PIPELINE: pilnuje konfiguracji discovery i transportu e-mail.
# ZALEŻNOŚCI: pytest, pl_spedycja_keywords, gu_bundesland_rotation, libs.mail_transport, tempfile.
# WEJŚCIE/WYJŚCIE: Moduł nie przyjmuje argumentów CLI; pytest/unittest odkrywa i uruchamia testy; nic nie zwraca (wynik = zielone/czerwone testy).
# ============================================================
"""Testy jednostkowe: pl_spedycja_keywords, rotacja województw, mail_transport."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


# >>> OPIS FUNKCJI: klasa TestPlSpedycjaKeywords
# Grupa testów: słowniki województw, frazy discovery, debug CLI.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestPlSpedycjaKeywords:
    # >>> OPIS FUNKCJI: funkcja TestPlSpedycjaKeywords.test_wojewodztwa_count_and_keys
    # Test: jest 16 województw z kluczami, skrótem i miastami (np. Mazowieckie → Warszawa).
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_wojewodztwa_count_and_keys(self):
        from pl_spedycja_keywords import ALL_BUNDESLAENDER, BUNDESLAND_CONFIG

        assert len(BUNDESLAND_CONFIG) == 16
        assert len(ALL_BUNDESLAENDER) == 16
        assert "Mazowieckie" in BUNDESLAND_CONFIG
        assert "Lodzkie" in BUNDESLAND_CONFIG
        assert "short" in BUNDESLAND_CONFIG["Mazowieckie"]
        assert "Warszawa" in BUNDESLAND_CONFIG["Mazowieckie"]["cities"]

    # >>> OPIS FUNKCJI: funkcja TestPlSpedycjaKeywords.test_normalize_land_aliases
    # Test: aliasy (MZ, łódzkie, śląskie, warmińsko-mazurskie) są normalizowane do kluczy bez polskich znaków.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_normalize_land_aliases(self):
        from pl_spedycja_keywords import _normalize_land_key

        assert _normalize_land_key("MZ") == "Mazowieckie"
        assert _normalize_land_key("łódzkie") == "Lodzkie"
        assert _normalize_land_key("śląskie") == "Slaskie"
        assert _normalize_land_key("warmińsko-mazurskie") == "Warminsko-Mazurskie"

    # >>> OPIS FUNKCJI: funkcja TestPlSpedycjaKeywords.test_resolve_active_aliases_and_fallback
    # Test: resolve_active_bundeslaender rozpoznaje aliasy, a nieznane nazwy (Bayern, NRW) wracają do pełnej listy PL.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_resolve_active_aliases_and_fallback(self):
        from pl_spedycja_keywords import (
            DEFAULT_ACTIVE_BUNDESLAENDER,
            resolve_active_bundeslaender,
        )

        assert resolve_active_bundeslaender(["mz", "śląskie"]) == [
            "Mazowieckie",
            "Slaskie",
        ]
        # Nieznane klucze DE → fallback na pełną listę PL
        assert resolve_active_bundeslaender(["Bayern", "NRW"]) == list(
            DEFAULT_ACTIVE_BUNDESLAENDER
        )

    # >>> OPIS FUNKCJI: funkcja TestPlSpedycjaKeywords.test_default_max_discovery_terms_capped
    # Test: limit fraz rośnie z liczbą miast/powiatów; cała PL obcięta do 8000.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_default_max_discovery_terms_capped(self):
        from pl_spedycja_keywords import (
            ALL_BUNDESLAENDER,
            BUNDESLAND_CONFIG,
            default_max_discovery_terms_for,
        )

        assert len(BUNDESLAND_CONFIG["Mazowieckie"]["cities"]) >= 80
        assert len(BUNDESLAND_CONFIG["Mazowieckie"]["powiaty"]) >= 30
        assert default_max_discovery_terms_for(["Mazowieckie"]) >= 200
        assert default_max_discovery_terms_for(list(ALL_BUNDESLAENDER)) == 8000

    # >>> OPIS FUNKCJI: funkcja TestPlSpedycjaKeywords.test_lodzkie_discovery_terms
    # Test: frazy dla łódzkiego zawierają Łódź/Polska i słowo 'spedycja'.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_lodzkie_discovery_terms(self):
        from pl_spedycja_keywords import build_discovery_terms

        terms = build_discovery_terms(["Lodzkie"], max_terms=96)
        assert len(terms) >= 10
        assert any("Łódź" in t or "Polska" in t or "Lodzkie" in t for t in terms)
        assert any("spedycja" in t.lower() for t in terms)

    # >>> OPIS FUNKCJI: funkcja TestPlSpedycjaKeywords.test_discovery_terms_rotate_segments
    # Test: frazy rotują wszystkie segmenty z RETAIL_CHAINS_ROTATION.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_discovery_terms_rotate_segments(self):
        from pl_spedycja_keywords import RETAIL_CHAINS_ROTATION, build_discovery_terms

        terms = build_discovery_terms(
            ["Mazowieckie"], max_terms=len(RETAIL_CHAINS_ROTATION) * 2
        )
        found = [
            c
            for c in RETAIL_CHAINS_ROTATION
            if any(c.lower() in t.lower() for t in terms)
        ]
        assert len(found) == len(RETAIL_CHAINS_ROTATION)

    # >>> OPIS FUNKCJI: funkcja TestPlSpedycjaKeywords.test_region_suffix_pl
    # Test: sufiks regionu: 'Polska' dla całości/jednego województwa, 'Polska MZ LD' dla dwóch.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_region_suffix_pl(self):
        from pl_spedycja_keywords import ALL_BUNDESLAENDER, build_region_suffix

        assert build_region_suffix(list(ALL_BUNDESLAENDER)) == "Polska"
        assert build_region_suffix(["Mazowieckie"]) == "Polska"
        assert build_region_suffix(["Mazowieckie", "Lodzkie"]) == "Polska MZ LD"

    # >>> OPIS FUNKCJI: funkcja TestPlSpedycjaKeywords.test_fallback_broad_places_landkreis_nonempty
    # Test: listy fraz fallback/broad/powiat/places nie są puste i zawierają miasta/słowa PL.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_fallback_broad_places_landkreis_nonempty(self):
        from pl_spedycja_keywords import (
            build_broad_discovery_terms,
            build_fallback_terms,
            build_landkreis_discovery_terms,
            build_places_discovery_terms,
        )

        active = ["Pomorskie"]
        assert any("Gdańsk" in t or "Pomorskie" in t for t in build_fallback_terms(active))
        assert any("spedycja" in t.lower() for t in build_broad_discovery_terms(active))
        assert any("powiat" in t or "okolice" in t for t in build_landkreis_discovery_terms(active))
        assert any("Gdańsk" in t or "Gdynia" in t for t in build_places_discovery_terms(active))

    # >>> OPIS FUNKCJI: funkcja TestPlSpedycjaKeywords.test_serper_positive_negative_and_segments
    # Test: słowniki pozytywne/negatywne Serper (spedycja, kurier, InPost, TIMOCOM) i segment FTL są obecne.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_serper_positive_negative_and_segments(self):
        from pl_spedycja_keywords import (
            RETAIL_CHAINS_ROTATION,
            SERPER_NEGATIVE_TERMS,
            SERPER_POSITIVE_TERMS,
        )

        assert "spedycja" in SERPER_POSITIVE_TERMS
        assert "FTL" in RETAIL_CHAINS_ROTATION
        assert "kurier" in SERPER_NEGATIVE_TERMS
        assert "InPost" in SERPER_NEGATIVE_TERMS
        assert "TIMOCOM" in SERPER_NEGATIVE_TERMS

    # >>> OPIS FUNKCJI: funkcja TestPlSpedycjaKeywords.test_configure_campaign_reloads_module_lists
    # Test: configure_campaign_bundeslaender przeładowuje listy fraz na obiekcie modułu zgodnie z aktywnymi województwami.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: modyfikuje atrapę modułu w teście. Błędy: AssertionError przy niespełnionej asercji.
    def test_configure_campaign_reloads_module_lists(self):
        from types import SimpleNamespace

        from pl_spedycja_keywords import configure_campaign_bundeslaender

        module = SimpleNamespace()
        active = configure_campaign_bundeslaender(
            module, ["Mazowieckie", "Lodzkie"], max_discovery_terms=80
        )
        assert active == ["Mazowieckie", "Lodzkie"]
        assert module.CAMPAIGN_ACTIVE_BUNDESLAENDER == active
        assert 1 <= len(module.SERPER_DISCOVERY_TERMS) <= 80
        assert module.SERPER_DISCOVERY_FALLBACK_TERMS
        assert module.SERPER_DISCOVERY_BROAD_TERMS
        assert module.SERPER_DISCOVERY_LANDKREIS_TERMS
        assert module.SERPER_DISCOVERY_PLACES_TERMS
        assert "Polska" in module.SERPER_DISCOVERY_REGION_SUFFIX

    # >>> OPIS FUNKCJI: funkcja TestPlSpedycjaKeywords.test_debug_keywords_campaign_snapshot
    # Test: debug_keywords_campaign zwraca snapshot (aktywne województwa, miasta, limit fraz, sufiks, liczby fraz).
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_debug_keywords_campaign_snapshot(self):
        from pl_spedycja_keywords import RETAIL_CHAINS_ROTATION, debug_keywords_campaign

        d = debug_keywords_campaign(["Mazowieckie"], max_terms=40, sample=3)
        assert d["active"] == ["Mazowieckie"]
        assert d["cities_total"] >= 5
        assert d["max_terms"] == 40
        assert d["region_suffix"] == "Polska"
        assert d["counts"]["primary"] == 40
        assert d["counts"]["fallback"] >= 1
        assert d["counts"]["broad"] >= 1
        assert d["counts"]["places"] >= 1
        assert len(d["samples"]["primary"]) == 3
        assert d["segments_in_primary"]
        assert d["segments_coverage"].endswith(f"/{len(RETAIL_CHAINS_ROTATION)}")
        assert d["serper_positive_count"] >= 5
        assert d["serper_negative_count"] >= 5

    # >>> OPIS FUNKCJI: funkcja TestPlSpedycjaKeywords.test_debug_land_key
    # Test: debug_land_key zwraca znormalizowany klucz, skrót i miasta dla znanego województwa oraz known=False dla nieznanego.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_debug_land_key(self):
        from pl_spedycja_keywords import debug_land_key

        ok = debug_land_key("łódzkie")
        assert ok["known"] is True
        assert ok["normalized"] == "Lodzkie"
        assert ok["short"] == "LD"
        assert "Łódź" in ok["cities"]

        bad = debug_land_key("Bayern")
        assert bad["known"] is False
        assert bad["resolve_active"]  # fallback na pełną listę PL

    # >>> OPIS FUNKCJI: funkcja TestPlSpedycjaKeywords.test_cli_debug_json
    # Test: _cli_debug wypisuje JSON i zwraca kod 0.
    # Parametry: self, capsys. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: przechwytywanie stdout (capsys). Błędy: AssertionError przy niespełnionej asercji.
    def test_cli_debug_json(self, capsys):
        from pl_spedycja_keywords import _cli_debug

        assert _cli_debug(["--land-key", "MZ"]) == 0
        out = capsys.readouterr().out
        assert '"normalized": "Mazowieckie"' in out
        assert _cli_debug(["Mazowieckie", "--max-terms", "12", "--sample", "2"]) == 0
        out2 = capsys.readouterr().out
        assert '"primary": 12' in out2


# >>> OPIS FUNKCJI: klasa TestBundeslandRotation
# Grupa testów: rotacja województw.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestBundeslandRotation:
    # >>> OPIS FUNKCJI: funkcja TestBundeslandRotation.test_peek_and_commit
    # Test: peek_next_bundesland zaczyna od Dolnoslaskie, a commit przesuwa rotację na następne województwo.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: stan rotacji w pliku tymczasowym. Błędy: AssertionError przy niespełnionej asercji.
    def test_peek_and_commit(self):
        from gu_bundesland_rotation import (
            BUNDESLAND_ROTATION_ORDER,
            commit_rotation_after_run,
            load_rotation_state,
            peek_next_bundesland,
            rotation_state_path,
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = rotation_state_path(Path(tmp))
            state = load_rotation_state(path)
            assert BUNDESLAND_ROTATION_ORDER[0] == "Dolnoslaskie"
            land = peek_next_bundesland(state)
            assert land == "Dolnoslaskie"
            nxt = commit_rotation_after_run(path, state, land)
            assert nxt == BUNDESLAND_ROTATION_ORDER[1]


# >>> OPIS FUNKCJI: klasa TestMailTransportGmail
# Grupa testów: wykrywanie hosta SMTP.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestMailTransportGmail:
    # >>> OPIS FUNKCJI: funkcja TestMailTransportGmail.test_gmail_host_detection
    # Test: dla MAIL_USER @gmail.com host SMTP to smtp.gmail.com.
    # Parametry: self, monkeypatch. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: monkeypatch zmienia zmienne środowiskowe tylko na czas testu (cofane automatycznie). Błędy: AssertionError przy niespełnionej asercji.
    def test_gmail_host_detection(self, monkeypatch):
        from mail_transport import get_smtp_host

        monkeypatch.setenv("MAIL_USER", "test@gmail.com")
        monkeypatch.delenv("SMTP_HOST", raising=False)
        assert get_smtp_host() == "smtp.gmail.com"

    # >>> OPIS FUNKCJI: funkcja TestMailTransportGmail.test_no_homepl_default_without_gmail
    # Test: dla innej domeny nie jest używany domyślny host home.pl.
    # Parametry: self, monkeypatch. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: monkeypatch zmienia zmienne środowiskowe tylko na czas testu (cofane automatycznie). Błędy: AssertionError przy niespełnionej asercji.
    def test_no_homepl_default_without_gmail(self, monkeypatch):
        from mail_transport import get_smtp_host

        monkeypatch.setenv("MAIL_USER", "kontakt@firma.de")
        monkeypatch.delenv("SMTP_HOST", raising=False)
        host = get_smtp_host()
        assert "home.pl" not in host.lower()

# -*- coding: utf-8 -*-
"""Testy jednostkowe: pl_spedycja_keywords, rotacja województw, mail_transport."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


class TestPlSpedycjaKeywords:
    def test_wojewodztwa_count_and_keys(self):
        from pl_spedycja_keywords import ALL_BUNDESLAENDER, BUNDESLAND_CONFIG

        assert len(BUNDESLAND_CONFIG) == 16
        assert len(ALL_BUNDESLAENDER) == 16
        assert "Mazowieckie" in BUNDESLAND_CONFIG
        assert "Lodzkie" in BUNDESLAND_CONFIG
        assert "short" in BUNDESLAND_CONFIG["Mazowieckie"]
        assert "Warszawa" in BUNDESLAND_CONFIG["Mazowieckie"]["cities"]

    def test_normalize_land_aliases(self):
        from pl_spedycja_keywords import _normalize_land_key

        assert _normalize_land_key("MZ") == "Mazowieckie"
        assert _normalize_land_key("łódzkie") == "Lodzkie"
        assert _normalize_land_key("śląskie") == "Slaskie"
        assert _normalize_land_key("warmińsko-mazurskie") == "Warminsko-Mazurskie"

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

    def test_default_max_discovery_terms_capped(self):
        from pl_spedycja_keywords import (
            ALL_BUNDESLAENDER,
            default_max_discovery_terms_for,
        )

        assert default_max_discovery_terms_for(["Mazowieckie"]) >= 200
        assert default_max_discovery_terms_for(list(ALL_BUNDESLAENDER)) == 1000

    def test_lodzkie_discovery_terms(self):
        from pl_spedycja_keywords import build_discovery_terms

        terms = build_discovery_terms(["Lodzkie"], max_terms=96)
        assert len(terms) >= 10
        assert any("Łódź" in t or "Polska" in t or "Lodzkie" in t for t in terms)
        assert any("spedycja" in t.lower() for t in terms)

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

    def test_region_suffix_pl(self):
        from pl_spedycja_keywords import ALL_BUNDESLAENDER, build_region_suffix

        assert build_region_suffix(list(ALL_BUNDESLAENDER)) == "Polska"
        assert build_region_suffix(["Mazowieckie"]) == "Polska"
        assert build_region_suffix(["Mazowieckie", "Lodzkie"]) == "Polska MZ LD"

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

    def test_cli_debug_json(self, capsys):
        from pl_spedycja_keywords import _cli_debug

        assert _cli_debug(["--land-key", "MZ"]) == 0
        out = capsys.readouterr().out
        assert '"normalized": "Mazowieckie"' in out
        assert _cli_debug(["Mazowieckie", "--max-terms", "12", "--sample", "2"]) == 0
        out2 = capsys.readouterr().out
        assert '"primary": 12' in out2


class TestBundeslandRotation:
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


class TestMailTransportGmail:
    def test_gmail_host_detection(self, monkeypatch):
        from mail_transport import get_smtp_host

        monkeypatch.setenv("MAIL_USER", "test@gmail.com")
        monkeypatch.delenv("SMTP_HOST", raising=False)
        assert get_smtp_host() == "smtp.gmail.com"

    def test_no_homepl_default_without_gmail(self, monkeypatch):
        from mail_transport import get_smtp_host

        monkeypatch.setenv("MAIL_USER", "kontakt@firma.de")
        monkeypatch.delenv("SMTP_HOST", raising=False)
        host = get_smtp_host()
        assert "home.pl" not in host.lower()

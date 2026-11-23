# -*- coding: utf-8 -*-
"""Testy jednostkowe: scraper_run_config (load / apply / launch / debug)."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scraper_run_config import (
    _cli_debug,
    apply_run_config_file,
    debug_run_config,
    load_run_config_file,
    run_scraper_launch_kwargs,
)

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def _stub(**overrides):
    base = SimpleNamespace(
        CUSTOM_EMAIL_LANG="",
        SERPER_LANGUAGE="",
        CUSTOM_EMAIL_CITY="",
        INQUIRY_REGION_DE="",
        ENABLE_AUTO_EMAIL=True,
        MIN_CONTACTS_TARGET=0,
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


class TestLoadRunConfig:
    def test_load_pl_fas_spedycja(self):
        data = load_run_config_file("run_config/pl_fas_spedycja.json", ROOT)
        assert data["config_type"] == "pl_spedycja"
        assert data["lang"] == "pl"
        assert data["active_bundeslaender"][0] == "Dolnoslaskie"
        assert len(data["active_bundeslaender"]) == 16

    def test_load_rejects_non_object(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("[1, 2]", encoding="utf-8")
        with pytest.raises(ValueError, match="JSON object"):
            load_run_config_file(bad, tmp_path)


class TestApplyAndLaunch:
    def test_apply_sets_common_attrs(self, tmp_path):
        cfg = tmp_path / "cfg.json"
        cfg.write_text(
            json.dumps(
                {
                    "config_type": "pl_spedycja",
                    "lang": "pl",
                    "city_name": "Głogów",
                    "enable_auto_email": False,
                    "min_contacts_target": 42,
                    "discovery_mode": "serper_only",
                    "max_new_rows": "15",
                    "dry_run_email": True,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        mod = _stub()
        data = apply_run_config_file(mod, cfg, tmp_path)
        assert data["lang"] == "pl"
        assert mod._RUN_CONFIG_TYPE == "pl_spedycja"
        assert mod.CUSTOM_EMAIL_LANG == "pl"
        assert mod.SERPER_LANGUAGE == "pl"
        assert mod.CUSTOM_EMAIL_CITY == "Głogów"
        assert mod.ENABLE_AUTO_EMAIL is False
        assert mod.MIN_CONTACTS_TARGET == 42

        kw = run_scraper_launch_kwargs(mod)
        assert kw["enable_auto_email"] is False
        assert kw["dry_run_email"] is True
        assert kw["discovery_mode"] == "serper_only"
        assert kw["max_new_rows"] == 15

    def test_launch_kwargs_fallback_enable_auto_email(self):
        mod = _stub(ENABLE_AUTO_EMAIL=False)
        mod._RUN_CONFIG_DATA = {}
        kw = run_scraper_launch_kwargs(mod)
        assert kw["enable_auto_email"] is False

    def test_apply_skips_blank_strings(self, tmp_path):
        cfg = tmp_path / "cfg.json"
        cfg.write_text(
            json.dumps({"lang": "  ", "city_name": "Warszawa"}),
            encoding="utf-8",
        )
        mod = _stub(CUSTOM_EMAIL_LANG="keep", SERPER_LANGUAGE="keep")
        apply_run_config_file(mod, cfg, tmp_path)
        assert mod.CUSTOM_EMAIL_LANG == "keep"
        assert mod.CUSTOM_EMAIL_CITY == "Warszawa"


class TestDebugRunConfig:
    def test_debug_pl_fas_snapshot(self):
        d = debug_run_config("run_config/pl_fas_spedycja.json", ROOT)
        assert d["config_type"] == "pl_spedycja"
        assert d["lang"] == "pl"
        assert d["active_bundeslaender_count"] == 16
        assert d["active_bundeslaender_head"][0] == "Dolnoslaskie"
        assert d["module_attrs"]["CUSTOM_EMAIL_LANG"] == "pl"
        assert d["module_attrs"]["ENABLE_AUTO_EMAIL"] is False
        assert "active_bundeslaender" in d["keys_for_gu_extras"]
        assert "enable_claude_discovery_terms" in d["keys_for_gu_extras"]
        assert "enable_auto_email" in d["launch_kwargs"]

    def test_cli_debug_json(self, capsys):
        assert _cli_debug(["run_config/pl_fas_spedycja.json", "--base-dir", str(ROOT)]) == 0
        out = capsys.readouterr().out
        assert '"config_type": "pl_spedycja"' in out
        assert '"Dolnoslaskie"' in out


class TestApplyGuRunConfigExtrasIcp:
    def test_pl_fas_json_sets_segment_and_small_firm_flags(self):
        from pl_fas_spedycja_scraper import apply_gu_run_config_extras

        data = load_run_config_file("run_config/pl_fas_spedycja.json", ROOT)
        assert data["require_named_retail_chain"] is True
        assert data["require_small_firm"] is True
        mod = SimpleNamespace(
            REQUIRE_NAMED_RETAIL_CHAIN=False,
            REQUIRE_SMALL_FIRM=False,
            REQUIRE_WEBSITE_RETAIL_VERIFICATION=False,
            REQUIRE_WEBSITE_REFERENCES_OR_PORTFOLIO=True,
            REQUIRE_MARKET_PROJECTS_IN_PORTFOLIO=True,
            REQUIRE_GENERALUNTERNEHMER=True,
            REQUIRE_FORWARDER_ROLE=True,
            ENABLE_REGION_PLZ_FILTER=True,
            ENABLE_DISTANCE_FROM_REGION_KM=True,
            ENABLE_PLZ_PREFIX_REGION_MATCH=True,
            _pl_spedycja_filter=None,
        )
        apply_gu_run_config_extras(mod, data)
        assert mod.REQUIRE_NAMED_RETAIL_CHAIN is True
        assert mod.REQUIRE_SMALL_FIRM is True
        assert mod.REQUIRE_WEBSITE_RETAIL_VERIFICATION is True
        assert mod.REQUIRE_WEBSITE_REFERENCES_OR_PORTFOLIO is False
        assert mod.REQUIRE_MARKET_PROJECTS_IN_PORTFOLIO is False
        assert mod.REQUIRE_GENERALUNTERNEHMER is False

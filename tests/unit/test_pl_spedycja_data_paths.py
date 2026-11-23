# -*- coding: utf-8 -*-
"""Testy jednostkowe: pl_spedycja_data_paths (lokalne Wyniki, folder Excela Drive)."""
from __future__ import annotations

from pathlib import Path

import pytest

from pl_spedycja_data_paths import (
    GOOGLE_DRIVE_FAS_FOLDER_ID,
    GOOGLE_DRIVE_FAS_FOLDER_URL,
    GOOGLE_DRIVE_GU_FOLDER_ID,
    GOOGLE_DRIVE_GU_FOLDER_URL,
    _cli_debug,
    campaign_output_paths,
    debug_data_paths,
    resolve_data_root,
    wyniki_dir,
)

pytestmark = pytest.mark.unit


class TestExcelDriveFolder:
    def test_final_excel_folder_id(self):
        assert GOOGLE_DRIVE_FAS_FOLDER_ID == "1bRCAqle6BS46YEw0fScq4P095LsJUSgL"
        assert GOOGLE_DRIVE_FAS_FOLDER_ID in GOOGLE_DRIVE_FAS_FOLDER_URL
        assert GOOGLE_DRIVE_GU_FOLDER_ID is GOOGLE_DRIVE_FAS_FOLDER_ID
        assert GOOGLE_DRIVE_GU_FOLDER_URL is GOOGLE_DRIVE_FAS_FOLDER_URL


class TestResolveDataRootLocalOnly:
    def test_defaults_to_campaign_dir(self, tmp_path, monkeypatch):
        monkeypatch.delenv("KANBUD_DATA_DIR", raising=False)
        monkeypatch.delenv("KANBUD_GOOGLE_DRIVE_GU_PATH", raising=False)
        assert resolve_data_root(tmp_path) == tmp_path.resolve()

    def test_ignores_google_drive_env(self, tmp_path, monkeypatch):
        fake_drive = tmp_path / "My Drive" / "PL Spedycja Wyniki"
        fake_drive.mkdir(parents=True)
        monkeypatch.delenv("KANBUD_DATA_DIR", raising=False)
        monkeypatch.setenv("KANBUD_GOOGLE_DRIVE_GU_PATH", str(fake_drive))
        assert resolve_data_root(tmp_path) == tmp_path.resolve()

    def test_kanbud_data_dir_override(self, tmp_path, monkeypatch):
        data = tmp_path / "data"
        data.mkdir()
        camp = tmp_path / "camp"
        camp.mkdir()
        monkeypatch.setenv("KANBUD_DATA_DIR", str(data))
        assert resolve_data_root(camp) == data.resolve()


class TestCampaignOutputPaths:
    def test_pl_spedycja_paths_under_wyniki(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KANBUD_DATA_DIR", str(tmp_path))
        paths = campaign_output_paths(tmp_path, "pl_spedycja")
        assert paths["cache_file"] == wyniki_dir(tmp_path.resolve()) / "pl_spedycja_cache.json"
        assert paths["log_file"].name == "pl_spedycja_scraper.log"
        assert paths["output_file"].name == "pl_spedycja_kontakte.xlsx"
        assert paths["cache_file"].is_relative_to(tmp_path.resolve())
        assert "Google Drive" not in str(paths["cache_file"])
        assert "My Drive" not in str(paths["log_file"])


class TestDebugDataPaths:
    def test_debug_snapshot_local(self, tmp_path, monkeypatch):
        monkeypatch.delenv("KANBUD_DATA_DIR", raising=False)
        d = debug_data_paths(tmp_path, basename="pl_spedycja", apply_env=False)
        assert d["resolved_data_root"] == str(tmp_path.resolve())
        assert d["looks_like_google_drive_path"] is False
        assert d["cache_and_log_on_drive"] is False
        assert d["paths"]["cache_file"].endswith("pl_spedycja_cache.json")
        assert d["excel_drive_upload"]["folder_id"] == GOOGLE_DRIVE_FAS_FOLDER_ID
        assert "1bRCAq" in d["excel_drive_upload"]["folder_url"]

    def test_cli_debug_json(self, tmp_path, monkeypatch, capsys):
        monkeypatch.delenv("KANBUD_DATA_DIR", raising=False)
        assert _cli_debug([str(tmp_path), "--basename", "pl_spedycja"]) == 0
        out = capsys.readouterr().out
        assert '"cache_and_log_on_drive": false' in out
        assert "pl_spedycja_cache.json" in out


class TestLegacyShim:
    def test_campaign_data_paths_reexports(self):
        import campaign_data_paths as legacy
        import pl_spedycja_data_paths as neu

        assert legacy.GOOGLE_DRIVE_FAS_FOLDER_ID == neu.GOOGLE_DRIVE_FAS_FOLDER_ID
        assert legacy.GOOGLE_DRIVE_GU_FOLDER_ID == neu.GOOGLE_DRIVE_FAS_FOLDER_ID
        assert legacy.resolve_data_root is neu.resolve_data_root

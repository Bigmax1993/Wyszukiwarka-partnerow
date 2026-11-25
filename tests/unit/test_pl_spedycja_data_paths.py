# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# MODUŁ TESTOWY: tests/unit/test_pl_spedycja_data_paths.py
# CO ROBI: testy ścieżek danych kampanii: lokalne Wyniki, ignorowanie Dysku Google dla cache/logów, ID folderu Excela i shim campaign_data_paths.
# ROLA W PIPELINE: pilnuje, że cache i logi zostają lokalnie, a na Drive trafia tylko końcowy Excel.
# ZALEŻNOŚCI: pytest (tmp_path, monkeypatch, capsys), pl_spedycja_data_paths, campaign_data_paths (shim).
# WEJŚCIE/WYJŚCIE: Moduł nie przyjmuje argumentów CLI; pytest/unittest odkrywa i uruchamia testy; nic nie zwraca (wynik = zielone/czerwone testy).
# ============================================================
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


# >>> OPIS FUNKCJI: klasa TestExcelDriveFolder
# Grupa testów: ID folderu Drive.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestExcelDriveFolder:
    # >>> OPIS FUNKCJI: funkcja TestExcelDriveFolder.test_final_excel_folder_id
    # Test: ID folderu końcowego Excela jest stałe, zawarte w URL-u, a aliasy GU wskazują na FAS.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_final_excel_folder_id(self):
        assert GOOGLE_DRIVE_FAS_FOLDER_ID == "1bRCAqle6BS46YEw0fScq4P095LsJUSgL"
        assert GOOGLE_DRIVE_FAS_FOLDER_ID in GOOGLE_DRIVE_FAS_FOLDER_URL
        assert GOOGLE_DRIVE_GU_FOLDER_ID is GOOGLE_DRIVE_FAS_FOLDER_ID
        assert GOOGLE_DRIVE_GU_FOLDER_URL is GOOGLE_DRIVE_FAS_FOLDER_URL


# >>> OPIS FUNKCJI: klasa TestResolveDataRootLocalOnly
# Grupa testów: katalog danych tylko lokalny.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestResolveDataRootLocalOnly:
    # >>> OPIS FUNKCJI: funkcja TestResolveDataRootLocalOnly.test_defaults_to_campaign_dir
    # Test: bez zmiennych env katalog danych = katalog kampanii.
    # Parametry: self, tmp_path, monkeypatch. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: monkeypatch zmienia zmienne środowiskowe tylko na czas testu (cofane automatycznie). Błędy: AssertionError przy niespełnionej asercji.
    def test_defaults_to_campaign_dir(self, tmp_path, monkeypatch):
        monkeypatch.delenv("KANBUD_DATA_DIR", raising=False)
        monkeypatch.delenv("KANBUD_GOOGLE_DRIVE_GU_PATH", raising=False)
        assert resolve_data_root(tmp_path) == tmp_path.resolve()

    # >>> OPIS FUNKCJI: funkcja TestResolveDataRootLocalOnly.test_ignores_google_drive_env
    # Test: zmienna KANBUD_GOOGLE_DRIVE_GU_PATH jest ignorowana.
    # Parametry: self, tmp_path, monkeypatch. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: monkeypatch zmienia zmienne środowiskowe tylko na czas testu (cofane automatycznie). Błędy: AssertionError przy niespełnionej asercji.
    def test_ignores_google_drive_env(self, tmp_path, monkeypatch):
        fake_drive = tmp_path / "My Drive" / "PL Spedycja Wyniki"
        fake_drive.mkdir(parents=True)
        monkeypatch.delenv("KANBUD_DATA_DIR", raising=False)
        monkeypatch.setenv("KANBUD_GOOGLE_DRIVE_GU_PATH", str(fake_drive))
        assert resolve_data_root(tmp_path) == tmp_path.resolve()

    # >>> OPIS FUNKCJI: funkcja TestResolveDataRootLocalOnly.test_kanbud_data_dir_override
    # Test: KANBUD_DATA_DIR nadpisuje katalog danych.
    # Parametry: self, tmp_path, monkeypatch. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: monkeypatch zmienia zmienne środowiskowe tylko na czas testu (cofane automatycznie). Błędy: AssertionError przy niespełnionej asercji.
    def test_kanbud_data_dir_override(self, tmp_path, monkeypatch):
        data = tmp_path / "data"
        data.mkdir()
        camp = tmp_path / "camp"
        camp.mkdir()
        monkeypatch.setenv("KANBUD_DATA_DIR", str(data))
        assert resolve_data_root(camp) == data.resolve()


# >>> OPIS FUNKCJI: klasa TestCampaignOutputPaths
# Grupa testów: ścieżki wyjściowe kampanii.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestCampaignOutputPaths:
    # >>> OPIS FUNKCJI: funkcja TestCampaignOutputPaths.test_pl_spedycja_paths_under_wyniki
    # Test: cache, log i Excel leżą pod Wyniki/ z nazwami pl_spedycja_*.
    # Parametry: self, tmp_path, monkeypatch. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: monkeypatch zmienia zmienne środowiskowe tylko na czas testu (cofane automatycznie). Błędy: AssertionError przy niespełnionej asercji.
    def test_pl_spedycja_paths_under_wyniki(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KANBUD_DATA_DIR", str(tmp_path))
        paths = campaign_output_paths(tmp_path, "pl_spedycja")
        assert paths["cache_file"] == wyniki_dir(tmp_path.resolve()) / "pl_spedycja_cache.json"
        assert paths["log_file"].name == "pl_spedycja_scraper.log"
        assert paths["output_file"].name == "pl_spedycja_kontakte.xlsx"
        assert paths["cache_file"].is_relative_to(tmp_path.resolve())
        assert "Google Drive" not in str(paths["cache_file"])
        assert "My Drive" not in str(paths["log_file"])


# >>> OPIS FUNKCJI: klasa TestDebugDataPaths
# Grupa testów: diagnostyka ścieżek.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestDebugDataPaths:
    # >>> OPIS FUNKCJI: funkcja TestDebugDataPaths.test_debug_snapshot_local
    # Test: snapshot debug wskazuje ścieżki lokalne (cache_and_log_on_drive=False) i folder Excela na Drive.
    # Parametry: self, tmp_path, monkeypatch. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: monkeypatch zmienia zmienne środowiskowe tylko na czas testu (cofane automatycznie). Błędy: AssertionError przy niespełnionej asercji.
    def test_debug_snapshot_local(self, tmp_path, monkeypatch):
        monkeypatch.delenv("KANBUD_DATA_DIR", raising=False)
        d = debug_data_paths(tmp_path, basename="pl_spedycja", apply_env=False)
        assert d["resolved_data_root"] == str(tmp_path.resolve())
        assert d["looks_like_google_drive_path"] is False
        assert d["cache_and_log_on_drive"] is False
        assert d["paths"]["cache_file"].endswith("pl_spedycja_cache.json")
        assert d["excel_drive_upload"]["folder_id"] == GOOGLE_DRIVE_FAS_FOLDER_ID
        assert "1bRCAq" in d["excel_drive_upload"]["folder_url"]

    # >>> OPIS FUNKCJI: funkcja TestDebugDataPaths.test_cli_debug_json
    # Test: _cli_debug wypisuje JSON i zwraca 0.
    # Parametry: self, tmp_path, monkeypatch, capsys. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: monkeypatch zmienia zmienne środowiskowe tylko na czas testu (cofane automatycznie); przechwytywanie stdout. Błędy: AssertionError przy niespełnionej asercji.
    def test_cli_debug_json(self, tmp_path, monkeypatch, capsys):
        monkeypatch.delenv("KANBUD_DATA_DIR", raising=False)
        assert _cli_debug([str(tmp_path), "--basename", "pl_spedycja"]) == 0
        out = capsys.readouterr().out
        assert '"cache_and_log_on_drive": false' in out
        assert "pl_spedycja_cache.json" in out


# >>> OPIS FUNKCJI: klasa TestLegacyShim
# Grupa testów: shim campaign_data_paths.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestLegacyShim:
    # >>> OPIS FUNKCJI: funkcja TestLegacyShim.test_campaign_data_paths_reexports
    # Test: moduł legacy re-eksportuje te same stałe i funkcje.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_campaign_data_paths_reexports(self):
        import campaign_data_paths as legacy
        import pl_spedycja_data_paths as neu

        assert legacy.GOOGLE_DRIVE_FAS_FOLDER_ID == neu.GOOGLE_DRIVE_FAS_FOLDER_ID
        assert legacy.GOOGLE_DRIVE_GU_FOLDER_ID == neu.GOOGLE_DRIVE_FAS_FOLDER_ID
        assert legacy.resolve_data_root is neu.resolve_data_root

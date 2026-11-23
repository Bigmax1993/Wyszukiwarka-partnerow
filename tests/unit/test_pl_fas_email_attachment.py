# -*- coding: utf-8 -*-
"""Testy jednostkowe: pl_fas_email_attachment (załącznik Drive / FAS)."""
from __future__ import annotations

import logging
from pathlib import Path

import pytest

from pl_fas_email_attachment import (
    ATTACHMENT_EXTRA_FILENAME,
    ATTACHMENT_FILENAME,
    EMAIL_ATTACHMENT_DRIVE_FILE_ID,
    EMAIL_ATTACHMENT_DRIVE_URL,
    EMAIL_ATTACHMENT_EXTRA_DRIVE_FILE_ID,
    EMAIL_ATTACHMENT_EXTRA_DRIVE_URL,
    GOOGLE_SLIDES_PRESENTATION_ID,
    _download_attachment_pptx,
    _download_slides_pptx,
    ensure_fas_email_attachment,
    ensure_fas_email_attachments,
    ensure_mfg_email_attachment,
    resolve_fas_email_attachment,
    resolve_mfg_email_attachment,
)

pytestmark = pytest.mark.unit

_LOG = logging.getLogger("test_pl_fas_email_attachment")


class TestAttachmentConstants:
    def test_drive_file_id_is_fas_client_file(self):
        assert EMAIL_ATTACHMENT_DRIVE_FILE_ID == "1t6m-M49t4w0RuLzc8rWebwjldLUMMRW3"
        assert EMAIL_ATTACHMENT_DRIVE_FILE_ID in EMAIL_ATTACHMENT_DRIVE_URL
        assert EMAIL_ATTACHMENT_DRIVE_FILE_ID == GOOGLE_SLIDES_PRESENTATION_ID

    def test_extra_presentation_drive_id(self):
        assert EMAIL_ATTACHMENT_EXTRA_DRIVE_FILE_ID == "164qbEQOTyO8VTgfZr2wtIVTY-zttk6u7"
        assert EMAIL_ATTACHMENT_EXTRA_DRIVE_FILE_ID in EMAIL_ATTACHMENT_EXTRA_DRIVE_URL
        assert ATTACHMENT_EXTRA_FILENAME.endswith((".pptx", ".pdf", ".docx"))

    def test_default_local_filename(self):
        assert ATTACHMENT_FILENAME.endswith((".pptx", ".pdf", ".docx"))
        assert "FAS" in ATTACHMENT_FILENAME or "zalacznik" in ATTACHMENT_FILENAME.lower()

    def test_mfg_aliases_point_to_fas(self):
        assert resolve_mfg_email_attachment is resolve_fas_email_attachment
        assert ensure_mfg_email_attachment is ensure_fas_email_attachment
        assert _download_slides_pptx is _download_attachment_pptx
        assert GOOGLE_SLIDES_PRESENTATION_ID == EMAIL_ATTACHMENT_DRIVE_FILE_ID


def _clear_attachment_env(monkeypatch):
    monkeypatch.delenv("FAS_EMAIL_ATTACHMENT_PATH", raising=False)
    monkeypatch.delenv("FAS_EMAIL_ATTACHMENT_EXTRA_PATH", raising=False)
    monkeypatch.delenv("MFG_EMAIL_ATTACHMENT_PATH", raising=False)


class TestResolveAttachment:
    def test_fas_env_path_wins(self, tmp_path, monkeypatch):
        f = tmp_path / "oferta.pptx"
        f.write_bytes(b"x" * 2000)
        _clear_attachment_env(monkeypatch)
        monkeypatch.setenv("FAS_EMAIL_ATTACHMENT_PATH", str(f))
        assert resolve_fas_email_attachment(tmp_path) == f

    def test_mfg_env_alias_still_works(self, tmp_path, monkeypatch):
        f = tmp_path / "legacy.pptx"
        f.write_bytes(b"x" * 2000)
        _clear_attachment_env(monkeypatch)
        monkeypatch.setenv("MFG_EMAIL_ATTACHMENT_PATH", str(f))
        assert resolve_fas_email_attachment(tmp_path) == f

    def test_fas_env_preferred_over_mfg(self, tmp_path, monkeypatch):
        fas = tmp_path / "fas.pptx"
        mfg = tmp_path / "mfg.pptx"
        fas.write_bytes(b"f" * 2000)
        mfg.write_bytes(b"m" * 2000)
        _clear_attachment_env(monkeypatch)
        monkeypatch.setenv("FAS_EMAIL_ATTACHMENT_PATH", str(fas))
        monkeypatch.setenv("MFG_EMAIL_ATTACHMENT_PATH", str(mfg))
        assert resolve_fas_email_attachment(tmp_path) == fas

    def test_cache_in_wyniki(self, tmp_path, monkeypatch):
        _clear_attachment_env(monkeypatch)
        monkeypatch.setenv("KANBUD_DATA_DIR", str(tmp_path))
        wyniki = tmp_path / "Wyniki"
        wyniki.mkdir()
        cached = wyniki / ATTACHMENT_FILENAME
        cached.write_bytes(b"y" * 2000)
        assert resolve_fas_email_attachment(tmp_path) == cached

    def test_bundled_assets(self, tmp_path, monkeypatch):
        _clear_attachment_env(monkeypatch)
        monkeypatch.setenv("KANBUD_DATA_DIR", str(tmp_path))
        (tmp_path / "Wyniki").mkdir(exist_ok=True)
        assets = tmp_path / "assets" / "campaign"
        assets.mkdir(parents=True)
        bundled = assets / ATTACHMENT_FILENAME
        bundled.write_bytes(b"z" * 2000)
        assert resolve_fas_email_attachment(tmp_path) == bundled

    def test_missing_returns_none(self, tmp_path, monkeypatch):
        _clear_attachment_env(monkeypatch)
        monkeypatch.setenv("KANBUD_DATA_DIR", str(tmp_path))
        (tmp_path / "Wyniki").mkdir(exist_ok=True)
        assert resolve_fas_email_attachment(tmp_path) is None

    def test_ignores_mfg_legacy_asset_paths(self, tmp_path, monkeypatch):
        """Krok 2: MFG Referenzliste / Fliesenboden nie są w hot path."""
        import pl_fas_email_attachment as mod

        _clear_attachment_env(monkeypatch)
        monkeypatch.setenv("KANBUD_DATA_DIR", str(tmp_path))
        (tmp_path / "Wyniki").mkdir(exist_ok=True)
        assets = tmp_path / "assets" / "campaign"
        assets.mkdir(parents=True)
        mfg = assets / "MFG_Referenzliste_Einzelhandel.pptx"
        mfg.write_bytes(b"m" * 2000)
        assert not hasattr(mod, "LEGACY_ATTACHMENT_PATH")
        assert resolve_fas_email_attachment(tmp_path) is None


class TestEnsureAttachment:
    def test_ensure_returns_existing_without_download(self, tmp_path, monkeypatch):
        f = tmp_path / "local.pptx"
        f.write_bytes(b"a" * 1500)
        _clear_attachment_env(monkeypatch)
        monkeypatch.setenv("FAS_EMAIL_ATTACHMENT_PATH", str(f))
        called = {"n": 0}

        def boom(*_a, **_k):
            called["n"] += 1
            return False

        monkeypatch.setattr("pl_fas_email_attachment._download_attachment_pptx", boom)
        assert ensure_fas_email_attachment(tmp_path, _LOG) == f
        assert called["n"] == 0

    def test_ensure_tries_download_when_missing(self, tmp_path, monkeypatch):
        _clear_attachment_env(monkeypatch)
        monkeypatch.setenv("KANBUD_DATA_DIR", str(tmp_path))
        (tmp_path / "Wyniki").mkdir(exist_ok=True)

        def fake_download(dest: Path, logger=None, **_kw) -> bool:
            dest.write_bytes(b"d" * 2000)
            return True

        monkeypatch.setattr(
            "pl_fas_email_attachment._download_attachment_pptx", fake_download
        )
        out = ensure_fas_email_attachment(tmp_path, _LOG)
        assert out is not None
        assert out.is_file()
        assert out.stat().st_size >= 2000

    def test_ensure_attachments_returns_both(self, tmp_path, monkeypatch):
        _clear_attachment_env(monkeypatch)
        oferta = tmp_path / "oferta.pptx"
        prez = tmp_path / "prez.pptx"
        oferta.write_bytes(b"a" * 1500)
        prez.write_bytes(b"b" * 1500)
        monkeypatch.setenv("FAS_EMAIL_ATTACHMENT_PATH", str(oferta))
        monkeypatch.setenv("FAS_EMAIL_ATTACHMENT_EXTRA_PATH", str(prez))
        out = ensure_fas_email_attachments(tmp_path, _LOG)
        assert len(out) == 2
        assert out[0] == oferta
        assert out[1] == prez


class TestLegacyShim:
    def test_shim_module_reexports(self):
        import fas_email_attachment as mid
        import mfg_gu_email_attachment as legacy
        import pl_fas_email_attachment as neu

        assert mid.resolve_fas_email_attachment is neu.resolve_fas_email_attachment
        assert legacy.resolve_fas_email_attachment is neu.resolve_fas_email_attachment
        assert legacy.ensure_mfg_email_attachment is neu.ensure_fas_email_attachment

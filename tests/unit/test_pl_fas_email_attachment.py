# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# MODUŁ TESTOWY: tests/unit/test_pl_fas_email_attachment.py
# CO ROBI: testy modułu pl_fas_email_attachment: stałe ID plików Drive, rozwiązywanie ścieżki załącznika (env, cache Wyniki, zasoby), pobieranie i shim legacy.
# ROLA W PIPELINE: chroni dostępność załączników PPTX wymaganych przy wysyłce B2B.
# ZALEŻNOŚCI: pytest (tmp_path, monkeypatch), pl_fas_email_attachment oraz shimy fas_email_attachment / mfg_gu_email_attachment.
# WEJŚCIE/WYJŚCIE: Moduł nie przyjmuje argumentów CLI; pytest/unittest odkrywa i uruchamia testy; nic nie zwraca (wynik = zielone/czerwone testy).
# ============================================================
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


# >>> OPIS FUNKCJI: klasa TestAttachmentConstants
# Grupa testów: stałe załączników.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestAttachmentConstants:
    # >>> OPIS FUNKCJI: funkcja TestAttachmentConstants.test_drive_file_id_is_fas_client_file
    # Test: ID pliku Drive załącznika oferty jest stałe, zawarte w URL-u i równe GOOGLE_SLIDES_PRESENTATION_ID (alias).
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_drive_file_id_is_fas_client_file(self):
        assert EMAIL_ATTACHMENT_DRIVE_FILE_ID == "1t6m-M49t4w0RuLzc8rWebwjldLUMMRW3"
        assert EMAIL_ATTACHMENT_DRIVE_FILE_ID in EMAIL_ATTACHMENT_DRIVE_URL
        assert EMAIL_ATTACHMENT_DRIVE_FILE_ID == GOOGLE_SLIDES_PRESENTATION_ID

    # >>> OPIS FUNKCJI: funkcja TestAttachmentConstants.test_extra_presentation_drive_id
    # Test: ID dodatkowej prezentacji jest stałe, zawarte w URL-u, a nazwa pliku ma rozszerzenie pptx/pdf/docx.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_extra_presentation_drive_id(self):
        assert EMAIL_ATTACHMENT_EXTRA_DRIVE_FILE_ID == "164qbEQOTyO8VTgfZr2wtIVTY-zttk6u7"
        assert EMAIL_ATTACHMENT_EXTRA_DRIVE_FILE_ID in EMAIL_ATTACHMENT_EXTRA_DRIVE_URL
        assert ATTACHMENT_EXTRA_FILENAME.endswith((".pptx", ".pdf", ".docx"))

    # >>> OPIS FUNKCJI: funkcja TestAttachmentConstants.test_default_local_filename
    # Test: domyślna lokalna nazwa załącznika ma dozwolone rozszerzenie i zawiera 'FAS'/'zalacznik'.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_default_local_filename(self):
        assert ATTACHMENT_FILENAME.endswith((".pptx", ".pdf", ".docx"))
        assert "FAS" in ATTACHMENT_FILENAME or "zalacznik" in ATTACHMENT_FILENAME.lower()

    # >>> OPIS FUNKCJI: funkcja TestAttachmentConstants.test_mfg_aliases_point_to_fas
    # Test: aliasy MFG wskazują na te same funkcje FAS.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_mfg_aliases_point_to_fas(self):
        assert resolve_mfg_email_attachment is resolve_fas_email_attachment
        assert ensure_mfg_email_attachment is ensure_fas_email_attachment
        assert _download_slides_pptx is _download_attachment_pptx
        assert GOOGLE_SLIDES_PRESENTATION_ID == EMAIL_ATTACHMENT_DRIVE_FILE_ID


# >>> OPIS FUNKCJI: funkcja _clear_attachment_env
# Pomocnik testowy: usuwa z env zmienne FAS_EMAIL_ATTACHMENT_PATH, FAS_EMAIL_ATTACHMENT_EXTRA_PATH i MFG_EMAIL_ATTACHMENT_PATH. Parametry: monkeypatch (fixtura pytest). Zwraca: None. Efekty uboczne: zmiana env na czas testu. Błędy: brak.
def _clear_attachment_env(monkeypatch):
    monkeypatch.delenv("FAS_EMAIL_ATTACHMENT_PATH", raising=False)
    monkeypatch.delenv("FAS_EMAIL_ATTACHMENT_EXTRA_PATH", raising=False)
    monkeypatch.delenv("MFG_EMAIL_ATTACHMENT_PATH", raising=False)


# >>> OPIS FUNKCJI: klasa TestResolveAttachment
# Grupa testów: rozwiązywanie ścieżki załącznika.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestResolveAttachment:
    # >>> OPIS FUNKCJI: funkcja TestResolveAttachment.test_fas_env_path_wins
    # Test: ścieżka z FAS_EMAIL_ATTACHMENT_PATH ma pierwszeństwo.
    # Parametry: self, tmp_path, monkeypatch. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: monkeypatch zmienia zmienne środowiskowe tylko na czas testu (cofane automatycznie). Błędy: AssertionError przy niespełnionej asercji.
    def test_fas_env_path_wins(self, tmp_path, monkeypatch):
        f = tmp_path / "oferta.pptx"
        f.write_bytes(b"x" * 2000)
        _clear_attachment_env(monkeypatch)
        monkeypatch.setenv("FAS_EMAIL_ATTACHMENT_PATH", str(f))
        assert resolve_fas_email_attachment(tmp_path) == f

    # >>> OPIS FUNKCJI: funkcja TestResolveAttachment.test_mfg_env_alias_still_works
    # Test: legacy MFG_EMAIL_ATTACHMENT_PATH nadal działa.
    # Parametry: self, tmp_path, monkeypatch. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: monkeypatch zmienia zmienne środowiskowe tylko na czas testu (cofane automatycznie). Błędy: AssertionError przy niespełnionej asercji.
    def test_mfg_env_alias_still_works(self, tmp_path, monkeypatch):
        f = tmp_path / "legacy.pptx"
        f.write_bytes(b"x" * 2000)
        _clear_attachment_env(monkeypatch)
        monkeypatch.setenv("MFG_EMAIL_ATTACHMENT_PATH", str(f))
        assert resolve_fas_email_attachment(tmp_path) == f

    # >>> OPIS FUNKCJI: funkcja TestResolveAttachment.test_fas_env_preferred_over_mfg
    # Test: gdy ustawione obie, wybierana jest ścieżka FAS.
    # Parametry: self, tmp_path, monkeypatch. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: monkeypatch zmienia zmienne środowiskowe tylko na czas testu (cofane automatycznie). Błędy: AssertionError przy niespełnionej asercji.
    def test_fas_env_preferred_over_mfg(self, tmp_path, monkeypatch):
        fas = tmp_path / "fas.pptx"
        mfg = tmp_path / "mfg.pptx"
        fas.write_bytes(b"f" * 2000)
        mfg.write_bytes(b"m" * 2000)
        _clear_attachment_env(monkeypatch)
        monkeypatch.setenv("FAS_EMAIL_ATTACHMENT_PATH", str(fas))
        monkeypatch.setenv("MFG_EMAIL_ATTACHMENT_PATH", str(mfg))
        assert resolve_fas_email_attachment(tmp_path) == fas

    # >>> OPIS FUNKCJI: funkcja TestResolveAttachment.test_cache_in_wyniki
    # Test: plik zapisany w katalogu Wyniki (cache) jest znajdowany.
    # Parametry: self, tmp_path, monkeypatch. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: monkeypatch zmienia zmienne środowiskowe tylko na czas testu (cofane automatycznie); pliki w tmp_path. Błędy: AssertionError przy niespełnionej asercji.
    def test_cache_in_wyniki(self, tmp_path, monkeypatch):
        _clear_attachment_env(monkeypatch)
        monkeypatch.setenv("KANBUD_DATA_DIR", str(tmp_path))
        wyniki = tmp_path / "Wyniki"
        wyniki.mkdir()
        cached = wyniki / ATTACHMENT_FILENAME
        cached.write_bytes(b"y" * 2000)
        assert resolve_fas_email_attachment(tmp_path) == cached

    # >>> OPIS FUNKCJI: funkcja TestResolveAttachment.test_bundled_assets
    # Test: dołączone zasoby repozytorium są używane jako źródło.
    # Parametry: self, tmp_path, monkeypatch. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: monkeypatch zmienia zmienne środowiskowe tylko na czas testu (cofane automatycznie); pliki w tmp_path. Błędy: AssertionError przy niespełnionej asercji.
    def test_bundled_assets(self, tmp_path, monkeypatch):
        _clear_attachment_env(monkeypatch)
        monkeypatch.setenv("KANBUD_DATA_DIR", str(tmp_path))
        (tmp_path / "Wyniki").mkdir(exist_ok=True)
        assets = tmp_path / "assets" / "campaign"
        assets.mkdir(parents=True)
        bundled = assets / ATTACHMENT_FILENAME
        bundled.write_bytes(b"z" * 2000)
        assert resolve_fas_email_attachment(tmp_path) == bundled

    # >>> OPIS FUNKCJI: funkcja TestResolveAttachment.test_missing_returns_none
    # Test: brak pliku → None.
    # Parametry: self, tmp_path, monkeypatch. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: monkeypatch zmienia zmienne środowiskowe tylko na czas testu (cofane automatycznie). Błędy: AssertionError przy niespełnionej asercji.
    def test_missing_returns_none(self, tmp_path, monkeypatch):
        _clear_attachment_env(monkeypatch)
        monkeypatch.setenv("KANBUD_DATA_DIR", str(tmp_path))
        (tmp_path / "Wyniki").mkdir(exist_ok=True)
        assert resolve_fas_email_attachment(tmp_path) is None

    # >>> OPIS FUNKCJI: funkcja TestResolveAttachment.test_ignores_mfg_legacy_asset_paths
    # Test: stare zasoby MFG (Referenzliste/Fliesenboden) nie są w ścieżce wyszukiwania.
    # Parametry: self, tmp_path, monkeypatch. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: monkeypatch zmienia zmienne środowiskowe tylko na czas testu (cofane automatycznie). Błędy: AssertionError przy niespełnionej asercji.
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


# >>> OPIS FUNKCJI: klasa TestEnsureAttachment
# Grupa testów: pobieranie/zapewnienie załącznika.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestEnsureAttachment:
    # >>> OPIS FUNKCJI: funkcja TestEnsureAttachment.test_ensure_returns_existing_without_download
    # Test: istniejący plik jest zwracany bez pobierania (pobieranie nie jest wołane).
    # Parametry: self, tmp_path, monkeypatch. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: monkeypatch zmienia zmienne środowiskowe tylko na czas testu (cofane automatycznie); atrapa pobierania. Błędy: AssertionError przy niespełnionej asercji.
    def test_ensure_returns_existing_without_download(self, tmp_path, monkeypatch):
        f = tmp_path / "local.pptx"
        f.write_bytes(b"a" * 1500)
        _clear_attachment_env(monkeypatch)
        monkeypatch.setenv("FAS_EMAIL_ATTACHMENT_PATH", str(f))
        called = {"n": 0}

        # >>> OPIS FUNKCJI: funkcja TestEnsureAttachment.test_ensure_returns_existing_without_download.boom
        # Atrapa testowa: podmieniona funkcja pobierania — zwiększa licznik wywołań (test oczekuje 0). Parametry: *args/**kwargs. Zwraca: None/wyjątek wg testu. Efekty uboczne: licznik. Błędy: brak.
        def boom(*_a, **_k):
            called["n"] += 1
            return False

        monkeypatch.setattr("pl_fas_email_attachment._download_attachment_pptx", boom)
        assert ensure_fas_email_attachment(tmp_path, _LOG) == f
        assert called["n"] == 0

    # >>> OPIS FUNKCJI: funkcja TestEnsureAttachment.test_ensure_tries_download_when_missing
    # Test: gdy pliku brak, wywoływane jest pobieranie, a wynik to istniejący plik >= 2000 bajtów.
    # Parametry: self, tmp_path, monkeypatch. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: monkeypatch zmienia zmienne środowiskowe tylko na czas testu (cofane automatycznie); atrapa pobierania zapisuje plik w tmp_path. Błędy: AssertionError przy niespełnionej asercji.
    def test_ensure_tries_download_when_missing(self, tmp_path, monkeypatch):
        _clear_attachment_env(monkeypatch)
        monkeypatch.setenv("KANBUD_DATA_DIR", str(tmp_path))
        (tmp_path / "Wyniki").mkdir(exist_ok=True)

        # >>> OPIS FUNKCJI: funkcja TestEnsureAttachment.test_ensure_tries_download_when_missing.fake_download
        # Atrapa testowa pobierania: zapisuje pozorny plik PPTX pod ścieżką docelową. Parametry: dest (Path), logger. Zwraca: ścieżkę/True wg testu. Efekty uboczne: zapis pliku w katalogu tymczasowym. Błędy: brak.
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

    # >>> OPIS FUNKCJI: funkcja TestEnsureAttachment.test_ensure_attachments_returns_both
    # Test: ensure_fas_email_attachments zwraca oba pliki (oferta, prezentacja) w tej kolejności.
    # Parametry: self, tmp_path, monkeypatch. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: monkeypatch zmienia zmienne środowiskowe tylko na czas testu (cofane automatycznie); pliki w tmp_path. Błędy: AssertionError przy niespełnionej asercji.
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


# >>> OPIS FUNKCJI: klasa TestLegacyShim
# Grupa testów: kompatybilność wsteczna importów.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestLegacyShim:
    # >>> OPIS FUNKCJI: funkcja TestLegacyShim.test_shim_module_reexports
    # Test: moduły legacy re-eksportują te same funkcje co pl_fas_email_attachment.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_shim_module_reexports(self):
        import fas_email_attachment as mid
        import mfg_gu_email_attachment as legacy
        import pl_fas_email_attachment as neu

        assert mid.resolve_fas_email_attachment is neu.resolve_fas_email_attachment
        assert legacy.resolve_fas_email_attachment is neu.resolve_fas_email_attachment
        assert legacy.ensure_mfg_email_attachment is neu.ensure_fas_email_attachment

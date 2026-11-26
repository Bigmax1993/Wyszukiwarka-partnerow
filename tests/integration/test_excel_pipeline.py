# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# MODUŁ TESTOWY: tests/integration/test_excel_pipeline.py
# CO ROBI: testy integracyjne zapisu Excela w trybie append oraz wysyłki raportu (send_excel_gmail) w trybie dry-run, na plikach tymczasowych.
# ROLA W PIPELINE: sprawdza spójność save_excel → plik XLSX → raport mailowy.
# ZALEŻNOŚCI: pytest (znacznik integration), tempfile, unittest.mock, pandas/openpyxl (przez scraper), pl_fas_spedycja_scraper, scripts.send_excel_gmail.
# WEJŚCIE/WYJŚCIE: Moduł nie przyjmuje argumentów CLI; pytest/unittest odkrywa i uruchamia testy; nic nie zwraca (wynik = zielone/czerwone testy).
# ============================================================
"""Testy integracyjne: Excel append + send_excel_gmail dry-run."""
from __future__ import annotations

import gc
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.integration

_FAS_SNIPPET = (
    "Firma spedycyjna. Transport drogowy FTL LTL Europa — "
    "realizacje i flota."
)


# >>> OPIS FUNKCJI: funkcja _pipeline_row
# Pomocnik testowy: buduje przykładowy wiersz pipeline zweryfikowanej firmy spedycyjnej. Parametry: url, name, email, chain (str — segmenty). Zwraca: dict (url, nazwa, email_target, retail_verified=True, is_gu=True, is_small_firm=True, retail_chains_found, page_snippet, bundesland). Efekty uboczne/błędy: brak.
def _pipeline_row(url: str, name: str, email: str, chain: str) -> dict:
    return {
        "url": url,
        "www": url,
        "official_website": url,
        "nazwa": name,
        "company_name_clean": name,
        "email_target": email,
        "telefon": "+48 71 123 45 67",
        "phones_found": "+48 71 123 45 67",
        "retail_verified": True,
        "is_gu": True,
        "is_small_firm": True,
        "retail_chains_found": chain,
        "verification_reason": "claude:test",
        "page_snippet": _FAS_SNIPPET,
        "bundesland": "Dolnoslaskie",
    }


# >>> OPIS FUNKCJI: klasa TestExcelPipelineIntegration
# Grupa testów: integracja zapisu Excela i raportu.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestExcelPipelineIntegration:
    # >>> OPIS FUNKCJI: funkcja TestExcelPipelineIntegration.test_save_excel_appends_to_existing_file
    # Test: save_excel dopisuje nowe firmy do istniejącego pliku i zachowuje stare; arkusz ma kolumny Województwo i Segmenty/Spedycja.
    # Parametry: self (+ fixtury pytest wskazane w nawiasie). Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: tworzy i usuwa tymczasowy plik XLSX. Błędy: AssertionError przy niespełnionej asercji.
    def test_save_excel_appends_to_existing_file(self):
        import pl_fas_spedycja_scraper as scraper

        with tempfile.TemporaryDirectory() as tmp:
            xlsx = Path(tmp) / "kontakte.xlsx"
            rows_existing = [
                _pipeline_row(
                    "https://alt-spedycja.pl",
                    "Alt Spedycja Sp. z o.o.",
                    "alt@alt-spedycja.pl",
                    "ftl",
                )
            ]
            rows_new = [
                _pipeline_row(
                    "https://neu-spedycja.pl",
                    "Neu Spedycja Sp. z o.o.",
                    "neu@neu-spedycja.pl",
                    "ltl",
                )
            ]
            logger = scraper.setup_logging()
            # Bez live Claude — test sprawdza append, nie API cleanup
            with patch.object(scraper, "ENABLE_CLAUDE_ROW_CLEANUP", False):
                scraper.save_excel(rows_existing, xlsx, logger, cache={})
                assert xlsx.is_file()
                scraper.save_excel(rows_existing + rows_new, xlsx, logger, cache={})

            import pandas as pd

            with pd.ExcelFile(xlsx) as book:
                df = pd.read_excel(book, sheet_name="Kontakte")
            assert not df.empty
            assert "URL" in df.columns
            urls = {
                str(u).strip()
                for u in df["URL"].fillna("").tolist()
                if str(u).strip()
            }
            assert "https://alt-spedycja.pl" in urls
            assert "https://neu-spedycja.pl" in urls
            assert "Województwo" in df.columns
            assert "Segmenty" in df.columns or "Spedycja" in df.columns
            del df
            gc.collect()
            try:
                xlsx.unlink(missing_ok=True)
            except PermissionError:
                pass

    # >>> OPIS FUNKCJI: funkcja TestExcelPipelineIntegration.test_send_excel_gmail_dry_run
    # Test: send_excel_report w trybie dry-run zwraca (True, 'dry_run') bez wysyłania maila.
    # Parametry: self (+ fixtury pytest wskazane w nawiasie). Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: patch resolve_excel_path; tymczasowy plik XLSX; brak SMTP. Błędy: AssertionError przy niespełnionej asercji.
    def test_send_excel_gmail_dry_run(self):
        from scripts import send_excel_gmail as mailer

        with tempfile.TemporaryDirectory() as tmp:
            xlsx = Path(tmp) / "pl_spedycja_kontakte.xlsx"
            import pandas as pd

            pd.DataFrame(
                [
                    {
                        "Nazwa firmy": "Test Spedycja Sp. z o.o.",
                        "URL": "https://x.pl",
                        "E-mail": "a@b.pl",
                        "Województwo": "Dolnoslaskie",
                        "Segmenty": "ftl",
                    }
                ]
            ).to_excel(xlsx, sheet_name="Kontakte", index=False)
            with patch.object(mailer, "resolve_excel_path", return_value=xlsx.resolve()):
                ok, info = mailer.send_excel_report(dry_run=True)
            assert ok
            assert info == "dry_run"

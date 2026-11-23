# -*- coding: utf-8 -*-
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


def _pipeline_row(url: str, name: str, email: str, chain: str) -> dict:
    return {
        "url": url,
        "nazwa": name,
        "company_name_clean": name,
        "email_target": email,
        "retail_verified": True,
        "is_gu": True,
        "is_small_firm": True,
        "retail_chains_found": chain,
        "verification_reason": "claude:test",
        "page_snippet": _FAS_SNIPPET,
        "bundesland": "Dolnoslaskie",
    }


class TestExcelPipelineIntegration:
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
            scraper.save_excel(rows_existing, xlsx, logger, cache={})
            assert xlsx.is_file()
            scraper.save_excel(rows_existing + rows_new, xlsx, logger, cache={})

            import pandas as pd

            with pd.ExcelFile(xlsx) as book:
                df = pd.read_excel(book, sheet_name="Kontakte")
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

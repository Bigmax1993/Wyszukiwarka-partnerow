# -*- coding: utf-8 -*-
"""Testy integracyjne: Excel append + send_excel_gmail dry-run."""
from __future__ import annotations

import gc
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.integration

_GU_SNIPPET = (
    "Generalunternehmer Filialbau Supermarkt Neubau Rewe ÔÇö "
    "Referenzprojekt realisiert."
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
        "page_snippet": _GU_SNIPPET,
    }


class TestExcelPipelineIntegration:
    def test_save_excel_appends_to_existing_file(self):
        import de_gu_bauunternehmen_scraper as scraper

        with tempfile.TemporaryDirectory() as tmp:
            xlsx = Path(tmp) / "kontakte.xlsx"
            rows_existing = [
                _pipeline_row("https://alt.de", "Alt GmbH", "alt@alt.de", "rewe")
            ]
            rows_new = [
                _pipeline_row("https://neu.de", "Neu GmbH", "neu@neu.de", "aldi")
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
            assert "https://alt.de" in urls
            assert "https://neu.de" in urls
            del df
            gc.collect()

    def test_send_excel_gmail_dry_run(self):
        from scripts import send_excel_gmail as mailer

        with tempfile.TemporaryDirectory() as tmp:
            xlsx = Path(tmp) / "de_gu_bauunternehmen_kontakte.xlsx"
            import pandas as pd

            pd.DataFrame(
                [{"Nazwa firmy": "Test", "URL": "https://x.de", "E-mail": "a@b.de"}]
            ).to_excel(xlsx, sheet_name="Kontakte", index=False)
            with patch.object(mailer, "resolve_excel_path", return_value=xlsx.resolve()):
                ok, info = mailer.send_excel_report(dry_run=True)
            assert ok
            assert info == "dry_run"

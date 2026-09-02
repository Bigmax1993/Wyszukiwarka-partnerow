# -*- coding: utf-8 -*-
"""Testy append Excel — merge bez kasowania istniejących wierszy."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import de_gu_bauunternehmen_scraper as scraper


class ExcelAppendMergeTest(unittest.TestCase):
    def test_merge_export_rows_appends_new_and_updates_existing(self):
        existing = [
            {
                "Nazwa firmy": "Alt GmbH",
                "URL": "https://alt.de",
                "E-mail": "alt@alt.de",
                "Odpowiedź": "tak",
            }
        ]
        incoming = [
            {
                "Nazwa firmy": "Alt GmbH neu",
                "URL": "https://alt.de",
                "E-mail": "alt@alt.de",
                "Telefon": "+49111",
            },
            {
                "Nazwa firmy": "Neu GmbH",
                "URL": "https://neu.de",
                "E-mail": "neu@neu.de",
            },
        ]
        merged, appended, updated = scraper.merge_export_rows_append(
            existing, incoming, logger=None
        )
        self.assertEqual(len(merged), 2)
        self.assertEqual(appended, 1)
        self.assertEqual(updated, 1)
        by_url = {r["URL"]: r for r in merged}
        self.assertEqual(by_url["https://alt.de"]["Telefon"], "+49111")
        self.assertEqual(by_url["https://alt.de"]["Odpowiedź"], "tak")
        self.assertEqual(by_url["https://neu.de"]["Nazwa firmy"], "Neu GmbH")

    def test_merge_pipeline_rows_keeps_excel_only_rows(self):
        existing = [{"url": "https://excel-only.de", "nazwa": "Excel Only"}]
        incoming = [{"url": "https://cache.de", "nazwa": "From Cache"}]
        merged = scraper.merge_pipeline_rows(existing, incoming)
        urls = {r["url"] for r in merged}
        self.assertEqual(urls, {"https://excel-only.de", "https://cache.de"})

    def test_export_row_dedupe_key_prefers_email(self):
        key = scraper.export_row_dedupe_key(
            {"E-mail": "a@b.de", "URL": "https://x.de", "Nazwa firmy": "X"}
        )
        self.assertEqual(key, "email:a@b.de")


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.gdrive_upload_wyniki import (  # noqa: E402
    _skip_gdrive_upload,
    versioned_xlsx_upload_name,
)


class GdriveVersionedXlsxTest(unittest.TestCase):
    def test_versions_kontakte_xlsx(self):
        name = versioned_xlsx_upload_name(
            "pl_spedycja_kontakte.xlsx", stamp="2026-06-08_1405"
        )
        self.assertEqual(name, "pl_spedycja_kontakte_2026-06-08_1405.xlsx")

    def test_non_xlsx_unchanged(self):
        self.assertEqual(
            versioned_xlsx_upload_name("pl_spedycja_cache.json", stamp="x"),
            "pl_spedycja_cache.json",
        )

    def test_cache_and_log_skipped_from_drive(self):
        self.assertTrue(_skip_gdrive_upload(Path("pl_spedycja_cache.json")))
        self.assertTrue(_skip_gdrive_upload(Path("pl_spedycja_scraper.log")))
        self.assertFalse(_skip_gdrive_upload(Path("pl_spedycja_kontakte.xlsx")))


if __name__ == "__main__":
    unittest.main()

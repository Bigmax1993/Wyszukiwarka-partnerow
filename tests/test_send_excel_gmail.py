# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import send_excel_gmail as mailer
from scraper_env import DEFAULT_EXCEL_REPORT_TO


class SendExcelGmailTest(unittest.TestCase):
    def test_default_recipient(self):
        with patch.dict("os.environ", {}, clear=False):
            import scraper_env

            scraper_env._DOTENV_LOADED = True
            self.assertEqual(
                scraper_env.get_excel_report_to(), DEFAULT_EXCEL_REPORT_TO
            )

    def test_build_email_subject_contains_filename(self):
        path = Path("de_gu_bauunternehmen_kontakte.xlsx")
        subject = mailer.build_email_subject(path)
        self.assertIn("GU Kontakte Excel", subject)
        self.assertIn(path.name, subject)


if __name__ == "__main__":
    unittest.main()

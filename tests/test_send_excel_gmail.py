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
        path = Path("pl_spedycja_kontakte.xlsx")
        subject = mailer.build_email_subject(path)
        self.assertIn("PL FAS Kontakte Excel", subject)
        self.assertIn(path.name, subject)

    def test_build_email_body_pl_fas(self):
        path = Path("pl_spedycja_kontakte.xlsx")
        with patch.object(Path, "stat") as st:
            st.return_value.st_size = 2048
            body = mailer.build_email_body(path, 3)
        self.assertIn("PL FAS / spedycja drogowa", body)
        self.assertNotIn("Generalunternehmer", body)
        self.assertIn(path.name, body)


if __name__ == "__main__":
    unittest.main()

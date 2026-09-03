# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
LIBS = ROOT / "libs"
for p in (str(LIBS), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import scraper_env  # noqa: E402


class KillSwitchFlagsTest(unittest.TestCase):
    def test_contractor_emails_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DISABLE_CONTRACTOR_EMAILS", None)
            self.assertTrue(scraper_env.is_contractor_emails_disabled())

    def test_contractor_emails_enabled_with_zero(self):
        with patch.dict(os.environ, {"DISABLE_CONTRACTOR_EMAILS": "0"}, clear=False):
            self.assertFalse(scraper_env.is_contractor_emails_disabled())

    def test_google_drive_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DISABLE_GOOGLE_DRIVE", None)
            self.assertTrue(scraper_env.is_google_drive_disabled())

    def test_google_drive_enabled_with_false(self):
        with patch.dict(os.environ, {"DISABLE_GOOGLE_DRIVE": "false"}, clear=False):
            self.assertFalse(scraper_env.is_google_drive_disabled())

    def test_excel_report_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DISABLE_EXCEL_REPORT_EMAIL", None)
            self.assertTrue(scraper_env.is_excel_report_email_disabled())


if __name__ == "__main__":
    unittest.main()

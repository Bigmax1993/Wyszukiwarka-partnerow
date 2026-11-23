# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pl_spedycja_filter import has_retail_context_without_named_chain


class RetailContextLooseTest(unittest.TestCase):
    def test_accepts_spedycja_without_named_segment(self):
        text = (
            "Firma spedycyjna. Transport drogowy i organizacja przewozu. "
            "Logistyka na terenie Polski."
        )
        self.assertTrue(has_retail_context_without_named_chain(text))

    def test_accepts_dyspozytor_with_trade_context(self):
        text = "Spedytor. Dyspozytor fracht — transport międzynarodowy."
        self.assertTrue(has_retail_context_without_named_chain(text))

    def test_rejects_irrelevant_role(self):
        text = "Agencja pracy — oferty pracy kierowca, kurs na prawo jazdy."
        self.assertFalse(has_retail_context_without_named_chain(text))

    def test_rejects_pure_construction(self):
        text = "Bauunternehmen für Wohnungsbau und Bürosanierung."
        self.assertFalse(has_retail_context_without_named_chain(text))


if __name__ == "__main__":
    unittest.main(verbosity=2)

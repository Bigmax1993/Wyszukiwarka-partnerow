# -*- coding: utf-8 -*-
"""Testy pełnej geo PL (miasta + powiaty) pod discovery."""
from __future__ import annotations

import unittest

from pl_geo_locations import (
    PL_GEO_BY_LAND,
    cities_for,
    geo_counts,
    iter_land_keys,
    powiaty_for,
)
from pl_spedycja_keywords import (
    BUNDESLAND_CONFIG,
    build_landkreis_discovery_terms,
    build_maps_discovery_terms,
)
from gu_bundesland_rotation import BUNDESLAND_ROTATION_ORDER


class TestPlGeoLocations(unittest.TestCase):
    def test_sixteen_lands_aligned_with_rotation_and_config(self):
        keys = set(PL_GEO_BY_LAND)
        self.assertEqual(len(keys), 16)
        self.assertEqual(keys, set(BUNDESLAND_ROTATION_ORDER))
        self.assertEqual(keys, set(BUNDESLAND_CONFIG))

    def test_geo_counts_scale(self):
        c = geo_counts()
        self.assertEqual(c["lands"], 16)
        self.assertGreaterEqual(c["cities_total"], 900)
        self.assertGreaterEqual(c["powiaty_total"], 300)
        self.assertIn("Dolnoslaskie", c["per_land"])

    def test_seed_hubs_present(self):
        self.assertIn("Głogów", cities_for("Dolnoslaskie"))
        self.assertIn("Warszawa", cities_for("Mazowieckie"))
        self.assertIn("Poznań", cities_for("Wielkopolskie"))

    def test_powiaty_nonempty_and_helpers(self):
        self.assertGreaterEqual(len(powiaty_for("Lubuskie")), 10)
        self.assertEqual(list(iter_land_keys()), list(PL_GEO_BY_LAND.keys()))

    def test_config_exposes_powiaty(self):
        self.assertIn("powiaty", BUNDESLAND_CONFIG["Mazowieckie"])
        self.assertGreaterEqual(len(BUNDESLAND_CONFIG["Mazowieckie"]["cities"]), 80)

    def test_maps_and_landkreis_scale_single_land(self):
        maps = build_maps_discovery_terms(["Lubuskie"])
        lk = build_landkreis_discovery_terms(["Lubuskie"])
        # miasta*5 + powiaty*2 + frazy na woj.
        self.assertGreaterEqual(len(maps), 200)
        self.assertGreaterEqual(len(lk), 50)
        self.assertTrue(any("powiat" in t.lower() for t in maps))
        self.assertTrue(any("powiat" in t.lower() for t in lk))


if __name__ == "__main__":
    unittest.main()

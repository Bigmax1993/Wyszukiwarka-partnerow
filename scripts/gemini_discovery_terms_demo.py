# -*- coding: utf-8 -*-
"""Podgląd fraz Gemini discovery (wymaga GOOGLE_AI_STUDIO_API_KEY w .env)."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
for p in (ROOT / "libs", ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import de_gu_bauunternehmen_scraper as scraper
from gemini_discovery_terms import generate_gemini_discovery_terms
from scraper_env import get_google_ai_studio_api_key

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gemini_discovery_demo")

lands = sys.argv[1:] or list(scraper.CAMPAIGN_ACTIVE_BUNDESLAENDER)
cache: dict = {}
api_key = get_google_ai_studio_api_key()
if not api_key:
    print("Brak GOOGLE_AI_STUDIO_API_KEY — ustaw w .env")
    sys.exit(1)

terms = generate_gemini_discovery_terms(
    cache,
    logger,
    lands,
    gemini_generate_text=scraper.gemini_generate_text,
    api_key=api_key,
    terms_requested=10,
    use_cache=False,
)
print(f"Land: {', '.join(lands)}")
print(f"Fraz po walidacji: {len(terms)}")
for i, t in enumerate(terms, 1):
    print(f"  {i}. {t}")

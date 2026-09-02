# -*- coding: utf-8 -*-
"""Wspólna konfiguracja pytest."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIBS = ROOT / "libs"
for p in (LIBS, ROOT):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

import os

os.environ.setdefault("KANBUD_PROJECT_ROOT", str(LIBS))
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("USE_GEMINI_REPLY_INTELLIGENCE", "0")

# -*- coding: utf-8 -*-
"""Unit: scripts/verify_pl_cache.py"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
VERIFY = ROOT / "scripts" / "verify_pl_cache.py"


def _run_verify(campaign_dir: Path) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k != "KANBUD_DATA_DIR"}
    return subprocess.run(
        [sys.executable, str(VERIFY), "--campaign-dir", str(campaign_dir)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


@pytest.mark.unit
def test_verify_missing_cache_ok(tmp_path):
    (tmp_path / "Wyniki").mkdir()
    proc = _run_verify(tmp_path)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    stamp = tmp_path / "Wyniki" / ".cache_verified_for_discovery.json"
    assert stamp.is_file()
    data = json.loads(stamp.read_text(encoding="utf-8"))
    assert data["ok"] is True
    assert data["exists"] is False
    assert data["respect_cache"] is True


@pytest.mark.unit
def test_verify_valid_cache_stats(tmp_path):
    out = tmp_path / "Wyniki"
    out.mkdir()
    cache = {
        "contacts": {
            "https://a.pl/": {
                "email_target": "a@a.pl",
                "gap_status": "enriched",
                "discovery_source": "google_maps",
            },
            "https://b.pl/": {
                "gap_status": "needs_enrich",
                "discovery_source": "google_maps",
            },
        },
        "serper_discovery": {"q1": {}},
        "serper": {},
    }
    (out / "pl_spedycja_cache.json").write_text(
        json.dumps(cache), encoding="utf-8"
    )
    proc = _run_verify(tmp_path)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "contacts=2" in proc.stdout
    stamp = json.loads(
        (out / ".cache_verified_for_discovery.json").read_text(encoding="utf-8")
    )
    assert stamp["stats"]["needs_enrich"] == 1
    assert stamp["stats"]["with_email"] == 1
    assert stamp["stats"]["maps_source"] == 2


@pytest.mark.unit
def test_verify_corrupt_cache_fails(tmp_path):
    out = tmp_path / "Wyniki"
    out.mkdir()
    (out / "pl_spedycja_cache.json").write_text("{not-json", encoding="utf-8")
    proc = _run_verify(tmp_path)
    assert proc.returncode == 2
    stamp = json.loads(
        (out / ".cache_verified_for_discovery.json").read_text(encoding="utf-8")
    )
    assert stamp["ok"] is False

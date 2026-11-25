# -*- coding: utf-8 -*-
"""Unit: pipeline_notify dry-run + state."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
NOTIFY = ROOT / "scripts" / "pipeline_notify.py"


@pytest.mark.unit
def test_pipeline_notify_dry_run_start(tmp_path, monkeypatch):
    monkeypatch.setenv("DISABLE_PIPELINE_NOTIFY", "0")
    # nie pisz state do prawdziwego logs/ — użyj --no-state
    proc = subprocess.run(
        [
            sys.executable,
            str(NOTIFY),
            "start",
            "--job",
            "discovery/test",
            "--dry-run",
            "--no-state",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "DISABLE_PIPELINE_NOTIFY": "0"},
    )
    assert proc.returncode == 0, proc.stderr
    assert "[DRY-RUN]" in proc.stdout
    assert "START" in proc.stdout
    assert "discovery/test" in proc.stdout


@pytest.mark.unit
def test_pipeline_notify_disabled(monkeypatch):
    proc = subprocess.run(
        [
            sys.executable,
            str(NOTIFY),
            "alert",
            "--job",
            "discovery/test",
            "--no-state",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "DISABLE_PIPELINE_NOTIFY": "1"},
    )
    assert proc.returncode == 0
    assert "NO-OP" in proc.stdout

# -*- coding: utf-8 -*-
"""
Weryfikacja cache PL FAS przed porannym discovery (cron Contabo ~04:00).

Sprawdza, że Wyniki/pl_spedycja_cache.json jest czytelny i ma sensowną strukturę,
zapisuje stempel dla run_discovery.sh (--respect-cache).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pl_spedycja_data_paths import campaign_output_paths  # noqa: E402


STAMP_NAME = ".cache_verified_for_discovery.json"
BASENAME = "pl_spedycja"


def _contact_stats(contacts: dict[str, Any]) -> dict[str, int]:
    total = 0
    with_email = 0
    needs_enrich = 0
    still_gap = 0
    enriched = 0
    maps_source = 0
    for info in contacts.values():
        if not isinstance(info, dict):
            continue
        total += 1
        if (info.get("email_target") or "").strip():
            with_email += 1
        gap = (info.get("gap_status") or "").strip()
        if gap == "needs_enrich":
            needs_enrich += 1
        elif gap == "still_gap":
            still_gap += 1
        elif gap == "enriched":
            enriched += 1
        if (info.get("discovery_source") or "") == "google_maps":
            maps_source += 1
    return {
        "contacts": total,
        "with_email": with_email,
        "needs_enrich": needs_enrich,
        "still_gap": still_gap,
        "enriched": enriched,
        "maps_source": maps_source,
    }


def verify_cache(cache_path: Path) -> dict[str, Any]:
    if not cache_path.exists():
        return {
            "ok": True,
            "exists": False,
            "message": f"Brak cache — discovery utworzy nowy ({cache_path.name})",
            "stats": {
                "contacts": 0,
                "with_email": 0,
                "needs_enrich": 0,
                "still_gap": 0,
                "enriched": 0,
                "maps_source": 0,
                "serper": 0,
                "serper_discovery": 0,
            },
        }

    try:
        raw = cache_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "exists": True,
            "message": f"Cache JSON uszkodzony: {exc}",
            "stats": {},
        }
    except OSError as exc:
        return {
            "ok": False,
            "exists": True,
            "message": f"Nie można odczytać cache: {exc}",
            "stats": {},
        }

    if not isinstance(data, dict):
        return {
            "ok": False,
            "exists": True,
            "message": "Cache JSON nie jest obiektem (oczekiwano dict)",
            "stats": {},
        }

    contacts = data.get("contacts")
    if contacts is None:
        contacts = {}
    if not isinstance(contacts, dict):
        return {
            "ok": False,
            "exists": True,
            "message": "Pole contacts nie jest obiektem",
            "stats": {},
        }

    stats = _contact_stats(contacts)
    serper = data.get("serper") if isinstance(data.get("serper"), dict) else {}
    serper_discovery = (
        data.get("serper_discovery")
        if isinstance(data.get("serper_discovery"), dict)
        else {}
    )
    stats["serper"] = len(serper)
    stats["serper_discovery"] = len(serper_discovery)

    return {
        "ok": True,
        "exists": True,
        "message": (
            f"Cache OK: contacts={stats['contacts']} email={stats['with_email']} "
            f"needs_enrich={stats['needs_enrich']} still_gap={stats['still_gap']} "
            f"maps={stats['maps_source']} serper_discovery={stats['serper_discovery']}"
        ),
        "stats": stats,
        "size_bytes": cache_path.stat().st_size,
    }


def write_stamp(stamp_path: Path, payload: dict[str, Any]) -> None:
    stamp_path.parent.mkdir(parents=True, exist_ok=True)
    stamp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Weryfikacja pl_spedycja_cache.json")
    parser.add_argument(
        "--campaign-dir",
        type=Path,
        default=ROOT,
        help="Root kampanii (domyślnie root repo)",
    )
    parser.add_argument(
        "--stamp",
        type=Path,
        default=None,
        help="Ścieżka stempla (domyślnie Wyniki/.cache_verified_for_discovery.json)",
    )
    args = parser.parse_args(argv)

    paths = campaign_output_paths(args.campaign_dir.resolve(), BASENAME)
    cache_path = Path(paths["cache_file"])
    stamp_path = args.stamp or (Path(paths["output_dir"]) / STAMP_NAME)

    result = verify_cache(cache_path)
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    stamp = {
        "verified_at": now,
        "cache_file": str(cache_path),
        "ok": bool(result["ok"]),
        "exists": bool(result.get("exists")),
        "message": result.get("message"),
        "stats": result.get("stats") or {},
        "respect_cache": True,
    }
    write_stamp(stamp_path, stamp)

    print(result["message"])
    print(f"Stamp: {stamp_path}")
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

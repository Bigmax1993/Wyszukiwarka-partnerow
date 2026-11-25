# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Uzupełnienie opisu modułu scraper_run_config (komentarz; docstring poniżej opisuje przepływ).
#   Rola w pipeline: pierwszy krok konfiguracji uruchomienia — plik run_config/*.json (np.
#   pl_fas_spedycja.json, przekazywany przez --run-config) ustawia wspólne pola na module scrapera;
#   pola geo / Claude / ICP stosuje później apply_gu_run_config_extras w pl_fas_spedycja_scraper.py.
#   Zależności: tylko stdlib (json, pathlib, typing); sam nie importuje scrapera — modyfikuje przekazany
#   obiekt modułu (wstrzykiwanie). Wejście: ścieżka JSON + base_dir. Wyjście: mutacja modułu
#   (_RUN_CONFIG_DATA, _RUN_CONFIG_TYPE, stałe), słowniki kwargs dla run_scraper oraz raport debug.
#   Błędy: nieistniejący plik / niepoprawny JSON propagują się wyjątkiem; JSON niebędący obiektem → ValueError.
# ============================================================
"""
Ładowanie plików ``run_config/*.json`` (CLI ``--run-config``) dla scrapera kampanii.

Po co: jeden JSON (np. `run_config/pl_fas_spedycja.json`) ustawia język, limity
i flagi startu bez hardcodu w scraperze. Ten moduł stosuje **wspólne** pola
na module scrapera; pola geo / Claude / ICP dla kampanii GU/PL obsługuje
``apply_gu_run_config_extras`` w `pl_fas_spedycja_scraper.py`
(wywoływane **po** `apply_run_config_file`).

Nazwa pliku zostaje bez zmian (współdzielona ścieżka importu scrapera).

Przepływ typowy::

    apply_run_config_file(module, path, base_dir)
    apply_gu_run_config_extras(module, data)   # active_bundeslaender, Claude, …
    run_scraper(**run_scraper_launch_kwargs(module))
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# JSON key → atrybuty string na module scrapera (pierwszy istniejący win).
# ``delivery_address`` mapuje na legacy ``INQUIRY_REGION_DE`` (nazwa atrybutu DE).
_MODULE_STRING_ATTRS = {
    "lang": ("CUSTOM_EMAIL_LANG", "SERPER_LANGUAGE"),
    "city_name": ("CUSTOM_EMAIL_CITY",),
    "delivery_address": ("INQUIRY_REGION_DE",),
}

# JSON key → flaga bool na module.
_MODULE_BOOL_ATTRS = {
    "enable_auto_email": "ENABLE_AUTO_EMAIL",
}

# Klucze z JSON, które mogą wejść prosto do ``run_scraper(**kwargs)``.
_LAUNCH_KW_KEYS = (
    "enable_auto_email",
    "dry_run_email",
    "discovery_mode",
    "max_new_rows",
    "force_resend",
    "ignore_send_window",
    "rebuild_from_cache",
)


def _resolve_config_path(path: Path | str, base_dir: Path | str) -> Path:
    """
    Zamienia ścieżkę run_config na absolutną względem ``base_dir``.

    Po co: CLI często podaje ``run_config\\pl_fas_spedycja.json`` względnie
    do katalogu repo — ``base_dir`` to zwykle folder pliku scrapera.
    """
    p = Path(path)
    if not p.is_absolute():
        p = Path(base_dir) / p
    return p.resolve()


def load_run_config_file(path: Path | str, base_dir: Path | str) -> dict[str, Any]:
    """
    Wczytuje JSON run_config i zwraca dict (bez mutacji modułu scrapera).

    Rzuca ``ValueError``, gdy plik nie jest obiektem JSON (``{…}``).
    Używane też przy ponownym odczycie pod ``apply_gu_run_config_extras``.
    """
    cfg_path = _resolve_config_path(path, base_dir)
    with open(cfg_path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"run_config must be a JSON object: {cfg_path}")
    return data


def apply_run_config_file(module, path: Path | str, base_dir: Path | str) -> dict[str, Any]:
    """
    Wczytaj JSON i zastosuj **wspólne** pola na module scrapera.

    Ustawia:
      - ``module._RUN_CONFIG_DATA`` — pełny dict (źródło dla launch kwargs),
      - ``module._RUN_CONFIG_TYPE`` — np. ``pl_spedycja``,
      - stringi: ``lang`` → ``CUSTOM_EMAIL_LANG`` / ``SERPER_LANGUAGE``,
        ``city_name``, ``delivery_address`` (legacy ``INQUIRY_REGION_DE``),
      - bool: ``enable_auto_email`` → ``ENABLE_AUTO_EMAIL``,
      - ``min_contacts_target`` → ``MIN_CONTACTS_TARGET`` (także dublowane
        w ``apply_gu_run_config_extras`` dla pewności kolejności wywołań).

    **Nie** ustawia listy województw ani flag Claude — to robi extras w scraperze
    (`active_bundeslaender`, `enable_claude_*`, limity Serper/Claude, …).

    Zwraca wczytany dict (ten sam obiekt co w ``_RUN_CONFIG_DATA``).
    """
    data = load_run_config_file(path, base_dir)
    module._RUN_CONFIG_DATA = data

    config_type = data.get("config_type")
    if config_type is not None:
        module._RUN_CONFIG_TYPE = str(config_type)

    for json_key, attr_names in _MODULE_STRING_ATTRS.items():
        if json_key not in data:
            continue
        value = str(data[json_key]).strip()
        if not value:
            continue
        for attr in attr_names:
            if hasattr(module, attr):
                setattr(module, attr, value)

    for json_key, attr_name in _MODULE_BOOL_ATTRS.items():
        if json_key in data and hasattr(module, attr_name):
            setattr(module, attr_name, bool(data[json_key]))

    if "min_contacts_target" in data and hasattr(module, "MIN_CONTACTS_TARGET"):
        try:
            module.MIN_CONTACTS_TARGET = int(data["min_contacts_target"])
        except (TypeError, ValueError):
            pass

    return data


def run_scraper_launch_kwargs(module) -> dict[str, Any]:
    """
    Buduje kwargs dla ``run_scraper()`` z zapisanego run_config i stanu modułu.

    Bierze wartości z ``module._RUN_CONFIG_DATA`` dla kluczy w ``_LAUNCH_KW_KEYS``
    (cast bool/int/str). Jeśli JSON nie ma ``enable_auto_email``, dokłada
    bieżące ``module.ENABLE_AUTO_EMAIL`` — żeby start scrapera miał spójną flagę
    nawet przy częściowym configu.

    Nie uruchamia scrapera — tylko dict do rozpakowania: ``run_scraper(**kw)``.
    """
    data: dict[str, Any] = getattr(module, "_RUN_CONFIG_DATA", None) or {}
    kw: dict[str, Any] = {}

    for key in _LAUNCH_KW_KEYS:
        if key not in data or data[key] is None:
            continue
        value = data[key]
        if key == "discovery_mode":
            kw[key] = str(value)
        elif key == "max_new_rows":
            try:
                kw[key] = int(value)
            except (TypeError, ValueError):
                pass
        elif key in (
            "enable_auto_email",
            "dry_run_email",
            "force_resend",
            "ignore_send_window",
            "rebuild_from_cache",
        ):
            kw[key] = bool(value)
        else:
            kw[key] = value

    if "enable_auto_email" not in kw and hasattr(module, "ENABLE_AUTO_EMAIL"):
        kw["enable_auto_email"] = bool(module.ENABLE_AUTO_EMAIL)

    return kw


def debug_run_config(
    path: Path | str,
    base_dir: Path | str | None = None,
    *,
    module: Any | None = None,
) -> dict[str, Any]:
    """
    Diagnostyka pliku run_config: co JSON zawiera vs co ten moduł stosuje.

    Po co: przy strojeniu `pl_fas_spedycja.json` widać od razu resolved path,
    pola wspólne (lang, enable_auto_email, min_contacts…), launch kwargs
    oraz które klucze zostawia na ``apply_gu_run_config_extras`` (województwa,
    Claude, limity Serper).

    Nie mutuje prawdziwego scrapera — jeśli ``module`` nie podano, używa
    lekkiego stubu. Zwraca dict (bez side-effectów poza stubem lokalnym).
    """
    from types import SimpleNamespace

    root = Path(base_dir) if base_dir is not None else Path(__file__).resolve().parent
    cfg_path = _resolve_config_path(path, root)
    raw = load_run_config_file(cfg_path, root)

    stub = module
    if stub is None:
        stub = SimpleNamespace(
            CUSTOM_EMAIL_LANG="",
            SERPER_LANGUAGE="",
            CUSTOM_EMAIL_CITY="",
            INQUIRY_REGION_DE="",
            ENABLE_AUTO_EMAIL=True,
            MIN_CONTACTS_TARGET=0,
        )

    applied = apply_run_config_file(stub, cfg_path, root)
    launch = run_scraper_launch_kwargs(stub)

    known_here = set(_MODULE_STRING_ATTRS) | set(_MODULE_BOOL_ATTRS) | {
        "min_contacts_target",
        "config_type",
        "campaign_id",
        *_LAUNCH_KW_KEYS,
    }
    extras_keys = sorted(k for k in applied if k not in known_here)

    return {
        "path": str(cfg_path),
        "config_type": applied.get("config_type"),
        "campaign_id": applied.get("campaign_id"),
        "lang": applied.get("lang"),
        "enable_auto_email": applied.get("enable_auto_email"),
        "min_contacts_target": applied.get("min_contacts_target"),
        "active_bundeslaender_count": len(applied.get("active_bundeslaender") or []),
        "active_bundeslaender_head": list(applied.get("active_bundeslaender") or [])[:5],
        "module_attrs": {
            "CUSTOM_EMAIL_LANG": getattr(stub, "CUSTOM_EMAIL_LANG", None),
            "SERPER_LANGUAGE": getattr(stub, "SERPER_LANGUAGE", None),
            "ENABLE_AUTO_EMAIL": getattr(stub, "ENABLE_AUTO_EMAIL", None),
            "MIN_CONTACTS_TARGET": getattr(stub, "MIN_CONTACTS_TARGET", None),
            "_RUN_CONFIG_TYPE": getattr(stub, "_RUN_CONFIG_TYPE", None),
        },
        "launch_kwargs": launch,
        "keys_for_gu_extras": extras_keys,
        "keys_total": len(applied),
    }


# >>> OPIS FUNKCJI: funkcja _cli_debug
# Cel: wejście CLI do diagnostyki run_config (python scraper_run_config.py [ścieżka.json] [--base-dir DIR]).
# Parametry: argv (list[str]|None) — argumenty (None = sys.argv); domyślna ścieżka run_config/pl_fas_spedycja.json,
#   domyślny base-dir = katalog tego pliku.
# Zwraca: int — kod wyjścia (zawsze 0 po wypisaniu raportu).
# Efekty uboczne: odczyt pliku JSON, wypisanie raportu debug_run_config jako JSON (ensure_ascii=False) na stdout.
# Błędy: argparse kończy proces przy błędnych argumentach; wyjątki odczytu pliku propagują się (brak try/except).
def _cli_debug(argv: list[str] | None = None) -> int:
    """
    CLI: ``python scraper_run_config.py [ścieżka.json]``.

    Domyślnie: ``run_config/pl_fas_spedycja.json`` względem katalogu repo.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Debug run_config JSON (scraper_run_config)."
    )
    parser.add_argument(
        "path",
        nargs="?",
        default="run_config/pl_fas_spedycja.json",
        help="Ścieżka do JSON (względem repo lub absolutna)",
    )
    parser.add_argument(
        "--base-dir",
        default=None,
        help="Katalog bazowy (domyślnie katalog tego pliku / repo root)",
    )
    args = parser.parse_args(argv)
    base = Path(args.base_dir) if args.base_dir else Path(__file__).resolve().parent
    payload = debug_run_config(args.path, base)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli_debug())

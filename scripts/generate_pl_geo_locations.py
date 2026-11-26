# -*- coding: utf-8 -*-
# >>> OPIS SKRYPTU ========================================
# Skrypt: generate_pl_geo_locations.py — regeneruje pl_geo_locations.py.
#
# CO ROBI
#   Czyta snapshoty JSON z data/, mapuje miasta i powiaty na 16 kluczy województw
#   kampanii PL FAS, deduplikuje powiaty (preferencja diakrytyków), dokleja SEEDS
#   (huby discovery) i EMITUJE pl_geo_locations.py z obszernym nagłówkiem OPIS MODULU,
#   komentarzami per woj. oraz helperami cities_for / powiaty_for / geo_counts.
#
# KIEDY URUCHAMIAĆ
#   Po aktualizacji data/*.json albo zmianie SEEDS / ORDER / mapowania slug→klucz.
#   Nie edytuj ręcznie list w pl_geo_locations.py — wróć tutaj i wygeneruj ponownie.
#
# UŻYCIE
#   python scripts/generate_pl_geo_locations.py   (cwd dowolny; ścieżki względem ROOT)
# ============================================================
"""Generate pl_geo_locations.py from data/*_src.json + all_county.json."""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data"
OUT_PY = ROOT / "pl_geo_locations.py"

KEY_BY_SLUG = {
    "dolnoslaskie": "Dolnoslaskie",
    "kujawsko-pomorskie": "Kujawsko-Pomorskie",
    "lubelskie": "Lubelskie",
    "lubuskie": "Lubuskie",
    "lodzkie": "Lodzkie",
    "malopolskie": "Malopolskie",
    "mazowieckie": "Mazowieckie",
    "opolskie": "Opolskie",
    "podkarpackie": "Podkarpackie",
    "podlaskie": "Podlaskie",
    "pomorskie": "Pomorskie",
    "slaskie": "Slaskie",
    "swietokrzyskie": "Swietokrzyskie",
    "warminsko-mazurskie": "Warminsko-Mazurskie",
    "wielkopolskie": "Wielkopolskie",
    "zachodniopomorskie": "Zachodniopomorskie",
}

EN_TO_KEY = {v: v for v in KEY_BY_SLUG.values()}

ORDER = (
    "Dolnoslaskie",
    "Mazowieckie",
    "Zachodniopomorskie",
    "Lubuskie",
    "Wielkopolskie",
    "Lodzkie",
    "Slaskie",
    "Malopolskie",
    "Pomorskie",
    "Kujawsko-Pomorskie",
    "Warminsko-Mazurskie",
    "Podlaskie",
    "Lubelskie",
    "Podkarpackie",
    "Swietokrzyskie",
    "Opolskie",
)

SEEDS = {
    "Mazowieckie": [
        "Warszawa",
        "Radom",
        "Płock",
        "Siedlce",
        "Pruszków",
        "Piaseczno",
        "Ostrołęka",
        "Żyrardów",
    ],
    "Lodzkie": [
        "Łódź",
        "Piotrków Trybunalski",
        "Pabianice",
        "Tomaszów Mazowiecki",
        "Bełchatów",
        "Zgierz",
        "Kutno",
    ],
    "Wielkopolskie": [
        "Poznań",
        "Kalisz",
        "Konin",
        "Piła",
        "Ostrów Wielkopolski",
        "Gniezno",
        "Leszno",
        "Swarzędz",
    ],
    "Dolnoslaskie": [
        "Głogów",
        "Wrocław",
        "Wałbrzych",
        "Legnica",
        "Jelenia Góra",
        "Lubin",
        "Świdnica",
        "Oleśnica",
    ],
    "Slaskie": [
        "Katowice",
        "Gliwice",
        "Zabrze",
        "Bytom",
        "Ruda Śląska",
        "Tychy",
        "Dąbrowa Górnicza",
        "Rybnik",
        "Częstochowa",
        "Sosnowiec",
    ],
    "Malopolskie": [
        "Kraków",
        "Tarnów",
        "Nowy Sącz",
        "Oświęcim",
        "Chrzanów",
        "Olkusz",
        "Skawina",
    ],
    "Pomorskie": [
        "Gdańsk",
        "Gdynia",
        "Sopot",
        "Słupsk",
        "Tczew",
        "Starogard Gdański",
        "Wejherowo",
    ],
    "Zachodniopomorskie": [
        "Szczecin",
        "Koszalin",
        "Stargard",
        "Świnoujście",
        "Kołobrzeg",
        "Police",
    ],
    "Lubuskie": [
        "Zielona Góra",
        "Gorzów Wielkopolski",
        "Nowa Sól",
        "Żary",
        "Żagań",
    ],
    "Kujawsko-Pomorskie": [
        "Bydgoszcz",
        "Toruń",
        "Włocławek",
        "Grudziądz",
        "Inowrocław",
        "Brodnica",
    ],
    "Warminsko-Mazurskie": [
        "Olsztyn",
        "Elbląg",
        "Ełk",
        "Ostróda",
        "Iława",
        "Giżycko",
    ],
    "Podlaskie": [
        "Białystok",
        "Suwałki",
        "Łomża",
        "Augustów",
        "Bielsk Podlaski",
    ],
    "Lubelskie": [
        "Lublin",
        "Chełm",
        "Zamość",
        "Biała Podlaska",
        "Puławy",
        "Kraśnik",
    ],
    "Podkarpackie": [
        "Rzeszów",
        "Przemyśl",
        "Stalowa Wola",
        "Mielec",
        "Krosno",
        "Dębica",
        "Jarosław",
    ],
    "Swietokrzyskie": [
        "Kielce",
        "Ostrowiec Świętokrzyski",
        "Starachowice",
        "Skarżysko-Kamienna",
        "Sandomierz",
    ],
    "Opolskie": [
        "Opole",
        "Kędzierzyn-Koźle",
        "Nysa",
        "Brzeg",
        "Kluczbork",
    ],
}


def strip_diacritics(s: str) -> str:
    s = s.replace("ł", "l").replace("Ł", "L")
    nk = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nk if not unicodedata.combining(c))


def to_key_from_local(name: str) -> str:
    n = strip_diacritics(name.strip().lower()).replace(" ", "-")
    return KEY_BY_SLUG.get(n, "")


def clean_powiat(name: str) -> str:
    return name.replace("\n", "").strip()


def main() -> None:
    cities = json.loads((BASE / "cities_src.json").read_text(encoding="utf-8"))
    counties = json.loads((BASE / "counties_src.json").read_text(encoding="utf-8"))
    vois = json.loads((BASE / "voivodeships_src.json").read_text(encoding="utf-8"))
    all_county = json.loads((BASE / "all_county.json").read_text(encoding="utf-8"))

    voi_by_id = {v["id"]: v for v in vois}
    county_by_id = {c["id"]: c for c in counties}
    geo: dict[str, dict[str, set[str]]] = {
        k: {"cities": set(), "powiaty": set()} for k in KEY_BY_SLUG.values()
    }

    missing_city = 0
    for city in cities:
        name = (city.get("name") or "").strip()
        if not name:
            continue
        cty = county_by_id.get(city.get("county_id"))
        if not cty:
            missing_city += 1
            continue
        voi = voi_by_id.get(cty["voivodeship_id"])
        if not voi:
            missing_city += 1
            continue
        key = KEY_BY_SLUG.get(voi["slug"])
        if not key:
            missing_city += 1
            continue
        geo[key]["cities"].add(name)

    for cty in counties:
        voi = voi_by_id.get(cty["voivodeship_id"])
        if not voi:
            continue
        key = KEY_BY_SLUG.get(voi["slug"])
        if not key:
            continue
        raw = (cty.get("name") or "").strip()
        if raw:
            geo[key]["powiaty"].add(raw)

    unmapped = 0
    for c in all_county:
        parent = (c.get("parent") or {}).get("name") or {}
        slug = (parent.get("slug") or "").split("-pl")[0]
        en = (parent.get("en") or "").strip()
        key = KEY_BY_SLUG.get(slug) or EN_TO_KEY.get(en) or to_key_from_local(
            parent.get("local") or ""
        )
        if not key:
            unmapped += 1
            continue
        local = ((c.get("name") or {}).get("local") or "").strip()
        if local:
            geo[key]["powiaty"].add(local)

    for k, lst in SEEDS.items():
        geo[k]["cities"].update(lst)

    final: dict[str, dict[str, tuple[str, ...]]] = {}
    for k in ORDER:
        cities_t = tuple(
            sorted(geo[k]["cities"], key=lambda s: strip_diacritics(s).lower())
        )
        by_norm: dict[str, str] = {}
        for p in geo[k]["powiaty"]:
            p = clean_powiat(p)
            if not p:
                continue
            norm = strip_diacritics(p).lower()
            prev = by_norm.get(norm)
            if prev is None:
                by_norm[norm] = p
                continue
            score = (
                sum(1 for ch in p if ord(ch) > 127),
                1 if p[:1].islower() else 0,
                len(p),
            )
            score_prev = (
                sum(1 for ch in prev if ord(ch) > 127),
                1 if prev[:1].islower() else 0,
                len(prev),
            )
            if score > score_prev:
                by_norm[norm] = p
        powiaty_t = tuple(
            sorted(by_norm.values(), key=lambda s: strip_diacritics(s).lower())
        )
        final[k] = {"cities": cities_t, "powiaty": powiaty_t}

    total_c = sum(len(v["cities"]) for v in final.values())
    total_p = sum(len(v["powiaty"]) for v in final.values())
    print(
        f"lands={len(final)} cities={total_c} powiaty={total_p} "
        f"missing_city_rows={missing_city} unmapped_counties={unmapped}"
    )
    for k, v in final.items():
        print(f"{k:22} cities={len(v['cities']):3d} powiaty={len(v['powiaty']):3d}")

    lines = [
        "# -*- coding: utf-8 -*-",
        "# >>> OPIS MODULU ========================================",
        "# Moduł: pl_geo_locations — pełna geografia Polski pod discovery PL FAS.",
        "#",
        "# CO ROBI",
        "#   Trzyma statyczny słownik PL_GEO_BY_LAND: dla każdego z 16 województw (klucze jak w",
        "#   BUNDESLAND_CONFIG / gu_bundesland_rotation) dwa posortowane tuple:",
        "#     • cities  — nazwy miast (SIMC / lista miast), używane w frazach Google Maps i Serper",
        "#                 Places / broad (np. „firma spedycyjna Głogów”, „spedycja Poznań”);",
        "#     • powiaty — nazwy powiatów ziemskich i grodzkich, używane głównie w fali",
        "#                 landkreis („spedycja powiat bolesławiecki”) oraz uzupełniająco w Maps.",
        "#   Moduł NIE wykonuje I/O w runtime — to czyste dane + cienkie helpery odczytu.",
        "#",
        "# ROLA W PIPELINE",
        "#   1) pl_spedycja_keywords importuje PL_GEO_BY_LAND i buduje BUNDESLAND_CONFIG",
        "#      (short + cities + powiaty).",
        "#   2) build_maps_discovery_terms / build_places_discovery_terms iterują cities",
        "#      (i skrócone frazy powiatowe) → Faza A Maps + Places.",
        "#   3) build_landkreis_discovery_terms iteruje powiaty → fala Serper „powiat”.",
        "#   4) commercial_contact_filter / _infer_wojewodztwo / Excel city match czytają",
        "#      cities z BUNDESLAND_CONFIG (więc pośrednio stąd) jako markery geo.",
        "#   5) Rotacja 1 woj./dzień (gu_bundesland_rotation) zawęża active do jednego klucza",
        "#      — wtedy Maps dostaje tylko cities/powiaty TEGO województwa.",
        "#",
        "# SKĄD DANE (snapshot, nie live API)",
        "#   • data/cities_src.json, counties_src.json, voivodeships_src.json",
        "#     — github.com/ryczek02/Polskie-jednostki-administracyjne (miasta + powiaty ziemskie,",
        "#     polskie znaki diakrytyczne).",
        "#   • data/all_county.json",
        "#     — github.com/open-admin-data/poland-administrative-divisions (pełne ~380 powiatów,",
        "#     w tym grodzkie); deduplikacja woli wariant z diakrytykami / formy przymiotnikowe.",
        "#   • SEEDS w generatorze: dotychczasowe huby kampanii (Warszawa, Głogów, …) — gwarancja,",
        "#     że krytyczne miasta nie wypadną przy różnicach pisowni w źródłach.",
        "#",
        "# REGENERACJA",
        "#   python scripts/generate_pl_geo_locations.py",
        "#   Nadpisuje TEN plik (nagłówek + dane + helpery). Ręcznych edycji list miast zwykle",
        "#   NIE rób tutaj — dopisz SEEDS / popraw źródła JSON i odpal generator ponownie,",
        "#   żeby nie stracić zmian przy następnym generate.",
        "#",
        "# KLUCZE WOJEWÓDZTW",
        "#   Bez polskich znaków w identyfikatorze (legacy scraper): Dolnoslaskie, Lodzkie,",
        "#   Malopolskie, Slaskie, Swietokrzyskie, Warminsko-Mazurskie, … — MUSZĄ być 1:1 z",
        "#   BUNDESLAND_CONFIG i BUNDESLAND_ROTATION_ORDER (assert na dole + w keywords).",
        "#",
        "# SKALA / KOSZT DISCOVERY (ważne operacyjnie)",
        "#   Rząd wielkości: ~1000 miast + ~380 powiatów. Maps: 5 szablonów/miasto + 2/powiat",
        "#   → np. Mazowieckie setki fraz; przy ~1–2 min/zapytanie Maps jedno duże woj. może",
        "#   zająć wiele godzin (Contabo: SCRAPER_MAX_RUNTIME_SECONDS domyślnie 12h + resume).",
        "#   Serper landkreis po powiatach jest tańszy czasowo niż Maps, ale też rośnie z geo.",
        "#",
        "# ZALEŻNOŚCI",
        "#   Brak zależności runtime poza stdlib. Konsument: pl_spedycja_keywords (i dalej scraper,",
        "#   filter, rotacja). Nie importować scrapera wstecz — ten moduł ma zostać liściem.",
        "#",
        "# WEJŚCIE / WYJŚCIE",
        "#   Wejście: brak (stałe). Wyjście: PL_GEO_BY_LAND oraz helpery counts / listing.",
        "#   Asserty na imporcie: dokładnie 16 landów; każde ma niepuste cities i powiaty.",
        "# ============================================================",
        '"""',
        "Pełna geografia PL pod discovery spedycji (miasta + powiaty per województwo).",
        "",
        "Ten plik jest GENEROWANY — źródło prawdy list to `data/*.json` +",
        "`scripts/generate_pl_geo_locations.py`. Opis pipeline / skali: komentarz OPIS MODULU powyżej.",
        '"""',
        "from __future__ import annotations",
        "",
        "from typing import Iterable",
        "",
        "# ---------------------------------------------------------------------------",
        "# PL_GEO_BY_LAND",
        "# Słownik: klucz województwa → {\"cities\": tuple[str, ...], \"powiaty\": tuple[str, ...]}.",
        "# Kolejność kluczy = kolejność rotacji kampanii (Dolnośląskie → … → Opolskie), żeby",
        "# diffy/PR-y były czytelne i zbieżne z BUNDESLAND_ROTATION_ORDER.",
        "# Tuple (nie list): niemutowalne po imporcie; sortowanie alfabetyczne bez diakrytyków",
        "# w generatorze (ł→l), żeby „Łódź” padało obok „Lublin” logicznie w źródłach JSON.",
        "# Nazwy powiatów: często forma przymiotnikowa mała („bolesławiecki”) — frazy dokładają",
        "# słowo „powiat” w builderach keywords; grodzkie bywają nazwą miasta („Opole”, „Warszawa”).",
        "# ---------------------------------------------------------------------------",
        "PL_GEO_BY_LAND: dict[str, dict[str, tuple[str, ...]]] = {",
    ]
    for k in ORDER:
        v = final[k]
        n_c, n_p = len(v["cities"]), len(v["powiaty"])
        lines.append(
            f"    # --- {k}: {n_c} miast, {n_p} powiatów "
            f"(Maps≈{n_c * 5 + n_p * 2} fraz przy pełnych szablonach) ---"
        )
        lines.append(f'    "{k}": {{')
        lines.append(
            f'        # cities — wszystkie miasta woj. {k} (SIMC / snapshot); '
            f"używane w Maps + Places + broad."
        )
        lines.append('        "cities": (')
        for c in v["cities"]:
            lines.append(f"            {c!r},")
        lines.append("        ),")
        lines.append(
            f'        # powiaty — ziemskie + grodzkie woj. {k}; fala Serper landkreis + Maps „powiat X”.'
        )
        lines.append('        "powiaty": (')
        for p in v["powiaty"]:
            lines.append(f"            {p!r},")
        lines.append("        ),")
        lines.append("    },")
    lines.extend(
        [
            "}",
            "",
            "# ---------------------------------------------------------------------------",
            "# Asserty importu — fail-fast gdy generator / ręczna edycja rozjedzie się z kampanią.",
            "# 16 = liczba województw PL; keywords i rotacja wymagają dokładnie tego zbioru kluczy.",
            "# ---------------------------------------------------------------------------",
            "assert len(PL_GEO_BY_LAND) == 16, (",
            '    f"Oczekiwano 16 województw, jest {len(PL_GEO_BY_LAND)}"',
            ")",
            "assert all(",
            '    isinstance(v.get("cities"), tuple)',
            '    and isinstance(v.get("powiaty"), tuple)',
            '    and len(v["cities"]) > 0',
            '    and len(v["powiaty"]) > 0',
            "    for v in PL_GEO_BY_LAND.values()",
            "), \"Każde województwo musi mieć niepuste tuple cities i powiaty\"",
            "",
            "",
            "# >>> OPIS FUNKCJI: funkcja iter_land_keys",
            "# Cel: stabilna kolejność kluczy województw (jak w PL_GEO_BY_LAND / rotacji).",
            "# Parametry: brak. Zwraca: Iterable[str]. Efekty uboczne: brak.",
            "def iter_land_keys() -> Iterable[str]:",
            '    """Klucze województw w kolejności zadeklarowanej w PL_GEO_BY_LAND."""',
            "    return PL_GEO_BY_LAND.keys()",
            "",
            "",
            "# >>> OPIS FUNKCJI: funkcja cities_for",
            "# Cel: pobrać tuple miast dla jednego województwa (klucz kampanii).",
            "# Parametry: land (str) — np. \"Dolnoslaskie\". Zwraca: tuple[str, ...]; KeyError gdy zły klucz.",
            "# Efekty uboczne: brak. Użycie: testy, diagnostyka, ewentualne skrypty poza keywords.",
            "def cities_for(land: str) -> tuple[str, ...]:",
            '    """Miasta danego województwa (klucz jak w BUNDESLAND_CONFIG)."""',
            '    return PL_GEO_BY_LAND[land]["cities"]',
            "",
            "",
            "# >>> OPIS FUNKCJI: funkcja powiaty_for",
            "# Cel: pobrać tuple powiatów dla jednego województwa.",
            "# Parametry: land (str). Zwraca: tuple[str, ...]; KeyError gdy zły klucz.",
            "# Efekty uboczne: brak.",
            "def powiaty_for(land: str) -> tuple[str, ...]:",
            '    """Powiaty (ziemskie/grodzkie) danego województwa."""',
            '    return PL_GEO_BY_LAND[land]["powiaty"]',
            "",
            "",
            "# >>> OPIS FUNKCJI: funkcja geo_counts",
            "# Cel: podsumowanie skali geo (do logów, testów, szacunku czasu discovery).",
            "# Parametry: brak. Zwraca: dict z kluczami:",
            "#   lands (int), cities_total (int), powiaty_total (int),",
            "#   per_land (dict[str, dict[str,int]] z cities/powiaty per woj.).",
            "# Efekty uboczne: brak.",
            "def geo_counts() -> dict[str, object]:",
            '    """Policz miasta/powiaty łącznie i per województwo."""',
            "    per: dict[str, dict[str, int]] = {}",
            "    cities_total = 0",
            "    powiaty_total = 0",
            "    for land, cfg in PL_GEO_BY_LAND.items():",
            '        n_c = len(cfg["cities"])',
            '        n_p = len(cfg["powiaty"])',
            '        per[land] = {"cities": n_c, "powiaty": n_p}',
            "        cities_total += n_c",
            "        powiaty_total += n_p",
            "    return {",
            '        "lands": len(PL_GEO_BY_LAND),',
            '        "cities_total": cities_total,',
            '        "powiaty_total": powiaty_total,',
            '        "per_land": per,',
            "    }",
            "",
        ]
    )
    OUT_PY.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT_PY} ({OUT_PY.stat().st_size} bytes)")


if __name__ == "__main__":
    main()

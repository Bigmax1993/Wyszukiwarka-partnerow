# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Uzupełnienie opisu modułu pl_spedycja_keywords (komentarz; docstring poniżej opisuje zakres ICP i nazewnictwo).
#   Rola w pipeline: etap discovery — słowniki (BUNDESLAND_CONFIG = województwa i miasta, segmenty
#   RETAIL_CHAINS_ROTATION, szablony fraz, SERPER_NEGATIVE_TERMS) oraz generatory kolejnych „fal” fraz Serper
#   (główna, powiat/okolice, places, broad, fallback).
#   Zależności: tylko __future__ (moduł liściowy) — dlatego importują go filter, prompty i rotacja.
#   Wejście: lista województw, limit fraz. Wyjście: list[str] fraz lub konfiguracja ustawiona na module
#   (configure_campaign_bundeslaender mutuje atrybuty przekazanego modułu scrapera).
# ============================================================
"""
Słowniki i generatory fraz Serper / www — polskie spedycje drogowe.

Zakres ICP: biura spedycyjne PL (FTL / LTL / międzynarodowy / ADR / chłodnia),
nie kurierzy, nie giełdy, nie wielkie 3PL.

Geo: województwa (`BUNDESLAND_CONFIG` — nazwa legacy DE dla kompatybilności
importów scrapera). Segmenty oferty (`RETAIL_CHAINS_ROTATION`) rotują w
placeholderze ``{chain}`` zamiast dawnych sieci handlowych.

Nazwy symboli `BUNDESLAND_*`, `RETAIL_*`, `GU_*`, `SERPER_DISCOVERY_*`
zostają pod starymi identyfikatorami, żeby scraper i testy nie wymagały
masowej zmiany importów — zmienia się treść PL, nie API modułu.
"""
from __future__ import annotations

# Segmenty rotowane w szablonach (dawniej Aldi/Rewe/Netto).
RETAIL_CHAINS_ROTATION = (
    "FTL",
    "LTL",
    "całopojazdowy",
    "międzynarodowy",
    "Europa",
    "Niemcy",
    "grupaż",
    "ADR",
    "chłodnia",
    "plandełka",
    "tir",
    "fracht",
)

# Role / markery „to jest spedycja” (dawniej GU_ROLE_KEYWORDS)
GU_ROLE_KEYWORDS = (
    "spedycja",
    "spedytor",
    "firma spedycyjna",
    "biuro spedycyjne",
    "freight forwarding",
    "freight forwarder",
    "organizacja transportu",
    "dyspozytor",
    "dyspozytornia",
)

RETAIL_CHAIN_KEYWORDS = RETAIL_CHAINS_ROTATION
REQUIRED_RETAIL_CHAIN_KEYWORDS = (
    "FTL",
    "LTL",
    "fracht",
    "spedycja",
    "transport międzynarodowy",
    "transport drogowy",
    "całopojazdowy",
    "grupaż",
)

RETAIL_BUILD_KEYWORDS = (
    "transport drogowy",
    "transport międzynarodowy",
    "transport ciężarowy",
    "organizacja przewozu",
    "obsługa frachtu",
    "spedycja FTL",
    "spedycja LTL",
)

RETAIL_TRADE_ACTIVITY_KEYWORDS = (
    "załadunek",
    "rozładunek",
    "trasa",
    "kierunek",
    "flota",
    "naczepa",
    "tir",
    "plandełka",
    "chłodnia",
    "ADR",
)

RETAIL_HOCHBAU_CORE_KEYWORDS = (
    "spedycja",
    "logistyka",
    "transport",
    "fracht",
    "FTL",
)

RETAIL_REFERENCE_KEYWORDS = (
    "realizacje",
    "klienci",
    "referencje",
    "trasy",
    "kierunki",
    "portfolio",
    "o nas",
    "flota",
)

RETAIL_URL_PRIORITY_KEYWORDS = (
    "kontakt",
    "contact",
    "o-nas",
    "o_nas",
    "onas",
    "flota",
    "oferta",
    "uslugi",
    "usługi",
    "spedycja",
    "transport",
    "kariera",
    "praca",
    "rodo",
)

IMPRESSUM_GUESS_PATHS = (
    "/kontakt",
    "/kontakt/",
    "/contact",
    "/contact/",
    "/o-nas",
    "/o-nas/",
    "/o_firmie",
    "/o-firmie",
    "/about",
    "/firma",
    "/dane-firmy",
    "/polityka-prywatnosci",
    "/rodo",
)

RETAIL_CONTACT_LINK_KEYWORDS = (
    "kontakt",
    "contact",
    "napisz",
    "zapytanie",
    "oferta",
    "biuro",
    "e-mail",
    "email",
)

SERPER_POSITIVE_TERMS = (
    "spedycja",
    "spedytor",
    "firma spedycyjna",
    "freight forwarding",
    "FTL",
    "LTL",
    "transport międzynarodowy",
    "transport drogowy",
    "fracht",
    "dyspozytor",
    "całopojazdowy",
    "grupaż",
    "organizacja transportu",
)

SERPER_NEGATIVE_TERMS = (
    "praca",
    "oferty pracy",
    "kariera",
    "kurier",
    "paczkomat",
    "InPost",
    "DPD",
    "DHL Express",
    "giełda transportowa",
    "TIMOCOM",
    "Trans.eu",
    "ogłoszenia",
    "szkolenie",
    "kurs na prawo jazdy",
    "wynajem autokarów",
    "przeprowadzki",
)

LARGE_COMPANY_DOMAINS_EXTRA = frozenset(
    {
        "raben-group.com",
        "dbschenker.com",
        "dhl.com",
        "dpd.com",
        "inpost.pl",
        "geodis.com",
        "kuehne-nagel.com",
        "dsv.com",
        "rohlig.com",
        "pekaes.pl",
        "rohlig.pl",
    }
)

LARGE_COMPANY_NAME_MARKERS_EXTRA = (
    "Raben",
    "DB Schenker",
    "Schenker",
    "DHL",
    "DPD",
    "InPost",
    "GEODIS",
    "Kuehne",
    "Kuehne+Nagel",
    "DSV",
    "PEKAES",
    "Rohlig",
    "FM Logistic",
)

SMALL_COMPANY_PAGE_MARKERS_EXTRA = (
    "firma rodzinna",
    "spedycja lokalna",
    "od lat na rynku",
    "biuro w",
    "nasze biuro",
    "właściciel",
    "założyciel",
)

SMALL_COMPANY_DISCOVERY_TERMS_EXTRA = (
    "mała spedycja",
    "lokalna firma spedycyjna",
    "spedycja rodzinna",
)

DE_OST_PLACE_MARKERS: tuple[str, ...] = ()
DE_OST_REGION_KEYWORDS = (
    "polska",
    "poland",
    "rp",
)
DE_OST_RURAL_HINTS: tuple[str, ...] = (
    "powiat",
    "gmina",
    "okolice",
)

# Frazy Serper: część z rotującym {chain} (= segment FTL/LTL/…), część bez (lepsze małe miasta).
CHAIN_SIMPLE_TERM_TEMPLATES = (
    "spedycja {chain} {city}",
    "firma spedycyjna {city} {chain}",
    "spedycja drogowa {city} {chain}",
    "transport FTL {city} {chain}",
    "spedycja międzynarodowa {city} {chain}",
    "dyspozytor fracht {city} {chain}",
    "organizacja transportu {city} {chain}",
    "spedycja {city} transport drogowy {chain}",
    "freight forwarding {city} {chain}",
    "biuro spedycyjne {city} {chain}",
    # Bez {chain}
    "spedycja {city}",
    "firma spedycyjna {city}",
    "spedycja drogowa {city}",
    "spedycja międzynarodowa {city}",
    "organizacja transportu {city}",
    "spedycja {city} transport drogowy",
    "freight forwarding {city}",
    "biuro spedycyjne {city}",
    "dyspozytor fracht {city}",
)

TERM_TEMPLATES = (
    "firma spedycyjna transport międzynarodowy {city} {chain}",
    "spedycja FTL Polska {chain} {city}",
    "spedycja drogowa Europa {city} {chain}",
    "transport całopojazdowy {city} {chain}",
    "spedycja {city} {land} {chain}",
    "firma transportowa spedycja {city} {chain}",
    "spedytor {city} fracht {chain}",
    "logistyka kontraktowa spedycja {city} {chain}",
    "transport ciężarowy spedycja {city} {chain}",
    "oferty frachtowe spedycja {city} {chain}",
    # Bez {chain}
    "spedycja {city}",
    "firma spedycyjna {city}",
    "spedycja drogowa {city}",
    "biuro spedycyjne {city}",
    "spedytor {city}",
    "firma spedycyjna transport międzynarodowy {city}",
    "transport całopojazdowy {city}",
    "spedycja {city} {land}",
    "firma transportowa spedycja {city}",
    "spedytor {city} fracht",
    "logistyka kontraktowa spedycja {city}",
    "transport ciężarowy spedycja {city}",
    "oferty frachtowe spedycja {city}",
    "spedycja drogowa Europa {city}",
)

SIMPLE_TERM_TEMPLATES = CHAIN_SIMPLE_TERM_TEMPLATES

BUNDESLAND_CONFIG: dict[str, dict] = {
    "Mazowieckie": {
        "short": "MZ",
        "cities": (
            "Warszawa",
            "Radom",
            "Płock",
            "Siedlce",
            "Pruszków",
            "Piaseczno",
            "Ostrołęka",
            "Żyrardów",
        ),
    },
    "Lodzkie": {
        "short": "LD",
        "cities": (
            "Łódź",
            "Piotrków Trybunalski",
            "Pabianice",
            "Tomaszów Mazowiecki",
            "Bełchatów",
            "Zgierz",
            "Kutno",
        ),
    },
    "Wielkopolskie": {
        "short": "WP",
        "cities": (
            "Poznań",
            "Kalisz",
            "Konin",
            "Piła",
            "Ostrów Wielkopolski",
            "Gniezno",
            "Leszno",
            "Swarzędz",
        ),
    },
    "Dolnoslaskie": {
        "short": "DS",
        "cities": (
            "Głogów",
            "Wrocław",
            "Wałbrzych",
            "Legnica",
            "Jelenia Góra",
            "Lubin",
            "Świdnica",
            "Oleśnica",
        ),
    },
    "Slaskie": {
        "short": "SL",
        "cities": (
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
        ),
    },
    "Malopolskie": {
        "short": "MP",
        "cities": (
            "Kraków",
            "Tarnów",
            "Nowy Sącz",
            "Oświęcim",
            "Chrzanów",
            "Olkusz",
            "Skawina",
        ),
    },
    "Pomorskie": {
        "short": "PM",
        "cities": (
            "Gdańsk",
            "Gdynia",
            "Sopot",
            "Słupsk",
            "Tczew",
            "Starogard Gdański",
            "Wejherowo",
        ),
    },
    "Zachodniopomorskie": {
        "short": "ZP",
        "cities": (
            "Szczecin",
            "Koszalin",
            "Stargard",
            "Świnoujście",
            "Kołobrzeg",
            "Police",
        ),
    },
    "Lubuskie": {
        "short": "LB",
        "cities": (
            "Zielona Góra",
            "Gorzów Wielkopolski",
            "Nowa Sól",
            "Żary",
            "Żagań",
        ),
    },
    "Kujawsko-Pomorskie": {
        "short": "KP",
        "cities": (
            "Bydgoszcz",
            "Toruń",
            "Włocławek",
            "Grudziądz",
            "Inowrocław",
            "Brodnica",
        ),
    },
    "Warminsko-Mazurskie": {
        "short": "WN",
        "cities": (
            "Olsztyn",
            "Elbląg",
            "Ełk",
            "Ostróda",
            "Iława",
            "Giżycko",
        ),
    },
    "Podlaskie": {
        "short": "PD",
        "cities": (
            "Białystok",
            "Suwałki",
            "Łomża",
            "Augustów",
            "Bielsk Podlaski",
        ),
    },
    "Lubelskie": {
        "short": "LU",
        "cities": (
            "Lublin",
            "Chełm",
            "Zamość",
            "Biała Podlaska",
            "Puławy",
            "Kraśnik",
        ),
    },
    "Podkarpackie": {
        "short": "PK",
        "cities": (
            "Rzeszów",
            "Przemyśl",
            "Stalowa Wola",
            "Mielec",
            "Krosno",
            "Dębica",
            "Jarosław",
        ),
    },
    "Swietokrzyskie": {
        "short": "SK",
        "cities": (
            "Kielce",
            "Ostrowiec Świętokrzyski",
            "Starachowice",
            "Skarżysko-Kamienna",
            "Sandomierz",
        ),
    },
    "Opolskie": {
        "short": "OP",
        "cities": (
            "Opole",
            "Kędzierzyn-Koźle",
            "Nysa",
            "Brzeg",
            "Kluczbork",
        ),
    },
}

DEFAULT_ACTIVE_BUNDESLAENDER = list(BUNDESLAND_CONFIG.keys())
CAMPAIGN_ACTIVE_BUNDESLAENDER = list(DEFAULT_ACTIVE_BUNDESLAENDER)
# Alias legacy (testy / scraper DE naming)
ALL_BUNDESLAENDER = tuple(DEFAULT_ACTIVE_BUNDESLAENDER)


def default_max_discovery_terms_for(active: list[str] | None = None) -> int:
    """
    Domyślny limit długości listy fraz Serper dla aktywnych województw.

    Po co: scraper i `configure_campaign_bundeslaender` muszą wiedzieć, ile
    wariantów wygenerować — za mało = słabe pokrycie geo, za dużo = koszt API.

    Formuła: ``12 × liczba miast`` w wybranych województwach, obcięta do
    zakresu 200…1000 (górny limit kampanii PL).
    """
    lands = resolve_active_bundeslaender(active)
    return max(
        200,
        min(1000, 12 * sum(len(BUNDESLAND_CONFIG[w]["cities"]) for w in lands)),
    )


def _normalize_land_key(name: str) -> str:
    """
    Normalizuje surową nazwę / skrót województwa do klucza `BUNDESLAND_CONFIG`.

    Przyjmuje: kod dwuliterowy (``MZ``), nazwę ze znakami diakrytycznymi
    (``łódzkie``) oraz zapis ASCII (``Lodzkie``). Nieznany ciąg zwracany
    jest bez zmian — `resolve_active_bundeslaender` potem odrzuci go,
    jeśli nie ma go w konfiguracji.
    """
    n = (name or "").strip()
    aliases = {
        "mz": "Mazowieckie",
        "mazowsze": "Mazowieckie",
        "mazowieckie": "Mazowieckie",
        "ld": "Lodzkie",
        "łódzkie": "Lodzkie",
        "lodzkie": "Lodzkie",
        "wp": "Wielkopolskie",
        "wielkopolskie": "Wielkopolskie",
        "ds": "Dolnoslaskie",
        "dolnośląskie": "Dolnoslaskie",
        "dolnoslaskie": "Dolnoslaskie",
        "sl": "Slaskie",
        "śląskie": "Slaskie",
        "slaskie": "Slaskie",
        "mp": "Malopolskie",
        "małopolskie": "Malopolskie",
        "malopolskie": "Malopolskie",
        "pm": "Pomorskie",
        "pomorskie": "Pomorskie",
        "zp": "Zachodniopomorskie",
        "zachodniopomorskie": "Zachodniopomorskie",
        "lb": "Lubuskie",
        "lubuskie": "Lubuskie",
        "kp": "Kujawsko-Pomorskie",
        "kujawsko-pomorskie": "Kujawsko-Pomorskie",
        "wn": "Warminsko-Mazurskie",
        "warmińsko-mazurskie": "Warminsko-Mazurskie",
        "warminsko-mazurskie": "Warminsko-Mazurskie",
        "pd": "Podlaskie",
        "podlaskie": "Podlaskie",
        "lu": "Lubelskie",
        "lubelskie": "Lubelskie",
        "pk": "Podkarpackie",
        "podkarpackie": "Podkarpackie",
        "sk": "Swietokrzyskie",
        "świętokrzyskie": "Swietokrzyskie",
        "swietokrzyskie": "Swietokrzyskie",
        "op": "Opolskie",
        "opolskie": "Opolskie",
    }
    low = n.lower()
    if low in aliases:
        return aliases[low]
    for key in BUNDESLAND_CONFIG:
        if key.lower() == low:
            return key
    return n


def resolve_active_bundeslaender(names: list[str] | None = None) -> list[str]:
    """
    Buduje uporządkowaną listę aktywnych województw kampanii.

    ``names=None`` / pusta → bieżące `CAMPAIGN_ACTIVE_BUNDESLAENDER`.
    Wejście może być listą albo ciągami z przecinkami/średnikami
    (np. z CLI / JSON run_config). Duplikaty są usuwane z zachowaniem
    kolejności. Gdy po normalizacji nic nie zostaje — wraca pełna lista
    `DEFAULT_ACTIVE_BUNDESLAENDER` (wszystkie 16 województw).

    Nazwa funkcji zostaje DE (`bundeslaender`) przez kompatybilność scrapera.
    """
    if not names:
        return list(CAMPAIGN_ACTIVE_BUNDESLAENDER)
    out: list[str] = []
    for raw in names:
        for part in str(raw).replace(";", ",").split(","):
            key = _normalize_land_key(part)
            if key in BUNDESLAND_CONFIG and key not in out:
                out.append(key)
    return out or list(DEFAULT_ACTIVE_BUNDESLAENDER)


def _append_unique_term(terms: list[str], seen: set[str], text: str, *, max_terms: int) -> bool:
    """
    Dopisuje unikalną frazę do listy discovery.

    Puste i już widziane frazy są pomijane. Zwraca ``True``, gdy po dodaniu
    osiągnięto ``max_terms`` — sygnał dla generatorów, żeby przerwać pętlę.
    """
    t = (text or "").strip()
    if not t or t in seen:
        return False
    seen.add(t)
    terms.append(t)
    return len(terms) >= max_terms


def _rotating_chain(counter: list[int]) -> str:
    """
    Kolejny segment oferty z `RETAIL_CHAINS_ROTATION` (FTL, LTL, ADR, …).

    ``counter`` to jednoelementowa lista-mutowalny licznik współdzielony
    w ramach jednego przebiegu `build_*` — dzięki temu placeholdery
    ``{chain}`` rozkładają się równomiernie po miastach i szablonach.
    """
    chain = RETAIL_CHAINS_ROTATION[counter[0] % len(RETAIL_CHAINS_ROTATION)]
    counter[0] += 1
    return chain


def _format_chain_term(
    tmpl: str,
    *,
    city: str,
    land: str,
    chain: str,
) -> str:
    """
    Wypełnia szablon Serper polami ``{city}``, ``{land}``, ``{chain}``.

    Szablony bez któregoś placeholdera są poprawne — `str.format`
    wymaga tylko użytych kluczy; tu podajemy wszystkie trzy zawsze.
    """
    return tmpl.format(city=city, land=land, chain=chain)


def build_discovery_terms(
    active: list[str] | None = None, *, max_terms: int | None = None
) -> list[str]:
    """
    Główna (fala 1) lista fraz Serper: miasto × szablon × rotujący segment.

    Łączy `CHAIN_SIMPLE_TERM_TEMPLATES` i `TERM_TEMPLATES`, iteruje aktywne
    województwa i ich miasta. Przy ≥10 województwach dokłada też krótkie
    frazy ogólnopolskie („Polska”, „Europa”). Kończy wcześniej, gdy
    ``max_terms`` (domyślnie z `default_max_discovery_terms_for`) jest pełny.

    Wynik trafia do `SERPER_DISCOVERY_TERMS` / scrapera jako primary query set.
    """
    lands = resolve_active_bundeslaender(active)
    if max_terms is None:
        max_terms = default_max_discovery_terms_for(lands)
    seen: set[str] = set()
    terms: list[str] = []
    chain_counter = [0]
    all_templates = (*CHAIN_SIMPLE_TERM_TEMPLATES, *TERM_TEMPLATES)
    for land in lands:
        cfg = BUNDESLAND_CONFIG[land]
        cities = cfg["cities"]
        for city in cities:
            for tmpl in all_templates:
                chain = _rotating_chain(chain_counter)
                if _append_unique_term(
                    terms,
                    seen,
                    _format_chain_term(tmpl, city=city, land=land, chain=chain),
                    max_terms=max_terms,
                ):
                    return terms
    if len(lands) >= 10:
        nationwide = (
            "spedycja FTL Polska {chain}",
            "firma spedycyjna transport międzynarodowy Polska {chain}",
            "spedycja drogowa Europa Polska {chain}",
            "biuro spedycyjne Polska {chain}",
            "organizacja transportu FTL Polska {chain}",
            "freight forwarding Poland {chain}",
            "spedycja Polska Niemcy {chain}",
            "spedytor fracht Polska {chain}",
            # Bez {chain}
            "spedycja Polska",
            "firma spedycyjna Polska",
            "spedycja drogowa Polska",
            "biuro spedycyjne Polska",
            "organizacja transportu Polska",
            "freight forwarding Poland",
            "spedycja Polska Niemcy",
            "spedytor Polska",
            "firma spedycyjna transport międzynarodowy Polska",
        )
        for tmpl in nationwide:
            chain = _rotating_chain(chain_counter)
            if _append_unique_term(
                terms,
                seen,
                tmpl.format(chain=chain),
                max_terms=max_terms,
            ):
                return terms
    return terms


def build_landkreis_discovery_terms(active: list[str] | None = None) -> list[str]:
    """
    Fala discovery z geo „powiat / okolice” (dawniej landkreis w DE).

    Po co: primary frazy często trafiają w duże miasta; ten zestaw szuka
    biur w mniejszych ośrodkach wokół hubów (pierwsze 6 miast woj. +
    fraza na całe województwo). Limit praktycznie otwarty (10k) — pełne
    pokrycie geo, bez obcinania jak w fali 1.
    """
    lands = resolve_active_bundeslaender(active)
    seen: set[str] = set()
    terms: list[str] = []
    chain_counter = [0]
    for land in lands:
        short = BUNDESLAND_CONFIG[land]["short"]
        for city in BUNDESLAND_CONFIG[land]["cities"][:6]:
            for tmpl in (
                "spedycja {city} powiat {chain}",
                "firma spedycyjna okolice {city} {chain}",
                "transport FTL {city} {short} {chain}",
                # Bez segmentu {chain} — lepsze pokrycie mniejszych miast (Serper).
                "spedycja {city} powiat",
                "firma spedycyjna okolice {city}",
                "spedycja drogowa {city}",
                "biuro spedycyjne {city}",
            ):
                chain = _rotating_chain(chain_counter)
                _append_unique_term(
                    terms,
                    seen,
                    tmpl.format(city=city, short=short, chain=chain),
                    max_terms=10_000,
                )
        chain = _rotating_chain(chain_counter)
        _append_unique_term(
            terms,
            seen,
            f"spedycja drogowa {land} {chain}",
            max_terms=10_000,
        )
        _append_unique_term(
            terms,
            seen,
            f"spedycja drogowa {land}",
            max_terms=10_000,
        )
        _append_unique_term(
            terms,
            seen,
            f"firma spedycyjna {land}",
            max_terms=10_000,
        )
    return terms


def build_maps_discovery_terms(active: list[str] | None = None) -> list[str]:
    """
    Frazy pod Google Maps (Faza A) — bez FTL/LTL/ADR/{chain}.

    Local Pack lubi krótkie zapytania jak „firma spedycyjna Głogów”.
    Segmenty FTL/LTL w query Maps pogarszają wyniki (puste / śmieci).
    """
    lands = resolve_active_bundeslaender(active)
    seen: set[str] = set()
    terms: list[str] = []
    for land in lands:
        for city in BUNDESLAND_CONFIG[land]["cities"]:
            for tmpl in (
                "firma spedycyjna {city}",
                "spedycja {city}",
                "spedytor {city}",
                "biuro spedycyjne {city}",
                "firma transportowa {city}",
            ):
                _append_unique_term(
                    terms, seen, tmpl.format(city=city), max_terms=10_000
                )
        for tmpl in (
            "firma spedycyjna {land}",
            "spedycja {land}",
            "biuro spedycyjne {land}",
        ):
            _append_unique_term(
                terms, seen, tmpl.format(land=land), max_terms=10_000
            )
    return terms


def build_places_discovery_terms(active: list[str] | None = None) -> list[str]:
    """
    Krótkie frazy pod endpoint Serper ``/places`` (wizytówki firm).

    Places lubi zwięzłe zapytania typu „spedycja {city}” —
    dłuższe szablony z fali 1 słabiej działają na lokalnym indeksie.
    Bierze do 8 miast na województwo + jedną frazę na samo woj.
    Bez FTL/LTL w query (Local Pack ich nie potrzebuje).
    """
    lands = resolve_active_bundeslaender(active)
    seen: set[str] = set()
    terms: list[str] = []
    for land in lands:
        for city in BUNDESLAND_CONFIG[land]["cities"][:8]:
            for tmpl in (
                "spedycja {city}",
                "firma spedycyjna {city}",
                "spedytor {city}",
                "biuro spedycyjne {city}",
                "firma transportowa {city}",
            ):
                _append_unique_term(
                    terms, seen, tmpl.format(city=city), max_terms=10_000
                )
        _append_unique_term(
            terms,
            seen,
            f"spedycja {land}",
            max_terms=10_000,
        )
        _append_unique_term(
            terms,
            seen,
            f"firma spedycyjna {land}",
            max_terms=10_000,
        )
    return terms


def build_broad_discovery_terms(active: list[str] | None = None) -> list[str]:
    """
    Szersza / luźniejsza fala discovery (gdy primary zwraca za mało URL).

    Mniej segmentów w frazie (często samo miasto lub samo województwo),
    więcej wariantów na każde miasto. Używana jako `SERPER_DISCOVERY_BROAD_TERMS`
    po wyczerpaniu primary / landkreis.
    """
    lands = resolve_active_bundeslaender(active)
    seen: set[str] = set()
    terms: list[str] = []
    chain_counter = [0]
    for land in lands:
        short = BUNDESLAND_CONFIG[land]["short"]
        for city in BUNDESLAND_CONFIG[land]["cities"]:
            for tmpl in (
                "spedycja {city}",
                "firma spedycyjna {city}",
                "transport drogowy {city}",
                "spedytor {city} {chain}",
                # Bez {chain}
                "spedytor {city}",
                "biuro spedycyjne {city}",
                "spedycja drogowa {city}",
            ):
                chain = _rotating_chain(chain_counter)
                _append_unique_term(
                    terms, seen, tmpl.format(city=city, chain=chain), max_terms=10_000
                )
        for tmpl in (
            "spedycja {land} {chain}",
            "firma spedycyjna {land}",
            "transport FTL {short}",
            "spedycja drogowa {land}",
            "freight forwarding {land}",
            # Bez {chain}
            "spedycja {land}",
            "spedytor {land}",
            "biuro spedycyjne {land}",
        ):
            chain = _rotating_chain(chain_counter)
            _append_unique_term(
                terms,
                seen,
                tmpl.format(land=land, short=short, chain=chain),
                max_terms=10_000,
            )
    return terms


def build_fallback_terms(active: list[str] | None = None) -> list[str]:
    """
    Krótki zestaw awaryjny: 4 frazy na województwo + kilka ogólnopolskich.

    Po co: gdy cache Serper / rotacja wyczerpie dłuższe listy, scraper
    nadal ma sensowne zapytania bez regeneracji pełnej fali 1. Deduplikacja
    na końcu usuwa ewentualne powtórzenia z rotacji ``{chain}``.
    """
    lands = resolve_active_bundeslaender(active)
    fb: list[str] = []
    chain_counter = [0]
    for land in lands:
        short = BUNDESLAND_CONFIG[land]["short"]
        for tmpl in (
            "spedycja {land} {chain}",
            "firma spedycyjna {short} {chain}",
            "transport międzynarodowy {land}",
            "spedycja FTL {land}",
            # Bez {chain}
            "spedycja {land}",
            "firma spedycyjna {short}",
            "firma spedycyjna {land}",
            "spedycja drogowa {land}",
        ):
            chain = _rotating_chain(chain_counter)
            fb.append(tmpl.format(land=land, short=short, chain=chain))
    for tmpl in (
        "spedycja FTL Polska {chain}",
        "firma spedycyjna Polska {chain}",
        "transport drogowy międzynarodowy Polska",
        "spedytor fracht Polska {chain}",
        # Bez {chain}
        "spedycja Polska",
        "firma spedycyjna Polska",
        "spedytor Polska",
        "biuro spedycyjne Polska",
    ):
        chain = _rotating_chain(chain_counter)
        fb.append(tmpl.format(chain=chain))
    seen: set[str] = set()
    out: list[str] = []
    for t in fb:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def build_region_suffix(active: list[str] | None = None) -> str:
    """
    Krótki sufiks regionu doklejany do części zapytań Serper.

    0–1 lub ≥4 województwa → samo ``\"Polska\"`` (bez szumu kodów).
    2–3 województwa → ``\"Polska MZ LD …\"`` ze skrótami z configu —
    delikatne zawężenie geo bez pełnych nazw w zapytaniu.
    """
    lands = resolve_active_bundeslaender(active)
    if len(lands) <= 1:
        return "Polska"
    if len(lands) >= 4:
        return "Polska"
    shorts = " ".join(BUNDESLAND_CONFIG[l]["short"] for l in lands[:4])
    return f"Polska {shorts}"


def configure_campaign_bundeslaender(
    module,
    names: list[str],
    *,
    max_discovery_terms: int | None = None,
) -> list[str]:
    """
    Ustawia aktywne województwa i przeładowuje wszystkie listy Serper na module.

    Typowe użycie: scraper po wczytaniu `run_config` wywołuje tę funkcję
    z listą województw z JSON. Aktualizuje:
    - globalne `CAMPAIGN_ACTIVE_BUNDESLAENDER` w tym module,
    - atrybuty discovery na ``module`` (zwykle `pl_fas_spedycja_scraper`):
      TERMS / FALLBACK / BROAD / LANDKREIS / PLACES / REGION_SUFFIX.

    Zwraca ostateczną listę aktywnych województw (po normalizacji).
    """
    global CAMPAIGN_ACTIVE_BUNDESLAENDER
    active = resolve_active_bundeslaender(names)
    if max_discovery_terms is None:
        max_discovery_terms = default_max_discovery_terms_for(active)
    CAMPAIGN_ACTIVE_BUNDESLAENDER = active
    module.CAMPAIGN_ACTIVE_BUNDESLAENDER = active
    module.SERPER_DISCOVERY_TERMS = build_discovery_terms(
        active, max_terms=max_discovery_terms
    )
    module.SERPER_DISCOVERY_FALLBACK_TERMS = build_fallback_terms(active)
    module.SERPER_DISCOVERY_BROAD_TERMS = build_broad_discovery_terms(active)
    module.SERPER_DISCOVERY_LANDKREIS_TERMS = build_landkreis_discovery_terms(active)
    module.SERPER_DISCOVERY_PLACES_TERMS = build_places_discovery_terms(active)
    module.SERPER_DISCOVERY_MAPS_TERMS = build_maps_discovery_terms(active)
    module.SERPER_DISCOVERY_REGION_SUFFIX = build_region_suffix(active)
    return active


def debug_keywords_campaign(
    active: list[str] | None = None,
    *,
    max_terms: int | None = None,
    sample: int = 8,
) -> dict:
    """
    Narzędzie diagnostyczne: rozkład list Serper dla wybranych województw.

    Po co: przy strojeniu discovery widać od razu, ile fraz powstaje w każdej
    fali, jaki jest suffix regionu, które miasta wchodzą do geo i czy
    segmenty z ``RETAIL_CHAINS_ROTATION`` faktycznie pojawiają się w primary.

    Nie mutuje `CAMPAIGN_ACTIVE_BUNDESLAENDER` ani atrybutów scrapera —
    tylko buduje lokalne listy (jak produkcyjne `build_*`).

    Zwraca dict m.in. z polami:
      active, cities_total, max_terms, region_suffix,
      counts{primary,fallback,broad,landkreis,places},
      samples{…}, segments_in_primary, serper_pos/neg_count.
    """
    lands = resolve_active_bundeslaender(active)
    if max_terms is None:
        max_terms = default_max_discovery_terms_for(lands)
    sample_n = max(0, int(sample))

    primary = build_discovery_terms(lands, max_terms=max_terms)
    fallback = build_fallback_terms(lands)
    broad = build_broad_discovery_terms(lands)
    landkreis = build_landkreis_discovery_terms(lands)
    places = build_places_discovery_terms(lands)

    cities_by_land = {
        land: list(BUNDESLAND_CONFIG[land]["cities"]) for land in lands
    }
    cities_total = sum(len(v) for v in cities_by_land.values())

    segments_found = [
        seg
        for seg in RETAIL_CHAINS_ROTATION
        if any(seg.lower() in t.lower() for t in primary)
    ]

    return {
        "active": lands,
        "active_raw": list(active) if active else None,
        "cities_total": cities_total,
        "cities_by_land": {k: len(v) for k, v in cities_by_land.items()},
        "max_terms": max_terms,
        "region_suffix": build_region_suffix(lands),
        "counts": {
            "primary": len(primary),
            "fallback": len(fallback),
            "broad": len(broad),
            "landkreis": len(landkreis),
            "places": len(places),
        },
        "samples": {
            "primary": primary[:sample_n],
            "fallback": fallback[:sample_n],
            "broad": broad[:sample_n],
            "landkreis": landkreis[:sample_n],
            "places": places[:sample_n],
        },
        "segments_rotation": list(RETAIL_CHAINS_ROTATION),
        "segments_in_primary": segments_found,
        "segments_coverage": f"{len(segments_found)}/{len(RETAIL_CHAINS_ROTATION)}",
        "serper_positive_count": len(SERPER_POSITIVE_TERMS),
        "serper_negative_count": len(SERPER_NEGATIVE_TERMS),
        "templates": {
            "chain_simple": len(CHAIN_SIMPLE_TERM_TEMPLATES),
            "term": len(TERM_TEMPLATES),
        },
    }


def debug_land_key(name: str) -> dict:
    """
    Diagnostyka normalizacji nazwy województwa (alias → klucz config).

    Po co: szybki check CLI / JSON (`MZ`, `łódzkie`, literówki) zanim
    frazy Serper pójdą na fallback całej Polski.
    """
    raw = (name or "").strip()
    key = _normalize_land_key(raw)
    known = key in BUNDESLAND_CONFIG
    return {
        "raw": raw,
        "normalized": key,
        "known": known,
        "short": (BUNDESLAND_CONFIG[key]["short"] if known else None),
        "cities": list(BUNDESLAND_CONFIG[key]["cities"]) if known else [],
        "resolve_active": resolve_active_bundeslaender([raw]),
    }


# Eksport domyślny (fala 1) — do 1000 wariantów
SERPER_DISCOVERY_TERMS = build_discovery_terms(max_terms=1000)
SERPER_DISCOVERY_FALLBACK_TERMS = build_fallback_terms()
SERPER_DISCOVERY_BROAD_TERMS = build_broad_discovery_terms()
SERPER_DISCOVERY_LANDKREIS_TERMS = build_landkreis_discovery_terms()
SERPER_DISCOVERY_PLACES_TERMS = build_places_discovery_terms()
SERPER_DISCOVERY_MAPS_TERMS = build_maps_discovery_terms()
SERPER_DISCOVERY_REGION_SUFFIX = build_region_suffix()


def _cli_debug(argv: list[str] | None = None) -> int:
    """
    CLI: ``python pl_spedycja_keywords.py [woj…] [--max-terms N] [--sample N]``.

    Bez argumentów: snapshot dla bieżącej kampanii (wszystkie aktywne woj.).
    Z ``--land-key X``: tylko diagnostyka normalizacji jednego klucza.
    """
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Debug list Serper / geo PL (pl_spedycja_keywords)."
    )
    parser.add_argument(
        "lands",
        nargs="*",
        help="Województwa lub aliasy (np. Mazowieckie mz łódzkie)",
    )
    parser.add_argument("--max-terms", type=int, default=None)
    parser.add_argument("--sample", type=int, default=8)
    parser.add_argument(
        "--land-key",
        default=None,
        help="Tylko normalizacja jednego klucza (bez budowania list)",
    )
    args = parser.parse_args(argv)

    if args.land_key:
        payload = debug_land_key(args.land_key)
    else:
        payload = debug_keywords_campaign(
            args.lands or None,
            max_terms=args.max_terms,
            sample=args.sample,
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli_debug())

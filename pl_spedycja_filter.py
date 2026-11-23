# -*- coding: utf-8 -*-
"""
Kampania PL: firmy spedycyjne drogowe (FTL / LTL / międzynarodowy).

Moduł: ``pl_spedycja_filter`` (dawniej ``retail_store_builder_filter``).

Szkielet:
  1) listy ROLE / SEGMENT / SERVICE + REJECT
  2) helpery (_blob, _has_any)
  3) core (reject_reason, is_forwarder_role, has_forwarding_signal, …)
  4) public API + cienkie aliasy legacy (scraper / testy)

Checklist (krok J) — zrobione:
  1. usunięte legacy akceptowanie skrótu GU w Serper
  2. 3 whitelisty + aliasy starych nazw
  3. reject_reason w is_valid_* / serper
  4. mentions_*_core = ROLE ∧ (SEGMENT ∨ SERVICE)
  5. has_offer_evidence zamiast portfolio/zdjęć
  6. is_loose_serper_* → alias is_serper_only_*
  7. martwa gałąź REQUIRE=True wycięta
  8. docstringi bez Filialbau/Rewe
"""
from __future__ import annotations

from commercial_contact_filter import (
    is_non_commercial_contact,
    is_valid_commercial_company_contact,
)

# Flaga scrapera (alias REQUIRE_GENERALUNTERNEHMER na dole).
# False = wystarczy marker roli spedycji (bez twardego wymogu „GU”).
REQUIRE_FORWARDER_ROLE = False


def _uniq_markers(*groups: tuple[str, ...]) -> tuple[str, ...]:
    """
    Buduje jedną krotkę markerów z kilku grup wejściowych.

    Po co: listy ROLE / SEGMENT / SERVICE częściowo się pokrywają
    (np. „organizacja transportu”). Ta funkcja scala je do kontekstu
    branżowego (`TRANSPORT_CONTEXT_MARKERS`) bez powtórzeń.

    Jak działa: przechodzi grupy po kolei, normalizuje wpisy (strip + lower
    do porównania) i dopisuje tylko pierwsze wystąpienie każdego klucza.
    Kolejność pierwszego pojawienia się jest zachowana.
    """
    seen: set[str] = set()
    out: list[str] = []
    for group in groups:
        for item in group:
            key = (item or "").strip().lower()
            if key and key not in seen:
                seen.add(key)
                out.append(item.strip())
    return tuple(out)


# =============================================================================
# 1) Listy — akceptacja
# =============================================================================

# Rola firmy: biuro spedycji / freight forwarding (nie kurier, nie giełda).
FORWARDER_ROLE_MARKERS = (
    "spedycja",
    "spedytor",
    "firma spedycyjna",
    "biuro spedycyjne",
    "freight forwarding",
    "freight forwarder",
    "organizacja transportu",
    "dyspozytor",
    "dyspozytornia",
    "firma transportowa",
)

# Segment usług: FTL / LTL / fracht / kierunki.
TRANSPORT_SEGMENT_MARKERS = (
    "ftl",
    "ltl",
    "całopojazdowy",
    "calopojazdowy",
    "transport międzynarodowy",
    "transport miedzynarodowy",
    "fracht",
    "grupaż",
    "grupaz",
    "adr",
    "chłodnia",
    "chlodnia",
    "plandełka",
    "plandeka",
    "europa",
    "niemcy",
    "międzynarodowy",
    "miedzynarodowy",
)

# Opis usług / działalności transportowej na stronie.
TRANSPORT_SERVICE_MARKERS = (
    "transport drogowy",
    "transport międzynarodowy",
    "transport miedzynarodowy",
    "transport ciężarowy",
    "transport ciezarowy",
    "organizacja transportu",
    "organizacja przewozu",
    "spedycja ftl",
    "spedycja ltl",
    "transport ftl",
    "transport ltl",
    "całopojazdowy",
    "calopojazdowy",
    "grupaż",
    "grupaz",
    "obsługa frachtu",
    "obsluga frachtu",
    "fracht drogowy",
    "przewozy międzynarodowe",
    "przewozy miedzynarodowe",
    "przewozy całopojazdowe",
    "przewozy calopojazdowe",
    "logistyka kontraktowa",
    "transport europa",
    "transport niemcy",
    "polska niemcy",
    "załadunek",
    "zaladunek",
    "rozładunek",
    "rozladunek",
    "kierunki",
    "trasy",
    "kierunki europa",
    "trasy europa",
    "flota własna",
    "flota wlasna",
    "naczepy",
    "dopłata",
    "doplata",
    "mega",
    "firanka",
    "przewóz",
    "przewoz",
)

# Suma ROLE + SEGMENT + SERVICE + drobne synonimy kontekstu branżowego.
TRANSPORT_CONTEXT_MARKERS = _uniq_markers(
    FORWARDER_ROLE_MARKERS,
    TRANSPORT_SEGMENT_MARKERS,
    TRANSPORT_SERVICE_MARKERS,
    (
        "logistyka",
        "tir",
        "naczepa",
        "flota",
        "freight",
        "forwarding",
    ),
)

# Sekcje oferty na www (bez ścieżek zdjęć / galerii).
OFFER_SECTION_MARKERS = (
    "oferta",
    "referencje",
    "realizacje",
    "flota",
    "trasy",
    "kierunki",
    "usługi",
    "uslugi",
    "o nas",
    "o firmie",
    "klienci",
    "nasza oferta",
    "zakres usług",
    "zakres uslug",
)

# Jawne frazy „nie jesteśmy spedycją” — prosta negacja bez okien ±40.
_OFFER_NEGATION_PHRASES = (
    "nie prowadzimy spedycji",
    "bez spedycji",
    "nie jesteśmy spedycją",
    "nie jestesmy spedycja",
    "tylko flota własna bez biura",
    "tylko flota wlasna bez biura",
    "nie organizujemy transportu",
    "brak frachtów",
    "brak frachtow",
)

# =============================================================================
# 1b) Listy — REJECT
# =============================================================================

# Kurier / paczka — nie biuro spedycji FTL.
COURIER_REJECT_MARKERS = (
    "kurier",
    "kurierski",
    "kurierska",
    "paczkomat",
    "paczka",
    "przesyłka",
    "przesylka",
    "inpost",
    "dpd",
    "dhl express",
    "ups express",
    "gls",
    "fedex",
    "pocztex",
    "orlen paczka",
    "same day delivery",
    "dostawa paczek",
)

# Role poza ICP: praca, urząd, przeprowadzki, autokary, szkoły jazdy.
IRRELEVANT_ROLE_MARKERS = (
    "przeprowadzki",
    "przeprowadzka",
    "wynajem autokarów",
    "wynajem autokarow",
    "autokar",
    "autobusy turystyczne",
    "szkolenie kierowców",
    "szkolenie kierowcow",
    "kurs na prawo jazdy",
    "ośrodek szkolenia",
    "osrodek szkolenia",
    "urząd",
    "urzad",
    "ministerstwo",
    "gmina ",
    "starostwo",
    "oferty pracy",
    "praca kierowca",
    "praca jako kierowca",
    "kariera kierowca",
    "agencja pracy",
)

# Usługi poza ICP (gdy brak równoległej roli spedycji).
IRRELEVANT_SERVICE_MARKERS = (
    "przeprowadzki",
    "przeprowadzka",
    "wynajem autokarów",
    "wynajem autokarow",
    "taxi towarowe",
    "bus pasażerski",
    "bus pasazerski",
    "szkolenie b",
    "kurs na c+e",
    "oszczędny driving",
)

# Domeny giełd / kurierów / big 3PL / portali pracy.
EXCHANGE_OR_BIG3PL_DOMAIN_MARKERS = (
    "timocom",
    "trans.eu",
    "trans.eu/",
    "login.trans.eu",
    "teleroute",
    "wtransnet",
    "cargobase",
    "inpost.pl",
    "dpd.com",
    "dpd.pl",
    "dhl.com",
    "dhl.pl",
    "ups.com",
    "gls-group",
    "gls-poland",
    "fedex.com",
    "poczta-polska.pl",
    "orlenpaczka.pl",
    "pracuj.pl",
    "olx.pl/praca",
    "indeed.com",
    "raben-group.com",
    "dbschenker.com",
    "kuehne-nagel.com",
    "dsv.com",
    "geodis.com",
    "pekaes.pl",
)

# Frazy stron giełdy / kariery / śledzenia paczek (wymagają ≥2 trafień).
EXCHANGE_OR_JOBS_PAGE_MARKERS = (
    "giełda transportowa",
    "gielda transportowa",
    "giełda frachtów",
    "gielda frachtow",
    "oferty pracy",
    "praca kierowca",
    "dołącz do nas",
    "dolacz do nas",
    "aplikuj",
    "wyślij cv",
    "wyslij cv",
    "śledź paczkę",
    "sledz paczke",
    "nadaj paczkę",
    "nadaj paczke",
    "paczkomat",
    "cennik kurier",
)

# Domeny zawsze out — nawet przy słowie „transport” w snippecie.
_HARD_REJECT_DOMAIN_MARKERS = (
    "timocom",
    "trans.eu",
    "inpost",
    "dpd.",
    "dhl.",
    "raben-group",
    "dbschenker",
    "kuehne-nagel",
    "pracuj.pl",
)

# Portale informacyjne / media branżowe (nie firmy spedycyjne).
MEDIA_DOMAIN_MARKERS = (
    "trans.info",
    "logistyka.net.pl",
    "logistyczny.com",
    "rp.pl",
    "pb.pl",
    "wnp.pl",
    "money.pl",
    "forbes.pl",
    "presseportal",
    "business-news",
    "branchennews",
    "branchenportal",
    "magazin.",
    "redakcja.",
)

MEDIA_NAME_MARKERS = (
    "redakcja",
    "wydawnictwo",
    "portal branżowy",
    "portal branzowy",
    "magazyn logistyczny",
    "serwis informacyjny",
    "aktualności transport",
    "aktualnosci transport",
    "news group",
    "business news",
    "business media",
)

MEDIA_URL_PATH_MARKERS = (
    "/news/",
    "/aktualnosci/",
    "/aktualności/",
    "/artykul/",
    "/artykuł/",
    "/newsletter/",
    "/magazyn/",
    "/blog/",
)


# =============================================================================
# 2) Helpery
# =============================================================================

def _blob(*parts: str) -> str:
    """
    Składa nazwę, URL, e-mail i tekst strony w jeden ciąg do analizy markerów.

    Puste fragmenty są pomijane; wynik jest w małych literach, żeby porównania
    z whitelistami/rejectami były niezależne od wielkości liter. Używane na
    wejściu prawie każdej publicznej bramki filtra.
    """
    return " ".join((p or "").strip() for p in parts if (p or "").strip()).lower()


def _has_any(low: str, markers: tuple[str, ...]) -> bool:
    """
    Sprawdza, czy w tekście `low` występuje którykolwiek z podanych markerów.

    Match jest podciągowy (np. „ftl” złapie „spedycja FTL Europa”). To świadoma
    decyzja pod krótkie snippety Serper — kosztem rzadkich false positive.
    """
    return any(m in low for m in markers)


def _is_courier_reject(low: str) -> bool:
    """
    Odróżnia kuriera / paczkę od biura spedycji FTL.

    Po co: InPost, DPD, „nadaj paczkę” nie są ICP Forwarding Assistant.
    Jak działa:
      1) szuka markerów kurierskich w tekście / nazwie,
      2) jeśli ich nie ma → False (nie odrzucaj tą ścieżką),
      3) jeśli są, a brak roli spedycji → True (odrzuć),
      4) wyjątek: rola spedycji + SEGMENT + SERVICE jednocześnie
         (np. firma spedycyjna z FTL i transportem drogowym) → False.
    """
    courier = _has_any(low, COURIER_REJECT_MARKERS)
    name_courier = any(
        m in low for m in ("kurier", "inpost", "paczkomat", "dpd", "gls", "pocztex")
    )
    if not courier and not name_courier:
        return False
    strong_forwarder = _has_any(low, FORWARDER_ROLE_MARKERS)
    if not strong_forwarder:
        return True
    if (
        strong_forwarder
        and _has_any(low, TRANSPORT_SEGMENT_MARKERS)
        and _has_any(low, TRANSPORT_SERVICE_MARKERS)
    ):
        return False
    return True


def _is_exchange_or_big3pl_reject(url: str, low: str) -> bool:
    """
    Wykrywa giełdy frachtów, dużych 3PL, kurierów sieciowych i portale pracy.

    Po co: Timocom / Trans.eu / Raben / pracuj.pl nie są małym biurem spedycji.
    Jak działa:
      - domeny z `_HARD_REJECT_DOMAIN_MARKERS` w URL → zawsze True,
      - inne domeny z listy giełd/3PL → True, chyba że w tekście jest
        równolegle rola lub usługa spedycji (i URL nie jest „twardy”),
      - ≥2 frazy ze stron kariery/giełdy/paczki bez SERVICE → True.
    """
    url_low = (url or "").lower()
    if _has_any(url_low, _HARD_REJECT_DOMAIN_MARKERS):
        return True
    if _has_any(low, EXCHANGE_OR_BIG3PL_DOMAIN_MARKERS):
        if not (
            _has_any(low, TRANSPORT_SERVICE_MARKERS)
            or _has_any(low, FORWARDER_ROLE_MARKERS)
        ):
            return True
        if _has_any(url_low, _HARD_REJECT_DOMAIN_MARKERS):
            return True
    if sum(1 for m in EXCHANGE_OR_JOBS_PAGE_MARKERS if m in low) >= 2:
        if not _has_any(low, TRANSPORT_SERVICE_MARKERS):
            return True
    return False


def _is_media_reject(url: str, email: str, low: str) -> bool:
    """
    Wykrywa media / redakcje / portale informacyjne zamiast firmy spedycyjnej.

    Sprawdza: nazwy typu „redakcja”, „portal branżowy”, domeny (trans.info, …),
    ścieżki URL (/aktualnosci/, /artykul/, /blog/) oraz typowe maile prasowe
    (redakcja@, press@, media@). Trafienie którejkolwiek reguły → True.
    """
    if _has_any(low, MEDIA_NAME_MARKERS):
        return True
    url_low = (url or "").lower()
    if _has_any(url_low, MEDIA_DOMAIN_MARKERS):
        return True
    if _has_any(url_low, MEDIA_URL_PATH_MARKERS):
        return True
    email_low = (email or "").strip().lower()
    if email_low.startswith(("redakcja@", "redaktion@", "press@", "media@")):
        return True
    return False


# =============================================================================
# 3) Core
# =============================================================================

def reject_reason(
    *,
    email: str = "",
    url: str = "",
    name: str = "",
    text: str = "",
    check_commercial: bool = False,
) -> str | None:
    """
    Jedna, wspólna oś odrzuceń dla całego filtra ICP.

    Po co: zamiast osobnych `is_media_*` / `is_operator_*` / kurier / praca
    wszystkie negatywne reguły przechodzą przez tę funkcję. Bramki Serper
    i www wołają ją na początku i przy pierwszym kodzie wychodzą.

    Kolejność sprawdzeń (pierwsze trafienie wygrywa):
      non_commercial → media → exchange_or_big3pl → courier
      → irrelevant_role → irrelevant_service.

    Zwraca: string z kodem powodu albo None, gdy kontakt nie wpada w reject.
    `check_commercial=True` włącza test kontaktu niekomercyjnego (gmina, edukacja).
    """
    if check_commercial and is_non_commercial_contact(
        email=email, url=url, name=name
    ):
        return "non_commercial"
    low = _blob(name, url, email, text)
    if _is_media_reject(url, email, low):
        return "media"
    if _is_exchange_or_big3pl_reject(url, low):
        return "exchange_or_big3pl"
    if _is_courier_reject(low):
        return "courier"
    if _has_any(low, IRRELEVANT_ROLE_MARKERS):
        return "irrelevant_role"
    if _has_any(low, IRRELEVANT_SERVICE_MARKERS) and not _has_any(
        low, FORWARDER_ROLE_MARKERS
    ):
        return "irrelevant_service"
    return None


def is_forwarder_role(text: str) -> tuple[bool, str]:
    """
    Sprawdza, czy tekst opisuje rolę biura spedycji / freight forwardera.

    Po co: to pozytywna whitelist roli (FORWARDER_ROLE_MARKERS) — osobno od
    odrzuceń. Nie patrzy na kuriera ani giełdę; to robi `reject_reason`.

    Zwraca:
      (True, marker)  — pierwszy znaleziony marker, np. „firma spedycyjna”,
      (False, "")     — brak roli spedycyjnej w tekście.

    Używana przez scrapera pod starą nazwą `is_generalunternehmer`.
    """
    low = (text or "").lower()
    for marker in FORWARDER_ROLE_MARKERS:
        if marker in low:
            return True, marker.strip()
    return False, ""


def has_forwarding_signal(text: str) -> bool:
    """
    Główny pozytywny sygnał aktywności ICP na etapie www / Excel.

    Reguła: musi być ROLA spedycji ORAZ (SEGMENT usług LUB opis SERVICE).
    Przykład OK: „Firma spedycyjna. Transport drogowy FTL.”
    Przykład NIE: sama „Firma spedycyjna” bez FTL/usługi.

    To właśnie warunek, który woła `is_valid_retail_store_builder_contact`
    i alias `mentions_retail_store_build_activity_core`.
    """
    low = (text or "").lower()
    if not _has_any(low, FORWARDER_ROLE_MARKERS):
        return False
    if _has_any(low, TRANSPORT_SEGMENT_MARKERS):
        return True
    return _has_any(low, TRANSPORT_SERVICE_MARKERS)


def portfolio_negates(text: str) -> bool:
    """
    Wykrywa jawną deklarację „nie jesteśmy spedycją / nie organizujemy transportu”.

    Po co: firma może mieć słowo „spedycja” w negacji („nie prowadzimy spedycji”).
    Proste dopasowanie fraz z `_OFFER_NEGATION_PHRASES` — bez okien ±40 znaków.
    True → kontakt nie powinien przejść Serper ani www.
    """
    low = (text or "").lower()
    return _has_any(low, _OFFER_NEGATION_PHRASES)


def has_offer_evidence(text: str) -> bool:
    """
    Sprawdza, czy na stronie widać sekcję oferty powiązaną ze spedycją.

    Po co: scraper czasem wymaga „dowodu oferty” (referencje, flota, trasy,
    o nas, zakres usług). To uproszczona wersja dawnego portfolio ze zdjęciami.

    Warunki:
      - brak fraz negacji (`portfolio_negates`),
      - obecność markera sekcji oferty (`OFFER_SECTION_MARKERS`),
      - oraz ROLE albo SEGMENT w tym samym tekście.
    """
    low = (text or "").lower()
    if portfolio_negates(low):
        return False
    if not _has_any(low, OFFER_SECTION_MARKERS):
        return False
    return _has_any(low, FORWARDER_ROLE_MARKERS) or _has_any(
        low, TRANSPORT_SEGMENT_MARKERS
    )


def has_serper_trade_signal(low: str, search_term: str = "") -> bool:
    """
    Luźny sygnał branżowy na etapie discovery Serper (tytuł + snippet + fraza).

    Po co: Google rzadko powtarza w snippecie pełne „spedycja FTL”, ale fraza
    wyszukiwania już je zawiera. Dlatego sklejamy tekst z `search_term`.

    Wystarczy JEDNO z: ROLE, SEGMENT albo SERVICE w połączonym blobie.
    To luźniej niż `has_forwarding_signal` (www), które wymaga ROLE ∧ (…).
    """
    blob = f"{(low or '').lower()} {(search_term or '').lower()}".strip()
    if not blob:
        return False
    return (
        _has_any(blob, FORWARDER_ROLE_MARKERS)
        or _has_any(blob, TRANSPORT_SEGMENT_MARKERS)
        or _has_any(blob, TRANSPORT_SERVICE_MARKERS)
    )


def detect_transport_segments(text: str) -> list[str]:
    """
    Zwraca listę wykrytych markerów SEGMENT obecnych w tekście.

    Przykład: „Spedycja FTL i LTL Europa” → ['ftl', 'ltl', 'europa', …].
    Używane przy logowaniu / Excelu (kolumna segmentów) oraz jako alias
    dawnego `detect_required_retail_chains` (kiedyś sieci handlowe).
    """
    low = (text or "").lower()
    return [c for c in TRANSPORT_SEGMENT_MARKERS if c in low]


# =============================================================================
# 4) Public API (nazwy używane przez scraper) + aliasy legacy
# =============================================================================

def is_generalunternehmer(text: str) -> tuple[bool, str]:
    """
    Alias legacy nazwy DE → `is_forwarder_role`.

    Historycznie oznaczało „czy to Generalunternehmer”. W kampanii PL oznacza
    „czy tekst ma rolę spedycyjną”. Scraper i Claude nadal importują tę nazwę,
    więc zostaje cienkim wrapperem bez własnej logiki.
    """
    return is_forwarder_role(text)


def qualifies_as_gu_for_campaign(text: str) -> tuple[bool, str]:
    """
    Alias legacy: kwalifikacja leadu do kampanii.

    Dawniej miała złożoną gałąź REQUIRE=True (segmenty, referencje, loose).
    Przy `REQUIRE_FORWARDER_ROLE=False` sprowadza się do `is_forwarder_role`.
    """
    return is_forwarder_role(text)


def is_gu_or_retail_build_specialist(text: str) -> bool:
    """
    Alias legacy: „czy to specjalista branżowy”.

    Zwraca True/False z `is_forwarder_role` (sama rola spedycji, bez segmentu).
    """
    return is_forwarder_role(text)[0]


def is_gu_or_retail_build_specialist_for_serper_discovery(text: str) -> bool:
    """
    Alias legacy używany przy luźniejszym discovery Serper.

    Logicznie to samo co `is_forwarder_role` — zostawione, żeby nie łamać
    starych importów w scraperze / testach.
    """
    return is_forwarder_role(text)[0]


def mentions_retail_store_build_activity_core(text: str) -> bool:
    """
    Alias publicznej nazwy → `has_forwarding_signal`.

    To restrykcyjny warunek aktywności na www/Excel: ROLE ∧ (SEGMENT ∨ SERVICE).
    Nazwa „retail_store_build” jest legacy po kampanii DE.
    """
    return has_forwarding_signal(text)


def mentions_retail_store_build_activity(text: str) -> bool:
    """
    Aktywność ICP z uwzględnieniem negacji oferty.

    Najpierw wymaga `has_forwarding_signal`, potem odpada przy frazach typu
    „nie prowadzimy spedycji”. Nie wymaga osobnego portfolio/zdjęć.
    """
    low = (text or "").lower()
    if not has_forwarding_signal(low):
        return False
    return not portfolio_negates(low)


def mentions_retail_store_build_activity_serper_discovery(text: str) -> bool:
    """
    Luźniejsza aktywność tylko na tekście snippeta (bez frazy Serper).

    Wrapper na `has_serper_trade_signal(text)` — ROLE ∨ SEGMENT ∨ SERVICE.
    www i Excel nadal używają wersji `*_core` (ciaśniejszej).
    """
    return has_serper_trade_signal((text or "").lower())


def portfolio_negates_market_projects(text: str) -> bool:
    """
    Alias legacy → `portfolio_negates`.

    Dawna nazwa dotyczyła „braku projektów marketów”; teraz: brak spedycji.
    """
    return portfolio_negates(text)


def has_retail_references_or_portfolio(text: str) -> bool:
    """
    Alias → `has_offer_evidence`.

    Sprawdza, czy strona ma sekcję oferty/referencji/floty powiązaną
    z rolą spedycji lub segmentem FTL/LTL.
    """
    return has_offer_evidence(text)


def has_market_project_evidence_on_website(text: str) -> bool:
    """
    Alias legacy → `has_offer_evidence`.

    Dawniej szukał zdjęć marketów i ścieżek jpg; dziś to ten sam prosty
    warunek oferty tekstowej co `has_retail_references_or_portfolio`.
    """
    return has_offer_evidence(text)


# Alias zmiennej: ten sam warunek oferty co `has_offer_evidence`.
has_market_store_projects_portfolio = has_offer_evidence


def detect_required_retail_chains(text: str) -> list[str]:
    """
    Alias → `detect_transport_segments`.

    Dawniej zwracał nazwy sieci (Aldi/Rewe); teraz listę segmentów FTL/LTL/fracht.
    """
    return detect_transport_segments(text)


def has_required_retail_chain_mention(text: str) -> bool:
    """
    True, gdy w tekście jest co najmniej jeden marker SEGMENT.

    Szybki bool-wrapper na `detect_transport_segments` (np. „czy jest FTL?”).
    """
    return bool(detect_transport_segments(text))


def has_store_shell_build_evidence(text: str) -> bool:
    """
    Sygnał „wygląda na branżę transportu/spedycji”: ROLE ∨ SERVICE.

    Po co: `page_verify` i testy potrzebują prostego „czy to w ogóle transport?”,
    bez wymogu FTL. Nie wycofujemy z API — zostaje w hot-path.
    Nie obejmuje samego SEGMENT bez roli/usługi.
    """
    low = (text or "").lower()
    return _has_any(low, FORWARDER_ROLE_MARKERS) or _has_any(
        low, TRANSPORT_SERVICE_MARKERS
    )


def has_retail_context_without_named_chain(text: str) -> bool:
    """
    Kontekst branżowy bez wymogu konkretnego segmentu FTL/LTL.

    True przy ROLE albo SERVICE albo SEGMENT. False przy rolach nie-ICP
    (praca, urząd, przeprowadzki — `IRRELEVANT_ROLE_MARKERS`).
    Przydatne, gdy lead ma „firma spedycyjna + organizacja przewozu”
    bez słowa „FTL” w snippecie.
    """
    low = (text or "").lower()
    if _has_any(low, IRRELEVANT_ROLE_MARKERS):
        return False
    return (
        _has_any(low, FORWARDER_ROLE_MARKERS)
        or _has_any(low, TRANSPORT_SERVICE_MARKERS)
        or _has_any(low, TRANSPORT_SEGMENT_MARKERS)
    )


def is_excluded_non_gu_role(text: str) -> bool:
    """
    True, gdy tekst opisuje rolę poza ICP kampanii.

    Przykłady: oferty pracy kierowcy, urząd, przeprowadzki, autokary, OSK.
    Używane jako szybki pre-check; pełna oś reject i tak idzie przez `reject_reason`.
    """
    return _has_any((text or "").lower(), IRRELEVANT_ROLE_MARKERS)


def is_interior_fitout_specialist(text: str) -> tuple[bool, str]:
    """
    Alias legacy dla ścieżki „kurier / paczka”.

    Dawniej oznaczało specjalistę fit-out (wykończenie sklepów). Teraz:
      (True, "kurier_paczka") — tekst wygląda na kuriera bez twardej spedycji FTL,
      (False, "")            — nie odrzucaj tą ścieżką.
    Logika leży w `_is_courier_reject`.
    """
    if _is_courier_reject((text or "").lower()):
        return True, "kurier_paczka"
    return False, ""


def is_media_publisher_contact(
    *,
    url: str = "",
    email: str = "",
    name: str = "",
    text: str = "",
) -> bool:
    """
    True, gdy kontakt to medium / redakcja / portal informacyjny.

    Cienki wrapper: `reject_reason(...) == "media"`. Nie sprawdza roli spedycji —
    same sygnały medialne wystarczą do odrzucenia.
    """
    return reject_reason(email=email, url=url, name=name, text=text) == "media"


def is_retail_store_operator_contact(
    *,
    url: str = "",
    email: str = "",
    text: str = "",
) -> bool:
    """
    True, gdy kontakt to giełda frachtów, big 3PL lub portal pracy.

    Nazwa legacy („operator sieci handlowej”); kod to
    `reject_reason(...) == "exchange_or_big3pl"`.
    """
    return reject_reason(url=url, email=email, text=text) == "exchange_or_big3pl"


def is_serper_only_pending_candidate(
    *,
    email: str = "",
    url: str = "",
    name: str = "",
    text: str = "",
    search_term: str = "",
) -> bool:
    """
    Jedyna bramka filtra na etapie Serper (tytuł, snippet, fraza wyszukiwania).

    Po co: po wynikach Google zostawiamy tylko kandydatów wyglądających na
    polską spedycję — bez pełnej weryfikacji www.

    Kroki (kolejno, pierwsze False kończy):
      1) `reject_reason` (media, giełda, kurier, … + non_commercial),
      2) `portfolio_negates` — jawne „nie prowadzimy spedycji”,
      3) `is_valid_commercial_company_contact` — firma, nie osoba prywatna
         (uwaga: bez maila wiele domen .pl odpada),
      4) `has_serper_trade_signal` — ROLE/SEGMENT/SERVICE w tekście lub frazie.

    Alias `is_loose_serper_discovery_candidate` woła dokładnie tę funkcję.
    """
    combined = _blob(name, url, email, text)
    if reject_reason(
        email=email, url=url, name=name, text=combined, check_commercial=True
    ):
        return False
    if portfolio_negates(combined):
        return False
    if not is_valid_commercial_company_contact(email=email, url=url, name=name):
        return False
    return has_serper_trade_signal(combined, search_term)


def is_loose_serper_discovery_candidate(
    *,
    email: str = "",
    url: str = "",
    name: str = "",
    text: str = "",
    search_term: str = "",
) -> bool:
    """
    Alias legacy drugiej bramki Serper.

    Dawniej była osobna, niemal skopiowana funkcja. Teraz przekazuje te same
    argumenty do `is_serper_only_pending_candidate` — jeden kod, dwie nazwy API.
    """
    return is_serper_only_pending_candidate(
        email=email,
        url=url,
        name=name,
        text=text,
        search_term=search_term,
    )


def is_valid_retail_store_builder_contact(
    *,
    email: str = "",
    url: str = "",
    name: str = "",
    text: str = "",
) -> bool:
    """
    Pełna walidacja kontaktu ICP po crawl/www (oraz przy eksporcie Excel).

    Po co: ostateczna decyzja „czy to polska firma spedycyjna do outreachu”.
    Kroki:
      1) `reject_reason` z `check_commercial=True`,
      2) `is_valid_commercial_company_contact`,
      3) brak `portfolio_negates`,
      4) `has_forwarding_signal` = ROLE ∧ (SEGMENT ∨ SERVICE).

    Nazwa funkcji jest legacy (retail store builder); zachowana dla scrapera.
    """
    combined = _blob(name, url, email, text)
    if reject_reason(
        email=email, url=url, name=name, text=combined, check_commercial=True
    ):
        return False
    if not is_valid_commercial_company_contact(email=email, url=url, name=name):
        return False
    if portfolio_negates(combined):
        return False
    return has_forwarding_signal(combined)


def debug_filter_decision(
    *,
    email: str = "",
    url: str = "",
    name: str = "",
    text: str = "",
    search_term: str = "",
) -> dict:
    """
    Narzędzie diagnostyczne: rozkłada decyzję filtra na składowe.

    Po co: przy debugowaniu leada widać od razu, czy odpadł na reject,
    braku roli, braku FTL, negacji oferty, czy dopiero na bramce komercyjnej.

    Zwraca dict m.in. z polami:
      blob, reject_reason, role_ok, role_marker, forwarding_signal,
      offer_evidence, portfolio_negates, serper_trade_signal,
      is_valid, is_serper_candidate, segments.
    Nie zmienia stanu — tylko czyta te same funkcje co produkcja.
    """
    combined = _blob(name, url, email, text)
    role_ok, role_marker = is_forwarder_role(combined)
    return {
        "blob": combined[:500],
        "reject_reason": reject_reason(
            email=email, url=url, name=name, text=combined, check_commercial=True
        ),
        "role_ok": role_ok,
        "role_marker": role_marker,
        "forwarding_signal": has_forwarding_signal(combined),
        "offer_evidence": has_offer_evidence(combined),
        "portfolio_negates": portfolio_negates(combined),
        "serper_trade_signal": has_serper_trade_signal(combined, search_term),
        "is_valid": is_valid_retail_store_builder_contact(
            email=email, url=url, name=name, text=text
        ),
        "is_serper_candidate": is_serper_only_pending_candidate(
            email=email,
            url=url,
            name=name,
            text=text,
            search_term=search_term,
        ),
        "segments": detect_transport_segments(combined),
    }


def get_discovery_wojewodztwo(info: dict | None) -> str:
    """
    Odczytuje województwo discovery z wpisu cache / wiersza pipeline.

    Preferuje klucz PL ``discovery_wojewodztwo``; dla starego cache JSON
    akceptuje też legacy ``discovery_bundesland`` (kampania DE).
    Przy zapisie używaj ``set_discovery_wojewodztwo`` — bez legacy klucza.
    """
    if not isinstance(info, dict):
        return ""
    return (
        (info.get("discovery_wojewodztwo") or "").strip()
        or (info.get("discovery_bundesland") or "").strip()
    )


def set_discovery_wojewodztwo(target: dict, region: str) -> None:
    """
    Zapisuje województwo discovery pod kluczem PL ``discovery_wojewodztwo``.

    Usuwa legacy ``discovery_bundesland``, żeby JSON nie dublował starych nazw.
    Pusty ``region`` czyści oba klucze.
    """
    region = (region or "").strip()
    if region:
        target["discovery_wojewodztwo"] = region
    else:
        target.pop("discovery_wojewodztwo", None)
    target.pop("discovery_bundesland", None)


def is_cache_contact_not_store_builder(place_url: str, info: dict | None) -> bool:
    """
    Adapter wpisu z cache JSON → decyzja `is_valid_*`.

    Po co: przy czyszczeniu / rebuild cache scrapera trzeba wiedzieć,
    które kontakty nie są ICP i można je odfiltrować.

    Zwraca True = „to NIE jest spedycja ICP” (można wyrzucić).
    Specjalne przypadki, gdy zwraca False (jeszcze nie odrzucaj):
      - brak dicta info → True (traktuj jako nie-ICP),
      - `retail_verified` → False (już zweryfikowany pozytywnie),
      - `pending_www_verify` → False (czeka na crawl),
      - discovery województwa bez maila → False (mail może dojść później);
        region z ``get_discovery_wojewodztwo`` (PL + legacy).

    Potem zbiera email/url/nazwę/snippet z info i odwraca wynik
    `is_valid_retail_store_builder_contact`.
    """
    if not isinstance(info, dict):
        return True
    if info.get("retail_verified"):
        return False
    if (info.get("verification_reason") or "").strip() == "pending_www_verify":
        return False

    email = (info.get("email_target") or "").strip()
    if not email:
        found = (info.get("emails_found") or "").strip()
        if found:
            email = found.split(",")[0].strip()

    # Lead z discovery województwa bez maila — jeszcze nie odrzucaj
    if get_discovery_wojewodztwo(info) and not email:
        return False

    url = (place_url or info.get("official_website") or "").strip()
    name = (
        info.get("company_name_clean")
        or info.get("company_name")
        or info.get("company_name_raw")
        or ""
    ).strip()
    extra = " ".join(
        str(info.get(k) or "")
        for k in (
            "verification_reason",
            "page_snippet",
            "serper_title",
            "serper_snippet",
            "retail_chains",
            "retail_chains_found",
        )
    )
    return not is_valid_retail_store_builder_contact(
        email=email, url=url, name=name, text=extra
    )


# --- Aliasy list (scraper / stare importy) ------------------------------------
# Nazwy DE/GU zostają dla kompatybilności importów — wskazują na listy PL powyżej.
STRICT_GU_MARKERS = FORWARDER_ROLE_MARKERS
GU_BUILDER_MARKERS = FORWARDER_ROLE_MARKERS
FILIALBAU_SPECIALIST_MARKERS = FORWARDER_ROLE_MARKERS
STORE_SHELL_BUILD_MARKERS = FORWARDER_ROLE_MARKERS
REQUIRED_RETAIL_CHAIN_KEYWORDS = TRANSPORT_SEGMENT_MARKERS
RETAIL_CHAIN_IN_PORTFOLIO_MARKERS = TRANSPORT_SEGMENT_MARKERS
RETAIL_STORE_BUILD_MARKERS = TRANSPORT_SERVICE_MARKERS
RETAIL_STORE_UMBAU_MARKERS = TRANSPORT_SERVICE_MARKERS
RETAIL_PROJECT_BUILD_ACTIVITY_MARKERS = TRANSPORT_SERVICE_MARKERS
MARKET_PROJECT_IN_PORTFOLIO_MARKERS = TRANSPORT_SERVICE_MARKERS
RETAIL_STORE_CONTEXT_MARKERS = TRANSPORT_CONTEXT_MARKERS
REQUIRE_GENERALUNTERNEHMER = REQUIRE_FORWARDER_ROLE

INTERIOR_FITOUT_MARKERS = COURIER_REJECT_MARKERS
NON_GU_ROLE_EXCLUSION_MARKERS = IRRELEVANT_ROLE_MARKERS
RETAIL_OPERATOR_DOMAIN_MARKERS = EXCHANGE_OR_BIG3PL_DOMAIN_MARKERS
RETAIL_OPERATOR_PAGE_MARKERS = EXCHANGE_OR_JOBS_PAGE_MARKERS
FLEET_PHOTO_GALLERY_MARKERS = OFFER_SECTION_MARKERS
OFFER_DESCRIPTION_MARKERS = OFFER_SECTION_MARKERS
WEB_IMAGE_FILE_EXTENSIONS: tuple[str, ...] = ()
MARKET_PHOTO_GALLERY_MARKERS = FLEET_PHOTO_GALLERY_MARKERS
RETAIL_PROJECT_DESCRIPTION_MARKERS = OFFER_DESCRIPTION_MARKERS
RETAIL_IMAGE_FILE_EXTENSIONS = WEB_IMAGE_FILE_EXTENSIONS
PORTFOLIO_SECTION_MARKERS = OFFER_SECTION_MARKERS
MEDIA_PUBLISHER_DOMAIN_MARKERS = MEDIA_DOMAIN_MARKERS
MEDIA_PUBLISHER_NAME_MARKERS = MEDIA_NAME_MARKERS
MEDIA_PUBLISHER_URL_PATH_MARKERS = MEDIA_URL_PATH_MARKERS
PURE_RENOVATION_WITHOUT_STORE_BUILD = IRRELEVANT_SERVICE_MARKERS

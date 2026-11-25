# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Uzupełnienie opisu modułu commercial_contact_filter (komentarz; docstring poniżej szczegółowo opisuje reguły).
#   Rola w pipeline: filtr higieniczny po stronie kontaktów — odcina urzędy, portale, katalogi, izby i
#   fałszywe adresy z regexu (cookies, JS, SVG) zarówno przy zbieraniu (po Claude contact extract i regexie),
#   jak i przy czyszczeniu cache Serper/contacts.
#   Zależności: stdlib (re, urllib.parse); listy markerów są zdefiniowane w module. Jedyny import
#   projektowy to pl_spedycja_keywords.BUNDESLAND_CONFIG, wykonywany leniwie wewnątrz
#   _build_short_name_geo_markers (markery geo: miasta i województwa).
#   Wejście: adres e-mail, URL, nazwa firmy lub wpis cache (dict). Wyjście: bool (czy odrzucić / czy firma
#   jest komercyjna) albo przefiltrowana lista e-maili.
# ============================================================
"""
Filtr kontaktów komercyjnych — kampania PL FAS / spedycja.

=============================================================================
PO CO TEN MODUŁ
=============================================================================
Odcina urzędy, samorządy, izby, uczelnie, katalogi i śmieci regex od
prawdziwych firm (biura spedycyjne). Używany przy parse kontaktów Claude,
rankingu maili i czyszczeniu cache Serper/contacts.

Typowi wołający: ``contact_extract_utils.filter_commercial_emails``,
``pl_fas_spedycja_scraper`` (walidacja leadu / cache).

=============================================================================
CO JEST „KOMERCYJNE” (PL FAS)
=============================================================================
- Forma prawna PL (Sp. z o.o., S.A., sp. j./k./p.) lub DE/EU w nazwie
- Własna domena firmowa (mail ≈ host www)
- Heurystyka domeny: spedycja / transport / logist / forward / fracht
  (+ legacy DE: gmbh / bau / …)

=============================================================================
LISTY — PL + DE HIGIENA
=============================================================================
Exact domains, markery domen i nazwy: **najpierw PL** (gov.pl, BIP, UM,
katalogi, giełdy). Wpisy DE zostają — stary Serper/cache czasem wraca DE.

=============================================================================
GŁÓWNE BRAMKI
=============================================================================
``is_non_commercial_*``     → True = odrzuć (urząd/portal)
``is_junk_scraped_email``   → True = fałszywy regex (cookies/JS)
``filter_commercial_emails``→ lista maili po junk + non-commercial + dedupe
``is_valid_commercial_company_contact`` → True = prywatna firma OK do outreach
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

# Dokładne domeny (organizacje, portale, miasta, branżowe stowarzyszenia).
# PL FAS: gov/katalogi PL na początku; DE zostaje jako higiena (stary Serper/cache).
NON_COMMERCIAL_EMAIL_DOMAINS_EXACT = frozenset(
    {
        # --- PL: rząd / samorząd / instytucje ---
        "gov.pl",
        "sejm.gov.pl",
        "senat.gov.pl",
        "premier.gov.pl",
        "mf.gov.pl",
        "gov.mf.pl",
        "zus.pl",
        "krus.gov.pl",
        "stat.gov.pl",
        "pip.gov.pl",
        "uokik.gov.pl",
        "uke.gov.pl",
        "nfz.gov.pl",
        "pfron.gov.pl",
        "kprm.gov.pl",
        "mswia.gov.pl",
        "biznes.gov.pl",
        "pracuj.gov.pl",
        "warszawa.pl",
        "um.warszawa.pl",
        "bip.warszawa.pl",
        "krakow.pl",
        "um.krakow.pl",
        "gdansk.pl",
        "um.gdansk.pl",
        "wroclaw.pl",
        "um.wroclaw.pl",
        "poznan.pl",
        "um.poznan.pl",
        "lodz.pl",
        "uml.lodz.pl",
        "lublin.pl",
        "um.lublin.pl",
        "szczecin.pl",
        "um.szczecin.pl",
        "katowice.eu",
        "um.katowice.pl",
        "bialystok.pl",
        "um.bialystok.pl",
        # --- PL: katalogi / portale B2B (nie firma) ---
        "panoramafirm.pl",
        "pkt.pl",
        "aleo.com",
        "krs-online.com.pl",
        "krs-online.pl",
        "pracuj.pl",
        "olx.pl",
        "gumtree.pl",
        "allegro.pl",
        "biznesfinder.pl",
        "firmy.net",
        "yellowpages.pl",
        "timocom.com",
        "trans.eu",
        "teleroute.com",
        # --- DE / legacy (higiena) ---
        "leipzig.de",
        "dresden.de",
        "berlin.de",
        "potsdam.de",
        "cottbus.de",
        "chemnitz.de",
        "erfurt.de",
        "halle.de",
        "magdeburg.de",
        "brandenburg.de",
        "visitberlin.de",
        "thueringen-entdecken.de",
        "forst.thueringen.de",
        "dgnb.de",
        "nexxt-change.org",
        "bfw-bund.de",
        "rewe-group.com",
        "funkemedien.de",
        "th24.de",
        "freiepresse.de",
        "funkemedien",
        "wfs.saxony.de",
        "standort-sachsen.de",
        "firmen.standort-sachsen.de",
        "moerfelden-walldorf.de",
        "senatskanzlei.berlin.de",
        "bund.de",
        "bundestag.de",
        "bmwk.de",
        "bmi.bund.de",
        "arbeitsagentur.de",
        "jobcenter-ge.de",
        "europa.eu",
        "gov.de",
        "ibau.de",
        "tgzp.de",
        "ibau.com",
        "hoerbiger.com",  # portal branżowy
    }
)

# Fragment domeny e-mail / URL (urząd, izba, uczelnia, przetargi …).
# PL na górze; DE poniżej (higiena).
NON_COMMERCIAL_DOMAIN_MARKERS = (
    # --- PL: samorząd / BIP / gov ---
    "gov.pl",
    ".gov.pl",
    "bip.",
    ".bip.",
    "bip-",
    # Urzędy miast/gmin — tylko z kropką przed hostem (unikaj false-positive: plug.pl)
    ".um.",
    ".ug.",
    "um.warszawa",
    "um.krakow",
    "um.gdansk",
    "um.wroclaw",
    "um.poznan",
    "um.lublin",
    "um.szczecin",
    "um.katowice",
    "um.bialystok",
    "uml.lodz",
    "ump.",
    "starostwo",
    "powiat.",
    "powiat-",
    "wojewoda",
    "wojewodztwo",
    "województwo",
    "ministerstwo",
    "ministerstwo-",
    "kancelaria.",
    "sejm.",
    "senat.",
    "zus.pl",
    "krus.",
    "nfz.",
    "pup.",
    "wup.",
    "pup-",
    "urzad.",
    "urząd.",
    "urzad-",
    "gmina.",
    "gmina-",
    "miasto.",
    # --- PL: edukacja / izby ---
    "politechnika",
    "uniwersytet",
    "uczelnia",
    "akademia.",
    "sgh.waw.pl",
    "pjatk.",
    "izba-",
    "izbahandlowa",
    "izba.gospodarcza",
    "kig.pl",
    "pracodawcy",
    # --- PL: katalogi / giełdy / ogłoszenia ---
    "panoramafirm",
    "panorama-firm",
    "pkt.pl",
    "aleo.com",
    "krs-online",
    "pracuj.pl",
    "olx.pl",
    "biznesfinder",
    "firmy.net",
    "yellowpages",
    "timocom",
    "trans.eu",
    "teleroute",
    "facebook.com",
    "linkedin.com",
    # --- DE / legacy ---
    "vergabemarktplatz",
    "vergabe.",
    "ausschreibung",
    "evergabe",
    "stadt.",
    ".stadt.",
    "stadt-",
    "gemeinde.",
    "gemeinde-",
    "landkreis",
    "kreis.",
    "kreis-",
    "kreisfreie",
    "amt.",
    "amt-",
    "finanzamt",
    "ministerium",
    "senatskanzlei",
    "landtag.",
    "regierung.",
    "landesverwaltung",
    "verwaltung.",
    "dezernat",
    "rathaus",
    ".gov.",
    ".gov.de",
    "bund.de",
    "bundes",
    "landesamt",
    "landesbehörde",
    "ordnungsamt",
    "bauaufsicht",
    "ihk.",
    "ihk-",
    "hwk.",
    "hwk-",
    "handwerkskammer",
    "handelskammer",
    "wirtschaftsfoerderung",
    "wirtschaftsförderung",
    "wirtschaftsfoerder",
    "investitionsbank",
    "staatsbetrieb",
    "kommunal",
    "uni-",
    ".uni.",
    "universitaet",
    "universität",
    "hochschule",
    "fh-",
    ".fh.",
    "h-da.de",
    "museum.",
    "bibliothek.",
    "forst.",
    "forstamt",
    "naturschutz",
    "umweltamt",
    "agentur-fuer",
    "agentur für",
    "arbeitsagentur",
    "jobcenter",
    "polizei.",
    "justiz.",
    "gericht.",
    "finanzamt",
    "zoll.de",
    "steuerberaterkammer",  # izba zawodowa
    "architektenkammer",
    "ingenieurkammer",
    "tourismus",
    "entdecken.de",
    "wikipedia.",
    "11880.",
    "gelbeseiten.",
    "firmenabc.",
    "europages.",
    "wlw.de",
    "wer-macht-was",  # branżowy katalog IEK
    "wima-ihk",
    "technologiezentrum",  # Gründerzentrum / instytucja
    "gründerzentrum",
    "gruenderzentrum",
    "technologie-und-gruender",
    "innovationscluster",
    "clusterland",
    "pdf-xchange",
    "tracker-software",
    "ibau.",
    "ibau.de",
    "tgzp.",
    "tgzp.de",
    "gründerzentren",
    "gruenderzentren",
    "bauportal",
    "ausschreibungsportal",
    "tender",
    "evergabe-online",
)

# Nazwa / tytuł Serper (bez formy prawnej = często urząd/instytucja).
# PL na górze; DE poniżej (higiena).
NON_COMMERCIAL_NAME_MARKERS = (
    # --- PL: urząd / samorząd / instytucje ---
    "urząd ",
    "urzad ",
    "urząd miasta",
    "urzad miasta",
    "urząd gminy",
    "urzad gminy",
    "urząd marszałkowski",
    "gmina ",
    "powiat ",
    "starostwo",
    "województwo ",
    "wojewodztwo ",
    "wojewoda ",
    "ministerstwo ",
    "kancelaria premiera",
    "sejm ",
    "senat ",
    "zus ",
    "krus ",
    "nfz ",
    "pup ",
    "wup ",
    "powiatowy urząd pracy",
    "wojewódzki urząd pracy",
    "uczelnia ",
    "uniwersytet ",
    "politechnika ",
    "akademia ",
    "szkoła wyższa",
    "izba ",
    "izba gospodarcza",
    "izba handlowa",
    "krajowa izba",
    "stowarzyszenie ",
    "fundacja ",
    "panorama firm",
    "katalog firm",
    "baza firm",
    "ogłoszenia ",
    "oferty pracy",
    "pracuj.pl",
    "timocom",
    "trans.eu",
    "giełda transportowa",
    "giełda frachtów",
    # --- DE / legacy ---
    "stadt ",
    "stadt,",
    "gemeinde ",
    "landkreis",
    "kreisverwaltung",
    "kreisfreie stadt",
    "amt ",
    "ministerium",
    "senat ",
    "bezirk ",
    "dezernat",
    "rathaus",
    "verwaltung",
    "behörde",
    "behörde",
    "bundesamt",
    "landesamt",
    "finanzamt",
    "bauaufsicht",
    "ordnungsamt",
    "ihk ",
    "ihk-",
    "handelskammer",
    "handwerkskammer",
    "wirtschaftsförderung",
    "wirtschaftsfoerderung",
    "investitionsbank",
    "technologiezentrum",
    "gründerzentrum",
    "gruenderzentrum",
    "hochschule",
    "universität",
    "universitaet",
    "museum ",
    "bibliothek",
    "vergabemarktplatz",
    "ausschreibung",
    "öffentliche ausschreib",
    "öffentlicher auftrag",
    "staatsbetrieb",
    "kommunalunternehmen",
    "einrichtung der ",
    "anstalt des öffentlichen",
    "körperschaft",
    "landesforst",
    "forst thüringen",
    "forstamt",
    "agentur für",
    "arbeitsagentur",
    "jobcenter",
    "europäische union",
    "europa ",
    "stiftung ",  # często fundacje / publiczne
    "verein ",  # stowarzyszenia branżowe
    "verband ",  # BFW, branżowe związki
    "kammer ",  # izby
    "haus der mitteldeutschen wirtschaft",
    "wirtschaftsstandort",
    "hauptstadtregion",
    "mittelstand jobs",
    "firmendatenbank",
    "katalog",
    "mitgliedsunternehmen",
    "potsdamer technologie",
    "technologie- und gründer",
    "technologie- und gruender",
    "ibau",
    "generalunternehmer",  # sam opis bez GmbH — katalog/portal
    "generalbau",
    "komplexe bauleistungen",
    "gewerbebau",
    "baugewerbe ",
    "kaufangebote",
    "akteure",
    "wer macht was",
    "bei kaufland",
    "bei aldi",
    "penny in ",
    "aldi in ",
    "kaufland in ",
    "neuer penny",
    "neubau-rewe",
    "ratisbona baut",
    "baut markt",
)

# PL + DE/EU — sygnał „prywatna firma” w nazwie (nie urząd / portal).
_COMMERCIAL_LEGAL_FORM = re.compile(
    r"(?:"
    r"Sp(?:[óo]łka)?\s*\.?\s*z\s*\.?\s*o\s*\.?\s*o\.?|"
    r"S\.?\s*A\.?|"
    r"sp\s*\.?\s*j\.?|"
    r"sp\s*\.?\s*k\.?|"
    r"sp\s*\.?\s*p\.?|"
    r"GmbH|UG(?:\s*\(haftungsbeschränkt\))?|AG|GbR|"
    r"e\.?\s*K\.?|KG|OHG|PartG|Co\.\s*KG|mbH|SE"
    r")\b",
    re.IGNORECASE,
)

# Soft-pass w is_non_commercial_name: forma prawna + rola PL + ≥3 tokeny.
# Zastępuje stary wyjątek DE (generalunternehmer / gewerbebau + GmbH).
_PL_COMMERCIAL_ROLE_MARKERS = (
    "spedycja",
    "spedytor",
    "spedycyjn",  # spedycyjna / spedycyjny
    "forwarding",
    "forwarder",
    "freight forward",
    "transport drogowy",
    "fracht",
)


def _build_short_name_geo_markers() -> tuple[str, ...]:
    """
    Krótkie nazwy Serper bez formy prawnej + geo → często portal / urząd.

    Miasta i województwa z ``pl_spedycja_keywords.BUNDESLAND_CONFIG`` (PL FAS);
    DE geo zostaje jako higiena starego cache.
    """
    from pl_spedycja_keywords import BUNDESLAND_CONFIG

    markers: list[str] = []
    for land, cfg in BUNDESLAND_CONFIG.items():
        markers.append(land.lower())
        for city in cfg.get("cities") or ():
            c = str(city).strip().lower()
            if c:
                markers.append(c)
    # Ogólne PL (portal / admin) bez formy prawnej
    markers.extend(
        (
            "województwo",
            "wojewodztwo",
            "powiat",
            "gmina",
            "katalog firm",
            "ogłoszenia",
            "baza firm",
        )
    )
    # DE / legacy higiena
    markers.extend(
        (
            "erfurt",
            "leipzig",
            "potsdam",
            "cottbus",
            "chemnitz",
            "dresden",
            "halle",
            "brandenburg",
            "thüringen",
            "sachsen",
            "berlin",
            "gewerbe",
            "referenz",
            "projekt",
            "mittelstand",
        )
    )
    # Unikalne, bez bardzo krótkich kodów (MZ/LD itd. nie bierzemy z short)
    seen: set[str] = set()
    out: list[str] = []
    for m in markers:
        if len(m) < 4 or m in seen:
            continue
        seen.add(m)
        out.append(m)
    return tuple(out)


_SHORT_NAME_GEO_MARKERS = _build_short_name_geo_markers()


# >>> OPIS FUNKCJI: funkcja _normalize_host
# Cel: wyłuskać sam host z URL-a albo z domeny adresu e-mail. Parametry: url_or_email (str|None).
# Zwraca: str — lowercase, bez "www.", bez ścieżki; "" dla pustego/niepoprawnego wejścia.
# Efekty uboczne: brak. Błędy: wyjątek urlparse jest łapany → "".
def _normalize_host(url_or_email: str) -> str:
    """
    Wyciąga host z URL albo z domeny e-mail (po ``@``).

    Lowercase, bez ``www.``, bez ścieżki. Pusty string przy złym wejściu.
    """
    text = (url_or_email or "").strip().lower()
    if "@" in text:
        text = text.split("@", 1)[1]
    if "://" in text:
        try:
            text = (urlparse(text).netloc or "").lower()
        except Exception:
            return ""
    if text.startswith("www."):
        text = text[4:]
    return text.split("/", 1)[0].strip()


def is_non_commercial_email(email: str) -> bool:
    """
    True = e-mail urzędu / portalu / katalogu — nie zbierać, nie wysyłać.

    Przebieg: exact domain → markery w hoście → TLD ``.gov.pl`` / ``.gov.de``
    → wzorce DE stadt/kreis → wzorce PL ``um.`` / ``bip.`` / starostwo.
    Brak ``@`` lub pusta domena → True (odrzut bezpieczny).
    """
    low = (email or "").strip().lower()
    if not low or "@" not in low:
        return True
    _, _, domain = low.partition("@")
    domain = domain.strip()
    if not domain:
        return True
    if domain in NON_COMMERCIAL_EMAIL_DOMAINS_EXACT:
        return True
    if any(marker in domain for marker in NON_COMMERCIAL_DOMAIN_MARKERS):
        return True
    # Podstawowe domeny rządowe / edukacyjne (PL + DE + EDU)
    if domain.endswith((".gov.pl", ".gov.de", ".bund.de", ".edu", ".ac.uk")):
        return True
    if re.search(r"\.(stadt|gemeinde|kreis|landkreis)\.", domain):
        return True
    # PL: host urzędu miasta/gminy / BIP / starostwo (np. um.warszawa.pl, bip.gmina…)
    if re.search(r"(^|\.)(um|ug|uml|ump|bip|starostwo)\.", domain):
        return True
    return False


def is_non_commercial_website(url: str) -> bool:
    """
    True = strona wygląda na urząd / portal (nie firma prywatna).

    Te same listy co przy e-mailu + PDF na hoście samorządowym/gov.
    Pusty host → False (brak sygnału — nie odrzucaj „na ślepo”).
    """
    host = _normalize_host(url)
    if not host:
        return False
    if host in NON_COMMERCIAL_EMAIL_DOMAINS_EXACT:
        return True
    if any(marker in host for marker in NON_COMMERCIAL_DOMAIN_MARKERS):
        return True
    if host.endswith((".gov.pl", ".gov.de", ".bund.de")):
        return True
    path_low = (url or "").lower()
    if "/pdfs/" in path_low or path_low.endswith(".pdf"):
        if any(
            x in host
            for x in (
                "stadt",
                "gemeinde",
                "landkreis",
                "vergabe",
                "bund",
                "land.",
                "gov.pl",
                "bip.",
                "um.",
                "starostwo",
            )
        ):
            return True
    return False


def is_non_commercial_name(name: str) -> bool:
    """
    True = nazwa wygląda na urząd / portal / katalog (nie prywatna firma).

    Soft-pass PL FAS: jeśli w nazwie jest forma prawna (Sp. z o.o. / S.A. / …)
    **oraz** rola spedycji (``_PL_COMMERCIAL_ROLE_MARKERS``) **oraz** ≥3 tokeny
    → traktuj jako firmę nawet gdy złapał marker „izba ” / „katalog” itd.

    Stary soft-pass DE (``generalunternehmer`` + GmbH) usunięty — same GU/Bau
    bez roli PL zostają non-commercial.
    """
    text = " ".join((name or "").split()).strip()
    if not text:
        return False
    low = text.lower()
    if any(marker in low for marker in NON_COMMERCIAL_NAME_MARKERS):
        # Firma PL: forma prawna + rola spedycji + wystarczająco długa nazwa
        if _COMMERCIAL_LEGAL_FORM.search(text) and any(
            m in low for m in _PL_COMMERCIAL_ROLE_MARKERS
        ):
            name_parts = [p for p in re.split(r"\W+", low) if len(p) >= 2]
            if len(name_parts) >= 3:
                return False
        return True
    # Krótkie nazwy bez formy prawnej + geo PL (lub DE higiena) → miasto/portal
    if not _COMMERCIAL_LEGAL_FORM.search(text):
        if len(text.split()) <= 3 and any(
            x in low for x in _SHORT_NAME_GEO_MARKERS
        ):
            return True
    return False


def is_non_commercial_contact(
    *,
    email: str = "",
    url: str = "",
    name: str = "",
) -> bool:
    """
    True = odrzuć kontakt (urząd / instytucja / portal — nie firma).

    OR po polach: najpierw e-mail, potem URL, potem nazwa Serper.
    Puste pole = pomiń tę bramkę.
    """
    if email and is_non_commercial_email(email):
        return True
    if url and is_non_commercial_website(url):
        return True
    if name and is_non_commercial_name(name):
        return True
    return False


_JUNK_SCRAPED_EMAIL_DOMAIN_MARKERS = (
    "akzeptieren",
    "ablehnen",
    "einstellungen",
    "datenschutzhinweisen",
    "enschutzhinweisen",
    "cookie",
    "gdpr",
    "rocketlazyload",
    "rocket-loader",
    "lazyload",
    "foreach",
    "addednodes",
    "mutation",
    "webpack",
    "stylesheet",
    "javascript",
    "svg+xml",
    "image/svg",
    "w3.org",
    "example.com",
    "sentry.io",
)

_JUNK_SCRAPED_EMAIL_LOCAL_MARKERS = (
    "fonts.gst",
    "element.d",
    "mut",
)


def is_junk_scraped_email(email: str) -> bool:
    """
    True = fałszywe trafienie regex (baner cookies, JS, lazyload, SVG…).

    Nie jest to filtr ICP — tylko higiena HTML. Lokal/domena z markerów
    junk, zbyt długi local-part, dziwne TLD → odrzut.
    """
    low = (email or "").strip().lower()
    if not low or "@" not in low:
        return True
    if "data:" in low or "svg+xml" in low or "image/" in low:
        return True
    local, _, domain = low.partition("@")
    local, domain = local.strip(), domain.strip()
    if not local or not domain or "." not in domain:
        return True
    if any(m in local for m in _JUNK_SCRAPED_EMAIL_LOCAL_MARKERS):
        return True
    if any(m in domain for m in _JUNK_SCRAPED_EMAIL_DOMAIN_MARKERS):
        return True
    if any(m in low for m in ("@a:", "@a.", ".rocket", ".lazy", "unpkg.com")):
        return True
    tld = domain.rsplit(".", 1)[-1]
    if len(local) > 50:
        return True
    if len(tld) > 50 or not re.match(r"^[a-z0-9\-]{2,50}$", tld):
        return True
    if len(local) <= 2 and (len(tld) > 12 or tld in ("akzeptieren", "ablehnen")):
        return True
    if len(local) == 1 and len(domain) > 24:
        return True
    return False


def filter_commercial_emails(candidates: list[str]) -> list[str]:
    """
    Zwraca unikalne maile komercyjne (kolejność zachowana).

    Przebieg per kandydat: normalizacja lower → junk scrape →
    ``is_non_commercial_email`` → dedupe. Używane m.in. po Claude contact
    extract i regexie w scraperze.
    """
    out: list[str] = []
    for raw in candidates or []:
        e = (raw or "").strip().lower()
        if not e or "@" not in e:
            continue
        if is_junk_scraped_email(e):
            continue
        if is_non_commercial_email(e):
            continue
        if e not in out:
            out.append(e)
    return out


def _contact_fields_from_cache(place_url: str, info: dict | None) -> tuple[str, str, str]:
    """
    Wyciąga ``(email, url, name)`` z wpisu cache contacts scrapera.

    Klucze legacy: ``email_target`` / ``emails_found``, ``official_website``,
    ``company_name_clean`` → ``company_name`` → ``company_name_raw``.
    """
    if not isinstance(info, dict):
        return "", (place_url or "").strip(), ""
    email = (info.get("email_target") or "").strip()
    if not email:
        found = (info.get("emails_found") or "").strip()
        if found:
            email = found.split(",")[0].strip()
    url = (place_url or info.get("official_website") or "").strip()
    name = (
        info.get("company_name_clean")
        or info.get("company_name")
        or info.get("company_name_raw")
        or ""
    ).strip()
    return email, url, name


def is_valid_commercial_company_contact(
    *,
    email: str = "",
    url: str = "",
    name: str = "",
) -> bool:
    """
    True = prywatna firma OK pod outreach PL FAS.
    False = urząd, portal, izba, inkubator, sam tytuł bez firmy.

    Przebieg
    --------
    1. ``is_non_commercial_contact`` → False (odrzut).
    2. Forma prawna w nazwie (PL/DE) → True.
    3. Brak maila → False.
    4. Mail non-commercial → False.
    5. Mail na tej samej domenie co www (root ≥4 znaków) → True.
    6. Heurystyka domeny: spedycja/transport/logist/forward/fracht
       (+ legacy DE gmbh/bau/…) → True.
    7. Inaczej False.
    """
    if is_non_commercial_contact(email=email, url=url, name=name):
        return False
    text = " ".join((name or "").split()).strip()
    if _COMMERCIAL_LEGAL_FORM.search(text):
        return True
    email_low = (email or "").strip().lower()
    if not email_low or "@" not in email_low:
        return False
    if is_non_commercial_email(email_low):
        return False
    edom = email_low.split("@", 1)[1]
    host = _normalize_host(url) or edom
    # Własna domena firmy (mail na tej samej domenie co www)
    if host and (edom == host or host.endswith("." + edom) or edom in host):
        edom_root = edom.split(".")[0]
        if len(edom_root) >= 4:
            return True
    # Heurystyka domeny maila: PL spedycja/logistyka + legacy DE bau/gmbh
    if re.search(
        r"(?:spedycja|spedytor|transport|logist|forward|fracht|"
        r"gmbh|bau|ug|ag|gewerbe)",
        edom,
    ):
        return True
    return False


# >>> OPIS FUNKCJI: funkcja is_cache_contact_institution
# Cel: zdecydować, czy wpis contacts w cache JSON jest instytucją (do usunięcia z cache).
# Parametry: place_url (str) — klucz wpisu (URL miejsca); info (dict|None) — dane kontaktu.
# Zwraca: bool — True, gdy info nie jest dict albo wpis NIE spełnia is_valid_commercial_company_contact
# (odwrotność). Efekty uboczne: brak. Błędy: brak własnej obsługi.
def is_cache_contact_institution(place_url: str, info: dict | None) -> bool:
    """
    True = wpis contacts w JSON cache należy usunąć (nie prywatna firma).

    Odwrotność ``is_valid_commercial_company_contact`` po polach z cache.
    """
    if not isinstance(info, dict):
        return True
    email, url, name = _contact_fields_from_cache(place_url, info)
    return not is_valid_commercial_company_contact(email=email, url=url, name=name)


# >>> OPIS FUNKCJI: funkcja is_cache_serper_entry_institution
# Cel: sprawdzić, czy wynik Serper zapisany w cache wygląda na urząd/portal (czyszczenie cache discovery).
# Parametry: entry — dict z url/link i title albo sam URL (str).
# Zwraca: bool — dla dict: is_non_commercial_contact(url, name=title); dla str: is_non_commercial_website;
# inne typy → False. Efekty uboczne/błędy: brak.
def is_cache_serper_entry_institution(entry) -> bool:
    """
    True = wynik Serper (dict url/title albo sam URL) wygląda na instytucję.

    Używane przy czyszczeniu cache discovery — nie trzymać portali/urzędów.
    """
    if isinstance(entry, dict):
        url = entry.get("url") or entry.get("link") or ""
        title = entry.get("title") or ""
        return is_non_commercial_contact(url=str(url), name=str(title))
    if isinstance(entry, str):
        return is_non_commercial_website(entry)
    return False

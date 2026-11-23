# -*- coding: utf-8 -*-
"""
Ranking adresów e-mail pod zapytania ofertowe PL FAS / spedycja drogowa.

=============================================================================
PO CO TEN MODUŁ
=============================================================================
Z listy kandydatów (regex / Claude / cache) wybiera najlepszy adres do
outreachu FAS. Preferuje:
  - domenę zgodną ze stroną www firmy,
  - local-part ICP (spedycja, dyspozytornia, oferty, biuro…),
  - odrzuca HR / RODO / aggregatory / noreply.

Wywołujący: ``pl_fas_spedycja_scraper`` (oraz testy regresji).

=============================================================================
PROGI
=============================================================================
``MIN_EMAIL_SCORE_FOR_SEND`` (35)
    Minimalny score przy ścisłym ``pick_best_email_for_inquiry``.
Ścieżka scrape (``pick_best_email_from_website_scrape``)
    Luźniejsza: generic local (info/biuro/…) + score ≥ 6 → bump do min. 35.

=============================================================================
STAŁE
=============================================================================
``GENERIC_INQUIRY_LOCAL_PARTS`` — skrzynki ogólne PL (+ DE higiena).
``AGGREGATOR_EMAIL_DOMAINS`` — katalogi/social/giełdy (nie firma).
``_UNSUITABLE_LOCAL_MARKERS`` — local-part nie do zapytania ofertowego.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

try:
    import idna
except ImportError:  # pragma: no cover
    idna = None  # type: ignore

MIN_EMAIL_SCORE_FOR_SEND = 35

# Skrzynki ogólne akceptowane przy scrape www firmy (info@ / biuro@ mimo innej domeny).
GENERIC_INQUIRY_LOCAL_PARTS = frozenset(
    {
        # PL FAS
        "info",
        "kontakt",
        "biuro",
        "office",
        "mail",
        "hello",
        "service",
        "projekt",
        "oferty",
        "zapytania",
        "handlowy",
        "spedycja",
        # Legacy DE (higiena starego cache / Serper)
        "anfrage",
        "anfragen",
        "verkauf",
        "vertrieb",
    }
)

AGGREGATOR_EMAIL_DOMAINS = frozenset(
    {
        "facebook.com",
        "instagram.com",
        "linkedin.com",
        "gelbeseiten.de",
        "wikipedia.org",
        "google.com",
        "maps.google.com",
        "yellowpages.",
        "firmenabc.",
        "obi.pl",
        "leroymerlin.pl",
        "castorama.pl",
        # PL katalogi / giełdy / ogłoszenia (spójne z commercial_contact_filter)
        "panoramafirm.pl",
        "pkt.pl",
        "aleo.com",
        "timocom.com",
        "trans.eu",
        "pracuj.pl",
    }
)

_UNSUITABLE_LOCAL_MARKERS = (
    "ochrona",
    "rodo",
    "iod",
    "gdpr",
    "privacy",
    "dpo",
    "newsletter",
    "reklam",
    "complaint",
    "reklamac",
    "hr",
    "karier",
    "jobs",
    "praca",
    "prasa",
    "press",
    "media",
    "faktur",
    "invoice",
    "ksiegow",
    "it",
    "helpdesk",
    "support",
    "noreply",
    "no-reply",
    "donotreply",
    "postmaster",
    "mailer-daemon",
    "abuse",
    "security",
    "bezpieczenstw",
)


def _normalize_website(url: str) -> str:
    """
    Dopina schemat ``https://``, jeśli URL go nie ma.

    Pusty string → pusty. Używane przed ``urlparse`` w
    ``get_registrable_domain``.
    """
    if not url:
        return ""
    u = url.strip()
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    return u


def get_registrable_domain(url: str) -> str:
    """
    Host ze strony www (lowercase, bez ``www.``).

    =====================================================================
    PO CO
    =====================================================================
    Porównanie domeny maila z domeną firmy (score +52 przy dopasowaniu).

    =====================================================================
    ZWRACA
    =====================================================================
    Np. ``trans-spedycja.pl``; ``""`` przy złym URL / wyjątku parse.
    """
    try:
        netloc = (urlparse(_normalize_website(url)).netloc or "").lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return ""


def _fold_domain_token(value: str) -> str:
    """
    Sprowadza token domeny do ASCII a-z0-9 (porównania fuzzy).

    =====================================================================
    PO CO
    =====================================================================
    PL: ``Głogów`` → ``glogow``; DE: ``ä`` → ``ae``. Potem wycina myślniki
    i inne znaki — żeby ``głogów-spedycja`` ≈ ``glogowspedycja``.

    Używane w ``email_domain_related_to_website``.
    """
    low = (value or "").lower()
    for src, dst in (
        # PL
        ("ą", "a"),
        ("ć", "c"),
        ("ę", "e"),
        ("ł", "l"),
        ("ń", "n"),
        ("ó", "o"),
        ("ś", "s"),
        ("ź", "z"),
        ("ż", "z"),
        # DE / latynizacja
        ("ä", "ae"),
        ("ö", "oe"),
        ("ü", "ue"),
        ("ß", "ss"),
        ("é", "e"),
    ):
        low = low.replace(src, dst)
    return re.sub(r"[^a-z0-9]", "", low)


def _decode_idn_hostname(host: str) -> str:
    """
    Punycode (``xn--…``) → Unicode (gdy dostępne ``idna``).

    =====================================================================
    PO CO
    =====================================================================
    Domeny IDN w URL bywają w Punycode; mail często w Unicode / ASCII fold.
    Bez dekodowania fuzzy match domeny pada.

    Brak biblioteki ``idna`` → zwraca host bez zmian.
    """
    if not host or not idna:
        return host or ""
    labels = (host or "").lower().split(".")
    out: list[str] = []
    for label in labels:
        if not label:
            continue
        try:
            if label.startswith("xn--"):
                out.append(idna.decode(label.encode("ascii")))
            else:
                out.append(label)
        except Exception:
            out.append(label)
    return ".".join(out)


def _website_host_variants(website_url: str) -> list[str]:
    """
    Warianty hosta www do fuzzy match z domeną maila.

    Zwraca listę: host surowy + zdekodowany IDN (+ ewentualnie sam label
    Punycode po decode). Pusta lista, gdy brak hosta.
    """
    host = get_registrable_domain(website_url)
    if not host:
        return []
    variants = {host, _decode_idn_hostname(host)}
    first_label = host.split(".", 1)[0]
    if first_label.startswith("xn--"):
        variants.add(_decode_idn_hostname(first_label))
    return [v for v in variants if v]


def email_domain_related_to_website(email_domain: str, website_url: str) -> bool:
    """
    Czy domena maila jest „powiązana” ze stroną mimo Punycode / innej TLD.

    =====================================================================
    PO CO
    =====================================================================
    Firma bywa na ``firma-spedycja.pl``, a mail na ``firma.pl`` / IDN.
    Exact match host↔domain nie wystarczy — fuzzy po złożonych tokenach.

    =====================================================================
    PRZEBIEG
    =====================================================================
    1. Weź pierwszy label domeny maila, fold (PL/DE) — min. 5 znaków.
    2. Dla każdego wariantu hosta www: split po ``-`` / ``_``.
    3. Fold tokenu hosta; równość / containment / wspólny fragment ≥8.

    =====================================================================
    ZWRACA
    =====================================================================
    ``True`` → w ``score_email_candidate`` bonus +46 (prawie jak exact +52).
    """
    ed = _fold_domain_token((email_domain or "").split(".", 1)[0])
    if len(ed) < 5:
        return False
    for host in _website_host_variants(website_url):
        for token in re.split(r"[-_]", host.split(".", 1)[0]):
            ht = _fold_domain_token(token)
            if len(ht) < 5:
                continue
            if ed == ht or ed in ht or ht in ed:
                return True
            overlap = min(len(ed), len(ht))
            for size in range(overlap, 7, -1):
                for i in range(len(ed) - size + 1):
                    frag = ed[i : i + size]
                    if frag in ht:
                        return True
    return False


def is_unsuitable_inquiry_email(email: str) -> bool:
    """
    True = adres nie nadaje się do zapytania ofertowego FAS.

    =====================================================================
    PO CO
    =====================================================================
    Twardy filtr przed rankingiem / po LLM: nie wysyłaj na HR, RODO,
    faktury, noreply ani aggregatory (Panorama Firm, Timocom, social…).

    =====================================================================
    PRZEBIEG
    =====================================================================
    1. Brak / zły format → True.
    2. Domena w ``AGGREGATOR_EMAIL_DOMAINS`` (lub subdomain) → True.
    3. Local zawiera ``_UNSUITABLE_LOCAL_MARKERS`` → True.
    4. ``ochrona`` + ``danych`` w local → True (IOD).
    5. Inaczej False.
    """
    low = (email or "").strip().lower()
    if not low or "@" not in low:
        return True
    local, _, domain = low.partition("@")
    local = local.strip()
    domain = domain.strip()
    if not local or not domain:
        return True
    if domain in AGGREGATOR_EMAIL_DOMAINS or any(
        domain.endswith("." + agg) for agg in AGGREGATOR_EMAIL_DOMAINS if "." not in agg
    ):
        return True
    if any(marker in local for marker in _UNSUITABLE_LOCAL_MARKERS):
        return True
    if "ochrona" in local and "danych" in local:
        return True
    return False


def score_email_candidate(email: str, website_url: str) -> int:
    """
    Liczy score maila pod outreach PL FAS (im wyżej, tym lepiej).

    =====================================================================
    PO CO
    =====================================================================
    Jedna liczba do sortowania kandydatów. Domena firmowa waży najwięcej;
    local-part ICP spedycji dokłada bonusy; marketing/HR odejmuje.

    =====================================================================
    PRZEBIEG / SKŁADNIKI
    =====================================================================
    - Zły format → ``-999``; unsuitable → ``-500``.
    - Exact / parent domena vs www → ``+52``.
    - Fuzzy powiązanie domeny → ``+46``.
    - Bonusy local (spedycja, dyspozyt, fracht, ftl/ltl, ofert, biuro…);
      legacy piasek/kruszywa tylko ``+4``.
    - Kary: marketing/newsletter ``-42``; samych cyfr ``-40``; local ≤2 ``-25``.

    =====================================================================
    ZWRACA
    =====================================================================
    Int (może być ujemny). Próg wysyłki ścisłej:
    ``MIN_EMAIL_SCORE_FOR_SEND`` (35).
    """
    low = (email or "").strip().lower()
    if not low or "@" not in low:
        return -999
    if is_unsuitable_inquiry_email(low):
        return -500
    local, _, domain = low.partition("@")
    local = local.strip()
    domain = domain.strip()
    score = 0
    host = get_registrable_domain(website_url)
    if host and (domain == host or domain.endswith("." + host) or host.endswith("." + domain)):
        score += 52
    elif email_domain_related_to_website(domain, website_url):
        score += 46
    # Bonusy local-part pod ICP PL FAS (spedycja); piasek/kruszywa = niska higiena legacy.
    for kw, bonus in (
        ("spedycja", 30),
        ("spedytor", 28),
        ("dyspozyt", 26),
        ("fracht", 24),
        ("ftl", 22),
        ("ltl", 22),
        ("ekspedyc", 20),
        ("expedit", 20),
        ("ofert", 20),
        ("zapytan", 18),
        ("handl", 18),
        ("handel", 18),
        ("sprzedaz", 16),
        ("wycen", 16),
        ("logisty", 16),
        ("transport", 14),
        ("biuro", 14),
        ("kontakt", 10),
        ("info", 8),
        ("office", 6),
        # Legacy piasek/kruszywa — nisko, nie top ranking FAS
        ("piasek", 4),
        ("kruszyw", 4),
        ("hurtown", 4),
    ):
        if kw in local:
            score += bonus
    if any(x in local for x in ("marketing", "newsletter", "media", "prasa", "rekrut")):
        score -= 42
    if re.match(r"^[0-9]+$", local):
        score -= 40
    if len(local) <= 2:
        score -= 25
    return score


def rank_email_candidates(
    candidates: list[str], website_url: str
) -> list[tuple[str, int]]:
    """
    Sortuje unikalne maile malejąco po ``score_email_candidate``.

    =====================================================================
    PO CO
    =====================================================================
    Wspólna baza dla ``pick_best_*``, arbitracji LLM i debug/logów.

    =====================================================================
    ZWRACA
    =====================================================================
    Lista ``(email, score)``; pusta, gdy brak sensownych kandydatów.
    Dedupe case-insensitive; kolejność przy remisie = kolejność wejścia
    po stabilnym sort (Python sort jest stabilny — remisy zachowują
    kolejność pierwszego pojawienia się w ``ranked``).
    """
    ranked: list[tuple[str, int]] = []
    seen: set[str] = set()
    for raw in candidates:
        email = (raw or "").strip().lower()
        if not email or email in seen or "@" not in email:
            continue
        seen.add(email)
        ranked.append((email, score_email_candidate(email, website_url)))
    ranked.sort(key=lambda item: item[1], reverse=True)
    return ranked


def pick_best_email_for_inquiry(
    candidates: list[str], website_url: str
) -> tuple[str, int]:
    """
    Ścisły wybór najlepszego maila do wysyłki zapytania.

    =====================================================================
    PO CO
    =====================================================================
    Pipeline B2B / kolejka maili: tylko adres ≥ ``MIN_EMAIL_SCORE_FOR_SEND``
    i nie unsuitable. Inaczej ``("", score)`` — scraper może pominąć lead
    albo iść w LLM arbitration.

    =====================================================================
    ZWRACA
    =====================================================================
    ``(email, score)`` albo ``("", 0)`` / ``("", score)`` przy odrzuceniu.
    """
    ranked = rank_email_candidates(candidates, website_url)
    if not ranked:
        return "", 0
    best, score = ranked[0]
    if score < MIN_EMAIL_SCORE_FOR_SEND or is_unsuitable_inquiry_email(best):
        return "", score
    return best, score


def pick_best_email_from_website_scrape(
    candidates: list[str], website_url: str
) -> tuple[str, int]:
    """
    Luźniejszy wybór dla maili znalezionych na stronie firmy (kampania PL FAS).

    =====================================================================
    PO CO
    =====================================================================
    Po crawl/regex: firma często ma tylko ``info@`` / ``biuro@`` na skróconej
    domenie marki. Ścisły próg 35 + exact domain by je odrzucił — tu
    akceptujemy ``GENERIC_INQUIRY_LOCAL_PARTS`` przy score ≥ 6 i podbijamy
    score do min. ``MIN_EMAIL_SCORE_FOR_SEND`` (żeby kolejka traktowała
    jak „gotowy do wysyłki”).

    =====================================================================
    PRZEBIEG
    =====================================================================
    1. Rank kandydatów.
    2. Top unsuitable → ``("", score)``.
    3. Local w generic i score ≥ 6 → ``(best, max(score, 35))``.
    4. Inaczej ``("", score)`` (nie wymuszaj słabego / nietypowego local).

    =====================================================================
    ZWRACA
    =====================================================================
    Jak ``pick_best_email_for_inquiry``, ale z soft-pass na generic local.
    """
    ranked = rank_email_candidates(candidates, website_url)
    if not ranked:
        return "", 0
    best, score = ranked[0]
    if is_unsuitable_inquiry_email(best):
        return "", score
    local = best.split("@", 1)[0].strip().lower()
    if local in GENERIC_INQUIRY_LOCAL_PARTS and score >= 6:
        return best, max(score, MIN_EMAIL_SCORE_FOR_SEND)
    return "", score


def needs_llm_email_arbitration(candidates: list[str], website_url: str) -> bool:
    """
    True = ranking nie jest jednoznaczny — warto zapytać Claude o wybór.

    =====================================================================
    PO CO
    =====================================================================
    Gdy dwa maile „żywe” mają score w granicach 8 punktów, heurystyka
    lokalna może wybrać źle (np. biuro@ vs dyspozytornia@). LLM dostaje
    listę kandydatów i wybiera jeden — potem ``validate_llm_email_choice``.

    =====================================================================
    PRZEBIEG
    =====================================================================
    1. Rank; ``viable`` = score ≥ 35 i nie unsuitable.
    2. Brak viable, ale są kandydaci → True (niech LLM spróbuje).
    3. ≥2 viable i ≥2 w top−8 → True.
    4. Inaczej False (jeden wyraźny zwycięzca).
    """
    ranked = rank_email_candidates(candidates, website_url)
    viable = [
        (email, score)
        for email, score in ranked
        if score >= MIN_EMAIL_SCORE_FOR_SEND and not is_unsuitable_inquiry_email(email)
    ]
    if not viable:
        return bool(candidates)
    if len(viable) >= 2:
        top = viable[0][1]
        close = sum(1 for _, score in viable if score >= top - 8)
        if close >= 2:
            return True
    return False


def validate_llm_email_choice(
    choice: str,
    candidates: list[str],
    website_url: str = "",
) -> str:
    """
    Waliduje wybór maila z Claude — tylko z listy kandydatów i z progiem.

    =====================================================================
    PO CO
    =====================================================================
    LLM nie może „wymyślić” adresu spoza scrape’u ani wybrać unsuitable /
    poniżej ``MIN_EMAIL_SCORE_FOR_SEND``.

    =====================================================================
    PRZEBIEG
    =====================================================================
    1. Lower + musi być w ``candidates``.
    2. Nie unsuitable.
    3. Score ≥ ``MIN_EMAIL_SCORE_FOR_SEND`` (względem ``website_url``).
    4. OK → zwróć picked; inaczej ``""``.
    """
    picked = (choice or "").strip().lower()
    allowed = {(c or "").strip().lower() for c in candidates if (c or "").strip()}
    if not picked or picked not in allowed:
        return ""
    if is_unsuitable_inquiry_email(picked):
        return ""
    if score_email_candidate(picked, website_url) < MIN_EMAIL_SCORE_FOR_SEND:
        return ""
    return picked

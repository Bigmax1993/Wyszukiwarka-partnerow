# -*- coding: utf-8 -*-
"""
Bloklista kontrahentów — kampania PL FAS / spedycja.

=============================================================================
PO CO TEN MODUŁ
=============================================================================
Firmy, do których **nie** zbieramy leadów, nie eksportujemy i nie mailujemy
z pipeline PL FAS (``pl_fas_spedycja_scraper``).

=============================================================================
TREŚĆ LIST
=============================================================================
- Wpisy PL (komobex, wach-bud, pekabex, …) — wykluczenia kampanii.
- Własne FAS: ``swinczakdata.pl`` / nazwa Swinczak — nie lead.
- Big 3PL / kurierzy (Raben, DHL, InPost…) — **nie tu**; to ICP
  ``pl_spedycja_filter`` / large-company.
- MFG + stare DE GU — **higiena** (nie pisać z FAS). Nie usuwać hurtowo.

Dawna nazwa: ``de_contractor_exclusions`` (shim zachowany).
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

# Nazwy / fragmenty (substring po normalizacji) — PL + higiena DE/MFG
EXCLUDED_NAME_MARKERS: tuple[str, ...] = (
    "action deutschland",
    "action switzerland",
    "wach bud",
    "wach-bud",
    "grotz bauunternehmung",
    "grötz bauunternehmung",
    "hghi baumanagement",
    "komobex inel",
    "komobex-inel",
    "projekt kraft",
    "bauunternehmen frank eichstadt",
    "bauunternehmen frank eichstädt",
    "bob gmbh",
    "fuste polska",
    "grabo projektbau",
    "grabo projekt",
    "igb construct",
    "kessler bau",
    "keßler bau",
    "kiz gmbh",
    "moderner fliesenboden",
    "mfg moderner fliesenboden",
    "muller co ingenieurbau",
    "müller co ingenieurbau",
    "ratisbona",
    "riveto import",
    "schoofs baumanagement",
    "schoofs baumarkt",
    "ubs investment foundation",
    "vic zos",
    "vic-zos",
    "werner nagel",
    "wynajem samochodu",
    "aldi grundbesitz",
    "aldi grundstucksgesellschaft",
    "aldi grundstücksgesellschaft",
    "aldi se",
    "aldi grund",
    "domizil immobilien",
    "duhm projektbau",
    "flowcraft",
    "opel projektbau",
    "pekabex",
    "weemploy",
    "neula gmbh",
    "xpress bau",
    "slb stadt und landbau",
    "slb bautzen",
    "obag hochbau",
    "bauprojekt dresden",
    "kultbau",
    "max wiessner",
    "vobau gmbh",
    "freund bauunternehmung",
    "best bernauer stadtmarketing",
    "neubau edeka in halle",
    "gug hochbau",
    "ruba hausbau",
    "ruba-hausbau",
    "saale ausbau",
    "ausbau senftenberg",
    "plus hochbau",
    "gudat bau",
    "gieske",
    "baugeschaft konrad",
    "baugeschäft konrad",
    "bbf bau",
    "tief und hochbau",
    "tief- und hochbau",
    "tief und anlagenbau",
    "tief- und anlagenbau",
    "firma ogolnobudowlana",
    "firma ogólnobudowlana",
    "hghi",
    "moderner fliesen",
    "mfg fliesen",
    # --- PL FAS: własne / nie kontaktować (nie dubluj big 3PL — to ICP filter) ---
    "swinczak data",
    "swinczakdata",
    "maksym swinczak",
)

# Exact host e-mail / www — PL + higiena DE/MFG (mfg-fliesen zostaje)
EXCLUDED_EMAIL_DOMAINS_EXACT: frozenset[str] = frozenset(
    {
        "neula.de",
        "xpress-bau.de",
        "ostbau.de",
        "slb-bautzen.de",
        "obag-bautzen.de",
        "bauprojekt-dresden.de",
        "eichstaedtbau.de",
        "mfg-fliesen.de",
        "office.mfg-fliesen.de",
        "komobex.pl",
        "wach-bud.pl",
        "fuste.pl",
        "pekabex.pl",
        "riveto.cz",
        "weemploy.pl",
        # PL FAS — własne / partnerskie (nie lead)
        "swinczakdata.pl",
    }
)

# Fragment hosta (substring) — PL + higiena DE/MFG
EXCLUDED_DOMAIN_FRAGMENTS: tuple[str, ...] = (
    "hi-heute.de",
    "neula.de",
    "xpress-bau",
    "slb-bautzen",
    "obag-bautzen",
    "bauprojekt-dresden",
    "eichstaedtbau",
    "eichstdt",
    "mfg-fliesen",
    "modernerfliesenboden",
    "komobex",
    "wach-bud",
    "fuste.",
    "pekabex",
    "riveto.",
    "weemploy",
    "aldi.",
    "action.com",
    "schoofs.",
    "ratisbona",
    "grabo-projekt",
    "grotz.",
    "groetz.",
    "kessler-bau",
    "werner-nagel",
    "maxwiessner",
    "kultbau",
    "vobau",
    "gudat-bau",
    "gieske",
    "bbf-bau",
    "plus-hochbau",
    "freund-bau",
    # PL FAS
    "swinczakdata",
)


def _normalize_match_text(*parts: str) -> str:
    """
    Składa tekst do porównania z ``EXCLUDED_NAME_MARKERS``.

    =====================================================================
    PO CO
    =====================================================================
    Nazwy Serper / Excel bywają z PL znakami (``Ogólnobudowlana``) albo
    DE umlautami (``Grötz``). Markery na liście są w ASCII / uproszczone —
    bez fold match by nie zadziałał.

    =====================================================================
    PRZEBIEG
    =====================================================================
    1. Połącz niepuste ``parts`` spacją, ``lower()``.
    2. Fold PL: ą→a … ż→z (jak ``email_targeting._fold_domain_token``).
    3. Fold DE: ä→ae, ö→oe, ü→ue, ß→ss; ``&`` → `` und ``.
    4. Zamień znaki spoza ``a-z0-9@.\\-`` na spacje; zbĳ whitespace.

    =====================================================================
    ZWRACA
    =====================================================================
    Jedna linia ASCII-ish do substring match, np.
    ``firma ogolnobudowlana xyz``.
    """
    blob = " ".join((p or "").strip() for p in parts if (p or "").strip()).lower()
    for src, dst in (
        # PL (jak email_targeting._fold_domain_token)
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
        ("&", " und "),
    ):
        blob = blob.replace(src, dst)
    blob = re.sub(r"[^a-z0-9@.\-]+", " ", blob)
    return " ".join(blob.split())


def _website_host(url: str) -> str:
    """
    Wyciąga host z URL strony firmy (lowercase, bez ``www.``).

    =====================================================================
    PO CO
    =====================================================================
    Porównanie z ``EXCLUDED_EMAIL_DOMAINS_EXACT`` i
    ``EXCLUDED_DOMAIN_FRAGMENTS`` (www leadu, nie tylko e-mail).

    =====================================================================
    PRZEBIEG
    =====================================================================
    1. Pusty URL → ``""``.
    2. Bez schematu → dopnij ``https://`` (``urlparse`` wymaga netloc).
    3. ``netloc`` lower; obetnij ``www.``.
    4. Wyjątek parse → ``""`` (nie wywalaj scrapera).

    =====================================================================
    ZWRACA
    =====================================================================
    Np. ``swinczakdata.pl`` / ``mfg-fliesen.de``; pusty = brak sygnału hosta.
    """
    u = (url or "").strip()
    if not u:
        return ""
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    try:
        host = (urlparse(u).netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def is_excluded_kontrahent(
    *,
    name: str = "",
    url: str = "",
    email: str = "",
) -> tuple[bool, str]:
    """
    Czy lead jest na blokliście PL FAS (nie zbierać / nie eksportować / nie mailować).

    =====================================================================
    PO CO
    =====================================================================
    Twarda bramka w ``pl_fas_spedycja_scraper`` (Serper hit, contacts cache,
    przed SMTP). Osobno od ICP „czy to spedycja” — tu: **konkretne firmy
    „nie kontaktować”** + higiena MFG/DE GU + własne ``swinczakdata.pl``.

    Big 3PL / kurierzy (Raben, DHL, InPost) — **nie ta lista**; to
    ``pl_spedycja_filter`` / large-company.

    =====================================================================
    PRZEBIEG (KOLEJNOŚĆ BRAMEK)
    =====================================================================
    1. E-mail: domena exact w ``EXCLUDED_EMAIL_DOMAINS_EXACT``
       → ``(True, "email_domain:…")``.
    2. E-mail: substring w ``EXCLUDED_DOMAIN_FRAGMENTS``
       → ``(True, "email_domain_frag:…")``.
    3. Host www (z ``url``): exact → ``www_host:…``;
       fragment → ``www_frag:…``.
    4. Blob nazwa+url+email po ``_normalize_match_text``:
       marker z ``EXCLUDED_NAME_MARKERS`` → ``(True, "name:…")``.
    5. Brak trafienia → ``(False, "")``.

    =====================================================================
    ARGUMENTY
    =====================================================================
    ``name``
        Nazwa firmy (Serper title / Excel / clean).
    ``url``
        Oficjalna www albo link z wyniku Serper.
    ``email``
        Adres docelowy lub pierwszy z listy znalezionych.

    Wszystkie opcjonalne — wystarczy jedno pole z sygnałem.

    =====================================================================
    ZWRACA
    =====================================================================
    ``(excluded: bool, reason: str)`` — ``reason`` do logów / Excel reject;
    pusty gdy nie wykluczono. Prefiksy powodów nie zmieniać (scraper/testy).
    """
    # --- 1–2) Domena e-mail (exact, potem fragment) ---
    email_low = (email or "").strip().lower()
    if email_low and "@" in email_low:
        dom = email_low.split("@", 1)[1]
        if dom in EXCLUDED_EMAIL_DOMAINS_EXACT:
            return True, f"email_domain:{dom}"
        for frag in EXCLUDED_DOMAIN_FRAGMENTS:
            if frag in dom:
                return True, f"email_domain_frag:{frag}"

    # --- 3) Host strony www ---
    host = _website_host(url)
    if host:
        if host in EXCLUDED_EMAIL_DOMAINS_EXACT:
            return True, f"www_host:{host}"
        for frag in EXCLUDED_DOMAIN_FRAGMENTS:
            if frag in host:
                return True, f"www_frag:{frag}"

    # --- 4) Markery w znormalizowanej nazwie / blobie ---
    norm = _normalize_match_text(name, url, email)
    if not norm:
        return False, ""
    for marker in EXCLUDED_NAME_MARKERS:
        if marker in norm:
            return True, f"name:{marker}"

    # --- 5) OK — nie na blokliście ---
    return False, ""


def contact_info_excluded(info: dict | None, place_url: str = "") -> bool:
    """
    Czy rekord ``contacts`` w cache JSON jest na blokliście PL FAS.

    =====================================================================
    PO CO
    =====================================================================
    Wrapper nad ``is_excluded_kontrahent`` dla struktury cache scrapera
    (czyszczenie JSON, rebuild, kolejka maili). Nie mutuje ``info``.

    =====================================================================
    PRZEBIEG
    =====================================================================
    1. ``info`` nie-dict → ``False`` (brak danych ≠ wykluczenie).
    2. E-mail: ``email_target``, inaczej pierwszy z ``emails_found`` (CSV).
    3. Nazwa: ``company_name_clean`` → ``company_name`` → ``company_name_raw``.
    4. URL: ``place_url`` albo ``official_website``.
    5. ``is_excluded_kontrahent(...)[0]``.

    =====================================================================
    ARGUMENTY
    =====================================================================
    ``info``
        Dict z cache contacts (klucze legacy — **nie zmieniać nazw**).
    ``place_url``
        Klucz / URL miejsca w cache (nadpisuje www z info, gdy podane).

    =====================================================================
    ZWRACA
    =====================================================================
    ``True`` = usuń / pomiń lead; ``False`` = zostaw do dalszego ICP.
    """
    if not isinstance(info, dict):
        return False
    email = (info.get("email_target") or "").strip()
    if not email and info.get("emails_found"):
        email = str(info.get("emails_found")).split(",")[0].strip()
    name = (
        info.get("company_name_clean")
        or info.get("company_name")
        or info.get("company_name_raw")
        or ""
    )
    url = (place_url or info.get("official_website") or "").strip()
    excluded, _ = is_excluded_kontrahent(name=name, url=url, email=email)
    return excluded


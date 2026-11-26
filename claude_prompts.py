# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Uzupełnienie opisu modułu claude_prompts (komentarz; docstring poniżej wylicza funkcje publiczne).
#   Rola w pipeline: biblioteka szablonów — każdy etap LLM (page verify, row cleanup, contact extract,
#   discovery terms, mail personalizowany) ma tu funkcję budującą tekst promptu; moduł NIE wywołuje API.
#   Zależności: campaign_keyword_profile (próbki słów kluczowych), pl_spedycja_filter
#   (TRANSPORT_SEGMENT_MARKERS), stdlib re. Wołany przez: page_verify, claude_row_cleanup (przez wrapper
#   scrapera), claude_contact_extract, claude_discovery_terms oraz moduły maila.
#   Wejście: kontekst firmy / tekst crawla / parametry limitów. Wyjście: str (prompt).
# ============================================================
"""
Prompty Claude (Sonnet / Haiku) dla kampanii PL spedycja drogowa (FAS).

Moduł **nie woła API** — tylko buduje teksty promptów. Wywołania LLM są
w ``claude_page_verify``, ``claude_row_cleanup``, ``claude_discovery_terms``,
``email_custom_template``.

Funkcje publiczne:
  - ``prioritize_page_text_for_verify`` — skracanie crawla (priorytet ICP),
  - ``build_page_verify_prompt`` — werdykt ICP strony (JSON),
  - ``build_row_cleanup_prompt`` — QA pól przed Excel (JSON),
  - ``build_contact_extract_prompt`` — e-mail/telefon z www (JSON),
  - ``build_discovery_terms_prompt`` — frazy Serper (linie tekstu),
  - ``build_custom_email_prompt_pl`` / ``_de`` — personalizacja maila (JSON).

Keywordy pomocnicze (role, segmenty, negatywy) biorą się z
``campaign_keyword_profile`` + ``TRANSPORT_SEGMENT_MARKERS`` — ten sam
słownik co filtr regex / Serper.

Klucze JSON legacy DE (``is_gu``, ``has_retail_context``, ``matched_chains``,
``bundesland``, ``handelsketten``) zostają dla scrapera; semantyka = PL FAS.
"""
from __future__ import annotations

import re

from campaign_keyword_profile import (
    SERPER_TEMPLATE_PATTERNS,
    gu_required_keywords_sample,
    large_company_markers_sample,
    negative_keywords_sample,
    retail_chain_keywords_sample,
    retail_context_keywords_sample,
    small_company_markers_sample,
)
from pl_spedycja_filter import TRANSPORT_SEGMENT_MARKERS

# Whitelist segmentów do matched_chains / Segmenty Excel (legacy: Handelskette).
_REQUIRED_CHAINS = ", ".join(TRANSPORT_SEGMENT_MARKERS)
# Limit znaków wyciągu wklejanego do promptu verify / contact.
PAGE_VERIFY_MAX_CHARS = 18000
CONTACT_EXTRACT_MAX_CHARS = 16000
# Priorytet linii/sekcji przy extract kontaktów (nie przy page-verify).
_CONTACT_EXTRACT_TEXT_PRIORITY = (
    "kontakt",
    "dane-firmy",
    "dane firmy",
    "o-firmie",
    "o firmie",
    "o-nas",
    "o nas",
    "biuro",
    "spedycja",
    "nip",
    "impressum",
    "contact",
    "anschrift",
    "datenschutz",
    "mailto",
    "@",
    "tel",
    "telefon",
    "phone",
    "fax",
    "e-mail",
    "email",
)
# Domyślne keywordy priorytetu przy skracaniu crawla pod page-verify (PL FAS).
# Bez Aldi/Filialbau/Rewe — te nie powinny wypychać sekcji ICP spedycji.
_PAGE_VERIFY_TEXT_PRIORITY = (
    "spedycja",
    "spedytor",
    "firma spedycyjna",
    "biuro spedycyjne",
    "freight",
    "forwarding",
    "forwarder",
    "ftl",
    "ltl",
    "fracht",
    "transport drogowy",
    "transport",
    "całopojazdowy",
    "calopojazdowy",
    "grupaż",
    "grupaz",
    "adr",
    "chłodnia",
    "chlodnia",
    "cross-dock",
    "crossdock",
    "dyspozytor",
    "dyspozytornia",
    "europa",
    "oferta",
    "o nas",
    "o-nas",
    "o firmie",
    "o-firmie",
    "usługi",
    "uslugi",
    "flota",
    "naczepa",
    "plandeka",
    "plandełka",
    "linie",
    "kierunki",
)


def prioritize_page_text_for_verify(
    page_text: str,
    *,
    max_chars: int = PAGE_VERIFY_MAX_CHARS,
    priority_keywords: tuple[str, ...] | None = None,
) -> str:
    """
    Skraca tekst crawla pod limit tokenów Claude — najpierw treść ICP PL.

    =====================================================================
    PO CO
    =====================================================================
    Pełny crawl domeny (``website_full_crawl``) często przekracza budżet
    kontekstu modelu. Bez priorytetu Claude dostaje losowy ogon (blog,
    cookies, stopka) zamiast oferty FTL/LTL / strony Kontakt.

    =====================================================================
    GDZIE UŻYWANE
    =====================================================================
    - ``build_page_verify_prompt`` — domyślne ``_PAGE_VERIFY_TEXT_PRIORITY``,
    - ``build_contact_extract_prompt`` — ``_CONTACT_EXTRACT_TEXT_PRIORITY``.

    =====================================================================
    ARGUMENTY
    =====================================================================
    page_text:
        Surowy wyciąg (często z markerami ``=== https://… ===`` na sekcję).
    max_chars:
        Twardy limit długości wyniku (domyślnie ``PAGE_VERIFY_MAX_CHARS``).
    priority_keywords:
        Krotka podciągów (lowercase match). ``None`` → keywordy verify PL.
        Dla kontaktów przekaż ``_CONTACT_EXTRACT_TEXT_PRIORITY``.

    =====================================================================
    ALGORYTM
    =====================================================================
    1) Pusty / krótki tekst ≤ max_chars → zwróć bez zmian.
    2) Są sekcje ``=== http…`` → podziel na bloki URL; bloki z keywordem
       idą na początek, reszta na koniec; sklej ``\\n\\n``.
    3) Brak markerów URL → to samo na poziomie linii (sklej spacją).
    4) Wynik dłuższy niż max_chars → obetnij i doklej ``...``.

    =====================================================================
    ZWRACA
    =====================================================================
    String gotowy do wklejenia w prompt (może kończyć się ``...``).
    Nie mutuje wejścia; nie woła sieci.
    """
    keys = priority_keywords or _PAGE_VERIFY_TEXT_PRIORITY
    raw = (page_text or "").strip()
    if len(raw) <= max_chars:
        return raw
    if "=== http" in raw:
        sections = re.split(r"(?=\n=== https?://)", "\n" + raw)
        sections = [s.strip() for s in sections if s.strip()]
        priority_sec: list[str] = []
        other_sec: list[str] = []
        for sec in sections:
            low = sec.lower()
            if any(k in low for k in keys):
                priority_sec.append(sec)
            else:
                other_sec.append(sec)
        merged = "\n\n".join(priority_sec + other_sec)
    else:
        lines = [ln.strip() for ln in re.split(r"[\n\r]+", raw) if ln.strip()]
        if not lines:
            return raw[:max_chars]
        priority: list[str] = []
        other: list[str] = []
        for ln in lines:
            low = ln.lower()
            if any(k in low for k in keys):
                priority.append(ln)
            else:
                other.append(ln)
        merged = " ".join(priority + other)
    if len(merged) <= max_chars:
        return merged
    return merged[: max_chars - 3] + "..."


def build_page_verify_prompt(
    company_name: str,
    website: str,
    page_text: str,
    *,
    max_chars: int = PAGE_VERIFY_MAX_CHARS,
    serper_blob: str = "",
    pages_crawled: int = 0,
) -> str:
    """
    Buduje prompt Claude do weryfikacji ICP strony www (PL FAS).

    =====================================================================
    PO CO
    =====================================================================
    Po crawl + (opcjonalnie) Serper scraper pyta model: „czy to małe biuro
    spedycyjne z ofertą FTL/LTL / Europa / ADR, a nie kurier / giełda / 3PL?".
    Werdykt steruje ``retail_verified``, ``is_gu``, segmentami w Excelu.

    =====================================================================
    SEMANTYKA PÓL JSON (nazwy legacy DE — nie zmieniać kluczy)
    =====================================================================
    is_gu              → rola spedytora / freight forwardera (True/False)
    has_retail_context → ma usługi drogowe ICP w ofercie
    matched_chains     → segmenty whitelist (ftl, ltl, adr, …) — małe litery
    is_small_firm      → nie globalny 3PL (Raben, Schenker, …)
    primary_role       → Spedytor | Kurier | GieldaFrachtowa | …
    matched_*_keywords → cytaty z wyciągu (nie wymyślać)
    reason             → 1–2 zdania PL

    =====================================================================
    ARGUMENTY
    =====================================================================
    company_name, website:
        Identyfikacja leada (trafia do nagłówka kontekstu).
    page_text:
        Pełny / częściowy crawl; skracany przez ``prioritize_page_text_for_verify``.
    max_chars:
        Budżet znaków wyciągu w prompcie.
    serper_blob:
        Opcjonalny tytuł+snippet z discovery (doklejany w headerze).
    pages_crawled:
        Liczba stron; ``0`` → szacunek z liczby markerów ``=== http``.

    =====================================================================
    CO SKŁADA PROMPT
    =====================================================================
    1) Header kontekstu (``build_claude_context_header``),
    2) automatyczny excerpt dowodów (``build_automatic_evidence_excerpt``),
    3) próbki keywordów z ``campaign_keyword_profile``,
    4) instrukcja PL + drzewo decyzyjne + schema JSON,
    5) skrócony wyciąg strony.

    =====================================================================
    ZWRACA / KONTRAKT
    =====================================================================
    Sam string promptu. Model ma odpowiedzieć **czystym JSON** (bez Markdown).
    Parsowanie: ``claude_page_verify`` / pipeline scrapera.

    Wywołujący typowo: ``claude_page_verify.claude_verify_company_page``,
    wrapper ``page_verify.build_page_verify_prompt``.
    """
    from claude_page_text import (
        build_automatic_evidence_excerpt,
        build_claude_context_header,
        extract_crawl_section_urls,
    )

    raw = page_text or ""
    priority_urls = extract_crawl_section_urls(raw)
    header = build_claude_context_header(
        company_name,
        website,
        serper_blob=serper_blob,
        pages_crawled=pages_crawled or max(raw.count("=== http"), 1 if raw else 0),
        priority_urls=priority_urls,
    )
    evidence = build_automatic_evidence_excerpt(raw)
    snippet = prioritize_page_text_for_verify(raw, max_chars=max_chars)
    role_kw = ", ".join(gu_required_keywords_sample())
    service_kw = ", ".join(retail_context_keywords_sample())
    segment_kw = ", ".join(retail_chain_keywords_sample())
    neg_kw = ", ".join(negative_keywords_sample())
    small_kw = ", ".join(small_company_markers_sample())
    large_kw = ", ".join(large_company_markers_sample())
    return f"""ROLA
Jesteś sędzią ICP (warstwa 2) dla outreachu Forwarding Assistant / FAS w Polsce.
Warstwa 1 (reguły) już odcięła oczywisty śmieć — Ty oceniasz STRONĘ FIRMY.

ICP = TAK gdy to:
• biuro spedycyjne / freight forwarder / organizator transportu drogowego, ALBO
• firma transportowa drogowa (przewozy FTL/LTL/całopojazdowe / międzynarodowe
  dla klientów — nie kurier paczkowy).

NIE jesteś celem: kurierzy paczkowi (InPost/DPD/DHL Express jako produkt),
giełdy frachtów (Timocom, Trans.eu), portale ogłoszeń, media logistyczne,
producent/hurtownia z wyłącznie flotą własną (bez oferty dla klientów),
same oferty pracy HR, urzędy, przeprowadzki, autokary, OSK.

WAŻNE — słowo „spedycja” NIE musi być w H1.
Decyduje DOWÓD usług drogowych dla klientów: FTL / LTL / ADR / fracht /
temperatura / linie / flota usługowa / organizacja przewozu.
Zakładka „Praca / kariera” na stronie REALNEJ firmy NIE jest powodem odrzutu.

ZADANIE
Przeczytaj pełny wyciąg ze strony (wszystkie podstrony crawla, oznaczone
„=== URL ==="). Uwzględnij ścieżki obrazów, alt, galerie floty, sekcje Oferta / O nas.
Czy firma pasuje do ICP? Odpowiedz TYLKO obiektem JSON — bez Markdown, bez komentarza.

CO LICZY SIĘ JAKO DOWÓD (oferta — nie musi być osobna zakładka „Referencje")
• Opis usług: spedycja drogowa LUB firma transportowa drogowa, FTL, LTL, grupaż,
  fracht, transport międzynarodowy / całopojazdowy
• Flota / naczepy / plandeki / chłodnie / ADR jako usługa dla klientów
  (nie tylko „nasze ciężarówki producenta do własnych towarów")
• Linie / kierunki (PL–DE, Europa), cross-dock, dyspozytornia
• Sekcje Oferta / Usługi / O firmie wskazujące przewozy drogowe dla klientów

NATYCHMIAST is_gu=false / has_retail_context=false
• Kurier paczkowy / last-mile (InPost, DPD, DHL Express, Orlen Paczka) jako główny produkt
• Giełda frachtów / marketplace (Timocom, Trans.eu, TimoCom) bez własnego biura
• Portal ogłoszeń, media, blog branżowy, SAM portal pracy (pracuj.pl) jako podmiot
• Producent / hurtownia z wyłącznie flotą własną (bez oferty transportu/spedycji
  dla klientów zewnętrznych)
• Przeprowadzki, autokary, OSK, urzędy

DRZEWO DECYZYJNE (w tej kolejności)
1) Kurier / giełda / portal / HR-jako-podmiot / urząd dominuje → is_gu=false
2) primary_role = Kurier / GieldaFrachtowa / PortalOgloszeniowy / MediaLogistyczne /
   TylkoFlotaWlasna / Producent / HR / Urzad → is_gu=false
3) Brak roli spedycji ORAZ brak firmy transportowej drogowej (dla klientów) →
   is_gu=false
4) Jest „logistyka", ale BRAK usług drogowych ICP (FTL/LTL/fracht/ADR/…) →
   has_retail_context=false
5) Pasuje (spedycja LUB firma transportowa drogowa + segment): is_gu=true,
   has_retail_context=true, matched_chains niepuste
6) Wielkość → is_small_firm

SEGMENTY — WHITELIST (matched_chains)
Dozwolone TYLKO: {_REQUIRED_CHAINS}
• has_retail_context=true TYLKO gdy widać usługę drogową ICP ORAZ ≥1 segment
  z whitelisty w matched_chains (słowo występuje w wyciągu)
• matched_chains: małe litery; kanonicznie preferuj: ftl, ltl, adr, fracht, grupaz,
  chlodnia, europa, calopojazdowy — tylko gdy WPROST w tekście
• Bez nazwanego segmentu z whitelisty → has_retail_context=false

POLE is_small_firm — TY DECYDUJESZ (obowiązkowe)
Cel: lokalna / regionalna firma spedycyjna LUB transportowa — NIE globalny 3PL.
is_small_firm=true np.:
• firma rodzinna, biuro w jednym mieście, polski przewoźnik/spedytor, właściciel,
  < ~250 osób
is_small_firm=false np.:
• Raben, DB Schenker, DHL, DPD, InPost, GEODIS, Kuehne+Nagel, DSV, PEKAES,
  FM Logistic, holding, giełda globalna

MAŁE — INDYCJE: {small_kw}
DUŻE — INDYCJE: {large_kw}

POLE is_gu (nazwa legacy) — znaczenie w tej kampanii
true = biuro spedycyjne / freight forwarder / organizator transportu DROGOWEGO
       ALBO firma transportowa drogowa świadcząca przewozy dla klientów
(NIE kurier paczkowy, NIE sama flota producenta do własnych towarów).
Gdy ICP = TAK → MUSISZ ustawić is_gu=true (także dla firmy transportowej bez
słowa „spedycja” w nazwie) — inaczej lead nie wejdzie do Excela.

POLE has_retail_context (nazwa legacy) — znaczenie
true = ma usługi drogowe ICP (FTL/LTL/fracht/ADR/… z whitelisty) w ofercie.

W WĄTPLIWOŚCI: is_gu=false, has_retail_context=false.

SŁOWA POMOCNICZE (nie muszą wystąpić wszystkie)
[ROLA SPEDYCJI / TRANSPORT]
{role_kw}

[USŁUGI / KONTEKST TRANSPORTOWY]
{service_kw}

[SEGMENTY — whitelist]
{segment_kw}

[ODRZUĆ gdy dominuje]
{neg_kw}

PRZYKŁADY
✓ TAK: „Spedycja drogowa FTL/LTL Europa" + sekcja Oferta → is_gu=true
✓ TAK: „Organizujemy transport całopojazdowy i grupaż; ADR; chłodnia" → is_gu=true
✓ TAK: „Freight forwarding PL–DE" + flota / linie → is_gu=true, matched_chains=[ftl]/[europa]
✓ TAK: „Firma transportowa — przewozy FTL Europa / flota naczep" (bez słowa spedycja)
  → is_gu=true, primary_role=FirmaTransportowa
✓ TAK: HIT Transport + FTL/spedycja, nawet jeśli jest zakładka „Praca" → is_gu=true
✗ NIE: „Nadaj paczkę InPost / DPD" (kurier)
✗ NIE: „Giełda Timocom — znajdź fracht" (marketplace)
✗ NIE: sam portal „Pracuj jako kierowca — oferty pracy" (HR jako podmiot)
✗ NIE: fabryka mebli z flotą tylko do własnych dostaw (TylkoFlotaWlasna)
✗ NIE: Raben / DB Schenker jako główny podmiot → is_small_firm=false

POLA JSON (dokładnie te klucze)
{{
  "matched_gu_keywords": [],
  "matched_retail_keywords": [],
  "matched_chains": [],
  "matched_negative_keywords": [],
  "is_gu": false,
  "has_retail_context": false,
  "is_small_firm": false,
  "primary_role": "",
  "reason": ""
}}

REGUŁY
• matched_*: tylko pojęcia z wyciągu (w tym URL/alt) — nic nie wymyślaj
• matched_gu_keywords: np. spedycja, spedytor, freight forwarder, dyspozytornia,
  firma transportowa
• matched_retail_keywords: np. transport drogowy, organizacja przewozu, flota, oferta
• matched_chains: segmenty whitelist (ftl, ltl, adr, …) — małe litery
• primary_role: Spedytor, FreightForwarder, FirmaTransportowa, Kurier, GieldaFrachtowa,
  PortalOgloszeniowy, MediaLogistyczne, TylkoFlotaWlasna, Producent, HR, Urzad, Inne
• reason: max. 2 zdania PL — jaki dowód oferty (lub dlaczego odrzut)

KONTEKST
{header}

AUTOMATISCHE DOWODY (wstępna selekcja z crawla)
{evidence}

WYCIĄG ZE STRONY (wszystkie podstrony, === URL ===)
{snippet or "(pusty)"}
"""


def build_row_cleanup_prompt(
    *,
    company: str,
    address: str,
    phone: str,
    email: str,
    website: str,
    states: str,
    handelsketten: str = "",
    url: str = "",
) -> str:
    """
    Buduje prompt Claude do QA / czyszczenia wiersza przed Excel Kontakte.

    =====================================================================
    PO CO
    =====================================================================
    Serper i crawl zostawiają śmieci: tytuły PDF, podwójne telefony, SEO-nazwy.
    Cleanup ma dać jedną czystą nazwę + formę prawną, jeden telefon PL,
    kanoniczne www, województwo z listy i segmenty (ftl/ltl/…).

    Błędny wiersz = realny mail B2B do złego odbiorcy — stąd ostre reguły
    „KILLER” na ``company_name_clean``.

    =====================================================================
    MAPOWANIE EXCEL ↔ JSON (kluczy JSON nie zmieniać)
    =====================================================================
    bundesland     → kolumna „Województwo" (wartość z ``states``)
    handelsketten  → kolumna „Segmenty" (whitelist ``_REQUIRED_CHAINS``)
    company_name_clean, address, phone, website, url → pola Kontakte

    Parser (``claude_row_cleanup.parse_claude_row_cleanup_response``) akceptuje
    też aliasy PL: ``wojewodztwo`` / ``segmenty``.

    =====================================================================
    ARGUMENTY (wszystkie keyword-only poza domyślnymi)
    =====================================================================
    company, address, phone, email, website, url:
        Surowe wartości z pipeline (email tylko do plausibility — nie wraca w JSON).
    states:
        Lista dozwolonych województw, już sformatowana ze scrapera
        (np. ``"Mazowieckie, Dolnoslaskie, …"`` = ``PL_WOJEWODZTWA``).
    handelsketten:
        Aktualne segmenty z wiersza (``retail_chains_found``); w prompcie
        powtórzone też jako ``segmenty=`` dla czytelności modelu.

    =====================================================================
    FORMY PRAWNE / TELEFON
    =====================================================================
    Wymagane: Sp. z o.o., S.A., sp.j., … albo GmbH/AG (gdy firma DE w PL).
    Telefon: dokładnie jeden numer PL (+48 lub 0…).

    =====================================================================
    ZWRACA / KONTRAKT
    =====================================================================
    String promptu. Odpowiedź modelu = JSON ze schema w treści.
    Wrapper scrapera: ``build_claude_row_cleanup_prompt`` →
    ``claude_cleanup_row_fields``.
    """
    segments_whitelist = _REQUIRED_CHAINS
    return f"""ROLA
Jesteś liderem QA danych przed eksportem do Excela. Twój output trafia 1:1
do arkusza „Kontakte". Błędne wiersze = prawdziwe maile B2B do złych firm —
bądź bezlitośnie precyzyjny.

GRUPA DOCELOWA (tylko te firmy mogą zachować nazwę)
Małe/średnie biura spedycyjne w Polsce: organizacja transportu drogowego
FTL/LTL, fracht, grupaż, ADR, chłodnia, linie Europa — nie kurier paczkowy,
nie giełda Timocom/Trans.eu, nie portal, nie sama flota producenta.
ŻADNYCH tytułów PDF. ŻADNYCH miast jako „nazwa firmy". ŻADNYCH ogłoszeń pracy.

ZADANIE
Wyczyść pola wejściowe pod Excel. Odpowiedz TYLKO obiektem JSON — bez Markdown.

SCHEMA (dokładnie te klucze; puste stringi dozwolone)
{{"company_name_clean":"","address":"","phone":"","website":"","bundesland":"","handelsketten":"","url":""}}

Uwaga mapowania Excel (NIE zmieniaj nazw kluczy JSON):
• bundesland → kolumna „Województwo"
• handelsketten → kolumna „Segmenty" (ftl, ltl, adr, …)

═══ company_name_clean — REGUŁY KILLER (najwyższy priorytet) ═══
DOZWOLONE: oficjalna nazwa firmy + forma prawna w JEDNEJ linii.
Forma prawna WYMAGANA (PL lub DE):
  Sp. z o.o., Spółka z o.o., S.A., sp.j., sp.k., sp.p., sp. z o.o. sp.k.,
  GmbH, UG, AG, GbR, e.K., KG, OHG, PartG, Co. KG, SE.
OK: „Trans Spedycja Sp. z o.o.", „Euro Fracht S.A.", „Logistyka Nowak sp.j."
NIE OK: „Spedycja Warszawa", „FTL Europa", „Transport", sam kurier / giełda

NATYCHMIAST company_name_clean = "" gdy:
• PDF/dokument: [PDF], „strona X z Y", plan zagospodarowania, analiza
• Software/IT: PDF-XChange, Adobe, Microsoft, Tracker, shop@pdf-*
• Portale/katalogi: 11880, Panorama Firm, Wikipedia, pracuj.pl, Timocom, Trans.eu
• Samo miasto/nagłówek: „Głogów", „Spedycja FTL", tytuł artykułu bez firmy
• URL, e-mail, emoji, slogan marketingowy, dwukropek na końcu

Wyprowadzenie nazwy tylko z kontekstu danych firmy / kontaktu, gdy wejście
to śmieci — NIGDY nie wymyślaj. Wątpliwość → "".

═══ Kolumny Excel (formatowanie) ═══
• address → „ul. Nazwa 1, 00-001 Miasto" (Polska) lub "" — nie zmyślaj ulicy
• website → https://domenafirmowa.pl (root, bez podstrony, bez katalogu, bez PDF)
• url → identyczny z bazowym www (https://domena.pl)
• bundesland → DOKŁADNIE jedna wartość z listy województw: [{states}] — inaczej ""
  (to pole = Województwo w Excelu)
• handelsketten → małe litery, po przecinku, TYLKO segmenty z whitelisty:
  {segments_whitelist}
  — albo "" (to pole = Segmenty w Excelu; nie wpisuj sieci handlowych Aldi/Rewe)
• email_nur_info: NIE wstawiaj do JSON — tylko do kontroli wiarygodności

═══ phone — WALIDACJA 1:1 (identyczna z kodem Excela / gap-fill) ═══
Zwróć DOKŁADNIE JEDEN numer, który MUSI przejść tę samą walidację co pipeline:
• po usunięciu nie-cyfr: 9–15 cyfr łącznie
• PL: 9 cyfr krajowo ALBO ≥11 cyfr z prefiksem 48 (lub 0048)
• format wyjścia: „+48 XXX XXX XXX" albo „+48XXXXXXXXX" (jeden numer, bez przecinków)
• NIE wolno: daty (np. 05-11-2026), NIP, IBAN, 0000…, 0123456789, numery z ≤2 różnymi cyframi,
  faks, „Tel./Fax", dwa numery w jednej komórce, sklejki HTML
• Wejście często ma listę kandydatów po przecinku / „kandydaci:" — wybierz JEDEN prawdziwy
  telefon firmowy (preferuj +48). Jeśli żaden nie spełnia reguł → phone=""
Kod odrzuci numer, który nie spełnia tych reguł — Twoja odpowiedź ma być 1:1 pod walidację.

PRZYKŁADY NEGATYWNE
Wejście name=„PDF ogłoszenie przetarg transport" → company_name_clean=""
Wejście name=„InPost paczkomaty Warszawa" → company_name_clean=""
Wejście phone=„Tel +48 22 111 22 33, Fax +48 22 444" → phone=„+48 22 111 22 33"
Wejście phone=„05-11-2026, 0000081253, +48 327 935 935" → phone=„+48 327 935 935"
Wejście phone=„0000525946, 0/1393229, +48222501247" → phone=„+48 222 501 247"

EINGABE
name={company}
address={address}
phone={phone}
website={website}
url={url}
handelsketten={handelsketten}
segmenty={handelsketten}
email_nur_info={email}
"""


def build_contact_extract_prompt(
    company_name: str,
    website: str,
    page_text: str,
) -> str:
    """
    Buduje prompt Claude do ekstrakcji e-maili i telefonów z crawla (PL FAS).

    =====================================================================
    PO CO
    =====================================================================
    Regex / mailto nie zawsze wyłapie obfuskowane kontakty albo wybierze
    zły adres (noreply, portal). Model czyta wyciąg i zwraca listy
    ``emails``, ``phones``, ``impressum_emails`` — potem ranking w scraperze
    (``pick_best_email_*``).

    =====================================================================
    PRIORYTET SEKCJI (PL, nie tylko Impressum DE)
    =====================================================================
    /kontakt → /dane-firmy → /o-firmie → /o-nas → biuro / NIP →
    Impressum / RODO / legal.

    Tekst skracany z ``_CONTACT_EXTRACT_TEXT_PRIORITY`` (kontakt, biuro,
    spedycja, nip, …).

    =====================================================================
    ODRZUTY W INSTRUKCJI DLA MODELU
    =====================================================================
    - noreply / no-reply / mailer-daemon,
    - giełdy (Timocom, Trans.eu),
    - portale kurierskie (InPost/DPD jako domena portalu, nie lead),
    - katalogi, PDF-viewer.

    Telefony: format PL (+48 lub 0…), max 3 unikalne; faks pomijany gdy
    jest zwykły Tel.

    =====================================================================
    ARGUMENTY
    =====================================================================
    company_name, website:
        Kontekst w headerze (``build_claude_context_header``).
    page_text:
        Crawl domeny; priorytetyzowany pod kontakt, limit
        ``CONTACT_EXTRACT_MAX_CHARS``.

    =====================================================================
    ZWRACA / KONTRAKT JSON
    =====================================================================
    Prompt string. Model →::

        {"company_name":"","emails":[],"phones":[],"impressum_emails":[],"reason":""}

    ``impressum_emails`` = podzbiór z sekcji Kontakt/Dane firmy/O firmie/RODO
    (nazwa pola legacy). Wywołanie: warstwa Claude contact extract w scraperze.
    """
    from claude_page_text import build_claude_context_header, extract_crawl_section_urls

    raw = page_text or ""
    header = build_claude_context_header(
        company_name,
        website,
        pages_crawled=max(raw.count("=== http"), 1 if raw else 0),
        priority_urls=extract_crawl_section_urls(raw),
    )
    snippet = prioritize_page_text_for_verify(
        raw,
        max_chars=CONTACT_EXTRACT_MAX_CHARS,
        priority_keywords=_CONTACT_EXTRACT_TEXT_PRIORITY,
    )
    return f"""ROLA
Jesteś researcherem kontaktów B2B do outreachu do małych biur spedycyjnych w Polsce.
Jedyna misja: znaleźć adresy e-mail i numery telefonów w wyciągu ze strony.

KONTEKST
{header}

REGUŁY (ściśle)
• Wyciągaj TYLKO dane widoczne WPROST w tekście — nic nie wymyślaj, nic nie zgaduj.
• Najwyższy priorytet stron/sekcji (w tej kolejności):
  /kontakt, /dane-firmy, /o-firmie, /o-nas, biuro, NIP — potem Impressum / legal / RODO.
• Liczą się linki mailto: oraz widoczne adresy z @.
• Telefon: numery PL (+48 lub 0…); bez faksu, gdy jest zwykły Tel.; max. 3 unikalne.
• ODRZUĆ e-maile:
  – noreply / no-reply / donotreply / mailer-daemon,
  – giełdy i marketplace (timocom, trans.eu, trans.eu, freight exchange),
  – portale kurierskie / paczkowe (inpost, dpd.pl jako domena kontaktowa portalu,
    dhl.com formularze, orlenpaczka) gdy to nie domena firmowa leada,
  – katalogi (11880, panorama firm, panorfirm), PDF-viewer / adobe / pdf-xchange.
• Local-part (przed @): 1–50 znaków — dłuższe ignoruj.
• Gdy nic nie ma: puste listy.

OUTPUT (tylko JSON, bez Markdown)
{{"company_name":"","emails":[],"phones":[],"impressum_emails":[],"reason":""}}

Pola:
• company_name — oficjalna nazwa tylko gdy jasno w Kontakt / Dane firmy / O firmie, inaczej ""
• emails — wszystkie poprawne firmowe e-maile z tekstu
• impressum_emails — podzbiór emails z Kontakt / Dane firmy / O firmie / Impressum / RODO
• phones — max. 3 unikalne telefony PL
• reason — max. 1 zdanie PL (np. „Kontakt biuro@…" lub „brak kontaktów w wyciągu")

WYCIĄG ZE STRONY (pełny crawl domeny)
{snippet or "(pusty)"}
"""


def build_discovery_terms_prompt(
    lands: list[str],
    *,
    city_str: str,
    land_str: str,
    terms_requested: int,
    exclude_block: str = "",
    max_term_len: int = 55,
) -> str:
    """
    Buduje prompt Claude do **uzupełnienia** fraz Serper (discovery PL FAS).

    =====================================================================
    PO CO
    =====================================================================
    Szablony z ``pl_spedycja_keywords`` / ``SERPER_TEMPLATE_PATTERNS`` dają
    bazę zapytań. Gdy wynik discovery jest słaby, Claude dogrywa dodatkowe
    linie w tym samym stylu PL: ``spedycja FTL {miasto}`` — **nie**
    ``Generalunternehmer Filialbau Aldi``.

    Walidacja po stronie ``claude_discovery_terms.validate_discovery_term``
    (rola spedycji + segment z rotacji).

    =====================================================================
    ARGUMENTY
    =====================================================================
    lands:
        Lista województw (klucze ``BUNDESLAND_CONFIG``); w prompcie używana
        głównie pośrednio — kontekst to ``land_str`` / ``city_str``.
    city_str:
        Miasta po przecinku (np. z wrappera ``claude_discovery_terms``).
    land_str:
        Województwo(a) jako tekst do bloku KONTEKST.
    terms_requested:
        Dokładna liczba linii, których ma wygenerować model.
    exclude_block:
        Opcjonalny blok „już użyte — nie powtarzaj" (doklejany do promptu).
    max_term_len:
        Max długość jednej frazy (domyślnie 55, jak ``DISCOVERY_MAX_TERM_LEN``).

    =====================================================================
    OBOWIĄZKI W TREŚCI PROMPTU DLA MODELU
    =====================================================================
    - trzymać się szablonów PL (``{city}`` / ``{chain}``),
    - marker roli + segment z ``_REQUIRED_CHAINS``,
    - język polski, bez JSON (same linie tekstu).

    =====================================================================
    ZWRACA
    =====================================================================
    String promptu. Output modelu = N linii zapytań (nie JSON).
    Wrapper: ``claude_discovery_terms.build_discovery_terms_prompt``.
    """
    templates = "\n".join(f"- {t}" for t in SERPER_TEMPLATE_PATTERNS[:10])
    role_kw = ", ".join(gu_required_keywords_sample(max_items=6))
    service_kw = ", ".join(retail_context_keywords_sample(max_items=8))
    neg_kw = ", ".join(negative_keywords_sample(max_items=8))
    sample_city = city_str.split(",")[0].strip() if city_str else "Głogów"
    return f"""ROLA
Generujesz zapytania Google (Serper API) do discovery małych biur spedycyjnych
w Polsce (FTL/LTL, fracht, Europa). Każda linia = jedno zapytanie.
Jakość przed ilością. Język zapytań: polski.

KONTEKST
Województwo: {land_str}
Miasta: {city_str}

SZABLONY (warianty — {{city}} / {{chain}} zamień na prawdziwe miasto i segment)
Trzymaj się tych wzorców; NIE wymyślaj zapytań DE typu „Generalunternehmer Filialbau Aldi".
{templates}

OBOWIĄZEK w każdej linii
• Co najmniej jeden marker roli spedycji: {role_kw}
• Co najmniej jeden segment WPROST z whitelisty: {_REQUIRED_CHAINS}
  (rotuj — nie zawsze „ftl"; używaj też ltl, adr, europa, …)
• Kontekst usług mile widziany: {service_kw}
• Max {max_term_len} znaków
• Polski, bez numeracji, bez cudzysłowów, bez pustych linii
• Używaj miast z listy powyżej (lub bliskich w tym województwie)

ZAKAZANE
• {neg_kw}
• Same „transport" / „logistyka" BEZ markera spedycji / FTL / LTL
• Kurier paczkowy, InPost, DPD jako produkt, giełda Timocom/Trans.eu
• Duplikaty lub niemal identyczne linie
• Niemieckie frazy GU / Filialbau / Aldi / Rewe / Ladenbau
{exclude_block}

DOBRE PRZYKŁADY
spedycja FTL {sample_city}
firma spedycyjna {sample_city} LTL
spedycja drogowa Warszawa transport FTL
biuro spedycyjne {sample_city} Europa
organizacja transportu {sample_city} ADR

ZŁE PRZYKŁADY
Generalunternehmer Filialbau Hannover Aldi markt
GU Supermarktbau Rewe Neubau Braunschweig
transport Warszawa
InPost paczkomaty {sample_city}
Timocom giełda frachtów

OUTPUT
Dokładnie {terms_requested} linii — jedno zapytanie na linię, poza tym NIC
(bez JSON, bez komentarza).
"""


def build_custom_email_prompt_de(
    draft: str,
    company_name: str,
    *,
    city_name: str = "",
    delivery_address: str = "",
) -> str:
    """
    Buduje prompt personalizacji maila B2B po **niemiecku** — LEGACY.

    =====================================================================
    STATUS W KAMPANII PL FAS
    =====================================================================
    Nie jest domyślną ścieżką. ``email_custom_template.build_custom_draft_prompt``
    wybiera tę funkcję tylko gdy ``lang == "de"``. Kampania Forwarding
    Assistant używa ``build_custom_email_prompt_pl``.

    Zostawione dla starych szablonów DE / testów kompatybilności.
    **Nie rozwijamy** treści pod spedycję PL.

    =====================================================================
    ZACHOWANIE
    =====================================================================
    Minimalna adaptacja szablonu (1–2 zdania kontekstu), bez wymyślania
    cen, bez zmiany podpisu. Output modelu: JSON ``subject`` + ``body``.

    =====================================================================
    ARGUMENTY
    =====================================================================
    draft:
        Surowy tekst maila od użytkownika / GUI.
    company_name:
        Nazwa adresata (wstawiana w sekcji EMPFÄNGER).
    city_name, delivery_address:
        Opcjonalny kontekst projektu / adresu dostawy (bez zmian faktów).

    =====================================================================
    ZWRACA
    =====================================================================
    String promptu DE. Parser: ``parse_llm_email_json`` w
    ``libs/email_custom_template.py``.
    """
    ctx_city = f"Projektstadt: {city_name}. " if city_name else ""
    ctx_addr = f"Lieferadresse (unverändert): {delivery_address}. " if delivery_address else ""
    return f"""ROLLE
Du bist B2B-Texter für formelle Preisanfragen auf Deutsch. Minimal anpassen, nicht umschreiben.
(Legacy-Prompt — Hauptkampagne PL FAS nutzt die polnische Variante.)

EMPFÄNGER
{company_name}
{ctx_city}{ctx_addr}

AUFGABE
Passe die Nutzervorlage minimal an (1–2 Sätze Kontext zur Firma/Region).
Verbessere Lesbarkeit. ALLE Fakten exakt beibehalten: Mengen, Daten, Adressen, Fraktionen, Telefon, Signatur.

VERBOTEN
• Preise erfinden
• Wörter: kostenlos, Sonderangebot, dringend, jetzt zuschlagen
• Signatur inhaltlich ändern (Person, Firma, Telefon identisch)

OUTPUT (nur JSON)
{{"subject":"...","body":"..."}}
subject: max 78 Zeichen, konkret, ohne Re:/Erinnerung
body: vollständige sendefertige E-Mail, Plain Text

VORLAGE
{draft}
"""


def build_custom_email_prompt_pl(
    draft: str,
    company_name: str,
    *,
    city_name: str = "",
    delivery_address: str = "",
) -> str:
    """
    Buduje prompt generowania maila outreach PL FAS (oferta systemu).

    =====================================================================
    PO CO
    =====================================================================
    Claude pisze **ludzki, mało formalny** mail do biura spedycyjnego:
    najpierw przedstawienie, potem ból (niepełne zapytania FTL w skrzynce),
    potem Forwarding Assistant. Szablon = wzorzec stylu + obowiązkowe fakty
    (``fas_spedycja_inquiry_email_pl``).

    =====================================================================
    GDZIE UŻYWANE
    =====================================================================
    ``libs/email_custom_template`` / ``generate_email_content`` w scraperze.
    Nie dotyczy maili przypominających (``scraper_email_replies``).

    =====================================================================
    REGUŁY (skrót)
    =====================================================================
    - ton: Cześć / Pozdrawiam — bez „Szanowni Państwo", bez korpo-frazy,
    - personalizuj 1–2 zdania pod firmę/miasto (z kontekstu),
    - obowiązkowo zachowaj: „FAS nie wymyśla stawki, kwotę podajecie Wy.",
    - podpis 1:1 (Maksym Swinczak / swinczakdata.pl / telefon),
    - zakaz: ceny, promocja/pilne, kurier/giełda.

    =====================================================================
    ZWRACA
    =====================================================================
    Prompt → JSON ``subject`` + ``body``.
    """
    ctx_city = f"Miasto / region: {city_name}. " if city_name else ""
    ctx_addr = (
        f"Dodatkowy kontekst (bez zmian faktów): {delivery_address}. "
        if delivery_address
        else ""
    )
    return f"""ROLA
Piszesz krótki, ludzki mail B2B po polsku — jak od człowieka do spedytora,
nie jak z CRM. Kampania: oferta systemu Forwarding Assistant (FAS) dla
małych biur spedycyjnych FTL (ogarnianie zapytań z maila + Telegram HITL).

ADRESAT
{company_name}
{ctx_city}{ctx_addr}

STRUKTURA (kolejność obowiązkowa)
1) Przedstawienie: Maksym Swinczak / Forwarding Assistant
2) Dlaczego do tej firmy (1 zdanie z nazwy / miasta / FTL-Europa jeśli pasuje)
3) Ból: niepełne „ile za trasę?”, braki wagi/palet, Excel, stawka i tak ręcznie
4) Co robi FAS: kompletuje zlecenie, dopytuje, rzuca fracht na Telegrama
5) Obowiązkowe zdanie DOKŁADNIE: FAS nie wymyśla stawki, kwotę podajecie Wy.
6) CTA: krótki pokaz, bez długiej prezentacji; załącznik
7) Podpis 1:1 ze szablonu (imię, swinczakdata.pl, telefon) — bez zmian

TON
• mało formalny: „Cześć", „dajcie znać", „pokażę na szybko"
• bez: Szanowni Państwo, niniejszym, pragnę wyrazić, synergia, innowacyjny
• naturalne zdania, nie lista bulletów

ZAKAZ
• Wymyślanie cen, stawek frachtu, rabatów
• Słowa: gratis, promocja, pilne, kliknij, „najlepsza oferta"
• Zmiana podpisu / telefonu / strony
• Twierdzenie, że FAS to kurier paczkowy albo giełda frachtów
• Usuwanie zdania o tym, że FAS nie wymyśla stawki

OUTPUT (tylko JSON)
{{"subject":"...","body":"..."}}
subject: max 78 znaków, konkretny, bez Re:/Przypomnienie
body: pełny mail plain text, gotowy do wysyłki

WZORZEC STYLU I FAKTÓW (możesz lekko parafrazować treść poza podpisem
i poza obowiązkowym zdaniem o stawce; zachowaj sens 1:1)
{draft}
"""


def debug_claude_prompts(
    *,
    company: str = "Trans Spedycja Sp. z o.o.",
    website: str = "https://trans-spedycja.pl",
    city: str = "Głogów",
    land: str = "Dolnoslaskie",
    page_snippet: str | None = None,
) -> dict:
    """
    Diagnostyka modułu promptów PL FAS (bez wywołania API).

    Zwraca dict: limity, keywordy priorytetu, długości promptów, flagi
    sanity (brak DE GU w verify, obecność Województwo/Segmenty w cleanup, …).
    CLI: ``python claude_prompts.py`` / ``python claude_prompts.py --preview verify``.
    """
    page = page_snippet or (
        "=== https://trans-spedycja.pl/oferta ===\n"
        "Firma spedycyjna. Spedycja drogowa FTL LTL Europa. Organizacja transportu ADR.\n"
        "=== https://trans-spedycja.pl/kontakt ===\n"
        "biuro@trans-spedycja.pl +48 76 111 22 33\n"
    )
    states = "Dolnoslaskie, Mazowieckie, Lodzkie, Wielkopolskie"
    prompts = {
        "page_verify": build_page_verify_prompt(
            company, website, page, serper_blob=f"spedycja FTL {city}", pages_crawled=2
        ),
        "row_cleanup": build_row_cleanup_prompt(
            company=company,
            address=f"ul. Test 1, {city}",
            phone="+48 76 111 22 33",
            email="biuro@trans-spedycja.pl",
            website=website,
            states=states,
            handelsketten="ftl, ltl",
            url=website,
        ),
        "contact_extract": build_contact_extract_prompt(company, website, page),
        "discovery_terms": build_discovery_terms_prompt(
            [land],
            city_str=f"{city}, Wrocław",
            land_str=land,
            terms_requested=5,
        ),
        "email_pl": build_custom_email_prompt_pl(
            "Cześć,\n\nZnam ten ból: ile za trasę?\n"
            "FAS nie wymyśla stawki, kwotę podajecie Wy.\n\n"
            "Pozdrawiam\nMaksym Swinczak\nswinczakdata.pl\n+48 516 513 965",
            company,
            city_name=city,
        ),
        "email_de_legacy": build_custom_email_prompt_de("Hallo", company),
    }
    prioritized = prioritize_page_text_for_verify(page, max_chars=500)
    checks = {
        "verify_has_drzewo": "DRZEWO DECYZYJNE" in prompts["page_verify"],
        "verify_no_filialbau": "Filialbau" not in prompts["page_verify"],
        "verify_has_ftl": "ftl" in prompts["page_verify"].lower(),
        "cleanup_has_wojewodztwo": "Województwo" in prompts["row_cleanup"],
        "cleanup_has_segmenty": "Segmenty" in prompts["row_cleanup"],
        "cleanup_has_plus48": "+48" in prompts["row_cleanup"],
        "contact_has_kontakt_path": "/kontakt" in prompts["contact_extract"],
        "contact_no_wortlich": "WÖRTLICH" not in prompts["contact_extract"],
        "discovery_has_wojewodztwo": "Województwo:" in prompts["discovery_terms"],
        "discovery_no_bundesland_label": "Bundesland:" not in prompts["discovery_terms"],
        "email_pl_fas": "Forwarding Assistant" in prompts["email_pl"]
        and "FAS nie wymyśla stawki" in prompts["email_pl"],
        "email_de_legacy_marker": "Legacy" in prompts["email_de_legacy"],
        "priority_no_aldi": "aldi" not in _PAGE_VERIFY_TEXT_PRIORITY,
        "priority_has_spedycja": "spedycja" in _PAGE_VERIFY_TEXT_PRIORITY,
    }
    return {
        "campaign": "pl_fas_spedycja",
        "limits": {
            "PAGE_VERIFY_MAX_CHARS": PAGE_VERIFY_MAX_CHARS,
            "CONTACT_EXTRACT_MAX_CHARS": CONTACT_EXTRACT_MAX_CHARS,
        },
        "required_chains_preview": _REQUIRED_CHAINS[:120] + ("…" if len(_REQUIRED_CHAINS) > 120 else ""),
        "page_verify_priority_count": len(_PAGE_VERIFY_TEXT_PRIORITY),
        "contact_priority_count": len(_CONTACT_EXTRACT_TEXT_PRIORITY),
        "page_verify_priority_sample": list(_PAGE_VERIFY_TEXT_PRIORITY[:8]),
        "contact_priority_sample": list(_CONTACT_EXTRACT_TEXT_PRIORITY[:8]),
        "prompt_lengths": {k: len(v) for k, v in prompts.items()},
        "prioritized_excerpt_preview": prioritized[:240],
        "checks": checks,
        "checks_ok": all(checks.values()),
        "prompts": prompts,
    }


# >>> OPIS FUNKCJI: funkcja _cli_debug
# Cel: CLI diagnostyczne promptów (python claude_prompts.py [--preview NAZWA] [--json]), bez wywołania API.
# Parametry: argv (list[str]|None). Zwraca: int — 0, gdy wszystkie testy sanity z debug_claude_prompts
# przeszły (checks_ok), w przeciwnym razie 1.
# Efekty uboczne: wypisuje raport (lub JSON bez pełnych promptów) na stdout; opcjonalnie pełny tekst
# wybranego promptu. Błędy: argparse kończy proces przy błędnych argumentach; brak innego try/except.
def _cli_debug(argv: list[str] | None = None) -> int:
    """CLI: ``python claude_prompts.py [--preview NAME] [--json]``."""
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Debug claude_prompts (PL FAS) — bez wywołania Anthropic API."
    )
    parser.add_argument(
        "--preview",
        choices=(
            "page_verify",
            "row_cleanup",
            "contact_extract",
            "discovery_terms",
            "email_pl",
            "email_de_legacy",
            "none",
        ),
        default="none",
        help="Wypisz pełny tekst wybranego promptu na stdout",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Cały raport debug (bez pełnych promptów) jako JSON",
    )
    args = parser.parse_args(argv)
    report = debug_claude_prompts()
    if args.json:
        slim = {k: v for k, v in report.items() if k != "prompts"}
        print(json.dumps(slim, ensure_ascii=False, indent=2))
        return 0 if report["checks_ok"] else 1
    print("=== claude_prompts debug (PL FAS) ===")
    print(f"checks_ok: {report['checks_ok']}")
    for k, v in report["checks"].items():
        print(f"  [{'OK' if v else 'FAIL'}] {k}")
    print("limits:", report["limits"])
    print("prompt_lengths:", report["prompt_lengths"])
    print("page_verify_priority_sample:", report["page_verify_priority_sample"])
    print("required_chains_preview:", report["required_chains_preview"])
    print("--- prioritized excerpt ---")
    print(report["prioritized_excerpt_preview"])
    if args.preview != "none":
        print(f"\n=== PREVIEW: {args.preview} ===\n")
        print(report["prompts"][args.preview])
    return 0 if report["checks_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(_cli_debug())

# -*- coding: utf-8 -*-
"""
Outreach B2B PL — oferta systemu **Forwarding Assistant (FAS)** dla biur spedycyjnych.

=====================================================================
PO CO TEN MODUŁ
=====================================================================
Kampania ``Wyszukiwarka-partnerow`` zbiera polskie biura FTL/LTL, a potem
(gdy send B2B będzie włączony) wysyła mail z ofertą systemu FAS — asystenta
spedytora (mail → kompletność zlecenia → Telegram HITL; **bez** autonomicznej
wyceny frachtu).

Ten plik trzyma:
  - stałe nadawcy (imię, WWW, telefon),
  - domyślny **subject**,
  - **podpis** (sztywny — Claude nie może go zmieniać),
  - obowiązkowe zdanie o stawce,
  - **wzorzec draftu** (styl + fakty) pod prompt Claude,
  - funkcje budujące draft / fallback bez API.

=====================================================================
JAK TRAFIA DO PIPELINE
=====================================================================
1. Scraper ustawia ``CUSTOM_EMAIL_DRAFT = FAS_INQUIRY_DRAFT_PL``,
   ``USE_CUSTOM_EMAIL_TEMPLATE = True``, ``CUSTOM_EMAIL_LANG = "pl"``.
2. ``generate_email_content`` woła ``inquiry_try_custom`` /
   ``beautify_custom_email_draft`` z promptem
   ``claude_prompts.build_custom_email_prompt_pl``.
3. Claude pisze ludzki mail (przedstawienie → ból → FAS → CTA),
   zachowując podpis i zdanie o stawce.
4. Brak ``ANTHROPIC_API_KEY`` / błąd API → ``build_fas_inquiry_fallback_pl``.

Załącznik PPTX: ``pl_fas_email_attachment.py`` (Drive FAS; shim: ``mfg_gu_email_attachment``).  
Send SMTP: nadal sterowany ``DISABLE_CONTRACTOR_EMAILS`` (domyślnie OFF).

=====================================================================
LEGACY
=====================================================================
``archive/mfg_gu_inquiry_email_de.py`` — stary stały mail MFG DE (Bodenleger).
**Nie** używać w kampanii PL FAS.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Dane nadawcy (sztywne — muszą wrócić w body 1:1)
# ---------------------------------------------------------------------------
# Imię i nazwisko w treści przedstawienia oraz w podpisie.
FAS_SENDER_NAME = "Maksym Swinczak"
# Strona w podpisie (bez https:// — jak w zatwierdzonym wzorcu).
FAS_WEBSITE = "swinczakdata.pl"
# Telefon w formie czytelnej dla człowieka (ze spacjami).
FAS_PHONE = "+48 516 513 965"
# Ten sam numer bez spacji — do walidacji w scraperze
# (czy Claude nie uciął / nie przekręcił telefonu).
FAS_PHONE_COMPACT = "+48516513965"

# ---------------------------------------------------------------------------
# Subject domyślny (Claude może lekko spersonalizować ≤ 78 znaków;
# fallback / choose_subject_variant bierze ten string).
# ---------------------------------------------------------------------------
FAS_EMAIL_SUBJECT_PL = (
    "Maksym / Forwarding Assistant — szybkie pytanie do spedycji"
)

# ---------------------------------------------------------------------------
# Podpis — zawsze na końcu maila; Claude ma go skopiować bez zmian.
# ---------------------------------------------------------------------------
FAS_EMAIL_SIGNATURE_PL = f"""Pozdrawiam
{FAS_SENDER_NAME}
{FAS_WEBSITE}
{FAS_PHONE}"""

# ---------------------------------------------------------------------------
# Obowiązkowe zdanie produktowe (HITL wyceny).
# Prompt Claude + scraper sprawdzają obecność tego tekstu w body.
# Nie parafrazować — dokładnie ta treść.
# ---------------------------------------------------------------------------
FAS_MUST_KEEP_RATE_LINE = (
    "FAS nie wymyśla stawki, kwotę podajecie Wy."
)

# ---------------------------------------------------------------------------
# Wzorzec stylu + faktów dla Claude
# ---------------------------------------------------------------------------
# Kolejność akapitów = kontrakt promptu:
#   1) Cześć + kim jestem / co robię (FAS)
#   2) dlaczego piszę do tej firmy (haczyk — Claude personalizuje)
#   3) ból skrzynki FTL + co robi FAS + obowiązkowe zdanie o stawce
#   4) CTA (krótki pokaz, załącznik)
#   5) podpis sztywny
#
# Ton: mało formalny (Cześć / dajcie znać) — nie „Szanowni Państwo”.
# Personalizacja dozwolona głównie w akapicie „Piszę, bo…”.
# ---------------------------------------------------------------------------
FAS_INQUIRY_DRAFT_PL = f"""Cześć,

nazywam się Maksym Swinczak. Robię Forwarding Assistant —
narzędzie pod małe biura spedycyjne FTL, głównie pod ogarnianie
zapytań z maila.

Piszę, bo u Was na stronie widać klasyczną spedycję drogową
(Europa / FTL), a to dokładnie ten typ firm, z którym rozmawiam.

Znam ten ból: wpada „ile za trasę?”, brakuje wagi albo
palet, ktoś dopyta z ręki, ktoś wrzuci do Excela, a stawkę i tak
ustalacie sami. FAS pomaga w tej części — kompletuje zlecenie,
dopytuje o braki i rzuca fracht na Telegrama. {FAS_MUST_KEEP_RATE_LINE}

Jak temat w ogóle Was interesuje, dajcie znać — pokażę na
szybko, bez długiej prezentacji. W załączniku krótki opis.

{FAS_EMAIL_SIGNATURE_PL}"""


def build_fas_inquiry_draft_pl() -> str:
    """
    Zwraca kanoniczny draft outreach FAS (PL) — wzorzec dla Claude / testów.

    =====================================================================
    PO CO
    =====================================================================
    Jedno miejsce prawdy dla treści bazowej. Scraper wkłada wynik
    (przez stałą ``FAS_INQUIRY_DRAFT_PL`` / ``CUSTOM_EMAIL_DRAFT``) do
    promptu ``build_custom_email_prompt_pl``. Testy unit i smoke porównują
    obecność bloków (ból, stawka, podpis), nie cały mail z Claude.

    =====================================================================
    ZACHOWANIE
    =====================================================================
    - nie woła API,
    - nie personalizuje nazwy firmy (do tego ``build_fas_inquiry_fallback_pl``
      albo Claude),
    - ``.strip()`` — bez wiodących/końcowych pustych linii przy wklejeniu
      do promptu / SMTP.

    =====================================================================
    ZWRACA
    =====================================================================
    ``str`` — pełny plain-text draft (Cześć … podpis).
    """
    return FAS_INQUIRY_DRAFT_PL.strip()


def build_fas_inquiry_fallback_pl(company_name: str = "") -> str:
    """
    Buduje body maila **bez Claude** (brak klucza API, błąd LLM, dry-path).

    =====================================================================
    PO CO
    =====================================================================
    Pipeline nie może zostać bez treści, gdy Anthropic padnie albo
    ``inquiry_try_custom`` zwróci ``None``. Fallback = zatwierdzony wzorzec
    + opcjonalnie lekki haczyk z nazwą firmy, żeby mail nie wyglądał na
    całkowicie generyczny „do wszystkich”.

    Używane m.in. przez:
      - ``pl_fas_spedycja_scraper._assemble_inquiry_email_body``
      - ``generate_email_content`` (gałąź except / brak custom)

    =====================================================================
    ARGUMENTY
    =====================================================================
    company_name:
        Nazwa biura spedycyjnego z pipeline / Excela.
        Puste → zwykły draft bez wstawki.
        Niepuste → w akapicie „Piszę, bo…” wstawia ``Piszę do {name}, bo…``,
        o ile nazwa nie jest już w body (żeby nie dublować).

    =====================================================================
    CZEGO NIE ROBI
    =====================================================================
    - nie zmienia podpisu ani ``FAS_MUST_KEEP_RATE_LINE``,
    - nie wymyśla stawek / tras / wolumenów,
    - nie dokleja subjectu (subject bierze scraper z ``FAS_EMAIL_SUBJECT_PL``).

    =====================================================================
    ZWRACA
    =====================================================================
    ``str`` — gotowe body plain text do SMTP / dry-run / cache
    (``email_body`` w contacts).
    """
    body = build_fas_inquiry_draft_pl()
    name = (company_name or "").strip()
    if not name:
        return body
    # Haczyk tylko w znanym zdaniu wzorca — nie ruszamy przedstawienia ani CTA.
    needle = "Piszę, bo u Was na stronie widać klasyczną spedycję drogową"
    if needle in body and name not in body:
        body = body.replace(
            needle,
            f"Piszę do {name}, bo u Was na stronie widać klasyczną spedycję drogową",
            1,
        )
    return body


# Alias czytelności w scraperze / testach / smoke:
# „fixed” = kanoniczna treść bazowa (nie wynik Claude per firma).
FIXED_FAS_INQUIRY_PL = build_fas_inquiry_draft_pl()

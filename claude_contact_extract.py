# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Uzupełnienie opisu modułu claude_contact_extract (komentarz; docstring poniżej opisuje format zwrotu).
#   Rola w pipeline: etap „contact extract” — uzupełnia regex/mailto, gdy crawl nie dał maila/telefonu:
#   prosi Claude o kontakty z tekstu crawla i scala je z danymi zebranymi przez scraper (merge bez duplikatów).
#   Zależności: claude_client.claude_generate_text, claude_prompts.build_contact_extract_prompt,
#   contact_extract_utils.parse_contact_extract_response, scraper_env.get_anthropic_api_key.
#   Wejście: tekst crawla, nazwa firmy, www, cache, logger, collected (dict scrapera). Wyjście: dict z
#   kontaktami / zmodyfikowany słownik collected; błędy API są obsługiwane w funkcjach (bez przerwania pipeline).
# ============================================================
"""
Claude: ekstrakcja kontaktów ze stron www (kampania PL FAS / spedycja).

=============================================================================
PO CO TEN MODUŁ
=============================================================================
Uzupełnienie regex / mailto, gdy crawl domeny nie dał maila lub telefonu.
Prompt PL: ``claude_prompts.build_contact_extract_prompt``
(priorytet /kontakt, Dane firmy, NIP; telefony +48).

Parse / normalizacja: ``contact_extract_utils.parse_contact_extract_response``.
Wywołujący: ``pl_fas_spedycja_scraper`` (oraz testy).

=============================================================================
ZWROT ``claude_extract_contacts_from_pages``
=============================================================================
``None``
    Brak API key, pusty tekst strony albo błąd Claude / parse.
``dict``
    Sparsowany JSON: company_name, emails, phones, impressum_emails, reason.

=============================================================================
KLUCZE JSON — LEGACY (NIE ZMIENIAĆ NAZW)
=============================================================================
``emails``             → wszystkie znalezione maile (po filtrze commercial)
``impressum_emails``   → podzbiór z Kontakt / Dane firmy / O firmie / RODO
                         (nazwa legacy „Impressum”; semantyka PL)
``phones``             → telefony z normalizacji utils
``company_name``       → nazwa z kontekstu kontaktu (gdy da się wyprowadzić)
``reason``             → krótkie uzasadnienie PL z modelu
"""
from __future__ import annotations

from typing import Callable

from claude_client import claude_generate_text
from claude_prompts import build_contact_extract_prompt
from contact_extract_utils import parse_contact_extract_response
from scraper_env import get_anthropic_api_key


def merge_claude_contacts_into_collected(collected: dict, parsed: dict) -> dict:
    """
    Scala wynik Claude z dictem ``collected`` scrapera (bez duplikatów).

    =====================================================================
    PO CO
    =====================================================================
    Scraper najpierw zbiera kontakty regexem / mailto do ``collected``.
    Gdy Claude coś znajdzie dodatkowo, ta funkcja **dokłada** maile i
    telefony do tej samej struktury — nie nadpisuje list od zera.

    Typowy flow w ``pl_fas_spedycja_scraper``:

      collected = {emails, phones, impressum_emails, …}  # regex
      parsed = claude_extract_contacts_from_pages(…)     # LLM lub None
      if parsed:
          collected = merge_claude_contacts_into_collected(collected, parsed)

    =====================================================================
    PRZEBIEG
    =====================================================================
    1. Płytka kopia ``collected`` → ``out`` (nie mutuj wejścia w miejscu).
    2. Skopiuj listy ``emails`` / ``impressum_emails`` / ``phones``.
    3. Dokładaj maile z ``parsed["emails"]`` (dedupe po stringu).
    4. Dokładaj ``parsed["impressum_emails"]``:
         - do listy impressum,
         - oraz do ogólnej ``emails`` (impressum ⊆ emails).
    5. Dokładaj telefony z ``parsed["phones"]``.
    6. ``company_name``: tylko gdy w ``collected`` jeszcze puste
       (regex / Serper mają pierwszeństwo, jeśli już coś było).
    7. Zapisz ``claude_contact_reason`` z ``parsed["reason"]`` (audit).

    =====================================================================
    ARGUMENTY
    =====================================================================
    ``collected``
        Stan kontaktów ze scrapera (regex, ewentualnie wcześniejsze merge).
        Oczekiwane klucze (wszystkie opcjonalne): ``emails``,
        ``impressum_emails``, ``phones``, ``company_name``.
    ``parsed``
        Dict z ``parse_contact_extract_response`` / cache Claude
        (te same klucze JSON legacy).

    =====================================================================
    POLA W WYNIKU (LEGACY — NIE ZMIENIAĆ NAZW KLUCZY)
    =====================================================================
    ``emails``
        Unia maili regex + Claude (w tym z impressum).
    ``impressum_emails``
        Legacy key = e-maile z sekcji Kontakt / Dane firmy / O firmie /
        RODO (dawniej „Impressum” DE). **Nazwa klucza zostaje.**
    ``phones``
        Unia telefonów (po normalizacji w utils przy parse).
    ``company_name``
        Uzupełniane tylko gdy było puste.
    ``claude_contact_reason``
        Krótki reason PL z modelu — do logów / Excela / debug.

    =====================================================================
    ZWRACA
    =====================================================================
    Nowy dict (kopia ``collected`` + uzupełnienia). Wejście nie jest
    mutowane in-place poza tym, że wołający zwykle przypisuje wynik
    z powrotem do swojej zmiennej ``collected``.
    """
    # --- 1) Kopia wejścia; listy jako nowe obiekty (dedupe poniżej) ---
    out = dict(collected)
    emails = list(out.get("emails") or [])
    # Legacy key impressum_emails = maile z Kontakt / Dane firmy / RODO (nie Impressum DE).
    impressum_emails = list(out.get("impressum_emails") or [])
    phones = list(out.get("phones") or [])

    # --- 3) Maile ogólne z Claude ---
    for e in parsed.get("emails") or []:
        if e and e not in emails:
            emails.append(e)

    # --- 4) Maile „kontaktowe” (legacy impressum) → obie listy ---
    for e in parsed.get("impressum_emails") or []:
        if e and e not in impressum_emails:
            impressum_emails.append(e)
        if e and e not in emails:
            emails.append(e)

    # --- 5) Telefony ---
    for p in parsed.get("phones") or []:
        if p and p not in phones:
            phones.append(p)

    # --- 6) Nazwa firmy tylko jako uzupełnienie ---
    if parsed.get("company_name") and not out.get("company_name"):
        out["company_name"] = parsed["company_name"]

    # --- 7) Zapisz listy + reason audytowy ---
    out["emails"] = emails
    out["impressum_emails"] = impressum_emails
    out["phones"] = phones
    out["claude_contact_reason"] = parsed.get("reason") or ""
    return out


def claude_extract_contacts_from_pages(
    company_name: str,
    website: str,
    page_text: str,
    logger,
    cache: dict | None,
    *,
    cache_key: str = "",
    on_step: Callable[[str], None] | None = None,
) -> dict | None:
    """
    Szuka e-maili / telefonów w tekście crawla przez Claude (PL FAS).

    =====================================================================
    PO CO
    =====================================================================
    Regex / mailto nie zawsze wyłapie obfuskowany kontakt albo wybierze
    zły adres (katalog, kariera). Claude dostaje skrócony tekst strony
    (priorytet /kontakt, Dane firmy, NIP — patrz ``claude_prompts``)
    i zwraca JSON kontaktów pod outreach do małych biur spedycyjnych.

    Ta funkcja **tylko woła LLM + cache**. Scalanie z regexem robi
    ``merge_claude_contacts_into_collected``.

    =====================================================================
    PRZEBIEG
    =====================================================================
    1. Brak ``ANTHROPIC`` key **lub** pusty ``page_text`` → ``None``
       (scraper zostaje przy samym regexie; bez zbędnego calla).
    2. Klucz cache: ``cache_key`` albo ``website`` albo ``company_name``.
       Bucket: ``cache["claude_contact_extract"]``.
    3. Cache hit → kopia dicta (albo ``None`` jeśli w cache śmieć).
    4. Prompt PL: ``build_contact_extract_prompt(name, url, page_text)``.
    5. ``claude_generate_text`` z ``model_tier="verify"`` (jakość > Haiku).
       Opcjonalny ``on_step`` — postęp UI / log kroków.
    6. ``parse_contact_extract_response`` — JSON + normalizacja maili/tel
       + filtr commercial (utils). Wynik do cache i return.
    7. Wyjątek (API / JSON) → log warning PL FAS, return ``None``.

    =====================================================================
    ARGUMENTY
    =====================================================================
    ``company_name``
        Nazwa leadu (kontekst w prompcie; nie zmyślać kontaktów „spoza” strony).
    ``website``
        URL startowy crawla (w prompcie + fallback klucza cache).
    ``page_text``
        Połączony tekst stron z ``website_full_crawl`` (bloki ``=== http…``).
        Pusty → od razu ``None``.
    ``logger``
        Logger scrapera; może być falsy (wtedy bez info/warning).
    ``cache``
        Współdzielony dict sesji (Serper, verify, contacts…). ``None`` =
        bez persystencji między wywołaniami w tej sesji (i tak setdefault
        na lokalnym ``{}`` nie zapisze się u wołającego).
    ``cache_key``
        Preferowany klucz (np. znormalizowana domena). Pusty → website/name.
    ``on_step``
        Callback postępu przekazywany do ``claude_generate_text``.

    =====================================================================
    ZWRACA
    =====================================================================
    ``None``
        Brak klucza API, brak tekstu, błąd Claude/parse, albo uszkodzony
        wpis w cache. Wołający **nie** powinien crashować — kontynuuje
        z regexem.
    ``dict``
        Jak z ``parse_contact_extract_response``:
        ``company_name``, ``emails``, ``phones``, ``impressum_emails``,
        ``reason`` (+ ewentualne pola utils). Nazwy kluczy legacy —
        **nie zmieniać** (Excel / scraper czyta ``impressum_emails``).

    =====================================================================
    UWAGI PL FAS
    =====================================================================
    - Prompt i priorytet sekcji są PL; ten orchestrator ich nie dubluje.
    - Normalizacja ``+48`` / filtr katalogów: ``contact_extract_utils``
      i ``commercial_contact_filter`` — nie ten plik.
    - Logi: prefiks ``Claude contact extract PL FAS``.
    """
    # --- 1) Bez API lub bez treści strony nie wołamy modelu ---
    api_key = get_anthropic_api_key()
    if not api_key or not (page_text or "").strip():
        return None

    # --- 2–3) Cache per domena / firma ---
    key = cache_key or website or company_name
    extract_cache = (cache or {}).setdefault("claude_contact_extract", {})
    if key in extract_cache:
        cached = extract_cache[key]
        return dict(cached) if isinstance(cached, dict) else None

    # --- 4–6) Prompt PL → Claude → parse → cache ---
    prompt = build_contact_extract_prompt(company_name, website, page_text)
    try:
        text, model = claude_generate_text(
            prompt,
            logger,
            api_key,
            cache=cache,
            model_tier="verify",
            on_step=on_step,
        )
        if logger:
            logger.info(
                "Claude contact extract PL FAS, model=%s, key=%s", model, key[:80]
            )
        parsed = parse_contact_extract_response(text)
        extract_cache[key] = parsed
        return parsed
    except Exception as exc:
        # --- 7) Soft-fail: scraper idzie dalej na regexie ---
        if logger:
            logger.warning("Claude contact extract PL FAS: %s", exc)
        return None

# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Uzupełnienie opisu modułu page_verify (komentarz; docstring poniżej opisuje cztery kroki werdyktu ICP).
#   Rola w pipeline: logika werdyktu ICP niezależna od transportu API — twarde NO-GO bez LLM, budowa
#   promptu, parsowanie JSON Claude i połączenie z regułami tekstowymi (pl_spedycja_filter).
#   Zależności: campaign_keyword_profile.REJECT_PRIMARY_ROLES, claude_prompts.build_page_verify_prompt,
#   pl_spedycja_filter (reguły ról/segmentów), stdlib json, re. Wołany głównie przez claude_page_verify.
#   Wejście: tekst/kontekst strony i odpowiedź modelu. Wyjście: dict werdyktu (m.in. is_gu = rola spedytora,
#   primary_role, powody odrzucenia). Nazwy pól JSON (is_gu, handelsketten) są dziedzictwem — nie zmieniać.
# ============================================================
"""
Weryfikacja strony www pod ICP PL spedycja (FTL/LTL/ADR).

=============================================================================
PO CO TEN MODUŁ
=============================================================================
Warstwa „werdykt ICP” między crawl/tekstem strony a scraperem:

  1. Zbuduj prompt Claude (``build_page_verify_prompt`` → ``claude_prompts``).
  2. Sparsuj JSON odpowiedzi (``parse_page_verify_response``).
  3. Twarde NO-GO bez LLM (``hard_reject_page_context``).
  4. Połącz JSON Claude + reguły ``pl_spedycja_filter`` (``apply_page_verdict``).

Wywołujący typowo: ``claude_page_verify.claude_verify_company_page``
oraz ścieżki w ``pl_fas_spedycja_scraper``.

=============================================================================
KLUCZE JSON — LEGACY (NIE ZMIENIAĆ NAZW)
=============================================================================
``is_gu``                → rola spedytora / freight forwardera (True/False)
``has_retail_context``   → widać usługę drogową ICP (FTL/LTL/…)
``matched_chains``       → segmenty whitelist (ftl, ltl, adr, europa, …)
``matched_gu_keywords``  → markery roli (spedycja, spedytor, …)
``is_small_firm``        → małe/średnie biuro (nie holding / big 3PL)

=============================================================================
KODY REJECT
=============================================================================
Nowe kody PL: ``REASON_*`` poniżej.
Stare DE → PL: ``LEGACY_REJECT_REASON_ALIASES`` (logi / cache / Excel).
"""
from __future__ import annotations

import json
import re

from campaign_keyword_profile import REJECT_PRIMARY_ROLES
from claude_prompts import build_page_verify_prompt as _build_page_verify_prompt
from pl_spedycja_filter import (
    # Whitelist segmentów FTL/LTL/… (nazwa stałej legacy „RETAIL”)
    REQUIRED_RETAIL_CHAIN_KEYWORDS as REQUIRED_TRANSPORT_SEGMENT_KEYWORDS,
    detect_required_retail_chains as detect_required_transport_segments,
    # Role spoza ICP (legacy „non_gu”)
    is_excluded_non_gu_role as is_excluded_non_forwarder_role,
    # Kurier / paczka (legacy „interior fitout”)
    is_interior_fitout_specialist as is_courier_reject,
    is_media_publisher_contact,
    # Giełda frachtów / big 3PL / portal pracy (legacy „retail store operator”)
    is_retail_store_operator_contact as is_freight_exchange_or_3pl,
)

# Pierwszy blok ``{...}`` w odpowiedzi modelu (Claude czasem dokłada tekst obok JSON).
_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)

# Role z profilu keywordów — jeśli Claude zwróci primary_role z tej listy → reject.
_REJECT_ROLES_NORMALIZED = {r.lower() for r in REJECT_PRIMARY_ROLES}

# ---------------------------------------------------------------------------
# Kody reject PL (ICP spedycja) — używane w Excelu / cache / logach.
# ---------------------------------------------------------------------------
REASON_GIELDA_3PL_PORTAL = "gielda_3pl_portal"
REASON_EXCLUDED_NON_FORWARDER = "excluded_non_forwarder_role"
REASON_CLAUDE_BRAK_ROLI = "claude_brak_roli_spedycji"
REASON_BRAK_ROLI_FORWARDERA = "brak_roli_forwardera"
REASON_CLAUDE_BRAK_SEGMENTU = "claude_brak_segmentu_transport"
REASON_BRAK_SEGMENTU_FTL_LTL = "brak_segmentu_ftl_ltl"
REASON_BRAK_SYGNALU_TRANSPORT = "brak_sygnalu_transport"
REASON_CLAUDE_NIE_MALA_FIRMA = "claude_nie_mala_firma"

# Stare kody DE → kanoniczne PL (normalizacja historycznych wierszy / testów).
LEGACY_REJECT_REASON_ALIASES: dict[str, str] = {
    "einzelhandel_betrieb_kein_bau": REASON_GIELDA_3PL_PORTAL,
    "excluded_non_gu_role": REASON_EXCLUDED_NON_FORWARDER,
    "claude_kein_gu": REASON_CLAUDE_BRAK_ROLI,
    "kein_generalunternehmer": REASON_BRAK_ROLI_FORWARDERA,
    "claude_kein_retail": REASON_CLAUDE_BRAK_SEGMENTU,
    "keine_handelskette": REASON_BRAK_SEGMENTU_FTL_LTL,
    "kein_filialbau_hochbau": REASON_BRAK_SYGNALU_TRANSPORT,
    "claude_kein_kleinunternehmen": REASON_CLAUDE_NIE_MALA_FIRMA,
}


def hard_reject_page_context(
    *,
    url: str = "",
    name: str = "",
    page_text: str = "",
) -> tuple[bool, str]:
    """
    Warstwa 1 — twarde NO-GO na śmieci (bez Claude, tanie, deterministyczne).

    =====================================================================
    PO CO
    =====================================================================
    Odcina oczywisty junk zanim wydamy tokeny LLM. **Nie** ocenia
    „dobra spedycja vs dobry transport” — to warstwa 2 (Claude).
    Używane też jako pierwsza bramka w ``apply_page_verdict``.

    =====================================================================
    KOGO ODRZUCA (KOLEJNOŚĆ SPRAWDZEŃ)
    =====================================================================
    1. Giełda frachtów / big 3PL / portal pracy (domena)
       (``is_freight_exchange_or_3pl``) → ``gielda_3pl_portal``
    2. Media / wydawca / portal branżowy
       (``is_media_publisher_contact``) → ``medienportal``
    3. Czysty śmieć roli (sama agencja pracy, urząd, OSK…) —
       NIE firma transportowa/spedycyjna z zakładką „praca”
       (``is_excluded_non_forwarder_role``) → ``excluded_non_forwarder_role``
    4. Kurier / paczka bez twardej spedycji FTL
       (``is_courier_reject``) → zwykle ``kurier_paczka``

    =====================================================================
    ARGUMENTY (tylko keyword)
    =====================================================================
    ``url``
        Adres strony / domena (sygnał portalu / 3PL w hoście).
    ``name``
        Nazwa firmy z Serpera / Excela.
    ``page_text``
        Tekst www lub już złączony blob (page + serper).

    =====================================================================
    ZWRACA
    =====================================================================
    ``(True, reason_code)``  — twarde odrzucenie (kod PL / ``medienportal`` /
                               ``kurier_paczka``).
    ``(False, "")``          — brak twardego NO-GO; wolno iść dalej (Claude
                               lub reguły segmentów).
    """
    blob = " ".join([name, url, page_text]).lower()

    # 1) Giełda / holding 3PL / job board — nie biuro spedycji ICP
    if is_freight_exchange_or_3pl(url=url, text=blob):
        return True, REASON_GIELDA_3PL_PORTAL

    # 2) Media / portal publikacyjny
    if is_media_publisher_contact(url=url, name=name, text=blob):
        return True, "medienportal"

    # 3) Rola spoza ICP
    if is_excluded_non_forwarder_role(blob):
        return True, REASON_EXCLUDED_NON_FORWARDER

    # 4) Kurier / paczka
    is_courier, courier_reason = is_courier_reject(blob)
    if is_courier:
        return True, courier_reason

    return False, ""


def build_page_verify_prompt(
    company_name: str,
    website: str,
    page_text: str,
    *,
    max_chars: int = 8000,
    serper_blob: str = "",
    pages_crawled: int = 0,
) -> str:
    """
    Buduje prompt Claude do weryfikacji ICP PL (spedycja drogowa).

    =====================================================================
    PO CO
    =====================================================================
    Cienki wrapper nad ``claude_prompts.build_page_verify_prompt``, żeby
    ``claude_page_verify`` / testy importowały z jednego miejsca
    (``page_verify``) razem z parserem i werdyktem.

    Treść promptu (rola forwardera, segmenty FTL/LTL, reject kurier/3PL)
    żyje w ``claude_prompts`` — tu nie duplikujemy instrukcji.

    =====================================================================
    ARGUMENTY
    =====================================================================
    ``company_name``
        Nazwa firmy (nagłówek promptu / kontekst).
    ``website``
        URL witryny.
    ``page_text``
        Złączony tekst z crawl (kontakt / oferta / o nas).
    ``max_chars``
        Limit znaków wklejanych do promptu (domyślnie 8000).
    ``serper_blob``
        Opcjonalny snippet Serper (tytuł + opis) jako dodatkowy kontekst.
    ``pages_crawled``
        Liczba stron w crawl — informacja dla modelu / logów.

    =====================================================================
    ZWRACA
    =====================================================================
    Gotowy string promptu (system+user według ``claude_prompts``).
    """
    return _build_page_verify_prompt(
        company_name,
        website,
        page_text,
        max_chars=max_chars,
        serper_blob=serper_blob,
        pages_crawled=pages_crawled,
    )


def parse_page_verify_response(text: str) -> dict:
    """
    Parsuje odpowiedź Claude do słownika werdyktu ICP.

    =====================================================================
    PO CO
    =====================================================================
    Model czasem owija JSON komentarzem. Wyciągamy pierwszy blok ``{...}``,
    ładujemy i normalizujemy typy / listy. Nazwy kluczy **zostają legacy**
    (``is_gu``, ``matched_chains``, …) — Excel i cache ich oczekują.

    =====================================================================
    ARGUMENTY
    =====================================================================
    ``text``
        Surowa odpowiedź modelu (może zawierać markdown / tekst obok JSON).

    =====================================================================
    ZWRACA
    =====================================================================
    Dict z polami::

      matched_gu_keywords      list[str]  # markery roli (spedycja, …)
      matched_retail_keywords  list[str]  # markery oferty transportowej
      matched_chains           list[str]  # segmenty lowercase (ftl, ltl, …)
      matched_negative_keywords list[str]
      is_gu                    bool       # = rola forwardera
      has_retail_context       bool       # = oferta drogowa ICP
      is_small_firm            bool
      primary_role             str
      reason                   str

    =====================================================================
    WYJĄTKI
    =====================================================================
    ``json.JSONDecodeError`` — gdy brak poprawnego JSON.
    ``ValueError`` — gdy root JSON nie jest obiektem.
    """
    raw = (text or "").strip()
    match = _JSON_BLOCK_RE.search(raw)
    payload = match.group(0) if match else raw
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("Page verify: not a JSON object")

    # >>> OPIS FUNKCJI: funkcja parse_page_verify_response._list
    # Pomocnicza (zagnieżdżona): bezpiecznie pobiera listę stringów z pola JSON. Parametry: key (str) —
    # nazwa pola w słowniku data. Zwraca: list[str] — elementy po strip(), bez pustych; [] gdy pole puste lub
    # nie jest listą. Efekty uboczne/błędy: brak.
    def _list(key: str) -> list[str]:
        """Bezpieczne wyciągnięcie listy stringów z pola JSON."""
        val = data.get(key) or []
        if not isinstance(val, list):
            return []
        return [str(x).strip() for x in val if str(x).strip()]

    return {
        "matched_gu_keywords": _list("matched_gu_keywords"),
        "matched_retail_keywords": _list("matched_retail_keywords"),
        # Segmenty zawsze lowercase — zgodność z REQUIRED_RETAIL_CHAIN_KEYWORDS
        "matched_chains": [c.lower() for c in _list("matched_chains")],
        "matched_negative_keywords": _list("matched_negative_keywords"),
        # Klucz JSON ``is_gu`` = is_forwarder_ok (rola spedytora); nazwy NIE zmieniać
        "is_gu": bool(data.get("is_gu")),
        # ``has_retail_context`` = oferta drogowa ICP (nie sieci handlowe)
        "has_retail_context": bool(data.get("has_retail_context")),
        "is_small_firm": bool(data.get("is_small_firm")),
        "primary_role": str(data.get("primary_role") or "").strip(),
        "reason": str(data.get("reason") or "").strip(),
    }


def is_forwarder_ok_from_llm(llm: dict) -> bool:
    """
    Wrapper semantyczny PL: czy Claude uznał rolę spedytora / forwardera.

    Czyta klucz JSON ``is_gu`` (legacy — Excel/Claude). **Nie zmieniać nazwy
    pola w JSON**; ten helper tylko nadaje czytelne API w kodzie Python.
    """
    return bool((llm or {}).get("is_gu"))


def apply_page_verdict(
    llm: dict,
    *,
    page_text: str,
    serper_blob: str = "",
    # API legacy scrapera — no-op (bramka pure-forwarder usunięta).
    require_forwarder_role: bool = True,
    require_generalunternehmer: bool | None = None,
    require_small_firm: bool = True,
) -> tuple[bool, str, list[str]]:
    """
    Po Claude zostają TYLKO tanie zabezpieczenia (Claude bywa omylny):

      1. ``hard_reject`` śmieci (giełda / 3PL / kurier / media)
      2. ``matched_negative`` / ``primary_role`` na czarnej liście
      3. opcjonalnie ``is_small_firm`` (nie Raben / big 3PL)

    ICP biznesowe = wyłącznie ``is_gu`` z Claude (bez dogrywki tekstem,
    bez bramek segment/sygnał 6–8).

    ``require_forwarder_role`` / ``require_generalunternehmer``: no-op.
    Zwraca ``(ok, reason, chains)`` — ``chains`` tylko do Excela/cache.
    """
    _ = require_forwarder_role
    if require_generalunternehmer is not None:
        _ = require_generalunternehmer

    blob = " ".join([page_text or "", serper_blob or ""]).lower()

    # 1) hard_reject śmieci
    hard, hard_reason = hard_reject_page_context(page_text=blob)
    if hard:
        return False, hard_reason, []

    # 2a) matched_negative
    neg = llm.get("matched_negative_keywords") or []
    if neg:
        return False, f"claude_negative:{neg[0]}", llm.get("matched_chains") or []

    # 2b) primary_role czarna lista
    role = (llm.get("primary_role") or "").strip()
    if role and role.lower() in _REJECT_ROLES_NORMALIZED:
        return False, f"claude_role:{role}", llm.get("matched_chains") or []

    required_set = set(REQUIRED_TRANSPORT_SEGMENT_KEYWORDS)
    llm_chains = [
        c.lower()
        for c in (llm.get("matched_chains") or [])
        if c and c.lower() in required_set
    ]
    blob_chains = detect_required_transport_segments(blob)
    chains = list(dict.fromkeys(llm_chains + blob_chains))

    # Claude NIE → reject (bez ratowania regułami tekstowymi)
    if not is_forwarder_ok_from_llm(llm):
        return False, REASON_CLAUDE_BRAK_ROLI, chains

    # 3) opcjonalnie mała firma
    if require_small_firm and not llm.get("is_small_firm"):
        return False, REASON_CLAUDE_NIE_MALA_FIRMA, chains

    reason = (llm.get("reason") or "claude_pl_spedycja").strip()
    return True, f"claude:{reason[:120]}", chains

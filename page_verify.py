# -*- coding: utf-8 -*-
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
    # Oferta / referencje tras (legacy „market project”)
    has_market_project_evidence_on_website as has_transport_offer_evidence,
    # Sygnał transportu: rola ∨ usługa spedycyjna (legacy „store shell / filialbau”)
    has_store_shell_build_evidence as has_transport_signal,
    # Role spoza ICP (legacy „non_gu”)
    is_excluded_non_gu_role as is_excluded_non_forwarder_role,
    # Rola spedytora / freight forwarder (legacy import: is_generalunternehmer)
    is_forwarder_role,
    # Kurier / paczka (legacy „interior fitout”)
    is_interior_fitout_specialist as is_courier_reject,
    is_media_publisher_contact,
    # Giełda frachtów / big 3PL / portal pracy (legacy „retail store operator”)
    is_retail_store_operator_contact as is_freight_exchange_or_3pl,
    # Kwalifikacja leadu = is_forwarder_role (legacy „qualifies_as_gu”)
    qualifies_as_gu_for_campaign as qualifies_as_forwarder_for_campaign,
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
    Twarde NO-GO ICP — bez wołania Claude (tanie, deterministyczne).

    =====================================================================
    PO CO
    =====================================================================
    Odcina oczywiste non-lead'y zanim wydamy tokeny LLM albo zanim
    zaakceptujemy werdykt Claude. Używane też jako pierwsza bramka
    w ``apply_page_verdict`` (na blobie page+serper).

    =====================================================================
    KOGO ODRZUCA (KOLEJNOŚĆ SPRAWDZEŃ)
    =====================================================================
    1. Giełda frachtów / big 3PL / portal pracy
       (``is_freight_exchange_or_3pl``) → ``gielda_3pl_portal``
    2. Media / wydawca / portal branżowy
       (``is_media_publisher_contact``) → ``medienportal``
    3. Role wykluczone z ICP (producent, HR, urząd, tylko flota własna…)
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
    # Domyślnie True = bezpieczniej dla wywołań bez run_config.
    # Kampania PL zwykle przekazuje False (patrz docstring poniżej).
    require_forwarder_role: bool = True,
    require_generalunternehmer: bool | None = None,
    require_small_firm: bool = True,
) -> tuple[bool, str, list[str]]:
    """
    Łączy JSON Claude z regułami tekstowymi → ostateczny werdykt ICP.

    =====================================================================
    PO CO
    =====================================================================
    Claude może się mylić; ta funkcja:

      - najpierw twarde NO-GO na tekście,
      - potem negatywy / role z JSON,
      - potem rola forwardera (``is_gu`` / ``is_forwarder_ok_from_llm`` + filtr),
      - potem kontekst transportu + whitelist segmentów,
      - na końcu sygnał branżowy i (opcjonalnie) mała firma.

    Wynik idzie do ``verification_reason`` / ``retail_chains`` w pipeline.

    =====================================================================
    DOMYŚLNE FLAGI vs KAMPANIA PL
    =====================================================================
    ``require_forwarder_role=True`` (domyślnie)
        Bezpieczniejszy default biblioteki: bez jawnego False odrzuci
        leady bez markera roli spedytora. Dobre dla testów / ad-hoc.

    Kampania PL FAS zwykle przekazuje ``False`` z run_config::

      run_config/pl_fas_spedycja.json → ``"require_generalunternehmer": false``
      → scraper ``REQUIRE_FORWARDER_ROLE = False``
      → ``claude_verify_company_page(require_forwarder_role=False)``
      → ta funkcja: bramka 5 (twardy wymóg markera roli) **wyłączona**;
        wystarczy sygnał ICP z filtra / Claude (segmenty FTL/LTL, …).

    Alias: ``require_generalunternehmer`` (legacy) = to samo co
    ``require_forwarder_role``.

    =====================================================================
    PRZEBIEG (KOLEJNOŚĆ BRAMEK)
    =====================================================================
    0. Alias legacy: ``require_generalunternehmer`` nadpisuje
       ``require_forwarder_role`` (to samo znaczenie).
    1. ``hard_reject_page_context`` na page+serper.
    2. ``matched_negative_keywords`` z Claude → ``claude_negative:…``
    3. ``primary_role`` na liście ``REJECT_PRIMARY_ROLES`` → ``claude_role:…``
    4. Brak roli forwardera (``is_gu`` / is_forwarder_ok + filtr tekstowy)
       → ``claude_brak_roli_spedycji``
    5. Gdy ``require_forwarder_role`` (domyślnie True; PL run_config: False):
       brak markera roli w tekście/JSON → ``brak_roli_forwardera``
    6. Brak kontekstu transportu (``has_retail_context`` /
       ``has_transport_offer_evidence``)
       → ``claude_brak_segmentu_transport``
    7. Brak segmentu z whitelist (Claude ∪ tekst)
       → ``brak_segmentu_ftl_ltl``
    8. Brak sygnału transportu (``has_transport_signal``)
       → ``brak_sygnalu_transport``
    9. Gdy ``require_small_firm`` i Claude mówi nie-mała
       → ``claude_nie_mala_firma``
    10. OK → ``(True, "claude:<reason>", chains)``

    =====================================================================
    ARGUMENTY
    =====================================================================
    ``llm``
        Dict z ``parse_page_verify_response`` (lub ręczny fixture w testach).
    ``page_text``
        Tekst ze stron www (crawl).
    ``serper_blob``
        Opcjonalny tytuł+snippet Serper dołączany do bloba reguł.
    ``require_forwarder_role``
        Wymagaj roli spedytora / freight forwardera (preferowana nazwa PL).
        Default ``True`` (bezpiecznie). Kampania PL: zwykle ``False`` z
        ``run_config`` / ``REQUIRE_FORWARDER_ROLE``.
    ``require_generalunternehmer``
        Alias legacy tego samego; jeśli nie ``None``, nadpisuje
        ``require_forwarder_role``.
    ``require_small_firm``
        Wymagaj ``is_small_firm=True`` z Claude (holdingi / big 3PL OUT).

    =====================================================================
    ZWRACA
    =====================================================================
    ``(ok, reason, chains)`` gdzie:

      ``ok``      bool — True = lead przechodzi ICP verify
      ``reason``  str  — kod PL albo ``claude:<skrócony powód>``
      ``chains``  list[str] — segmenty (ftl/ltl/…) do Excela / cache;
                  pusta przy wczesnym reject bez segmentów
    """
    # --- 0) Preferuj require_forwarder_role; alias legacy nadal działa ---
    if require_generalunternehmer is not None:
        require_forwarder_role = require_generalunternehmer

    blob = " ".join([page_text or "", serper_blob or ""]).lower()

    # --- 1) Twarde NO-GO (giełda / media / kurier / role wykluczone) ---
    hard, hard_reason = hard_reject_page_context(page_text=blob)
    if hard:
        return False, hard_reason, []

    # --- 2) Negatywne keywordy z Claude ---
    neg = llm.get("matched_negative_keywords") or []
    if neg:
        return False, f"claude_negative:{neg[0]}", llm.get("matched_chains") or []

    # --- 3) primary_role na czarnej liście profilu kampanii ---
    role = (llm.get("primary_role") or "").strip()
    if role and role.lower() in _REJECT_ROLES_NORMALIZED:
        return False, f"claude_role:{role}", llm.get("matched_chains") or []

    # --- 4) Rola forwardera ---
    # is_forwarder_ok ≡ JSON ``is_gu`` (klucz legacy — nie zmieniać w Claude/Excel)
    is_forwarder_ok = is_forwarder_ok_from_llm(llm)
    forwarder_campaign_ok, _fwd_marker = qualifies_as_forwarder_for_campaign(blob)
    if not is_forwarder_ok and not forwarder_campaign_ok:
        return False, REASON_CLAUDE_BRAK_ROLI, llm.get("matched_chains") or []

    # --- 5) Opcjonalna twarda bramka roli (run_config) ---
    if require_forwarder_role:
        role_ok, _ = is_forwarder_role(blob)
        role_keywords = bool(llm.get("matched_gu_keywords"))
        if not role_ok and not role_keywords and not forwarder_campaign_ok:
            return False, REASON_BRAK_ROLI_FORWARDERA, llm.get("matched_chains") or []

    # --- 6) Kontekst oferty drogowej (JSON has_retail_context = legacy) ---
    has_transport_offer = bool(llm.get("has_retail_context")) or has_transport_offer_evidence(
        blob
    )
    if not has_transport_offer:
        return False, REASON_CLAUDE_BRAK_SEGMENTU, llm.get("matched_chains") or []

    # --- 7) Whitelist segmentów: Claude ∩ required ∪ detekcja w tekście ---
    required_set = set(REQUIRED_TRANSPORT_SEGMENT_KEYWORDS)
    llm_chains = [
        c.lower()
        for c in (llm.get("matched_chains") or [])
        if c and c.lower() in required_set
    ]
    blob_chains = detect_required_transport_segments(blob)
    chains = list(dict.fromkeys(llm_chains + blob_chains))
    if not chains:
        return False, REASON_BRAK_SEGMENTU_FTL_LTL, []

    # --- 8) Sygnał transportu (rola ∨ usługa spedycyjna) ---
    if not has_transport_signal(blob):
        return False, REASON_BRAK_SYGNALU_TRANSPORT, chains

    # --- 9) Mała firma (gdy flaga ON) ---
    if require_small_firm and not llm.get("is_small_firm"):
        return False, REASON_CLAUDE_NIE_MALA_FIRMA, chains

    # --- 10) Accept ---
    reason = (llm.get("reason") or "claude_pl_spedycja").strip()
    return True, f"claude:{reason[:120]}", chains

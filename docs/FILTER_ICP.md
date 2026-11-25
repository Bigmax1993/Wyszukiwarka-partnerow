# Filtr ICP — PL spedycja drogowa

Plik: [`pl_spedycja_filter.py`](../pl_spedycja_filter.py)  
Profil słów: [`campaign_keyword_profile.py`](../campaign_keyword_profile.py)

## ICP (Ideal Customer Profile)

| Akceptuj | Odrzucaj |
|----------|----------|
| Biuro spedycji / freight forwarding w PL | Kurier / paczkomat / same-day |
| Transport drogowy FTL / LTL / fracht | Giełda frachtów (Timocom, Trans.eu, …) |
| Organizacja przewozu, trasy Europa/Niemcy | Big 3PL (Raben, DB Schenker, DHL, …) |
| | Media / redakcja / portal branżowy |
| | Urząd, oferty pracy, przeprowadzki, autokary |

## Przepływ

**Warstwa 1 (reguły = tylko śmieci):** `reject_reason` / `hard_reject_page_context` —
portale pracy, giełdy, big 3PL, media, gov/OSK, kurier. **Nie** ocenia
„dobra spedycja vs dobry transport”. Firma transportowa/spedycyjna + zakładka
„praca” **nie** jest odrzucana (`_is_irrelevant_role_junk`).

```text
1) reject_reason(email, url, name, text)   ← warstwa 1 (śmieci)
      media | exchange_or_big3pl | courier | irrelevant_role | irrelevant_service | non_commercial
2) portfolio_negates  →  „nie prowadzimy spedycji” itd.
3a) www / Excel / is_valid_* :
      has_forwarding_signal = ROLE ∧ (SEGMENT ∨ SERVICE)
3b) Serper (tytuł/snippet + fraza) :
      has_serper_trade_signal = ROLE ∨ SEGMENT ∨ SERVICE
4) Claude page_verify                      ← warstwa 2 (sędzia ICP)
```

**Warstwa 2 (Claude):** prompt w `claude_prompts.build_page_verify_prompt`.
TAK = biuro spedycji **lub** firma transportowa drogowa (dla klientów) → `is_gu=true`.
NIE = kurier, giełda, portal, flota producenta, przeprowadzki, OSK, sam HR.

**Po Claude (`apply_page_verdict`) — tylko tanie zabezpieczenia:**
1. `hard_reject` śmieci (giełda / 3PL / kurier / media)
2. `matched_negative` / `primary_role` na czarnej liście
3. opcjonalnie `is_small_firm` (nie Raben)

ICP biznesowe = `is_gu` z Claude. Bez dogrywki pure-forwarder / segmentów.
`require_forwarder_role` = no-op.


Komercyjność kontaktu (`is_valid_commercial_company_contact`) jest wymagana na bramkach Serper i www — **bez maila** wiele domen `.pl` odpada (pending discovery warto mieć `email_target`).

## Listy (źródło prawdy)

| Stała | Rola |
|-------|------|
| `FORWARDER_ROLE_MARKERS` | rola firmy |
| `TRANSPORT_SEGMENT_MARKERS` | segment (FTL/LTL/fracht/…) |
| `TRANSPORT_SERVICE_MARKERS` | opis usług |
| `OFFER_SECTION_MARKERS` | oferta / flota / trasy / o nas |
| `COURIER_REJECT_MARKERS` | kurier |
| `EXCHANGE_OR_BIG3PL_DOMAIN_MARKERS` | giełda / big 3PL |
| `MEDIA_*` | media |
| `IRRELEVANT_ROLE_MARKERS` | praca / urząd / … |

Aliasy legacy (`STRICT_GU_MARKERS`, `REQUIRED_RETAIL_CHAIN_KEYWORDS`, …) wskazują na powyższe listy — **nie zmieniaj scrapera** tylko po rename.

## Publiczne funkcje (ważniejsze)

| Funkcja | Znaczenie |
|---------|-----------|
| `reject_reason(...)` | jedna oś odrzuceń |
| `is_forwarder_role` / `is_generalunternehmer` | rola |
| `has_forwarding_signal` / `mentions_*_core` | aktywność www |
| `has_offer_evidence` / `has_retail_references_or_portfolio` | oferta na stronie |
| `is_serper_only_pending_candidate` | filtr Serper (+ alias `is_loose_serper_*`) |
| `is_valid_retail_store_builder_contact` | pełna walidacja kontaktu |
| `is_cache_contact_not_store_builder` | adapter cache JSON |
| `debug_filter_decision(...)` | diagnostyka decyzji |

## Flagi

| Flaga | Domyślnie | Opis |
|-------|-----------|------|
| `REQUIRE_FORWARDER_ROLE` / `REQUIRE_GENERALUNTERNEHMER` | `False` | wystarczy marker roli; martwa gałąź `True` usunięta z filtra |

## Region discovery w cache

Klucz regionu discovery w cache / pipeline:

| Klucz | Status |
|-------|--------|
| `discovery_wojewodztwo` | **zapis i odczyt** (PL) |
| `discovery_bundesland` | tylko odczyt legacy — przy `load_cache` migracja do PL |

API: `get_discovery_wojewodztwo` / `set_discovery_wojewodztwo` w `pl_spedycja_filter.py`
(używane też przez scraper).

## Testy

```powershell
python -m pytest tests/unit/test_strict_gu_filter.py tests/test_strict_gu_filter.py `
  tests/unit/test_retail_references.py tests/test_retail_context_loose.py -q

# Regresje Serper / rola (wybrane klasy):
python -m pytest tests/test_gu_discovery_regression.py::StrictGuFilterRegression `
  tests/test_gu_discovery_regression.py::LooseSerperFilterRegression `
  tests/test_gu_discovery_regression.py::SerperOnlyFilterRegression -q
```

## Debug

```powershell
python -c @"
from pl_spedycja_filter import debug_filter_decision
d = debug_filter_decision(
    email='biuro@spedycja-example.pl',
    url='https://spedycja-example.pl',
    name='Spedycja Example Sp. z o.o.',
    text='Firma spedycyjna. Transport drogowy FTL Europa.',
    search_term='spedycja FTL Warszawa',
)
for k, v in d.items():
    print(f'{k}: {v}')
"@
```

## Co jeszcze nie jest w filtrze

- Treść outreach FAS: `fas_spedycja_inquiry_email_pl.py` + Claude — [`CLAUDE_PROMPTS.md`](CLAUDE_PROMPTS.md). Send B2B: GHA ON (`send_followup`); lokalnie default OFF — [`ROLLBACK_B2B.md`](ROLLBACK_B2B.md).

## Powiązane

- Prompty Claude (PL FAS + CLI debug): [`CLAUDE_PROMPTS.md`](CLAUDE_PROMPTS.md)
- Frazy Serper / geo: `pl_spedycja_keywords.py` (CLI debug: `python pl_spedycja_keywords.py …`)
- Baner cookie przed parse kontaktów: [`COOKIE_CONSENT.md`](COOKIE_CONSENT.md)

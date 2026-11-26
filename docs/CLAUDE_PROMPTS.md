# Prompty Claude — PL FAS (spedycja drogowa)

Plik: [`claude_prompts.py`](../claude_prompts.py)

Moduł **nie woła API** — tylko buduje teksty promptów. Wywołania LLM są w:

| Wrapper | Prompt |
|---------|--------|
| `claude_page_verify.py` | `build_page_verify_prompt` |
| `claude_row_cleanup.py` | `build_row_cleanup_prompt` |
| `claude_contact_extract.py` | `build_contact_extract_prompt` |
| `claude_discovery_terms.py` | `build_discovery_terms_prompt` |
| `libs/email_custom_template.py` | `build_custom_email_prompt_pl` / `_de` |
| `claude_client.py` | HTTP Anthropic (Haiku / Sonnet) |

Keywordy ICP: [`campaign_keyword_profile.py`](../campaign_keyword_profile.py) + `TRANSPORT_SEGMENT_MARKERS` (ten sam słownik co filtr / Serper). Filtr regex: [`FILTER_ICP.md`](FILTER_ICP.md).

## ICP w promptach

| Akceptuj | Odrzucaj |
|----------|----------|
| Biuro spedycyjne / freight forwarder PL | Kurier / paczkomat |
| FTL / LTL / Europa / ADR | Giełda frachtów, big 3PL |
| Mała/regionalna firma | Holding / globalny 3PL |

## Funkcje publiczne

| Funkcja | Output modelu |
|---------|---------------|
| `prioritize_page_text_for_verify` | skrócony crawl (priorytet PL FAS) |
| `build_page_verify_prompt` | JSON werdykt ICP strony |
| `build_row_cleanup_prompt` | JSON QA **całego rekordu** Excel (pola **1:1** pod walidację kodu) |
| `build_contact_extract_prompt` | JSON e-mail / telefon |
| `build_discovery_terms_prompt` | linie fraz Serper (tekst) |
| `build_custom_email_prompt_pl` | JSON subject/body (domyślny PL) |
| `build_custom_email_prompt_de` | JSON subject/body (**legacy** DE) |
| `debug_claude_prompts` | raport sanity bez API |

Limity wyciągu: `PAGE_VERIFY_MAX_CHARS` (18000), `CONTACT_EXTRACT_MAX_CHARS` (16000).

## Klucze JSON (legacy DE — semantyka PL)

Nazwy pól **nie zmieniać** (parser scrapera):

| Klucz | Znaczenie PL FAS |
|-------|------------------|
| `is_gu` | rola spedytora / forwardera |
| `has_retail_context` | usługi drogowe ICP w ofercie |
| `matched_chains` | segmenty (`ftl`, `ltl`, `adr`, …) → Excel **Segmenty** |
| `bundesland` | województwo → Excel **Województwo** |
| `handelsketten` | to samo co segmenty (cleanup) |
| `is_small_firm` | nie globalny 3PL |
| `primary_role` | np. `Spedytor` |

Parser cleanup akceptuje też aliasy PL: `wojewodztwo` / `segmenty`.

## Excel (Kontakte)

Mapowanie po cleanup / verify: Województwo, Miasto, Segmenty, WWW sprawdzone, Spedycja (`lang=pl`). Aliasy starych nagłówków DE są w scraperze.

## Testy

```powershell
# Unit (mocki — bez Anthropic)
python -m pytest tests/test_claude_prompts.py tests/test_claude_contact_extract.py `
  tests/test_claude_page_text.py -q

# Klucz Anthropic (live; wymaga ANTHROPIC_API_KEY)
$env:PYTHONPATH = ".;libs"
python -m pytest tests/integration/test_api_keys.py::test_anthropic_api_key_works -m api_live -q
```

## Diagnostyka (debug)

Bez API — buduje wszystkie prompty i sprawdza flagi PL FAS (brak Filialbau w verify, Województwo/Segmenty w cleanup, …):

```powershell
python claude_prompts.py
python claude_prompts.py --json
python claude_prompts.py --preview page_verify
python claude_prompts.py --preview row_cleanup
python claude_prompts.py --preview discovery_terms
```

Z kodu:

```powershell
python -c "from claude_prompts import debug_claude_prompts; r=debug_claude_prompts(); print(r['checks_ok'], r['prompt_lengths'])"
```

Live smoke (wymaga `ANTHROPIC_API_KEY` + `PYTHONPATH=.;libs`):

```powershell
$env:PYTHONPATH = ".;libs"
python -c @"
import logging, json, re
from claude_prompts import debug_claude_prompts
from claude_client import claude_generate_text
text, model = claude_generate_text(
    debug_claude_prompts()['prompts']['page_verify'],
    logging.getLogger('debug'), max_tokens=400, model_tier='verify', cache={},
)
print(model, json.loads(re.search(r'\{[\s\S]*\}', text).group(0)).get('primary_role'))
"@
```

## Modele

| Env | Domyślnie | Rola |
|-----|-----------|------|
| `CLAUDE_MODEL_VERIFY` / `CLAUDE_MODEL` | `claude-sonnet-4-6` | verify www |
| `CLAUDE_MODEL_FAST` | `claude-haiku-4-5` | discovery terms, cleanup, contact |

## Outreach mail FAS

Wzorzec + podpis: [`fas_spedycja_inquiry_email_pl.py`](../fas_spedycja_inquiry_email_pl.py).  
Prompt: `build_custom_email_prompt_pl` (ludzki ton; obowiązkowe „FAS nie wymyśla stawki…”).  
Scraper: `generate_email_content` → Claude; fallback bez API.  
Send B2B: **GHA ON** (cron `send_followup`); lokalnie default OFF (`DISABLE_CONTRACTOR_EMAILS=1`). Legacy DE: `archive/mfg_gu_inquiry_email_de.py`.

## Powiązane

- Filtr ICP: [`FILTER_ICP.md`](FILTER_ICP.md)
- Cookie przed parse kontaktów: [`COOKIE_CONSENT.md`](COOKIE_CONSENT.md)
- GHA / secrets Claude: [`GITHUB_ACTIONS.md`](GITHUB_ACTIONS.md)

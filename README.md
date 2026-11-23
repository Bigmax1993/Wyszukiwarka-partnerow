# Wyszukiwarka partnerów — kampania PL spedycja

Repozytorium: [Bigmax1993/Wyszukiwarka-partnerow](https://github.com/Bigmax1993/Wyszukiwarka-partnerow)

Cel: **wyszukiwanie polskich firm spedycyjnych (drogowych / FTL)** pod outreach oferty systemu **Forwarding Assistant**.

Pipeline: **Serper → strony www → cache/Excel** (+ B2B na GHA według harmonogramu).

- Maile B2B: **GHA ON** — nd Excel → **pon 09:00** partia 1 → **wt 09:00** partia 2 (tydzień *po* discovery; guard `send_followup`); lokalnie default OFF
- Pełny sync Drive (cache/logi): **wyłączony**
- Raport Excel: Gmail + **upload końcowego `.xlsx` na Drive** (nd 09:00 w tygodniu cyklu)
- Załączniki B2B: oferta + prezentacja (Drive → `pl_fas_email_attachment.py`)
- Serper: `gl=pl`, `hl=pl`

**Produkcja (GHA/PC):** `run_config/pl_fas_spedycja.json` — **wszystkie 16 województw**, discovery w 5 częściach (pon–pt) z `--respect-cache`.  
**Opcja ręczna:** `--rotate-bundesland` — jedno województwo na cykl (nie używane w GHA; flaga legacy).

Cadence **GHA:** od **2026-11-02**, potem co **55 dni** (tydzień wyrównany do poniedziałku). Task Scheduler na **PC** rejestruje zadania **co tydzień** (bez guarda). Szczegóły: [`docs/GITHUB_ACTIONS.md`](docs/GITHUB_ACTIONS.md), [`docs/LOCAL_VS_GHA.md`](docs/LOCAL_VS_GHA.md).

| Moduł | Plik |
|-------|------|
| Scraper | `pl_fas_spedycja_scraper.py` (shim: `de_gu_bauunternehmen_scraper.py`) |
| Filtr ICP (rola / segment / reject) | `pl_spedycja_filter.py` |
| Słownik kampanii (Serper / Claude sample) | `campaign_keyword_profile.py` |
| Frazy Serper (PL spedycja) | `pl_spedycja_keywords.py` |
| Config kampanii (16 województw) | `run_config/pl_fas_spedycja.json` |
| Rotacja 1 województwo (opcjonalna) | `gu_bundesland_rotation.py` |
| Cookie consent (Playwright, PL) | `playwright_cookie_consent.py` |
| Treść maila FAS (Claude) | `fas_spedycja_inquiry_email_pl.py` |
| Załączniki B2B (oferta + prezentacja) | `pl_fas_email_attachment.py` (shimy: `fas_email_attachment.py`, `mfg_gu_email_attachment.py`) |

## Szybki start (lokalnie)

```powershell
git clone https://github.com/Bigmax1993/Wyszukiwarka-partnerow.git
cd Wyszukiwarka-partnerow
pip install -r requirements.txt
$env:KANBUD_PROJECT_ROOT = "$PWD\libs"
python pl_fas_spedycja_scraper.py --test
```

Pełna bateria testów:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\RUN_ALL_TESTS.ps1
powershell -ExecutionPolicy Bypass -File scripts\RUN_ALL_TESTS.ps1 -SkipApiLive
```

| Typ | Folder | Marker pytest |
|-----|--------|---------------|
| Jednostkowe | `tests/unit/` | `-m unit` |
| Integracyjne | `tests/integration/` | `-m "integration and not api_live"` |
| Regresyjne | `tests/test_gu_discovery_regression.py`, `test_excel_append.py` | unittest |
| API live | `tests/integration/test_api_keys.py`, `test_gmail_gdrive_api.py` | `-m api_live` |

Raport Excel (Gmail, **wewnętrzny**, nie B2B): `svinchak1993@gmail.com`
(`EXCEL_REPORT_TO`, `DISABLE_EXCEL_REPORT_EMAIL=0`).
Workflow excel email — **niedziela 09:00** → Gmail **+ Drive (tylko xlsx)**.
Lokalnie: `python scripts/send_excel_gmail.py` / `--dry-run`.

## Wyniki

| Plik / folder | Opis |
|---------------|------|
| `Wyniki/pl_spedycja_cache.json` | Cache Serper + kontakty — **tylko lokalnie w repo** (nie Drive) |
| `Wyniki/pl_spedycja_kontakte.xlsx` | Excel lokalny — **append**; arkusz **Info** |
| `Wyniki/pl_spedycja_scraper.log` | Log — lokalnie w repo |
| `Wyniki/gu_bundesland_rotation.json` | Stan rotacji 1 województwa (opcjonalnie) |
| `Wyniki/FAS_zalacznik_kampania.pptx` | Cache oferty maila (po pobraniu z Drive) |
| `Wyniki/FAS_prezentacja.pptx` | Cache dodatkowej prezentacji B2B |
| `wyslane/` | Kopie .eml (wypełniane przy wysyłce B2B) |

**Google Drive** (szczegóły: [`docs/GOOGLE_DRIVE.md`](docs/GOOGLE_DRIVE.md)):

| Co | Gdzie |
|----|--------|
| Cache JSON + log | **nie** na Drive — lokalne `Wyniki/` |
| Końcowy Excel | [folder kontaktów](https://drive.google.com/drive/folders/1bRCAqle6BS46YEw0fScq4P095LsJUSgL?usp=drive_link) — secret `GDRIVE_FOLDER_ID` |
| Załączniki maila B2B | [oferta](https://drive.google.com/file/d/1t6m-M49t4w0RuLzc8rWebwjldLUMMRW3/view?usp=drive_link) + [prezentacja](https://drive.google.com/file/d/164qbEQOTyO8VTgfZr2wtIVTY-zttk6u7/view?usp=drive_link) — `pl_fas_email_attachment.py` |

## Uruchomienie scrapera

```powershell
$env:KANBUD_PROJECT_ROOT = "$PWD\libs"

python pl_fas_spedycja_scraper.py --test

# Jak produkcja GHA/PC (16 województw, discovery):
python pl_fas_spedycja_scraper.py --run-config run_config\pl_fas_spedycja.json --serper-only-discovery

# Debug JSON run_config (pola wspólne vs extras GU/PL):
python scraper_run_config.py run_config\pl_fas_spedycja.json

# Debug lokalnych ścieżek Wyniki/ (cache/log nie na Drive):
python pl_spedycja_data_paths.py .

python pl_fas_spedycja_scraper.py --backfill-emails-from-cache
python pl_fas_spedycja_scraper.py --rebuild-from-cache

# Wysyłka B2B: NO-OP przy DISABLE_CONTRACTOR_EMAILS=1 (domyślnie)
python pl_fas_spedycja_scraper.py --send-emails-only

# Podgląd treści bez SMTP:
python pl_fas_spedycja_scraper.py --dry-run-email --send-emails-only
```

### Produkcja: cała Polska (domyślnie w GHA)

GHA i skrypty `schedule/run_*_discovery.ps1` używają:

```powershell
python pl_fas_spedycja_scraper.py --run-config run_config\pl_fas_spedycja.json --serper-only-discovery
```

Config ma **16** województw w polu `active_bundeslaender` (nazwa pola legacy). Tydzień discovery dzieli się na 5 części (pon–pt) z kontynuacją cache (`--respect-cache` w GHA).

**Kolejność startu kampanii:** pierwsze województwo = **Dolnoslaskie**, pierwsze miasto w DS = **Głogów**
(`pl_fas_spedycja.json` → `active_bundeslaender`; miasta w `pl_spedycja_keywords.py` → `BUNDESLAND_CONFIG`).

Frazy Serper: `pl_spedycja_keywords.py` — do **1000** wariantów (`spedycja FTL {miasto}`, `firma spedycyjna …`, segmenty FTL/LTL/Europa/ADR itd.).

### Opcja: rotacja 1 województwo / cykl

```powershell
python pl_fas_spedycja_scraper.py --rotate-bundesland
python pl_fas_spedycja_scraper.py --rotation-status
```

Kolejność rotacji (`gu_bundesland_rotation.py` → `BUNDESLAND_ROTATION_ORDER`) też startuje od **Dolnoslaskie**.  
**Nie** jest używana w produkcyjnych workflowach GHA.

### Ręcznie wybrana lista województw

```powershell
python pl_fas_spedycja_scraper.py --bundesland Slaskie,Malopolskie,Dolnoslaskie
python pl_fas_spedycja_scraper.py --run-config run_config\welle_slask_malopolska_dolnyslask.json
```

Inne configi:

| Plik | Zakres |
|------|--------|
| `run_config/pl_fas_spedycja.json` | cała Polska (produkcja) |
| `run_config/polska_alle.json` | cała Polska (dry-run mail) |
| `run_config/wojewodztwo_slaskie.json` | Śląskie |
| `run_config/wojewodztwo_malopolskie.json` | Małopolskie |
| `run_config/welle_slask_malopolska_dolnyslask.json` | Śląskie + Małopolskie + Dolnośląskie |

## Limity

| Limit | Wartość |
|-------|---------|
| Serper | **1000** zapytań / dzień (`SERPER_DAILY_LIMIT`; też w `pl_fas_spedycja.json`) |
| E-mail B2B | **GHA ON** (pon/wt 09:00 po Excelu, `send_followup`); lokalnie default OFF; limit 300/dzień |
| Discovery Polska | 16 województw w 5 dniach (pon–pt), cache między dniami |

## Harmonogram

**GHA:** **02–08.11.2026** jak w poprzednim planie, potem co **55 dni** (guard; start = poniedziałek markera lub kolejny).  
**PC (Task Scheduler):** te same godziny **co tydzień** — bez guarda. Excel + Drive tylko na GHA.

Szczegóły: [`docs/GITHUB_ACTIONS.md`](docs/GITHUB_ACTIONS.md), [`schedule/PLAN_5_DNI.md`](schedule/PLAN_5_DNI.md), [`docs/LOCAL_VS_GHA.md`](docs/LOCAL_VS_GHA.md).

| Dzień | Godzina (PL) | PC | GitHub Actions |
|-------|--------------|-----|----------------|
| **Poniedziałek** | **18:00** | `run_poniedzialek_discovery.ps1` | discovery (część 1) — `pl_fas_pi.yml` |
| **Wtorek** | **18:00** | `run_wtorek_discovery.ps1` | discovery (część 2) |
| **Środa** | **18:00** | `run_sroda_discovery.ps1` | discovery (część 3) |
| **Czwartek** | **18:00** | `run_czwartek_discovery.ps1` | discovery (część 4) |
| **Piątek** | **18:00** | `run_piatek_discovery.ps1` | discovery (część 5) → **chain** backfill |
| **Niedziela** | **06:00** | `run_czwartek.ps1` (legacy nazwa = backfill) | backfill — `pl_fas_thu.yml` |
| **Niedziela** | **09:00** | — | excel email + Drive xlsx — `pl_fas_mon_excel_email.yml` |
| **Poniedziałek** (tydzień po Excelu) | **09:00** | — (PC: ręcznie) | B2B partia 1 — `pl_fas_tue.yml` (`send_followup`) |
| **Wtorek** (po partii 1) | **09:00** | — (PC: ręcznie) | B2B partia 2 — `pl_fas_fri.yml` (`send_followup`) |
| Prep / pełny Drive | — | — | **OFF** |

### Daty uruchomień GHA (tygodnie cyklu)

| Cykl | Discovery (pon–pt 18:00) | Backfill + Excel (nd 06:00 / 09:00) |
|------|--------------------------|------------------------------------|
| hist. | **21–25.09.2026** (stary 42d) | **27.09.2026** |
| 1 | **02–06.11.2026** | **08.11.2026** |
| 2 | **28.12.2026–01.01.2027** | **03.01.2027** |
| 3 | **22–26.02.2027** | **28.02.2027** |
| 4 | **19–23.04.2027** | **25.04.2027** |
| 5 | **14–18.06.2027** | **20.06.2027** |
| 6 | **09–13.08.2027** | **15.08.2027** |
| 7 | **04–08.10.2027** | **10.10.2027** |
| 8 | **22–26.11.2027** | **28.11.2027** |

Pełna tabela dzień-po-dniu: [`docs/GITHUB_ACTIONS.md`](docs/GITHUB_ACTIONS.md#kalendarz-uruchomień-gha-europewarsaw).

Po udanym discovery w **piątek** GHA odpala backfill od razu (`workflow_dispatch`). Cron nd 06:00 to zapasowy / restart.

Task Scheduler:

```powershell
powershell -ExecutionPolicy Bypass -File schedule\register_tasks_5_dni.ps1
```

Pełny pipeline na GitHub Actions (ręcznie; bez pełnego Drive sync — B2B = osobne workflowy send):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_full_pipeline_gha.ps1
powershell -ExecutionPolicy Bypass -File scripts\run_full_pipeline_gha.ps1 -SkipDiscovery
```

## GitHub Actions

[`docs/GITHUB_ACTIONS.md`](docs/GITHUB_ACTIONS.md)

| Secret | Wymagany | Opis |
|--------|----------|------|
| `SERPER_API_KEY` | tak (discovery) | API Serper |
| `ANTHROPIC_API_KEY` | tak (discovery + backfill) | Claude API |
| `CLAUDE_MODEL_FAST` | opcjonalny | Haiku — frazy Serper, cleanup Excel |
| `CLAUDE_MODEL_VERIFY` | opcjonalny | Sonnet — weryfikacja www |
| `MAIL_USER`, `MAIL_PASSWORD` | tak (Excel + B2B) | SMTP — raport `.xlsx` i maile kontrahentów |
| `GDRIVE_FOLDER_ID` | tak (nd 09:00) | `1bRCAqle6BS46YEw0fScq4P095LsJUSgL` (folder Excela) |
| `GDRIVE_OAUTH_*` | tak (Excel + załączniki B2B) | OAuth upload `.xlsx` / pobranie oferty+prezentacji |
| `GDRIVE_SERVICE_ACCOUNT_JSON` | nie | Pełny sync Shared Drive (OFF) |

## Maile B2B (GHA cron ON)

GHA: **ON** — **nd Excel → pon 09:00 partia 1 → wt 09:00 partia 2** (tydzień *po* discovery; `FAS_GUARD_MODE=send_followup`).  
Lokalnie: domyślnie OFF (`DISABLE_CONTRACTOR_EMAILS=1`). Treść: `fas_spedycja_inquiry_email_pl.py`. Legacy DE: `archive/mfg_gu_inquiry_email_de.py`.

| Element | Źródło |
|---------|--------|
| Załączniki | [oferta](https://drive.google.com/file/d/1t6m-M49t4w0RuLzc8rWebwjldLUMMRW3/view?usp=drive_link) + [prezentacja](https://drive.google.com/file/d/164qbEQOTyO8VTgfZr2wtIVTY-zttk6u7/view?usp=drive_link) → `pl_fas_email_attachment.py` |
| Rollback | [`docs/ROLLBACK_B2B.md`](docs/ROLLBACK_B2B.md) |
| Cc | auto `svinchak1993@gmail.com` + opcjonalne `MAIL_CC` |

Testy załącznika / ścieżek:

```powershell
python -m pytest tests/unit/test_pl_fas_email_attachment.py tests/unit/test_pl_spedycja_data_paths.py -q
```


## Filtr ICP (`pl_spedycja_filter.py`)

Akceptuj: **polskie biuro spedycji / freight forwarding** z transportem drogowym (FTL/LTL/fracht).  
Odrzucaj: kurier, giełda frachtów, big 3PL, media, urzędy/praca, przeprowadzki.

### Model decyzji

```text
reject_reason?  →  OUT
portfolio_negates?  →  OUT
www / Excel:  ROLE ∧ (SEGMENT ∨ SERVICE)   = has_forwarding_signal
Serper:       ROLE ∨ SEGMENT ∨ SERVICE     (+ fraza wyszukiwania)
```

| Lista | Znaczenie |
|-------|-----------|
| `FORWARDER_ROLE_MARKERS` | rola: spedycja, spedytor, freight forwarding, … |
| `TRANSPORT_SEGMENT_MARKERS` | FTL, LTL, fracht, Europa, ADR, … |
| `TRANSPORT_SERVICE_MARKERS` | transport drogowy, organizacja przewozu, … |
| REJECT (kurier / giełda / media / …) | oś `reject_reason` |

Stare nazwy API (`is_generalunternehmer`, `is_valid_retail_store_builder_contact`, …) zostają jako **aliasy** — scraper nie wymaga rename.

Diagnostyka jednego kontaktu:

```powershell
python -c "from pl_spedycja_filter import debug_filter_decision; print(debug_filter_decision(email='biuro@firma.pl', url='https://firma.pl', name='Spedycja X', text='Firma spedycyjna FTL', search_term='spedycja FTL Warszawa'))"
```

Debug fraz Serper / geo (liczniki fal, sample, segmenty):

```powershell
python pl_spedycja_keywords.py Dolnoslaskie --max-terms 40 --sample 5
python pl_spedycja_keywords.py --land-key łódzkie
```

Testy (filtr / keywords / cookie / run_config):

```powershell
python -m pytest tests/unit/test_strict_gu_filter.py tests/test_strict_gu_filter.py tests/unit/test_retail_references.py tests/test_retail_context_loose.py -q
python -m pytest tests/unit/test_keywords_rotation_mail.py tests/unit/test_playwright_cookie_consent.py tests/unit/test_scraper_run_config.py -q
```

Szczegóły: [`docs/FILTER_ICP.md`](docs/FILTER_ICP.md)

## Prompty Claude (`claude_prompts.py`)

Verify / cleanup / contact / discovery / mail PL — ICP spedycji (FTL/LTL/ADR). Klucze JSON legacy (`is_gu`, `matched_chains`) bez zmian nazw. Moduł nie woła API.

```powershell
python claude_prompts.py
python claude_prompts.py --preview page_verify
python -m pytest tests/test_claude_prompts.py tests/test_claude_contact_extract.py tests/test_claude_page_text.py -q
```

Szczegóły: [`docs/CLAUDE_PROMPTS.md`](docs/CLAUDE_PROMPTS.md)

## Cookie consent (`playwright_cookie_consent.py`)

Po `requests`, gdy w HTML widać baner CMP (Borlabs / Cookiebot / OneTrust / …), scraper
odpala headless Chromium (`pl-PL`), klika **Akceptuj** i ponownie parsuje kontakty.
Bez CAPTCHA, bez map. Flaga: `ENABLE_PLAYWRIGHT_COOKIE_CONSENT`.

```powershell
pip install -r requirements.txt
playwright install chromium
python -m pytest tests/unit/test_playwright_cookie_consent.py -q
python playwright_cookie_consent.py --text "Akceptuj wszystkie cookies" --label "Akceptuj wszystkie"
```

Szczegóły: [`docs/COOKIE_CONSENT.md`](docs/COOKIE_CONSENT.md)

## Stan adaptacji PL (moduły)

Stan na kampanię **PL FAS / spedycja**. **Gotowe** = treść/ICP PL; **częściowo** = działa PL, ale nazwy DE/MFG, docstringi albo stare stringi; **brak** = nadal logika/treść DE albo brak zamiennika PL.

### Gotowe

| Moduł | Uwagi |
|-------|--------|
| `pl_fas_spedycja_scraper.py` | Orchestrator PL (Serper `pl`, ICP, FAS draft, geo PL) |
| `de_gu_bauunternehmen_scraper.py` | Tylko shim → `pl_fas_spedycja_scraper` |
| `pl_spedycja_keywords.py` | Frazy/geo PL; symbole `BUNDESLAND_*` / `RETAIL_*` = aliasy |
| `pl_spedycja_filter.py` | ICP spedycji FTL/LTL; legacy nazwy fn mapują na PL |
| `pl_spedycja_data_paths.py` | `Wyniki/pl_spedycja_*` lokalnie; Drive tylko Excel/załącznik |
| `campaign_data_paths.py` | Shim → `pl_spedycja_data_paths` |
| `campaign_keyword_profile.py` | Sample PL z filter/keywords |
| `run_config/pl_fas_spedycja.json` (+ `polska_alle`, `wojewodztwo_*`, `welle_*`) | 16 woj., `lang=pl` |
| `fas_spedycja_inquiry_email_pl.py` | Outreach FAS (HITL, podpis PL) |
| `claude_prompts.py` | Prompty PL FAS; klucze JSON `is_gu` / `matched_chains` legacy |
| `claude_page_text.py` | URL tiers + evidence PL |
| `claude_row_cleanup.py` | Aliasy `wojewodztwo` / `segmenty` |
| `playwright_cookie_consent.py` | CMP PL / `pl-PL` |
| `website_full_crawl.py` | Crawl agnostyczny (komentarze PL) |
| `scraper_run_config.py` / `scraper_schedule_config.py` / `scraper_runtime_limit.py` | Config PL / okno wysyłki / limit |
| `gu_bundesland_rotation.py` | Kolejność 16 województw (nazwa pliku legacy) |
| `libs/email_custom_template.py` | Domyślnie `pl` → FAS |
| Docs: `FILTER_ICP`, `CLAUDE_PROMPTS`, `COOKIE_CONSENT`, `GITHUB_ACTIONS`, `ROLLBACK_B2B` | Opis PL FAS |
| Testy PL: `test_pl_fas_spedycja_scraper`, `test_fas_*`, `test_strict_gu_filter`, `test_claude_*` (reject DE GU) | ICP PL |
| `pl_fas_email_attachment.py` | **2** załączniki B2B (oferta `1t6m…` + prezentacja `164qb…`); shimy `fas_*` / `mfg_gu_*` |
| `scripts/export_fas_email_attachment.py` | Eksport obu PPTX z Drive; shim `export_mfg_slides_*` |

### Częściowo

| Moduł | Co jeszcze DE / legacy |
|-------|-------------------------|
| `page_verify.py` / `claude_page_verify.py` | Semantyka PL; kody reject PL (`brak_segmentu_ftl_ltl` …); aliasy DE w `LEGACY_REJECT_REASON_ALIASES` |
| `claude_discovery_terms.py` | Walidacja PL; fallback land = **`Polska`** (`DEFAULT_DISCOVERY_LAND`) |
| `claude_contact_extract.py` | **Gotowe** — docstringi/logi PL FAS; klucz legacy `impressum_emails` = Kontakt/Dane firmy/RODO |
| `commercial_contact_filter.py` | **Gotowe** — listy PL + DE higiena; soft-pass spedycja; geo z `BUNDESLAND_CONFIG`; docstringi PL FAS |
| `email_targeting.py` | **Gotowe** — score/localy PL FAS; aggregatory PL; fold PL diacritics; DE higiena |
| `pl_fas_mail_recipients.py` | **Gotowe** — auto-Cc `svinchak1993@gmail.com`; MFG office **odpięte**; + opcjonalne `MAIL_CC` |
| `pl_fas_contractor_exclusions.py` | **Gotowe** (rename) — bloklista; shim `de_contractor_exclusions`; treść DE/MFG = higiena |
| `scraper_web_config.py` | **Gotowe** — flagi + docstring PL FAS (discovery default OFF; run_config może ON) |
| `scripts/send_excel_gmail.py` (+ test) | **Gotowe** — temat/treść **PL FAS Kontakte**; ścieżki `pl_spedycja_*` |
| `pl_spedycja_data_paths` → `GOOGLE_DRIVE_FAS_*` | **Gotowe** — kanoniczne FAS; aliasy `GOOGLE_DRIVE_GU_*` |
| `schedule/*.ps1` | **Gotowe** — logi PL; `Spedycja_FAS_*`; `Enter-FasCampaign`; Warsaw; unregister `Kanbud_GU_*` |
| `.github/workflows/pl_fas_*.yml` | **Gotowe** — rename; B2B cron + `send_followup`; action `pl_fas_gha_window_guard`; concurrency `gu-pipeline` |
| Schema Excel/cache (`is_gu`, `handelsketten`, `bundesland`) | **Zostaw** — Excel PL; klucze JSON legacy celowo |
| `docs/LOCAL_VS_GHA.md`, `docs/GOOGLE_DRIVE.md` | **Gotowe** — PL FAS + B2B/załączniki |

### Brak (albo nieużywane DE)

| Moduł / luka | Status |
|--------------|--------|
| `archive/mfg_gu_inquiry_email_de.py` | Czysty MFG DE — **archiwum**; scraper nie importuje |
| Zamiennik PL dla `mfg_mail_recipients` | **Gotowe** — `pl_fas_mail_recipients`; Cc = `svinchak1993@gmail.com` |
| Zamiennik PL dla `de_contractor_exclusions` | **Gotowe** — `pl_fas_contractor_exclusions` (+ shim) |
| Rebrand `send_excel_gmail` (temat/treść PL FAS) | **Gotowe** |
| Rename workflowów `de_gu_*` / `gu-*` → `pl_fas_*` | **Gotowe** (pliki + action); concurrency `gu-pipeline` osobno |
| Domyślny land discovery → `Polska` w `claude_discovery_terms` | **Gotowe** (`DEFAULT_DISCOVERY_LAND`) |
| Włączenie wysyłki B2B (GHA `send_followup`) | **Gotowe** — pon/wt 09:00 po Excelu; lokalnie default OFF |
| Druga prezentacja B2B (`164qbEQO…`) | **Gotowe** — `EMAIL_ATTACHMENT_EXTRA_*` / `FAS_prezentacja.pptx` |

## Struktura repo

```
├── pl_fas_spedycja_scraper.py   # orchestrator PL FAS
├── pl_spedycja_filter.py / pl_spedycja_keywords.py
├── pl_spedycja_data_paths.py            # lokalne Wyniki/ + ID folderu Excela
├── fas_spedycja_inquiry_email_pl.py  # outreach FAS (Claude, ludzki ton)
├── pl_fas_email_attachment.py          # załączniki B2B: oferta + prezentacja
├── archive/mfg_gu_inquiry_email_de.py  # archiwum MFG DE
├── playwright_cookie_consent.py
├── scraper_run_config.py / scraper_runtime_limit.py / scraper_schedule_config.py
├── run_config/pl_fas_spedycja.json   # 16 woj. (1. = Dolnoslaskie)
├── Wyniki/                           # cache/log lokalnie (.gitignore)
├── tests/unit/                       # filtr, keywords, cookie, paths, attachment…
└── docs/                             # FILTER_ICP, CLAUDE_PROMPTS, COOKIE_CONSENT, …
```

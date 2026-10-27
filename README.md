# Wyszukiwarka partnerów — kampania GU (bundesweit)

Repozytorium: [Bigmax1993/Wyszukiwarka-partnerow](https://github.com/Bigmax1993/Wyszukiwarka-partnerow)

Pipeline: **Serper → strony www → cache/Excel** (tryb **discovery-only**).

- Maile B2B do kontrahentów: **wyłączone** (`DISABLE_CONTRACTOR_EMAILS=1`)
- Pełny sync Drive (cache/logi): **wyłączony**
- Raport Excel: Gmail + **upload końcowego `.xlsx` na Drive** (nd 09:00 w tygodniu cyklu)

**Produkcja (GHA/PC):** `run_config/mfg_gu_de.json` — **wszystkie 16 Bundesländer**, discovery w 5 częściach (pon–pt) z `--respect-cache`.  
**Opcja ręczna:** `--rotate-bundesland` — jeden land na cykl (nie używane w GHA).

Cadence **GHA:** co **6 tygodni** (42 dni) od **2026-09-21**. Task Scheduler na **PC** rejestruje zadania **co tydzień** (bez guarda 42 dni). Szczegóły: [`docs/GITHUB_ACTIONS.md`](docs/GITHUB_ACTIONS.md), [`docs/LOCAL_VS_GHA.md`](docs/LOCAL_VS_GHA.md).

| Moduł | Plik |
|-------|------|
| Scraper | `de_gu_bauunternehmen_scraper.py` |
| Frazy per Bundesland | `de_gu_keywords.py` |
| Config kampanii (16 landów) | `run_config/mfg_gu_de.json` |
| Rotacja 1 land (opcjonalna) | `gu_bundesland_rotation.py` |
| Treść maila DE | `mfg_gu_inquiry_email_de.py` |
| Załącznik PPTX | `mfg_gu_email_attachment.py` |

## Szybki start (lokalnie)

```powershell
git clone https://github.com/Bigmax1993/Wyszukiwarka-partnerow.git
cd Wyszukiwarka-partnerow
pip install -r requirements.txt
$env:KANBUD_PROJECT_ROOT = "$PWD\libs"
python de_gu_bauunternehmen_scraper.py --test
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
| API live | `tests/integration/test_api_keys.py` | `-m api_live` |

Raport Excel (Gmail, **wewnętrzny**, nie B2B): `svinchak1993@gmail.com`
(`EXCEL_REPORT_TO`, `DISABLE_EXCEL_REPORT_EMAIL=0`).
Workflow `GU poniedzialek excel email` — **niedziela 09:00** → Gmail **+ Drive (tylko xlsx)**.
Lokalnie: `python scripts/send_excel_gmail.py` / `--dry-run`.

## Wyniki

| Plik / folder | Opis |
|---------------|------|
| `Wyniki/de_gu_bauunternehmen_cache.json` | Cache Serper + kontakty (kumulacja tygodniowa) |
| `Wyniki/de_gu_bauunternehmen_kontakte.xlsx` | Excel — **append**; arkusz **Info** opisuje zasady zapisu |
| `Wyniki/de_gu_bauunternehmen_scraper.log` | Log |
| `Wyniki/de_gu_bundeslaender_rotation.json` | Stan rotacji 1-land (tylko przy `--rotate-bundesland`) |
| `wyslane/` | Kopie wysłanych maili (.eml) — puste przy B2B OFF |

**Google Drive:**

- Pełny sync OFF (`DISABLE_GOOGLE_DRIVE=1`)
- Końcowy Excel ON (nd 09:00, tydzień cyklu GHA) → folder z secretu `GDRIVE_FOLDER_ID`
- Folder GU (pełny sync / lokalnie): [GU Bauunternehmen](https://drive.google.com/drive/folders/1tP8oUi72t4EHDbE9GnHFdvfNtNsJe4xf)

Szczegóły: [`docs/GOOGLE_DRIVE.md`](docs/GOOGLE_DRIVE.md)

## Uruchomienie scrapera

```powershell
$env:KANBUD_PROJECT_ROOT = "$PWD\libs"

python de_gu_bauunternehmen_scraper.py --test

# Jak produkcja GHA/PC (16 landów, discovery):
python de_gu_bauunternehmen_scraper.py --run-config run_config\mfg_gu_de.json --serper-only-discovery

python de_gu_bauunternehmen_scraper.py --backfill-emails-from-cache
python de_gu_bauunternehmen_scraper.py --rebuild-from-cache

# Wysyłka B2B: NO-OP przy DISABLE_CONTRACTOR_EMAILS=1 (domyślnie)
python de_gu_bauunternehmen_scraper.py --send-emails-only

# Podgląd treści bez SMTP:
python de_gu_bauunternehmen_scraper.py --dry-run-email --send-emails-only
```

### Produkcja: bundesweit (domyślnie w GHA)

GHA i skrypty `schedule/run_*_discovery.ps1` używają:

```powershell
python de_gu_bauunternehmen_scraper.py --run-config run_config\mfg_gu_de.json --serper-only-discovery
```

Config ma **16** `active_bundeslaender`. Tydzień discovery dzieli się na 5 części (pon–pt) z kontynuacją cache (`--respect-cache` w GHA).

### Opcja: rotacja 1 Bundesland / cykl

```powershell
python de_gu_bauunternehmen_scraper.py --rotate-bundesland
python de_gu_bauunternehmen_scraper.py --rotation-status
```

Kolejność 16 landów: NRW → Bayern → BW → Niedersachsen → Hessen → Sachsen → … (`gu_bundesland_rotation.py`). **Nie** jest używana w produkcyjnych workflowach GHA.

### Ręcznie wybrana lista landów

```powershell
python de_gu_bauunternehmen_scraper.py --bundesland NRW,BY,BW
python de_gu_bauunternehmen_scraper.py --run-config run_config\welle_nrw_by_bw.json
```

## Limity

| Limit | Wartość |
|-------|---------|
| Serper | **1000** zapytań / dzień (`SERPER_DAILY_LIMIT`; też w `mfg_gu_de.json`) |
| E-mail B2B | **wyłączone** (`DISABLE_CONTRACTOR_EMAILS=1`); limity 300/dzień dotyczyły trybu send |
| Discovery bundesweit | 16 landów w 5 dniach (pon–pt), cache między dniami |

## Harmonogram

**GHA:** co **6 tygodni** od **21.09.2026** (guard 42 dni).  
**PC (Task Scheduler):** te same godziny **co tydzień** — bez guarda. Excel + Drive tylko na GHA.

Szczegóły: [`docs/GITHUB_ACTIONS.md`](docs/GITHUB_ACTIONS.md), [`schedule/PLAN_5_DNI.md`](schedule/PLAN_5_DNI.md), [`docs/LOCAL_VS_GHA.md`](docs/LOCAL_VS_GHA.md).

| Dzień | Godzina (PL) | PC | GitHub Actions |
|-------|--------------|-----|----------------|
| **Poniedziałek** | **18:00** | `run_poniedzialek_discovery.ps1` | `GU discovery` (część 1) |
| **Wtorek** | **18:00** | `run_wtorek_discovery.ps1` | `GU discovery` (część 2) |
| **Środa** | **18:00** | `run_sroda_discovery.ps1` | `GU discovery` (część 3) |
| **Czwartek** | **18:00** | `run_czwartek_discovery.ps1` | `GU discovery` (część 4) |
| **Piątek** | **18:00** | `run_piatek_discovery.ps1` | `GU discovery` (część 5) → **chain** backfill |
| **Niedziela** | **06:00** | `run_czwartek.ps1` (legacy nazwa = backfill) | `GU niedziela backfill` (cron + fallback) |
| **Niedziela** | **09:00** | — | `GU poniedzialek excel email` → Gmail + Drive xlsx |
| Prep / pełny Drive / send B2B | — | — | **OFF** |

Po udanym discovery w **piątek** GHA odpala `GU niedziela backfill` od razu (`workflow_dispatch`). Cron nd 06:00 to zapasowy / restart.

Task Scheduler:

```powershell
powershell -ExecutionPolicy Bypass -File schedule\register_tasks_5_dni.ps1
```

Pełny pipeline na GitHub Actions (ręcznie, discovery-only — bez B2B / bez pełnego Drive):

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
| `MAIL_USER`, `MAIL_PASSWORD` | tak (raport Excel) | SMTP — `.xlsx` na `svinchak1993@gmail.com` |
| `GDRIVE_FOLDER_ID` | tak (nd 09:00 Drive) | Folder końcowego Excela |
| `GDRIVE_OAUTH_*` | tak (nd 09:00 Drive) | OAuth upload końcowego `.xlsx` |
| `GDRIVE_SERVICE_ACCOUNT_JSON` | nie | Pełny sync Shared Drive (obecnie OFF) |

## Maile MFG (wyłączone)

Kod treści/załącznika zostaje w repo (łatwy rollback), ale **SMTP do kontrahentów jest OFF**.

- Treść (gdy włączysz maile): `mfg_gu_inquiry_email_de.py` (tylko niemiecki)
- Załącznik lokalny: `assets/campaign/MFG_Referenzliste_Einzelhandel.pptx`
- Checklist rollback: [`docs/ROLLBACK_B2B.md`](docs/ROLLBACK_B2B.md)
- Kill-switch: `DISABLE_CONTRACTOR_EMAILS=0` + usuń `if: false` z jobów send (`de_gu_tue.yml`, `de_gu_fri.yml`); ewentualnie dodaj cron/chain (obecnie tylko `workflow_dispatch`)
- Cc: tylko z `MAIL_CC` w `.env` — **bez** automatycznego `office@mfg-fliesen.de`

## Struktura repo

```
├── de_gu_bauunternehmen_scraper.py
├── gu_bundesland_rotation.py      # opcjonalna rotacja 1 land
├── claude_*.py / campaign_*.py
├── libs/                          # scraper_env, polish_text, …
├── run_config/mfg_gu_de.json      # produkcja: 16 landów
├── schedule/                      # PLAN_5_DNI.md, register_tasks_5_dni.ps1
├── assets/campaign/               # PPTX na runnerze GitHub
├── scripts/                       # gdrive_*, RUN_ALL_TESTS, pipeline GHA
├── tests/
├── .github/workflows/
├── .github/actions/gu-gha-window-guard/   # cadence 42 dni
└── docs/                          # GITHUB_ACTIONS, GOOGLE_DRIVE, LOCAL_VS_GHA, ROLLBACK_B2B
```

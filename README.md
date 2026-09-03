# Wyszukiwarka partnerów — kampania GU (bundesweit)



Repozytorium: [Bigmax1993/Wyszukiwarka-partnerow](https://github.com/Bigmax1993/Wyszukiwarka-partnerow) (private)



Pipeline: **Serper → strony www → cache/Excel** (tryb **discovery-only**).
Maile B2B do kontrahentów i Google Drive są **wyłączone** (`DISABLE_CONTRACTOR_EMAILS=1`, `DISABLE_GOOGLE_DRIVE=1`).
Rollback: ustaw obie flagi na `0` i włącz ponownie workflowy send/Drive.



| Moduł | Plik |

|-------|------|

| Scraper | `de_gu_bauunternehmen_scraper.py` |

| Frazy per Bundesland | `de_gu_keywords.py` |

| Rotacja landów | `gu_bundesland_rotation.py` |

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

Raport Excel (Gmail, **wewnętrzny**, nie B2B): jeden odbiorca `svinchak1993@gmail.com`
(`EXCEL_REPORT_TO`, `DISABLE_EXCEL_REPORT_EMAIL=0`).
Workflow `GU poniedzialek excel email` — **niedziela 09:00** (po backfillu 06:00).
Lokalnie: `python scripts/send_excel_gmail.py` / `--dry-run`.



## Wyniki



| Plik / folder | Opis |

|---------------|------|

| `Wyniki/de_gu_bauunternehmen_cache.json` | Cache Serper + kontakty (kumulacja tygodniowa) |

| `Wyniki/de_gu_bauunternehmen_kontakte.xlsx` | Excel — **append** (dopisywanie); arkusz **Info** opisuje zasady zapisu |

| `Wyniki/de_gu_bauunternehmen_scraper.log` | Log |

| `Wyniki/de_gu_bundeslaender_rotation.json` | Stan rotacji Bundesland |

| `wyslane/` | Kopie wysłanych maili (.eml) |



**Google Drive:** **OFF** by default (`DISABLE_GOOGLE_DRIVE=1`) — wyniki tylko w `Wyniki/` / artefaktach GHA.
Opcjonalnie: [folder GU](https://drive.google.com/drive/folders/1tP8oUi72t4EHDbE9GnHFdvfNtNsJe4xf) — [`docs/GOOGLE_DRIVE.md`](docs/GOOGLE_DRIVE.md)



## Uruchomienie scrapera



```powershell

$env:KANBUD_PROJECT_ROOT = "$PWD\libs"



python de_gu_bauunternehmen_scraper.py --test

python de_gu_bauunternehmen_scraper.py --rotate-bundesland

python de_gu_bauunternehmen_scraper.py --rotation-status

python de_gu_bauunternehmen_scraper.py --backfill-emails-from-cache

python de_gu_bauunternehmen_scraper.py --rebuild-from-cache

# Wysyłka B2B: NO-OP przy DISABLE_CONTRACTOR_EMAILS=1 (domyślnie)
python de_gu_bauunternehmen_scraper.py --send-emails-only

# Podgląd treści bez SMTP:
python de_gu_bauunternehmen_scraper.py --dry-run-email --send-emails-only

```



### Rotacja Bundesland (domyślnie — 1 land / piątek)



```powershell

python de_gu_bauunternehmen_scraper.py --rotate-bundesland

```



Kolejność 16 landów: NRW → Bayern → BW → Niedersachsen → Hessen → Sachsen → … (cykl w `gu_bundesland_rotation.py`).



### Ręcznie wiele landów



```powershell

python de_gu_bauunternehmen_scraper.py --bundesland NRW,BY,BW

python de_gu_bauunternehmen_scraper.py --run-config run_config\welle_nrw_by_bw.json

```



## Limity



| Limit | Wartość |

|-------|---------|

| Serper | 1500 zapytań / dzień |

| E-mail B2B | **wyłączone** (`DISABLE_CONTRACTOR_EMAILS=1`); limity 300/dzień dotyczyły trybu send |

| 1 Bundesland / tydzień | ~40–60 fraz Serper × 5 dni discovery |



## Harmonogram tygodnia



Szczegóły: [`schedule/PLAN_5_DNI.md`](schedule/PLAN_5_DNI.md)



| Dzień | Godzina (PL) | PC | GitHub Actions |

|-------|--------------|-----|----------------|

| **Poniedziałek** | **18:00** | `run_poniedzialek_discovery.ps1` | `GU discovery` (część 1) |
| **Wtorek** | **18:00** | `run_wtorek_discovery.ps1` | `GU discovery` (część 2) |
| **Środa** | **18:00** | `run_sroda_discovery.ps1` | `GU discovery` (część 3) |
| **Czwartek** | **18:00** | `run_czwartek_discovery.ps1` | `GU discovery` (część 4) |
| **Piątek** | **18:00** | `run_piatek_discovery.ps1` | `GU discovery` (część 5) |

| **Niedziela** | **06:00** | `run_czwartek.ps1` | `GU niedziela backfill` |

| **Niedziela** | **09:00** | — | `GU poniedzialek excel email` → `svinchak1993@gmail.com` |

| Prep / Drive / send B2B | — | — | **OFF** |



Task Scheduler:



```powershell

powershell -ExecutionPolicy Bypass -File schedule\register_tasks_5_dni.ps1

```



Pełny pipeline na GitHub Actions (ręcznie, **discovery-only** — bez Drive / bez send):

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

| `CLAUDE_MODEL_FAST` | opcjonalny | Haiku — frazy Serper, cleanup Excel (domyślnie `claude-haiku-4-5`) |

| `CLAUDE_MODEL_VERIFY` | opcjonalny | Sonnet — weryfikacja www, maile z HTML (domyślnie `claude-sonnet-4-6`) |

| `MAIL_USER`, `MAIL_PASSWORD` | tak (raport Excel) | SMTP — końcowy `.xlsx` na `svinchak1993@gmail.com` |

| `GDRIVE_OAUTH_*` | nie (Drive OFF) | Upload na „Mój dysk” — tylko po `DISABLE_GOOGLE_DRIVE=0` |

| `GDRIVE_SERVICE_ACCOUNT_JSON` | nie (Drive OFF) | Konto usługi (Shared Drive) |



## Maile MFG (wyłączone)

Kod treści/załącznika zostaje w repo (łatwy rollback), ale **SMTP do kontrahentów jest OFF**.

- Treść (gdy włączysz maile): `mfg_gu_inquiry_email_de.py` (tylko niemiecki)
- Załącznik lokalny: `assets/campaign/MFG_Referenzliste_Einzelhandel.pptx` (bez pobierania ze Slides/Drive przy `DISABLE_GOOGLE_DRIVE=1`)
- Kill-switch: `DISABLE_CONTRACTOR_EMAILS=0` + włącz workflowy send (usuń `if: false`)
- Cc: tylko z `MAIL_CC` w `.env` — **bez** automatycznego `office@mfg-fliesen.de`



## Struktura repo



```

├── de_gu_bauunternehmen_scraper.py

├── gu_bundesland_rotation.py

├── libs/

├── schedule/           # PLAN_5_DNI.md, register_tasks_5_dni.ps1

├── run_config/

├── assets/campaign/    # PPTX na runnerze GitHub

├── scripts/            # gdrive_*, run_full_pipeline_gha.ps1, RUN_ALL_TESTS.ps1

├── .github/workflows/

└── docs/

```



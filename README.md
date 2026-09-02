# Wyszukiwarka partnerów — kampania GU (bundesweit)

Repozytorium: [Bigmax1993/Wyszukiwarka-partnerow](https://github.com/Bigmax1993/Wyszukiwarka-partnerow) (private)

Pipeline: **Serper → strony www → cache/Excel** (Generalunternehmer / Filialbau DE).

Automatyczny pipeline kończy się na pliku Excel w `Wyniki/`; **w poniedziałek o 04:30** Excel jest wysyłany na Gmail (`svinchak1993@gmail.com`). Bez sync Google Drive i bez kampanii MFG.

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

Pełna bateria testów (jednostkowe, integracyjne, regresyjne, API live):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\RUN_ALL_TESTS.ps1
```

| Typ | Folder / plik | Marker pytest |
|-----|---------------|---------------|
| Jednostkowe | `tests/unit/` | `-m unit` |
| Integracyjne | `tests/integration/` | `-m integration` |
| Regresyjne | `tests/test_gu_discovery_regression.py`, `test_excel_append.py` | unittest |
| API live | `tests/integration/test_api_keys.py` | `-m api_live` |

## Wyniki

| Plik / folder | Opis |
|---------------|------|
| `Wyniki/de_gu_bauunternehmen_cache.json` | Cache Serper + kontakty (kumulacja tygodniowa) |
| `Wyniki/de_gu_bauunternehmen_kontakte.xlsx` | Excel — **append** (dopisywanie + aktualizacja po URL/e-mail; bez pełnej przebudowy) |
| `Wyniki/de_gu_bauunternehmen_scraper.log` | Log |
| `Wyniki/de_gu_bundeslaender_rotation.json` | Stan rotacji Bundesland |

Wyniki lokalnie w folderze `Wyniki/` (bez automatycznego uploadu na Drive).

## Uruchomienie scrapera

```powershell
$env:KANBUD_PROJECT_ROOT = "$PWD\libs"

python de_gu_bauunternehmen_scraper.py --test
python de_gu_bauunternehmen_scraper.py --rotate-bundesland
python de_gu_bauunternehmen_scraper.py --rotation-status
python de_gu_bauunternehmen_scraper.py --backfill-emails-from-cache
python de_gu_bauunternehmen_scraper.py --rebuild-from-cache
```

Ręcznie (poza automatycznym pipeline):

```powershell
python de_gu_bauunternehmen_scraper.py --send-emails-only
python de_gu_bauunternehmen_scraper.py --dry-run-email --send-emails-only
python scripts/gdrive_upload_wyniki.py --campaign-dir .
```

### Rotacja Bundesland (domyślnie — 1 land / sobota)

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
| Serper | 300 zapytań / dzień |
| 1 Bundesland / tydzień | ~40–60 fraz Serper (mieści się w 1 sobotę) |

## Harmonogram (3 dni)

Szczegóły: [`schedule/PLAN_5_DNI.md`](schedule/PLAN_5_DNI.md)

| Dzień | Godzina (PL) | PC | GitHub Actions |
|-------|--------------|-----|----------------|
| **Sobota** | 20:10 | `run_sroda.ps1` | `GU sobota discovery` |
| **Niedziela** | 06:00 | `run_czwartek.ps1` | `GU niedziela backfill` |
| **Poniedziałek** | **04:30** | `run_poniedzialek_excel_email.ps1` | `GU poniedzialek excel email` |
| **Poniedziałek** | 08:00 | `run_poniedzialek_prep.ps1` | `GU poniedzialek prep` |

Task Scheduler:

```powershell
scripts\register_gu_weekly_tasks.cmd
```

(lub ręcznie: `run_sroda.ps1` → `run_czwartek.ps1` → `run_poniedzialek_prep.ps1`)

Pełny pipeline na GitHub Actions (ręcznie — symuluje harmonogram tygodniowy):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_full_pipeline_gha.ps1
```

Kroki: discovery → backfill → excel email (Gmail) → prep.

## GitHub Actions

[`docs/GITHUB_ACTIONS.md`](docs/GITHUB_ACTIONS.md)

| Secret | Wymagany | Opis |
|--------|----------|------|
| `SERPER_API_KEY` | tak (discovery) | API Serper |
| `ANTHROPIC_API_KEY` | tak (verify/backfill) | Claude API |
| `MAIL_USER`, `MAIL_PASSWORD` | tak (pon 04:30 Excel) | Gmail + hasło aplikacji |
| `EXCEL_REPORT_TO` | opcjonalny | Domyślnie `svinchak1993@gmail.com` |
| `GDRIVE_OAUTH_*` | tylko ręczny sync | Google Drive |

## Raport Excel (Gmail, poniedziałek 04:30)

Skrypt `scripts/send_excel_gmail.py` wysyła `de_gu_bauunternehmen_kontakte.xlsx` na Gmail (yagmail).

```powershell
python scripts/send_excel_gmail.py
python scripts/send_excel_gmail.py --dry-run
```

W `.env`: `MAIL_USER` = konto Gmail nadawcy, `MAIL_PASSWORD` = [hasło aplikacji Google](https://myaccount.google.com/apppasswords).

## Struktura repo

```
├── de_gu_bauunternehmen_scraper.py
├── gu_bundesland_rotation.py
├── libs/
├── schedule/           # PLAN_5_DNI.md, run_*.ps1
├── tests/              # unit/, integration/, regresja
├── run_config/
├── assets/campaign/    # PPTX na runnerze GitHub
├── scripts/            # send_excel_gmail.py, run_full_pipeline_gha.ps1, RUN_ALL_TESTS.ps1
├── .github/workflows/
└── docs/
```


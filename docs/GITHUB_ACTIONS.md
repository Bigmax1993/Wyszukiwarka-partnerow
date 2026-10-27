# GitHub Actions — kampania GU (MFG / Filialbau)

Repozytorium: [Wyszukiwarka-partnerow](https://github.com/Bigmax1993/Wyszukiwarka-partnerow)

Crony używają `timezone: Europe/Warsaw` — godziny w YAML to **czas polski**.  
Gałąź CI: **`master`** (`tests.yml`, `ci-deploy.yml`).

## Tryb discovery-only (aktualny)

Pipeline na GHA zbiera firmy (Serper + Claude), buduje Excel w artefaktach i w niedzielę cyklu:
1. wysyła **raport Excel** na `svinchak1993@gmail.com`
2. uploaduje **tylko końcowy `.xlsx`** na Google Drive (`secrets.GDRIVE_FOLDER_ID`)

**Nie wysyła maili B2B** do kontrahentów. **Pełny sync** `Wyniki/` (cache/logi/`wyslane`) jest **DISABLED**.

Discovery używa `run_config/mfg_gu_de.json` (**16 Bundesländer**, bundesweit) — **bez** `--rotate-bundesland`. Artefakt discovery zawsze: `de-gu-wyniki-pi`.

| Flaga / mechanizm | Domyślnie | Efekt |
|-------------------|-----------|--------|
| `DISABLE_CONTRACTOR_EMAILS` | `1` | `--send-emails-only` = NO-OP |
| `DISABLE_GOOGLE_DRIVE` | `1` (workflow-level) | pełny sync OFF; krok Excel→Drive ustawia lokalnie `0` |
| `DISABLE_EXCEL_REPORT_EMAIL` | `0` | raport Excel na Gmail **WŁĄCZONY** |
| workflow `if: false` | send B2B + pełny Drive sync | te joby nie startują |

Rollback B2B: [`ROLLBACK_B2B.md`](ROLLBACK_B2B.md).  
PC vs GHA: [`LOCAL_VS_GHA.md`](LOCAL_VS_GHA.md).  
Drive: [`GOOGLE_DRIVE.md`](GOOGLE_DRIVE.md). Plan: [`../schedule/PLAN_5_DNI.md`](../schedule/PLAN_5_DNI.md).

## Workflowy

| Workflow | Plik | Trigger | Status | Co robi |
|----------|------|---------|--------|---------|
| **Tests** | `tests.yml` | push/PR → `master` | **aktywny** | pytest unit + integracja + regresja + API live |
| **CI Deploy** | `ci-deploy.yml` | push → `master` | **aktywny** | smoke + walidacja secretów |
| **GU discovery** | `de_gu_pi.yml` | cron pon–pt 18:00 + guard co 6 tyg., ręcznie | **aktywny** | Discovery bundesweit → `de-gu-wyniki-pi` |
| **GU niedziela backfill** | `de_gu_thu.yml` | cron nd 06:00 + guard, chain z pt, ręcznie | **aktywny** | Backfill + Excel → `de-gu-wyniki-thu` |
| **GU poniedzialek prep** | `de_gu_mon.yml` | tylko ręcznie | **cron OFF** | Awaryjny rebuild Excel |
| **GU poniedzialek excel email** | `de_gu_mon_excel_email.yml` | cron nd 09:00 + guard, ręcznie | **aktywny** | Excel → Gmail **+ Drive (tylko `.xlsx`)** |
| **GU poniedzialek send** | `de_gu_tue.yml` | tylko `workflow_dispatch` | **DISABLED** (`if: false`) | Wysyłka B2B partia 1 |
| **GU wtorek send** | `de_gu_fri.yml` | tylko `workflow_dispatch` | **DISABLED** (`if: false`) | Wysyłka B2B partia 2 |
| **Sync wyniki Google Drive** | `sync-google-drive.yml` | tylko `workflow_dispatch` | **DISABLED** | Pełny upload `Wyniki/` |
| **Sync tygodnia discovery na Drive** | `sync-week-discovery-drive.yml` | tylko `workflow_dispatch` | **DISABLED** | Jeden Excel tygodnia na Drive |
| **GU tydzien backfill i wysylka** | `week-backfill-and-send.yml` | ręcznie | **częściowo** | Backfill/Excel OK; kroki send = `if: false` (ops / historyczny) |

Nazwy plików YAML (`*_tue`, `*_fri`, `*_thu`) są legacy — liczy się **display name**.

### Ręczne / ops

| Workflow | Plik | Trigger | Uwagi |
|----------|------|---------|--------|
| GU catch-up | `gu-catch-up.yml` | ręcznie | Wąski scope (`discovery-tue`); pełny catch-up: `gh workflow run "GU discovery" -f discovery_phase=…` |
| Excel 7 firm z pi | `excel-seven-from-pi.yml` | ręcznie | Ops |
| GU reset pipeline cache | `de_gu_reset_cache.yml` | ręcznie | Ops |
| GU reprocess cache bez Serper | `de_gu_reprocess_no_serper.yml` | ręcznie | Upload Drive → folder GU `1tP8oUi…` (nie `GDRIVE_FOLDER_ID`); wymaga `DISABLE_GOOGLE_DRIVE=0` w kroku, inaczej NO-OP |
| GU discovery wtorek (jednorazowo 2026-07-01) | `gu-discovery-tue-once-2026-07-01.yml` | jednorazowy cron | Po dacie = skip; można zarchiwizować |

## Harmonogram cron (Europe/Warsaw) — aktywne

Cron w YAML jest tygodniowy, ale **guard** (`.github/actions/gu-gha-window-guard`) odpala joby **co 6 tygodni**:

| Parametr | Wartość |
|----------|---------|
| Anchor (poniedziałek) | `2026-09-21` (`GU_CADENCE_ANCHOR`) |
| Okres | **42 dni** (`GU_CADENCE_DAYS`, domyślnie 42) |
| Kolejne poniedziałki | `2026-09-21`, `2026-11-02`, `2026-12-14`, `2027-01-25`, … |
| Aktywne dni cyklu | pon–pt (discovery) + **niedziela** (backfill + excel) |
| Sobota | nieaktywna |
| `workflow_dispatch` | zawsze `active=true` (omija guard dnia tygodnia) |

| Dzień | Workflow | Cron | Godzina PL |
|-------|----------|------|------------|
| **Poniedziałek** | discovery | `0 18 * * 1` | **18:00** |
| **Wtorek** | discovery | `0 18 * * 2` | **18:00** |
| **Środa** | discovery | `0 18 * * 3` | **18:00** |
| **Czwartek** | discovery | `0 18 * * 4` | **18:00** |
| **Piątek** | discovery | `0 18 * * 5` | **18:00** |
| **Niedziela** | backfill | `0 6 * * 0` | **06:00** |
| **Niedziela** | excel email + Drive xlsx | `0 9 * * 0` | **09:00** |

Wyłączone z crona: prep, pełny sync Drive, send B2B (tylko `workflow_dispatch` + `if: false` na jobach send).

Limit Serper w GHA: `SERPER_DAILY_LIMIT=1000` (domyślnie w kodzie też 1000).

## Łańcuchy (auto `workflow_dispatch`)

| Po sukcesie | Uruchamia | Efekt dziś |
|-------------|-----------|------------|
| Discovery **piątek** | `GU niedziela backfill` (`artifact_run_id` = bieżący run) | **działa od razu** (dispatch omija guard dnia; w tygodniu poza cyklem cron nd i tak jest skip) |
| Discovery **pon–czw** | `GU wtorek send` | **no-op** (`if: false` na send) |
| Backfill (cron nd 06:00) | — | zapasowy / restart, jeśli chain z pt nie wystarczy |
| Backfill → Sync Drive | Sync Drive | step wyłączony |
| Prep → send | send | step wyłączony |

Typowy przebieg w tygodniu cyklu:

```
pt discovery → (chain) backfill → nd 09:00 Excel+Drive
(+ opcjonalnie nd 06:00 cron jako fallback backfill)
```

## Sekrety

| Secret | Wymagany teraz | Opis |
|--------|----------------|------|
| `SERPER_API_KEY` | tak (discovery) | API Serper |
| `ANTHROPIC_API_KEY` | tak (discovery + backfill) | Claude API |
| `MAIL_USER`, `MAIL_PASSWORD` | tak (raport Excel) | SMTP — końcowy `.xlsx` na `EXCEL_REPORT_TO` |
| `GMAIL_USER` / `GMAIL_APP_PASSWORD` | opcjonalnie | alternatywa SMTP dla raportu Excel |
| `GDRIVE_FOLDER_ID` | tak (nd 09:00 Drive) | folder docelowy końcowego Excela (komentarz YAML: `1JMPyphoNX_oS_EjW7LEhf103lvvtsMUL`) |
| `GDRIVE_OAUTH_CLIENT_ID` / `_SECRET` / `_REFRESH_TOKEN` | tak (nd 09:00 Drive) | OAuth upload końcowego `.xlsx` |
| `GDRIVE_SERVICE_ACCOUNT_JSON` | nie | Shared Drive — pełny sync (obecnie DISABLED) |

Folder GU Bauunternehmen (pełny sync / lokalnie / reprocess): `1tP8oUi72t4EHDbE9GnHFdvfNtNsJe4xf` — **osobny** od folderu raportu Excel z secretu.

Modele Claude:

| Zadanie | Tier | Domyślny model | Env |
|---------|------|----------------|-----|
| Frazy Serper, cleanup Excel | `fast` | `claude-haiku-4-5` | `CLAUDE_MODEL_FAST` |
| Weryfikacja www, wyciąganie maili | `verify` | `claude-sonnet-4-6` | `CLAUDE_MODEL_VERIFY` |

## Artifacty

```
pon→pi | wt→pi | sro→pi | czw→pi | pt→pi
  → (chain lub nd 06:00) thu
  → nd 09:00 excel email + Drive xlsx
(prep / pełny sync Drive / send B2B: OFF)
```

- **Pon–pt:** upload zawsze jako `de-gu-wyniki-pi` (nie mon/tue/wed).
- **Poniedziałek:** wznawia z `de-gu-wyniki-fri` z poprzedniego cyklu (jeśli jest), inaczej świeży start.
- **Wt–pt:** kontynuacja z ostatniego `de-gu-wyniki-pi`.
- **Backfill:** `de-gu-wyniki-thu` (`--verify-pending-contacts --reverify-all-contacts` + `mfg_gu_de.json`).
- **Nd 09:00:** artefakt `thu` (fallback `mon`) → Gmail + Drive (tylko `de_gu_bauunternehmen_kontakte.xlsx`).
- Ręczne wznawianie: input `resume_artifact_run_id`.

## Załącznik PPTX (tylko gdy maile B2B włączone)

`assets/campaign/MFG_Referenzliste_Einzelhandel.pptx`

Przy `DISABLE_CONTRACTOR_EMAILS=1` send workflowy nie startują (job `if: false`).  
Źródło (rollback): [Google Slides MFG](https://docs.google.com/presentation/d/1kBnp5x0pdgXZSPzVte9e92IUgn2A5gSe/edit).

## Ręczne uruchomienie

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_full_pipeline_gha.ps1
powershell -ExecutionPolicy Bypass -File scripts\run_full_pipeline_gha.ps1 -SkipDiscovery
```

```powershell
gh workflow run "GU discovery" -R Bigmax1993/Wyszukiwarka-partnerow
gh workflow run "GU discovery" -R Bigmax1993/Wyszukiwarka-partnerow -f discovery_phase=mon
gh workflow run "GU niedziela backfill" -R Bigmax1993/Wyszukiwarka-partnerow
gh workflow run "GU poniedzialek excel email" -R Bigmax1993/Wyszukiwarka-partnerow
gh workflow run "GU poniedzialek excel email" -R Bigmax1993/Wyszukiwarka-partnerow -f dry_run=true
```

Kolejność w tygodniu cyklu: discovery (pon–pt 18:00) → backfill (chain po pt **lub** nd 06:00) → excel email + Drive (nd 09:00).

Po piątkowym discovery:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\resume_pipeline_after_pi.ps1 -PiRunId RUN_ID
```

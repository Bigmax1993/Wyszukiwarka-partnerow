# GitHub Actions — kampania GU (MFG / Filialbau)

Repozytorium: [Wyszukiwarka-partnerow](https://github.com/Bigmax1993/Wyszukiwarka-partnerow)

Crony używają `timezone: Europe/Warsaw` — godziny w YAML to **czas polski**.

## Tryb discovery-only (aktualny)

Pipeline na GHA zbiera firmy (Serper + Claude), buduje Excel w artefaktach i w niedzielę cyklu:
1. wysyła **raport Excel** na `svinchak1993@gmail.com`
2. uploaduje **tylko końcowy `.xlsx`** na Google Drive (`secrets.GDRIVE_FOLDER_ID`)

**Nie wysyła maili B2B** do kontrahentów. **Pełny sync** `Wyniki/` (cache/logi/`wyslane`) jest **DISABLED**.

| Flaga / mechanizm | Domyślnie | Efekt |
|-------------------|-----------|--------|
| `DISABLE_CONTRACTOR_EMAILS` | `1` | `--send-emails-only` = NO-OP |
| `DISABLE_GOOGLE_DRIVE` | `1` (workflow-level) | pełny sync OFF; krok Excel→Drive ustawia lokalnie `0` |
| `DISABLE_EXCEL_REPORT_EMAIL` | `0` | raport Excel na Gmail **WŁĄCZONY** |
| workflow `if: false` | send B2B + pełny Drive sync | te joby nie startują |

Rollback B2B / pełnego Drive: ustaw flagi na `0` oraz usuń `if: false` z YAML send/Drive.  
Szczegóły: [`GOOGLE_DRIVE.md`](GOOGLE_DRIVE.md), [`../schedule/PLAN_5_DNI.md`](../schedule/PLAN_5_DNI.md).

## Workflowy

| Workflow | Plik | Trigger | Status | Co robi |
|----------|------|---------|--------|---------|
| **Tests** | `tests.yml` | push, PR | **aktywny** | pytest unit + integracja + regresja + API live |
| **CI Deploy** | `ci-deploy.yml` | push | **aktywny** | smoke + walidacja secretów |
| **GU discovery** | `de_gu_pi.yml` | cron pon–pt 18:00 + guard co 6 tyg., ręcznie | **aktywny** | Discovery → `de-gu-wyniki-pi` |
| **GU niedziela backfill** | `de_gu_thu.yml` | cron nd 06:00 + guard, ręcznie | **aktywny** | Backfill + Excel → `de-gu-wyniki-thu` |
| **GU poniedzialek prep** | `de_gu_mon.yml` | tylko ręcznie | **cron OFF** | Awaryjny rebuild Excel |
| **GU poniedzialek excel email** | `de_gu_mon_excel_email.yml` | cron nd 09:00 + guard, ręcznie | **aktywny** | Excel → Gmail **+ Drive (tylko `.xlsx`)** |
| **GU poniedzialek send** | `de_gu_tue.yml` | tylko `workflow_dispatch` | **DISABLED** | Wysyłka B2B partia 1 |
| **GU wtorek send** | `de_gu_fri.yml` | tylko `workflow_dispatch` | **DISABLED** | Wysyłka B2B partia 2 |
| **Sync wyniki Google Drive** | `sync-google-drive.yml` | tylko `workflow_dispatch` | **DISABLED** | Pełny upload `Wyniki/` |
| **Sync tygodnia discovery na Drive** | `sync-week-discovery-drive.yml` | tylko `workflow_dispatch` | **DISABLED** | Jeden Excel tygodnia na Drive |
| **GU tydzien backfill i wysylka** | `week-backfill-and-send.yml` | ręcznie | **częściowo** | Backfill/Excel OK; kroki send = `if: false` |

Nazwy plików YAML (`*_tue`, `*_fri`, `*_thu`) są legacy — liczy się **display name**.

### Ręczne / ops

| Workflow | Plik | Trigger |
|----------|------|---------|
| GU catch-up | `gu-catch-up.yml` | ręcznie |
| Excel 7 firm z pi | `excel-seven-from-pi.yml` | ręcznie |
| GU reset pipeline cache | `de_gu_reset_cache.yml` | ręcznie |
| GU reprocess cache bez Serper | `de_gu_reprocess_no_serper.yml` | ręcznie |
| GU discovery wtorek (jednorazowo 2026-07-01) | `gu-discovery-tue-once-2026-07-01.yml` | jednorazowy cron (po dacie = skip) |

## Harmonogram cron (Europe/Warsaw) — aktywne

Cron w YAML jest tygodniowy, ale **guard** (`.github/actions/gu-gha-window-guard`) odpala joby **co 6 tygodni**:

| Parametr | Wartość |
|----------|---------|
| Anchor (poniedziałek) | `2026-09-21` |
| Okres | **42 dni** (`GU_CADENCE_DAYS`, domyślnie 42) |
| Kolejne poniedziałki | `2026-09-21`, `2026-11-02`, `2026-12-14`, `2027-01-25`, … |
| Aktywne dni cyklu | pon–pt (discovery) + **niedziela** (backfill + excel) |
| `workflow_dispatch` | zawsze `active=true` |

| Dzień | Workflow | Cron | Godzina PL |
|-------|----------|------|------------|
| **Poniedziałek** | discovery | `0 18 * * 1` | **18:00** |
| **Wtorek** | discovery | `0 18 * * 2` | **18:00** |
| **Środa** | discovery | `0 18 * * 3` | **18:00** |
| **Czwartek** | discovery | `0 18 * * 4` | **18:00** |
| **Piątek** | discovery | `0 18 * * 5` | **18:00** |
| **Niedziela** | backfill | `0 6 * * 0` | **06:00** |
| **Niedziela** | excel email + Drive xlsx | `0 9 * * 0` | **09:00** |

Wyłączone z crona: prep, pełny sync Drive, send B2B.

Limit Serper w GHA: `SERPER_DAILY_LIMIT=1000` (domyślnie w kodzie też 1000).

## Łańcuchy (auto `workflow_dispatch`)

| Po sukcesie | Uruchamia | Efekt dziś |
|-------------|-----------|------------|
| Discovery **piątek** | `GU niedziela backfill` | działa (w niedzielę cyklu / ręcznie) |
| Discovery **pon–czw** | `GU wtorek send` | **no-op** (`if: false` na send) |
| Backfill | Sync Drive | step wyłączony |
| Prep | send | step wyłączony |

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

Folder GU Bauunternehmen (pełny sync / lokalnie): `1tP8oUi72t4EHDbE9GnHFdvfNtNsJe4xf` — osobny od folderu raportu Excel z secretu.

Modele Claude:

| Zadanie | Tier | Domyślny model | Env |
|---------|------|----------------|-----|
| Frazy Serper, cleanup Excel | `fast` | `claude-haiku-4-5` | `CLAUDE_MODEL_FAST` |
| Weryfikacja www, wyciąganie maili | `verify` | `claude-sonnet-4-6` | `CLAUDE_MODEL_VERIFY` |

## Artifacty

```
pon→pi | wt→pi | sro→pi | czw→pi | pt→pi → niedziela→thu → excel email + Drive xlsx (nd 09:00)
(prep / pełny sync Drive / send B2B: OFF)
```

- Pon–pt 18:00: discovery → `de-gu-wyniki-pi`
- Niedziela 06:00: backfill → `de-gu-wyniki-thu`
- Niedziela 09:00: artefakt `thu` (fallback `mon`) → Gmail + Drive (tylko `de_gu_bauunternehmen_kontakte.xlsx`)

## Załącznik PPTX (tylko gdy maile B2B włączone)

`assets/campaign/MFG_Referenzliste_Einzelhandel.pptx`

Przy `DISABLE_CONTRACTOR_EMAILS=1` send workflowy nie startują.  
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

Kolejność: discovery (pon–pt 18:00) → backfill (nd 06:00) → excel email + Drive (nd 09:00).

Po piątkowym discovery:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\resume_pipeline_after_pi.ps1 -PiRunId RUN_ID
```

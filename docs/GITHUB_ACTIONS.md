# GitHub Actions — kampania GU

Repozytorium: [Wyszukiwarka-partnerow](https://github.com/Bigmax1993/Wyszukiwarka-partnerow)

## Tryb discovery-only (aktualny)

Pipeline na GHA zbiera firmy (Serper + Claude) i buduje Excel w artefaktach.
**Nie wysyła maili B2B** i **nie syncuje Google Drive**.

| Flaga / mechanizm | Domyślnie | Efekt |
|-------------------|-----------|--------|
| `DISABLE_CONTRACTOR_EMAILS` | `1` | `--send-emails-only` = NO-OP |
| `DISABLE_GOOGLE_DRIVE` | `1` | upload/sync Drive = NO-OP |
| `DISABLE_EXCEL_REPORT_EMAIL` | `0` | raport Excel na `svinchak1993@gmail.com` **WŁĄCZONY** |
| workflow `if: false` | send B2B + Drive | joby send/Drive nie startują |

Rollback: ustaw flagi na `0` w `.env` / secrets env oraz usuń `if: false` z YAML send/Drive.
Szczegóły: [`GOOGLE_DRIVE.md`](GOOGLE_DRIVE.md), [`../schedule/PLAN_5_DNI.md`](../schedule/PLAN_5_DNI.md).

## Workflowy

| Workflow | Plik | Trigger | Status | Co robi |
|----------|------|---------|--------|---------|
| **Tests** | `tests.yml` | push, PR | **aktywny** | pytest unit + integracja + regresja + API live |
| **CI Deploy** | `ci-deploy.yml` | push | **aktywny** | smoke + walidacja secretów |
| **GU discovery** | `de_gu_pi.yml` | cron pon–pt 18:00, ręcznie | **aktywny** | Discovery → `de-gu-wyniki-pi` |
| **GU niedziela backfill** | `de_gu_thu.yml` | cron nd 06:00, ręcznie | **aktywny** | Backfill + Excel → `de-gu-wyniki-thu` |
| **GU poniedzialek prep** | `de_gu_mon.yml` | tylko ręcznie | **cron OFF** | Awaryjny rebuild Excel |
| **GU poniedzialek excel email** | `de_gu_mon_excel_email.yml` | cron nd 09:00, ręcznie | **aktywny** | Końcowy Excel → `svinchak1993@gmail.com` |
| **GU poniedzialek send** | `de_gu_tue.yml` | tylko `workflow_dispatch` | **DISABLED** | Wysyłka B2B partia 1 |
| **GU wtorek send** | `de_gu_fri.yml` | tylko `workflow_dispatch` | **DISABLED** | Wysyłka B2B partia 2 |
| **Sync wyniki Google Drive** | `sync-google-drive.yml` | tylko `workflow_dispatch` | **DISABLED** | Upload `Wyniki/` na Drive |
| **Sync tygodnia discovery na Drive** | `sync-week-discovery-drive.yml` | tylko `workflow_dispatch` | **DISABLED** | Jeden Excel tygodnia na Drive |
| **GU tydzien backfill i wysylka** | `week-backfill-and-send.yml` | ręcznie | **częściowo** | Backfill/Excel OK; kroki send = `if: false` |

## Harmonogram cron (Europe/Warsaw) — aktywne

| Dzień | Workflow | Cron | Godzina PL |
|-------|----------|------|------------|
| **Poniedziałek** | discovery | `0 18 * * 1` | **18:00** |
| **Wtorek** | discovery | `0 18 * * 2` | **18:00** |
| **Środa** | discovery | `0 18 * * 3` | **18:00** |
| **Czwartek** | discovery | `0 18 * * 4` | **18:00** |
| **Piątek** | discovery | `0 18 * * 5` | **18:00** |
| **Niedziela** | backfill | `0 6 * * 0` | **06:00** |
| **Niedziela** | excel email | `0 9 * * 0` | **09:00** |

Wyłączone z crona: prep, sync Drive, send B2B.

## Sekrety

| Secret | Wymagany teraz | Opis |
|--------|----------------|------|
| `SERPER_API_KEY` | tak (discovery) | API Serper |
| `ANTHROPIC_API_KEY` | tak (discovery + backfill) | Claude API |
| `MAIL_USER`, `MAIL_PASSWORD` | tak (raport Excel) | SMTP Gmail — wysyłka końcowego `.xlsx` na `EXCEL_REPORT_TO` |
| `GDRIVE_OAUTH_*` | nie (Drive OFF) | OAuth upload — tylko po `DISABLE_GOOGLE_DRIVE=0` |
| `GDRIVE_SERVICE_ACCOUNT_JSON` | nie (Drive OFF) | Konto usługi Shared Drive |

Modele Claude (domyślnie w kodzie, opcjonalnie env):

| Zadanie | Tier | Domyślny model | Env |
|---------|------|----------------|-----|
| Frazy Serper, cleanup Excel | `fast` | `claude-haiku-4-5` | `CLAUDE_MODEL_FAST` |
| Weryfikacja www, wyciąganie maili | `verify` | `claude-sonnet-4-6` | `CLAUDE_MODEL_VERIFY` (lub legacy `CLAUDE_MODEL`) |

## Artifacty (discovery-only)

```
pon→pi | wt→pi | sro→pi | czw→pi | pt→pi → niedziela→thu → excel email (nd 09:00)
(prep / sync Drive / send: OFF)
```

- Pon–pt 18:00: discovery → `de-gu-wyniki-pi`
- Niedziela 06:00: backfill → `de-gu-wyniki-thu`
- Niedziela 09:00: Excel na `svinchak1993@gmail.com`

## Załącznik PPTX (tylko gdy maile B2B włączone)

Kod i bundled plik zostają w repo:

`assets/campaign/MFG_Referenzliste_Einzelhandel.pptx`

Przy `DISABLE_CONTRACTOR_EMAILS=1` send workflowy nie startują — PPTX ze Slides nie jest pobierany.
Źródło (rollback): [Google Slides MFG](https://docs.google.com/presentation/d/1kBnp5x0pdgXZSPzVte9e92IUgn2A5gSe/edit).

## Ręczne uruchomienie

Pełny cykl discovery-only (PC — **pomija** Drive sync i obie partie send):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_full_pipeline_gha.ps1
powershell -ExecutionPolicy Bypass -File scripts\run_full_pipeline_gha.ps1 -SkipDiscovery
```

Pojedyncze kroki aktywne (`gh`):

```powershell
gh workflow run "GU discovery" -R Bigmax1993/Wyszukiwarka-partnerow
gh workflow run "GU discovery" -R Bigmax1993/Wyszukiwarka-partnerow -f discovery_phase=mon
gh workflow run "GU discovery" -R Bigmax1993/Wyszukiwarka-partnerow -f discovery_phase=tue
gh workflow run "GU discovery" -R Bigmax1993/Wyszukiwarka-partnerow -f discovery_phase=wed
gh workflow run "GU discovery" -R Bigmax1993/Wyszukiwarka-partnerow -f discovery_phase=thu
gh workflow run "GU discovery" -R Bigmax1993/Wyszukiwarka-partnerow -f discovery_phase=fri
gh workflow run "GU discovery" -R Bigmax1993/Wyszukiwarka-partnerow -f resume_artifact_run_id=RUN_ID

gh workflow run "GU niedziela backfill" -R Bigmax1993/Wyszukiwarka-partnerow
gh workflow run "GU poniedzialek prep" -R Bigmax1993/Wyszukiwarka-partnerow
gh workflow run "GU poniedzialek excel email" -R Bigmax1993/Wyszukiwarka-partnerow
gh workflow run "GU poniedzialek excel email" -R Bigmax1993/Wyszukiwarka-partnerow -f dry_run=true
```

Workflowy DISABLED (send B2B / Drive) mają `if: false` — `gh workflow run` ich **nie wykona** jobów, dopóki nie przywrócisz YAML.

Kolejność: discovery (pon–pt 18:00) → backfill (nd 06:00) → excel email (nd 09:00).

Po piątkowym discovery (ręcznie):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\resume_pipeline_after_pi.ps1 -PiRunId RUN_ID
```

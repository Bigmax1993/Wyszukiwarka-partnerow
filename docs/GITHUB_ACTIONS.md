# GitHub Actions — kampania GU

Repozytorium: [Wyszukiwarka-partnerow](https://github.com/Bigmax1993/Wyszukiwarka-partnerow)

## Tryb discovery-only (aktualny)

Pipeline na GHA zbiera firmy (Serper + Claude) i buduje Excel w artefaktach.
**Nie wysyła maili B2B** i **nie syncuje Google Drive**.

| Flaga / mechanizm | Domyślnie | Efekt |
|-------------------|-----------|--------|
| `DISABLE_CONTRACTOR_EMAILS` | `1` | `--send-emails-only` = NO-OP |
| `DISABLE_GOOGLE_DRIVE` | `1` | upload/sync Drive = NO-OP |
| `DISABLE_EXCEL_REPORT_EMAIL` | `1` | raport Excel na Gmail = NO-OP |
| workflow `if: false` | send + Drive + excel email | joby nie startują (nawet ręcznie) |

Rollback: ustaw flagi na `0` w `.env` / secrets env oraz usuń `if: false` z YAML send/Drive.
Szczegóły: [`GOOGLE_DRIVE.md`](GOOGLE_DRIVE.md), [`../schedule/PLAN_5_DNI.md`](../schedule/PLAN_5_DNI.md).

## Workflowy

| Workflow | Plik | Trigger | Status | Co robi |
|----------|------|---------|--------|---------|
| **Tests** | `tests.yml` | push, PR | **aktywny** | pytest unit + integracja + regresja + API live |
| **CI Deploy** | `ci-deploy.yml` | push | **aktywny** | smoke + walidacja secretów |
| **GU discovery** | `de_gu_pi.yml` | cron, ręcznie | **aktywny** | Discovery pon–pt → `de-gu-wyniki-pi` |
| **GU niedziela backfill** | `de_gu_thu.yml` | cron, ręcznie | **aktywny** | Backfill + Excel → `de-gu-wyniki-thu` |
| **GU poniedzialek prep** | `de_gu_mon.yml` | cron, ręcznie | **aktywny** | Rebuild Excel → `de-gu-wyniki-mon` |
| **GU poniedzialek excel email** | `de_gu_mon_excel_email.yml` | tylko `workflow_dispatch` | **DISABLED** | Raport Excel (wewnętrzny Gmail) |
| **GU poniedzialek send** | `de_gu_tue.yml` | tylko `workflow_dispatch` | **DISABLED** | Wysyłka B2B partia 1 |
| **GU wtorek send** | `de_gu_fri.yml` | tylko `workflow_dispatch` | **DISABLED** | Wysyłka B2B partia 2 |
| **Sync wyniki Google Drive** | `sync-google-drive.yml` | tylko `workflow_dispatch` | **DISABLED** | Upload `Wyniki/` na Drive |
| **Sync tygodnia discovery na Drive** | `sync-week-discovery-drive.yml` | tylko `workflow_dispatch` | **DISABLED** | Jeden Excel tygodnia na Drive |
| **GU tydzien backfill i wysylka** | `week-backfill-and-send.yml` | ręcznie | **częściowo** | Backfill/Excel OK; kroki send = `if: false` |

## Harmonogram cron (Europe/Warsaw) — aktywne

| Dzień | Workflow | Cron | Godzina PL |
|-------|----------|------|------------|
| **Poniedziałek** | discovery część 1 | `0 17 * * 1` | **17:00** |
| **Wtorek** | discovery część 2 | `0 15 * * 2` | **15:00** |
| **Środa** | discovery część 3 | `0 19 * * 3` | **19:00** |
| **Czwartek** | discovery część 4 | `0 20 * * 4` | **20:00** |
| **Piątek** | discovery część 5 | `0 16 * * 5` | **16:00** |
| **Niedziela** | backfill | `30 5 * * 0` | **05:30** |
| **Poniedziałek** | prep | `0 7 * * 1` | **07:00** |

Wyłączone z crona (DISABLED): excel email 04:30, sync Drive 06:00, send pon 09:00 / wt 09:00.

## Sekrety

| Secret | Wymagany teraz | Opis |
|--------|----------------|------|
| `SERPER_API_KEY` | tak (discovery) | API Serper |
| `ANTHROPIC_API_KEY` | tak (discovery + backfill) | Claude API |
| `MAIL_USER`, `MAIL_PASSWORD` | nie (discovery-only) | SMTP — tylko po rollbacku maili B2B / raportu Excel |
| `GDRIVE_OAUTH_*` | nie (Drive OFF) | OAuth upload — tylko po `DISABLE_GOOGLE_DRIVE=0` |
| `GDRIVE_SERVICE_ACCOUNT_JSON` | nie (Drive OFF) | Konto usługi Shared Drive |

Modele Claude (domyślnie w kodzie, opcjonalnie env):

| Zadanie | Tier | Domyślny model | Env |
|---------|------|----------------|-----|
| Frazy Serper, cleanup Excel | `fast` | `claude-haiku-4-5` | `CLAUDE_MODEL_FAST` |
| Weryfikacja www, wyciąganie maili | `verify` | `claude-sonnet-4-6` | `CLAUDE_MODEL_VERIFY` (lub legacy `CLAUDE_MODEL`) |

## Artifacty (discovery-only)

```
pon→pi | wt→pi | sro→pi | czw→pi | pt→pi → niedziela→thu → pon prep→mon
(sync Drive / send: DISABLED)
```

- Poniedziałek 17:00: nowy tydzień discovery → `de-gu-wyniki-pi`
- Wtorek–piątek: kontynuacja z `pi`
- Niedziela: backfill z `pi` → `de-gu-wyniki-thu`
- Poniedziałek 07:00: prep → `de-gu-wyniki-mon` (Excel, bez wysyłki)

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
```

Workflowy DISABLED (send / Drive / excel email) mają `if: false` — `gh workflow run` ich **nie wykona** jobów, dopóki nie przywrócisz YAML.

Kolejność discovery-only: discovery (pon–pt) → backfill → prep.

Po piątkowym discovery (ręcznie):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\resume_pipeline_after_pi.ps1 -PiRunId RUN_ID
```

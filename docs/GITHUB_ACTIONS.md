# GitHub Actions — kampania PL spedycja (Forwarding Assistant)

Repozytorium: [Wyszukiwarka-partnerow](https://github.com/Bigmax1993/Wyszukiwarka-partnerow)

Crony używają `timezone: Europe/Warsaw` — godziny w YAML to **czas polski**.  
Gałąź CI: **`master`** (`tests.yml`, `ci-deploy.yml`).

## Tryb aktualny (discovery + B2B według harmonogramu)

Pipeline na GHA zbiera firmy (Serper + Claude), buduje Excel w artefaktach i w niedzielę cyklu:
1. wysyła **raport Excel** na `svinchak1993@gmail.com`
2. uploaduje **tylko końcowy `.xlsx`** na Google Drive (`secrets.GDRIVE_FOLDER_ID`)
3. w **następnym** pon/wt 09:00 wysyła maile B2B (partia 1 / 2) — guard `FAS_GUARD_MODE=send_followup`

Maile B2B: **ON** (nd Excel → pon 09:00 → wt 09:00). **Pełny sync** `Wyniki/` nadal **DISABLED**.

Discovery używa `run_config/pl_fas_spedycja.json` (**16 województw**, cała Polska; **1. = Dolnoslaskie**) — **bez** `--rotate-bundesland`. Artefakt discovery zawsze: `pl-spedycja-wyniki-pi`.  
Filtr ICP (Serper / www): [`FILTER_ICP.md`](FILTER_ICP.md).  
Prompty Claude (PL FAS): [`CLAUDE_PROMPTS.md`](CLAUDE_PROMPTS.md).  
Cookie baner (Playwright pl-PL): [`COOKIE_CONSENT.md`](COOKIE_CONSENT.md).

| Flaga / mechanizm | Domyślnie | Efekt |
|-------------------|-----------|--------|
| `DISABLE_CONTRACTOR_EMAILS` | `0` w workflowach send | B2B ON (cron pon/wt 09:00); lokalnie domyślnie nadal `1` |
| `DISABLE_GOOGLE_DRIVE` | `1` (workflow-level) | pełny sync OFF; krok Excel→Drive ustawia lokalnie `0` |
| `DISABLE_EXCEL_REPORT_EMAIL` | `0` | raport Excel na Gmail **WŁĄCZONY** |
| workflow `if: false` | pełny Drive sync | sync `Wyniki/` OFF; send B2B **ON** (cron) |

Rollback B2B: [`ROLLBACK_B2B.md`](ROLLBACK_B2B.md).  
PC vs GHA: [`LOCAL_VS_GHA.md`](LOCAL_VS_GHA.md).  
Drive: [`GOOGLE_DRIVE.md`](GOOGLE_DRIVE.md). Plan: [`../schedule/PLAN_5_DNI.md`](../schedule/PLAN_5_DNI.md).

## Workflowy

| Workflow | Plik | Trigger | Status | Co robi |
|----------|------|---------|--------|---------|
| **Tests** | `tests.yml` | push/PR → `master` | **aktywny** | pytest unit + integracja + regresja + API live |
| **CI Deploy** | `ci-deploy.yml` | push → `master` | **aktywny** | smoke + walidacja secretów |
| **PL spedycja discovery** | `pl_fas_pi.yml` | cron pon–pt 18:00 + guard co 55 dni, ręcznie | **aktywny** | Discovery PL (16 woj.) → `pl-spedycja-wyniki-pi`; pt → chain backfill; **bez** chain send B2B |
| **PL spedycja niedziela backfill** | `pl_fas_thu.yml` | cron nd 06:00 + guard, chain z pt, ręcznie | **aktywny** | Backfill + Excel → `pl-spedycja-wyniki-thu` |
| **PL spedycja poniedzialek prep** | `pl_fas_mon.yml` | tylko ręcznie | **cron OFF** | Awaryjny rebuild Excel |
| **PL spedycja poniedzialek excel email** | `pl_fas_mon_excel_email.yml` | cron nd 09:00 + guard, ręcznie | **aktywny** | Excel → Gmail **+ Drive (tylko `.xlsx`)** |
| **PL spedycja poniedzialek send** | `pl_fas_tue.yml` | cron **pon 09:00** + `send_followup`, ręcznie | **aktywny** | B2B partia 1 (tydzień *po* Excelu; 2× PPTX) |
| **PL spedycja wtorek send** | `pl_fas_fri.yml` | cron **wt 09:00** + `send_followup`, ręcznie | **aktywny** | B2B partia 2 (po partii 1; 2× PPTX) |
| **Sync wyniki Google Drive** | `sync-google-drive.yml` | tylko `workflow_dispatch` | **DISABLED** | Pełny upload `Wyniki/` |
| **Sync tygodnia discovery na Drive** | `sync-week-discovery-drive.yml` | tylko `workflow_dispatch` | **DISABLED** | Jeden Excel tygodnia na Drive |
| **GU tydzien backfill i wysylka** | `week-backfill-and-send.yml` | ręcznie | **częściowo** | Backfill/Excel OK; kroki send = `if: false` (ops / historyczny) |

Nazwy plików YAML (`*_tue`, `*_fri`, `*_thu`) są legacy — liczy się **display name**.

### Ręczne / ops

| Workflow | Plik | Trigger | Uwagi |
|----------|------|---------|--------|
| PL FAS catch-up | `pl_fas_catch_up.yml` | ręcznie | Wąski scope (`discovery-tue`); pełny catch-up: `gh workflow run "PL spedycja discovery" -f discovery_phase=…` |
| Excel 7 firm z pi | `excel-seven-from-pi.yml` | ręcznie | Ops |
| PL spedycja reset pipeline cache | `pl_fas_reset_cache.yml` | ręcznie | Ops |
| PL spedycja reprocess cache bez Serper | `pl_fas_reprocess_no_serper.yml` | ręcznie | Upload Drive → folder Excela `1bRCAq…`; wymaga `DISABLE_GOOGLE_DRIVE=0` w kroku, inaczej NO-OP |
| PL spedycja discovery wtorek (jednorazowo 2026-07-01) | `pl_fas_discovery_tue_once_2026-07-01.yml` | jednorazowy cron | Po dacie = skip; można zarchiwizować |

## Harmonogram cron (Europe/Warsaw) — aktywne

Cron w YAML jest tygodniowy, ale **guard** (`.github/actions/pl_fas_gha_window_guard`) odpala joby **co 55 dni**:

| Parametr | Wartość |
|----------|---------|
| Anchor (poniedziałek) | `2026-11-02` (`GU_CADENCE_ANCHOR`) — ten tydzień jak w poprzednim planie |
| Okres | **55 dni** (`GU_CADENCE_DAYS`, domyślnie 55) od anchora |
| Start tygodnia pipeline | poniedziałek **w dniu** markera `anchor + n·55` albo **kolejny** poniedziałek (55 ∤ 7) |
| Kolejne poniedziałki | `2026-11-02`, `2026-12-28`, `2027-02-22`, `2027-04-19`, … |
| Historyczny (stary 42d) | `2026-09-21`–`2026-09-27` (już po) |
| Aktywne dni cyklu (pipeline) | pon–pt (discovery) + **niedziela** (backfill + excel) |
| Follow-up B2B | **pon/wt** tygodnia *po* niedzieli Excel (`FAS_GUARD_MODE=send_followup`) |
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
| **Poniedziałek** (po Excelu) | B2B partia 1 | `0 9 * * 1` | **09:00** |
| **Wtorek** (po partii 1) | B2B partia 2 | `0 9 * * 2` | **09:00** |

### Kalendarz uruchomień GHA (Europe/Warsaw)

Konkretne daty tygodni cyklu (guard = active). Poza tymi tygodniami cron jest **skip**.  
**02–08.11.2026** = ten sam tydzień co w starym planie; od niego cadence **55 dni** (start tygodnia wyrównany do poniedziałku → odstęp zwykle 56 dni).

| Cykl | Marker (+55d) | Pon 18:00 | Wt 18:00 | Śr 18:00 | Czw 18:00 | Pt 18:00 → chain backfill | Nd 06:00 backfill | Nd 09:00 Excel+Drive |
|------|---------------|-----------|----------|----------|-----------|---------------------------|-------------------|----------------------|
| hist. | (stary 42d) | **2026-09-21** | 2026-09-22 | 2026-09-23 | 2026-09-24 | 2026-09-25 | 2026-09-27 | 2026-09-27 |
| 1 | 2026-11-02 | **2026-11-02** | 2026-11-03 | 2026-11-04 | 2026-11-05 | 2026-11-06 | 2026-11-08 | 2026-11-08 |
| 2 | 2026-12-27 | **2026-12-28** | 2026-12-29 | 2026-12-30 | 2026-12-31 | 2027-01-01 | 2027-01-03 | 2027-01-03 |
| 3 | 2027-02-20 | **2027-02-22** | 2027-02-23 | 2027-02-24 | 2027-02-25 | 2027-02-26 | 2027-02-28 | 2027-02-28 |
| 4 | 2027-04-16 | **2027-04-19** | 2027-04-20 | 2027-04-21 | 2027-04-22 | 2027-04-23 | 2027-04-25 | 2027-04-25 |
| 5 | 2027-06-10 | **2027-06-14** | 2027-06-15 | 2027-06-16 | 2027-06-17 | 2027-06-18 | 2027-06-20 | 2027-06-20 |
| 6 | 2027-08-04 | **2027-08-09** | 2027-08-10 | 2027-08-11 | 2027-08-12 | 2027-08-13 | 2027-08-15 | 2027-08-15 |
| 7 | 2027-09-28 | **2027-10-04** | 2027-10-05 | 2027-10-06 | 2027-10-07 | 2027-10-08 | 2027-10-10 | 2027-10-10 |
| 8 | 2027-11-22 | **2027-11-22** | 2027-11-23 | 2027-11-24 | 2027-11-25 | 2027-11-26 | 2027-11-28 | 2027-11-28 |
| 9 | 2028-01-16 | **2028-01-17** | 2028-01-18 | 2028-01-19 | 2028-01-20 | 2028-01-21 | 2028-01-23 | 2028-01-23 |
| 10 | 2028-03-11 | **2028-03-13** | 2028-03-14 | 2028-03-15 | 2028-03-16 | 2028-03-17 | 2028-03-19 | 2028-03-19 |

Wyłączone z crona: prep, pełny sync Drive. Send B2B: **ON** (pon/wt 09:00 + guard).

Limit Serper w GHA: `SERPER_DAILY_LIMIT=1000` (domyślnie w kodzie też 1000).

## Łańcuchy (auto `workflow_dispatch`)

| Po sukcesie | Uruchamia | Efekt dziś |
|-------------|-----------|------------|
| Discovery **piątek** | `PL spedycja niedziela backfill` (`artifact_run_id` = bieżący run) | **działa od razu** (dispatch omija guard dnia; w tygodniu poza cyklem cron nd i tak jest skip) |
| Discovery **pon–czw** | — | **brak chain** (send = osobne crony `send_followup`) |
| Backfill (cron nd 06:00) | — | zapasowy / restart, jeśli chain z pt nie wystarczy |
| Backfill → Sync Drive | Sync Drive | step wyłączony |
| Prep → send | send | prep OFF; send = cron follow-up |

Send B2B według harmonogramu: **nd Excel → pon 09:00 partia 1 → wt 09:00 partia 2** (tydzień *po* discovery; `FAS_GUARD_MODE=send_followup`). Nie w poniedziałek rano tego samego dnia co discovery 18:00.

Typowy przebieg:

```
pon–czw discovery → stop (artefakt pl-spedycja-wyniki-pi)
pt discovery → (chain) backfill → nd 09:00 Excel+Drive
(+ opcjonalnie nd 06:00 cron jako fallback backfill)
→ (następny) pon 09:00 B2B partia 1 → wt 09:00 B2B partia 2
```

## Sekrety

| Secret | Wymagany teraz | Opis |
|--------|----------------|------|
| `SERPER_API_KEY` | tak (discovery) | API Serper |
| `ANTHROPIC_API_KEY` | tak (discovery + backfill) | Claude API |
| `MAIL_USER`, `MAIL_PASSWORD` | tak (Excel + B2B) | SMTP — raport `.xlsx` i maile kontrahentów |
| `GMAIL_USER` / `GMAIL_APP_PASSWORD` | opcjonalnie | alternatywa SMTP dla raportu Excel |
| `GDRIVE_FOLDER_ID` | tak (nd 09:00) | **ustaw** `1bRCAqle6BS46YEw0fScq4P095LsJUSgL` (folder Excela kontaktów) |
| `GDRIVE_OAUTH_CLIENT_ID` / `_SECRET` / `_REFRESH_TOKEN` | tak (Excel + załączniki B2B) | OAuth upload `.xlsx` / pobranie oferty+prezentacji |
| `GDRIVE_SERVICE_ACCOUNT_JSON` | nie | Shared Drive — pełny sync (obecnie DISABLED) |

Folder końcowego Excela kontaktów: [`1bRCAqle6BS46YEw0fScq4P095LsJUSgL`](https://drive.google.com/drive/folders/1bRCAqle6BS46YEw0fScq4P095LsJUSgL?usp=drive_link) — ustaw też jako secret `GDRIVE_FOLDER_ID`.

Modele Claude (treść promptów PL FAS: [`CLAUDE_PROMPTS.md`](CLAUDE_PROMPTS.md)):

| Zadanie | Tier | Domyślny model | Env |
|---------|------|----------------|-----|
| Frazy Serper, cleanup Excel | `fast` | `claude-haiku-4-5` | `CLAUDE_MODEL_FAST` |
| Weryfikacja www, wyciąganie maili | `verify` | `claude-sonnet-4-6` | `CLAUDE_MODEL_VERIFY` |

## Artifacty

```
pon→pi | wt→pi | sro→pi | czw→pi | pt→pi
  → (chain lub nd 06:00) thu
  → nd 09:00 excel email + Drive xlsx
  → (następny) pon send → pl-spedycja-wyniki-tue
  → wt send → pl-spedycja-wyniki-fri
(prep / pełny sync Drive: OFF)
```

- **Pon–pt:** upload zawsze jako `pl-spedycja-wyniki-pi` (nie mon/tue/wed).
- **Poniedziałek discovery:** seed z `pl-spedycja-wyniki-thu` (po backfillu) albo fallback `pl-spedycja-wyniki-pi`, z `--respect-cache` (kumulacja); brak artefaktu = świeży start.
- **Wt–pt:** kontynuacja z ostatniego `pl-spedycja-wyniki-pi` + `--respect-cache`.
- **Backfill:** `pl-spedycja-wyniki-thu` (`--verify-pending-contacts --reverify-all-contacts` + `pl_fas_spedycja.json`).
- **Nd 09:00:** artefakt `thu` (fallback `mon`) → Gmail + Drive (tylko `pl_spedycja_kontakte.xlsx`).
- **B2B pon:** preferuj `thu` → artefakt `pl-spedycja-wyniki-tue`.
- **B2B wt:** preferuj `tue` → artefakt `pl-spedycja-wyniki-fri`.
- Ręczne wznawianie: input `resume_artifact_run_id`.

## Załączniki maila B2B (GHA send ON)

| Plik | Drive | Lokalnie |
|------|-------|----------|
| Oferta | [`1t6m-M49…`](https://drive.google.com/file/d/1t6m-M49t4w0RuLzc8rWebwjldLUMMRW3/view?usp=drive_link) | `FAS_zalacznik_kampania.pptx` |
| Prezentacja | [`164qbEQO…`](https://drive.google.com/file/d/164qbEQOTyO8VTgfZr2wtIVTY-zttk6u7/view?usp=drive_link) | `FAS_prezentacja.pptx` |

Moduł: `pl_fas_email_attachment.py` (`ensure_fas_email_attachments`).  
Eksport: `python scripts/export_fas_email_attachment.py` (oba pliki; `--primary-only` = tylko oferta).  
Env GHA: `FAS_EMAIL_ATTACHMENT_PATH` + `FAS_EMAIL_ATTACHMENT_EXTRA_PATH`.  
Lokalnie: `DISABLE_CONTRACTOR_EMAILS=1` → send = NO-OP (workflowy GHA mają `0`).

## Ręczne uruchomienie

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_full_pipeline_gha.ps1
powershell -ExecutionPolicy Bypass -File scripts\run_full_pipeline_gha.ps1 -SkipDiscovery
```

```powershell
gh workflow run "PL spedycja discovery" -R Bigmax1993/Wyszukiwarka-partnerow
gh workflow run "PL spedycja discovery" -R Bigmax1993/Wyszukiwarka-partnerow -f discovery_phase=mon
gh workflow run "PL spedycja niedziela backfill" -R Bigmax1993/Wyszukiwarka-partnerow
gh workflow run "PL spedycja poniedzialek excel email" -R Bigmax1993/Wyszukiwarka-partnerow
gh workflow run "PL spedycja poniedzialek excel email" -R Bigmax1993/Wyszukiwarka-partnerow -f dry_run=true
gh workflow run "PL spedycja poniedzialek send" -R Bigmax1993/Wyszukiwarka-partnerow
gh workflow run "PL spedycja wtorek send" -R Bigmax1993/Wyszukiwarka-partnerow
```

Kolejność: discovery (pon–pt 18:00) → backfill → excel+Drive (nd 09:00) → B2B pon/wt 09:00 (`send_followup`).

Po piątkowym discovery:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\resume_pipeline_after_pi.ps1 -PiRunId RUN_ID
```

# Plan tygodniowy: poniedziałek–piątek discovery → niedziela → poniedziałek

Jeden **obrót** na **jedną falę** (1 Bundesland / tydzień, rotacja `--rotate-bundesland`).

**Tryb discovery-only (aktualny):** wysyłka kontrahentów **WYŁĄCZONA** (`DISABLE_CONTRACTOR_EMAILS=1`),
Google Drive **WYŁĄCZONY** (`DISABLE_GOOGLE_DRIVE=1`). Zostaje: discovery + backfill + Excel lokalnie / artefakty GHA.

## Cykl tygodniowy

```
Tydzień N (discovery):
  pon 17:00 → wt 15:00 → śr 19:00 → czw 20:00 → pt 16:00   [de-gu-wyniki-pi]

Tydzień N (przetwarzanie — BEZ send / BEZ Drive):
  nd 05:30 backfill → pon 07:00 prep
  (sync Drive + send: DISABLED)
```

**Poniedziałek:** rano prep kończy poprzednią falę (Excel), wieczorem (17:00) startuje **nowy** tydzień discovery.

## Tabela harmonogramu

| Dzień | Godzina (PL) | Skrypt PC | GitHub Actions |
|-------|--------------|-----------|----------------|
| **Poniedziałek** | **17:00** | `run_poniedzialek_discovery.ps1` | `GU discovery` (faza mon) |
| **Wtorek** | **15:00** | `run_wtorek_discovery.ps1` | `GU discovery` (faza tue) |
| **Środa** | **19:00** | `run_sroda_discovery.ps1` | `GU discovery` (faza wed) |
| **Czwartek** | **20:00** | `run_czwartek_discovery.ps1` | `GU discovery` (faza thu) |
| **Piątek** | **16:00** | `run_piatek_discovery.ps1` | `GU discovery` (faza fri) |
| **Niedziela** | 06:00 | `run_czwartek.ps1` | `GU niedziela backfill` (~05:30 Actions) |
| **Poniedziałek** | **06:00** | — | ~~`Sync wyniki Google Drive`~~ **DISABLED** |
| **Poniedziałek** | **07:00** | `run_poniedzialek_prep.ps1` | `GU poniedzialek prep` |
| **Poniedziałek** | **08:00** | — | `GU poniedzialek excel email` → `svinchak1993@gmail.com` |
| **Poniedziałek** | **09:00** | ~~`run_poniedzialek_send.ps1`~~ **NO-OP** | ~~`GU poniedzialek send`~~ **DISABLED** |
| **Wtorek** | **09:00** | ~~`run_wtorek.ps1`~~ **NO-OP** | ~~`GU wtorek send`~~ **DISABLED** |

| Dzień | Co robi |
|-------|---------|
| **Poniedziałek 17:00** | Discovery część 1 — nowy tydzień, cache z `fri` → `de-gu-wyniki-pi` |
| **Wtorek 15:00** | Discovery część 2 — `--respect-cache` |
| **Środa 19:00** | Discovery część 3 — `--respect-cache` |
| **Czwartek 20:00** | Discovery część 4 — `--respect-cache` |
| **Piątek 16:00** | Discovery część 5 — `--respect-cache`, domknięcie tygodnia |
| **Niedziela 05:30** | Verify www + backfill e-maili + Excel (`de-gu-wyniki-thu`) |
| **Poniedziałek 07:00** | Rebuild Excel z cache (`de-gu-wyniki-mon`), **bez wysyłki B2B** |
| **Poniedziałek 08:00** | Raport: końcowy Excel na `svinchak1993@gmail.com` (jeden odbiorca) |

## Task Scheduler (Windows)

```powershell
powershell -ExecutionPolicy Bypass -File "schedule\register_tasks_5_dni.ps1"
```

Rejestruje **tylko** discovery + backfill + prep (bez tasków send).

## GitHub Actions — artefakty

```
pon→pi | wt→pi | sro→pi | czw→pi | pt→pi → niedziela→thu → pon prep→mon
(sync Drive / send: DISABLED)
```

| Workflow | Plik | Cron (Europe/Warsaw) |
|----------|------|----------------------|
| discovery | `de_gu_pi.yml` | pon–pt discovery |
| backfill | `de_gu_thu.yml` | `30 5 * * 0` → **05:30** niedziela |
| sync Drive | `sync-google-drive.yml` | **DISABLED** |
| prep | `de_gu_mon.yml` | `0 7 * * 1` → **07:00** poniedziałek |
| excel email | `de_gu_mon_excel_email.yml` | `0 8 * * 1` → **08:00** poniedziałek |
| send 1/2 | `de_gu_tue.yml` / `de_gu_fri.yml` | **DISABLED** |

## CLI send

`--send-emails-only` = **NO-OP** dopóki `DISABLE_CONTRACTOR_EMAILS=1`.
Podgląd treści bez SMTP: `--dry-run-email --send-emails-only`.
Rollback wysyłki: `DISABLE_CONTRACTOR_EMAILS=0`.

## Pełny pipeline po piątku (GHA)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_full_pipeline_gha.ps1 -SkipDiscovery
```

Skrypt pomija Drive sync i obie partie send (discovery-only).

# Plan tygodniowy: sobota → niedziela → poniedziałek

Jeden **obrót** na **jedną falę** (1 Bundesland / tydzień, rotacja `--rotate-bundesland`).

**Pipeline kończy się na Excelu** — bez automatycznej wysyłki maili i bez sync Google Drive.

## Tabela harmonogramu

| Dzień | Godzina (PL) | Skrypt PC | GitHub Actions |
|-------|--------------|-----------|----------------|
| **Sobota** | **20:10** | `run_sroda.ps1` | `GU sobota discovery` |
| **Niedziela** | 06:00 | `run_czwartek.ps1` | `GU niedziela backfill` (~05:30 Actions) |
| **Poniedziałek** | **04:30** | `run_poniedzialek_excel_email.ps1` | `GU poniedzialek excel email` |
| **Poniedziałek** | 08:00 | `run_poniedzialek_prep.ps1` | `GU poniedzialek prep` |

| Dzień | Co robi |
|-------|---------|
| **Sobota** | Discovery Serper + www → cache JSON |
| **Niedziela** | Weryfikacja www + backfill e-maili + Excel |
| **Poniedziałek** | Rebuild Excel z cache — **gotowy plik w `Wyniki/`** |
| **Poniedziałek 04:30** | Wysyłka Excela na **svinchak1993@gmail.com** (Gmail / yagmail) |

## Poza automatycznym pipeline (ręcznie)

| Funkcja | Jak uruchomić |
|---------|---------------|
| Wysyłka maili MFG | `python de_gu_bauunternehmen_scraper.py --send-emails-only` lub workflow `GU poniedzialek send` / `GU wtorek send` |
| Sync Google Drive | `python scripts/gdrive_upload_wyniki.py` lub workflow `Sync wyniki Google Drive` |

## Task Scheduler (Windows)

```cmd
scripts\register_gu_weekly_tasks.cmd
```

Usunięcie starych zadań wysyłki: skrypt usuwa `Kanbud_GU_Poniedzialek_Send` i `Kanbud_GU_Wtorek_Send` przy rejestracji.

## GitHub Actions — artefakty

```
sobota → wed → niedziela → thu → pon prep → mon
```

| Workflow | Plik | Cron UTC (CEST → PL) |
|----------|------|----------------------|
| discovery | `de_gu_wed.yml` | `10 18 * * 6` → **20:10** sobota |
| backfill | `de_gu_thu.yml` | `30 3 * * 0` → **05:30** niedziela |
| excel email | `de_gu_mon_excel_email.yml` | `30 2 * * 1` → **04:30** poniedziałek |
| prep | `de_gu_mon.yml` | `0 6 * * 1` → **08:00** poniedziałek |

Sobota discovery kumuluje cache z poprzedniego `de-gu-wyniki-mon` (fallback: `de-gu-wyniki-fri`).

**Zimą (CET):** discovery → `10 19 * * 6` (20:10 PL).

# Plan tygodniowy — discovery-only (Europe/Warsaw)

Jeden **obrót** = 1 Bundesland / tydzień (`--rotate-bundesland`).

**Aktualny tryb:** bez maili B2B, bez Drive. Discovery + backfill + Excel na Gmail.

## Cykl

```
pon–pt 18:00 discovery → nd 06:00 backfill → nd 09:00 Excel → svinchak1993@gmail.com
(prep / send B2B / Drive: OFF)
```

## Harmonogram

| Dzień | Godzina (PL) | GitHub Actions | Cron |
|-------|--------------|----------------|------|
| **Poniedziałek** | **18:00** | `GU discovery` (mon) | `0 18 * * 1` |
| **Wtorek** | **18:00** | `GU discovery` (tue) | `0 18 * * 2` |
| **Środa** | **18:00** | `GU discovery` (wed) | `0 18 * * 3` |
| **Czwartek** | **18:00** | `GU discovery` (thu) | `0 18 * * 4` |
| **Piątek** | **18:00** | `GU discovery` (fri) | `0 18 * * 5` |
| **Niedziela** | **06:00** | `GU niedziela backfill` | `0 6 * * 0` |
| **Niedziela** | **09:00** | `GU poniedzialek excel email` | `0 9 * * 0` |

| Wyłączone | Status |
|-----------|--------|
| Prep pon 07:00 | cron OFF (tylko ręcznie) |
| Sync Drive | DISABLED |
| Send B2B pon/wt | DISABLED |

## Task Scheduler (PC)

```powershell
powershell -ExecutionPolicy Bypass -File "schedule\register_tasks_5_dni.ps1"
```

Rejestruje: pon–pt 18:00 discovery + nd 06:00 backfill. Excel mail tylko na GHA.

## Artefakty

```
pon→pi | wt→pi | sro→pi | czw→pi | pt→pi → niedziela→thu → excel email
```

## Pełny pipeline (GHA, ręcznie)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_full_pipeline_gha.ps1 -SkipDiscovery
```

Pomija Drive i send B2B; raport Excel idzie osobnym workflowem (cron nd 09:00).

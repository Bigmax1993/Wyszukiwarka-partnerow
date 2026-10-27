# Plan tygodniowy — discovery-only (Europe/Warsaw)

Jeden **obrót** = tydzień discovery **bundesweit** (`run_config/mfg_gu_de.json` — **16** Bundesländer), podzielony na 5 części (pon–pt).  
Rotacja `--rotate-bundesland` (1 land / cykl) jest **opcją ręczną**, nie trybem GHA/PC.

**Aktualny tryb:** bez maili B2B; bez pełnego sync Drive.  
Discovery + backfill + Excel na Gmail **oraz** upload końcowego `.xlsx` na Drive (tylko GHA).

**Cadence GHA:** co **6 tygodni** od **2026-09-21** (guard, 42 dni).  
**Task Scheduler PC:** te same godziny **co tydzień** (bez guarda) — patrz [`docs/LOCAL_VS_GHA.md`](../docs/LOCAL_VS_GHA.md).

## Cykl (GHA)

```
(aktywny tydzień co 42 dni od 2026-09-21)
pon–pt 18:00 discovery (16 landów, cache między dniami)
→ po pt: chain → backfill  (alternatywa: nd 06:00 cron)
→ nd 09:00 Excel → svinchak1993@gmail.com + Drive (tylko .xlsx)
(prep / send B2B / pełny sync Drive: OFF)
```

## Harmonogram GHA

Cron odpala się co tydzień, ale joby startują tylko gdy guard = active (tydzień cyklu).  
`workflow_dispatch` (np. chain po piątku) zawsze omija guard dnia tygodnia.

| Dzień | Godzina (PL) | GitHub Actions | Cron |
|-------|--------------|----------------|------|
| **Poniedziałek** | **18:00** | `GU discovery` (mon) | `0 18 * * 1` |
| **Wtorek** | **18:00** | `GU discovery` (tue) | `0 18 * * 2` |
| **Środa** | **18:00** | `GU discovery` (wed) | `0 18 * * 3` |
| **Czwartek** | **18:00** | `GU discovery` (thu) | `0 18 * * 4` |
| **Piątek** | **18:00** | `GU discovery` (fri) → chain backfill | `0 18 * * 5` |
| **Niedziela** | **06:00** | `GU niedziela backfill` (fallback) | `0 6 * * 0` |
| **Niedziela** | **09:00** | `GU poniedzialek excel email` (+ Drive xlsx) | `0 9 * * 0` |

| Wyłączone | Status |
|-----------|--------|
| Prep | cron OFF (tylko ręcznie) |
| Pełny Sync Drive | DISABLED |
| Send B2B pon/wt | DISABLED (`if: false`; tylko dispatch) |

Kolejne poniedziałki cyklu: `2026-09-21`, `2026-11-02`, `2026-12-14`, `2027-01-25`, …

Szczegóły: [`docs/GITHUB_ACTIONS.md`](../docs/GITHUB_ACTIONS.md), [`docs/GOOGLE_DRIVE.md`](../docs/GOOGLE_DRIVE.md).

## Task Scheduler (PC)

```powershell
powershell -ExecutionPolicy Bypass -File "schedule\register_tasks_5_dni.ps1"
```

Rejestruje: pon–pt 18:00 discovery + nd 06:00 backfill (**co tydzień**, bez guarda 42 dni).  
Excel mail + Drive **tylko na GHA** (nd 09:00).

PC backfill (`run_czwartek.ps1`) jest **uproszczony** względem GHA (bez pełnego `--reverify-all-contacts` / run-config w skrypcie).

## Artefakty

```
pon→pi | wt→pi | sro→pi | czw→pi | pt→pi
  → (chain lub nd 06:00) thu
  → nd 09:00 excel email + Drive xlsx
```

Artefakt discovery zawsze: `de-gu-wyniki-pi`.

## Pełny pipeline (GHA, ręcznie)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_full_pipeline_gha.ps1 -SkipDiscovery
```

Pomija pełny Drive sync i send B2B; raport Excel (+ Drive xlsx) idzie workflowem nd 09:00.

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

### Daty uruchomień (GHA)

| Cykl | Pon 18:00 | Wt 18:00 | Śr 18:00 | Czw 18:00 | Pt 18:00 | Nd 06:00 | Nd 09:00 |
|------|-----------|----------|----------|-----------|----------|----------|----------|
| 1 | **2026-09-21** | 2026-09-22 | 2026-09-23 | 2026-09-24 | 2026-09-25 | 2026-09-27 | 2026-09-27 |
| 2 | **2026-11-02** | 2026-11-03 | 2026-11-04 | 2026-11-05 | 2026-11-06 | 2026-11-08 | 2026-11-08 |
| 3 | **2026-12-14** | 2026-12-15 | 2026-12-16 | 2026-12-17 | 2026-12-18 | 2026-12-20 | 2026-12-20 |
| 4 | **2027-01-25** | 2027-01-26 | 2027-01-27 | 2027-01-28 | 2027-01-29 | 2027-01-31 | 2027-01-31 |
| 5 | **2027-03-08** | 2027-03-09 | 2027-03-10 | 2027-03-11 | 2027-03-12 | 2027-03-14 | 2027-03-14 |
| 6 | **2027-04-19** | 2027-04-20 | 2027-04-21 | 2027-04-22 | 2027-04-23 | 2027-04-25 | 2027-04-25 |
| 7 | **2027-05-31** | 2027-06-01 | 2027-06-02 | 2027-06-03 | 2027-06-04 | 2027-06-06 | 2027-06-06 |
| 8 | **2027-07-12** | 2027-07-13 | 2027-07-14 | 2027-07-15 | 2027-07-16 | 2027-07-18 | 2027-07-18 |

Kolejne: `+42 dni` od poniedziałku poprzedniego cyklu. Pełny kalendarz: [`docs/GITHUB_ACTIONS.md`](../docs/GITHUB_ACTIONS.md#kalendarz-uruchomień-gha-europewarsaw).

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

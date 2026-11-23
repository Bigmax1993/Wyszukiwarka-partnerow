# Plan tygodniowy — PL FAS / spedycja (Europe/Warsaw)

Jeden **obrót discovery** = tydzień **cała Polska** (`run_config/pl_fas_spedycja.json` — **16** województw), podzielony na 5 części (pon–pt).  
Rotacja `--rotate-bundesland` (1 województwo / cykl) jest **opcją ręczną**, nie trybem GHA/PC.  
Filtr ICP: [`docs/FILTER_ICP.md`](../docs/FILTER_ICP.md).

**Aktualny tryb GHA:** discovery + backfill + Excel/Drive **oraz** B2B według harmonogramu (pon/wt 09:00 po Excelu).  
Pełny sync Drive (cache/log): **OFF**.

**Cadence GHA:** **co tydzień** od **2026-11-02** (`GU_CADENCE_DAYS=7`).  
**Task Scheduler PC:** discovery/backfill **co tydzień**; B2B send **nie** rejestrowane na PC — patrz [`docs/LOCAL_VS_GHA.md`](../docs/LOCAL_VS_GHA.md).

## Cykl (GHA)

```
co tydzień od 02.11.2026:
pon–pt 18:00 discovery (16 województw, cache między dniami)
→ po pt: chain → backfill  (alternatywa: nd 06:00 cron)
→ nd 09:00 Excel → svinchak1993@gmail.com + Drive (tylko .xlsx)
→ (następny) pon 09:00 B2B partia 1  (guard send_followup)
→ wt 09:00 B2B partia 2
(prep / pełny sync Drive: OFF)
```

## Harmonogram GHA

Joby pipeline i B2B startują **co tydzień** (guard `GU_CADENCE_DAYS=7`).  
Joby **B2B** używają `FAS_GUARD_MODE=send_followup` — aktywne pon/wt tygodnia *po* niedzieli Excel.  
`workflow_dispatch` zawsze omija guard dnia tygodnia.

| Dzień | Godzina (PL) | GitHub Actions | Cron |
|-------|--------------|----------------|------|
| **Poniedziałek** | **18:00** | `PL spedycja discovery` (mon) | `0 18 * * 1` |
| **Wtorek** | **18:00** | `PL spedycja discovery` (tue) | `0 18 * * 2` |
| **Środa** | **18:00** | `PL spedycja discovery` (wed) | `0 18 * * 3` |
| **Czwartek** | **18:00** | `PL spedycja discovery` (thu) | `0 18 * * 4` |
| **Piątek** | **18:00** | `PL spedycja discovery` (fri) → chain backfill | `0 18 * * 5` |
| **Niedziela** | **06:00** | `PL spedycja niedziela backfill` (fallback) | `0 6 * * 0` |
| **Niedziela** | **09:00** | `PL spedycja poniedzialek excel email` (+ Drive xlsx) | `0 9 * * 0` |
| **Poniedziałek** (tydzień **po** Excelu) | **09:00** | `PL spedycja poniedzialek send` (B2B partia 1) | `0 9 * * 1` |
| **Wtorek** (dzień po partii 1) | **09:00** | `PL spedycja wtorek send` (B2B partia 2) | `0 9 * * 2` |

Kolejność B2B: **nd Excel → pon 09:00 send 1 → wt 09:00 send 2** (rano; discovery tego samego poniedzialku jest o 18:00).

| Wyłączone | Status |
|-----------|--------|
| Prep | cron OFF (tylko ręcznie) |
| Pełny Sync Drive | DISABLED |
| Send B2B | **ON** — pon/wt 09:00 (`pl_fas_tue` / `pl_fas_fri`, `send_followup`) |

### Przykład tygodnia

| Discovery | Excel | B2B 1 / 2 |
|-----------|-------|-----------|
| **02–06.11.2026** | **08.11** | **09–10.11** |
| **09–13.11.2026** | **15.11** | **16–17.11** |
| … | … | … (każdy kolejny tydzień) |

Szczegóły: [`docs/GITHUB_ACTIONS.md`](../docs/GITHUB_ACTIONS.md), [`docs/GOOGLE_DRIVE.md`](../docs/GOOGLE_DRIVE.md), [`docs/ROLLBACK_B2B.md`](../docs/ROLLBACK_B2B.md).

## Task Scheduler (PC)

```powershell
powershell -ExecutionPolicy Bypass -File "schedule\register_tasks_5_dni.ps1"
```

Rejestruje taski **`Spedycja_FAS_*`**: pon–pt 18:00 discovery + nd 06:00 backfill (**co tydzień**).  
Przy rejestracji usuwa stare **`Kanbud_GU_*`**. Excel mail + Drive + B2B send **tylko na GHA**.

PC backfill (`run_czwartek.ps1`) jest **uproszczony** względem GHA (bez pełnego `--reverify-all-contacts` / run-config w skrypcie).

## Artefakty

```
pon→pi | wt→pi | sro→pi | czw→pi | pt→pi
  → (chain lub nd 06:00) thu
  → nd 09:00 excel email + Drive xlsx
  → (następny) pon → tue (B2B 1)
  → wt → fri (B2B 2)
```

Artefakt discovery zawsze: `pl-spedycja-wyniki-pi`.

## Pełny pipeline (GHA, ręcznie)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_full_pipeline_gha.ps1 -SkipDiscovery
```

Pomija pełny Drive sync; raport Excel (+ Drive xlsx) idzie workflowem nd 09:00; B2B — osobne workflowy send.

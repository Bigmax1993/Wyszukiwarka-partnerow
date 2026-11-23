# Plan tygodniowy — PL FAS / spedycja (Europe/Warsaw)

Jeden **obrót discovery** = tydzień **cała Polska** (`run_config/pl_fas_spedycja.json` — **16** województw), podzielony na 5 części (pon–pt).  
Rotacja `--rotate-bundesland` (1 województwo / cykl) jest **opcją ręczną**, nie trybem GHA/PC.  
Filtr ICP: [`docs/FILTER_ICP.md`](../docs/FILTER_ICP.md).

**Aktualny tryb GHA:** discovery + backfill + Excel/Drive **oraz** B2B według harmonogramu (pon/wt 09:00 po Excelu).  
Pełny sync Drive (cache/log): **OFF**.

**Cadence GHA:** od **2026-11-02**, potem co **55 dni** (guard; start = poniedziałek markera lub kolejny).  
**Task Scheduler PC:** discovery/backfill **co tydzień** (bez guarda); B2B send **nie** rejestrowane na PC — patrz [`docs/LOCAL_VS_GHA.md`](../docs/LOCAL_VS_GHA.md).

## Cykl (GHA)

```
(pierwszy tydzień discovery: 02–08.11.2026; potem co 55 dni)
pon–pt 18:00 discovery (16 województw, cache między dniami)
→ po pt: chain → backfill  (alternatywa: nd 06:00 cron)
→ nd 09:00 Excel → svinchak1993@gmail.com + Drive (tylko .xlsx)
→ (następny) pon 09:00 B2B partia 1  (guard send_followup)
→ wt 09:00 B2B partia 2
(prep / pełny sync Drive: OFF)
```

## Harmonogram GHA

Cron odpala się co tydzień, ale joby **pipeline** startują tylko gdy guard = active (tydzień cyklu).  
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

Kolejność B2B: **nd Excel → pon 09:00 send 1 → wt 09:00 send 2** (nie w tym samym pon rano co start discovery 18:00).

| Wyłączone | Status |
|-----------|--------|
| Prep | cron OFF (tylko ręcznie) |
| Pełny Sync Drive | DISABLED |
| Send B2B | **ON** — pon/wt 09:00 (`pl_fas_tue` / `pl_fas_fri`, `send_followup`) |

### Daty uruchomień (GHA)

| Cykl | Pon 18:00 | Wt 18:00 | Śr 18:00 | Czw 18:00 | Pt 18:00 | Nd 06:00 | Nd 09:00 |
|------|-----------|----------|----------|-----------|----------|----------|----------|
| hist. | **2026-09-21** | 2026-09-22 | 2026-09-23 | 2026-09-24 | 2026-09-25 | 2026-09-27 | 2026-09-27 |
| 1 | **2026-11-02** | 2026-11-03 | 2026-11-04 | 2026-11-05 | 2026-11-06 | 2026-11-08 | 2026-11-08 |
| 2 | **2026-12-28** | 2026-12-29 | 2026-12-30 | 2026-12-31 | 2027-01-01 | 2027-01-03 | 2027-01-03 |
| 3 | **2027-02-22** | 2027-02-23 | 2027-02-24 | 2027-02-25 | 2027-02-26 | 2027-02-28 | 2027-02-28 |
| 4 | **2027-04-19** | 2027-04-20 | 2027-04-21 | 2027-04-22 | 2027-04-23 | 2027-04-25 | 2027-04-25 |
| 5 | **2027-06-14** | 2027-06-15 | 2027-06-16 | 2027-06-17 | 2027-06-18 | 2027-06-20 | 2027-06-20 |
| 6 | **2027-08-09** | 2027-08-10 | 2027-08-11 | 2027-08-12 | 2027-08-13 | 2027-08-15 | 2027-08-15 |
| 7 | **2027-10-04** | 2027-10-05 | 2027-10-06 | 2027-10-07 | 2027-10-08 | 2027-10-10 | 2027-10-10 |
| 8 | **2027-11-22** | 2027-11-23 | 2027-11-24 | 2027-11-25 | 2027-11-26 | 2027-11-28 | 2027-11-28 |

B2B partia 1/2 = **pon/wt 09:00 tygodnia zaraz po** kolumnie Nd 09:00 (np. cykl 1: Excel 08.11 → send 09–10.11.2026).

Kolejne: marker `+55 dni` od `2026-11-02`, start = poniedziałek markera lub kolejny. Pełny kalendarz: [`docs/GITHUB_ACTIONS.md`](../docs/GITHUB_ACTIONS.md#kalendarz-uruchomień-gha-europewarsaw).

Szczegóły: [`docs/GITHUB_ACTIONS.md`](../docs/GITHUB_ACTIONS.md), [`docs/GOOGLE_DRIVE.md`](../docs/GOOGLE_DRIVE.md), [`docs/ROLLBACK_B2B.md`](../docs/ROLLBACK_B2B.md).

## Task Scheduler (PC)

```powershell
powershell -ExecutionPolicy Bypass -File "schedule\register_tasks_5_dni.ps1"
```

Rejestruje taski **`Spedycja_FAS_*`**: pon–pt 18:00 discovery + nd 06:00 backfill (**co tydzień**, bez guarda 55 dni).  
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

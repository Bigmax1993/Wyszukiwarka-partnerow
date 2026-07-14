# GitHub Actions — kampania GU



Repozytorium: [Wyszukiwarka-partnerow](https://github.com/Bigmax1993/Wyszukiwarka-partnerow)



## Workflowy



| Workflow | Plik | Trigger | Co robi |

|----------|------|---------|---------|

| **Tests** | `tests.yml` | push, PR | `py_compile` + smoke `--test` |

| **CI Deploy** | `ci-deploy.yml` | push | smoke + walidacja secretów + dry-run maili |

| **GU discovery** | `de_gu_pi.yml` | cron, ręcznie | Discovery pon–pt (max 12 h/run) → `de-gu-wyniki-pi` |

| **GU niedziela backfill** | `de_gu_thu.yml` | cron, ręcznie | Backfill + Excel → `de-gu-wyniki-thu` |

| **GU poniedzialek prep** | `de_gu_mon.yml` | cron, ręcznie | Rebuild Excel → `de-gu-wyniki-mon` |

| **GU poniedzialek send** | `de_gu_tue.yml` | cron, ręcznie | Wysyłka partia 1 (do 300) → `de-gu-wyniki-tue` |

| **GU wtorek send** | `de_gu_fri.yml` | cron, ręcznie | Wysyłka partia 2 → `de-gu-wyniki-fri` |

| **Sync wyniki Google Drive** | `sync-google-drive.yml` | cron pon 06:00 PL, ręcznie | Upload `Wyniki/` na Drive |



## Harmonogram cron (Europe/Warsaw)

**Tymczasowo włączony na GitHub Actions** w oknie **14.07–21.07.2026** (cron + warunek daty w `jobs.*.if`). Po 21.07 harmonogram GHA pomija joby (uruchomienia `workflow_dispatch` i łańcuchy `gha_chain_workflow.sh` nadal działają). Poza tym oknem — lokalnie: `schedule/register_tasks_5_dni.ps1`.

Harmonogram (Europe/Warsaw):



| Dzień | Workflow | Cron | Godzina PL |
|-------|----------|------|------------|
| **Poniedziałek** | discovery część 1 | `0 17 * * 1` | **17:00** |
| **Wtorek** | discovery część 2 | `0 15 * * 2` | **15:00** |
| **Środa** | discovery część 3 | `0 19 * * 3` | **19:00** |
| **Czwartek** | discovery część 4 | `0 20 * * 4` | **20:00** |
| **Piątek** | discovery część 5 | `0 16 * * 5` | **16:00** |
| **Niedziela** | backfill | `30 5 * * 0` | **05:30** |
| **Poniedziałek** | sync Drive | `0 6 * * 1` | **06:00** |
| **Poniedziałek** | prep | `0 7 * * 1` | **07:00** |
| **Poniedziałek** | send 1 | `0 9 * * 1` | **09:00** |
| **Wtorek** | send 2 | `0 9 * * 2` | **09:00** |



Wysyłka w oknie **8–18** czasu berlińskiego (bez `DISABLE_SEND_WINDOW` w workflowach send).



## Sekrety



| Secret | Wymagany | Opis |

|--------|----------|------|

| `SERPER_API_KEY` | discovery | API Serper |

| `ANTHROPIC_API_KEY` | discovery + backfill | Claude API |

Modele Claude (domyślnie w kodzie, opcjonalnie env):

| Zadanie | Tier | Domyślny model | Env |
|---------|------|----------------|-----|
| Frazy Serper, cleanup Excel | `fast` | `claude-haiku-4-5` | `CLAUDE_MODEL_FAST` |
| Weryfikacja www, wyciąganie maili | `verify` | `claude-sonnet-4-6` | `CLAUDE_MODEL_VERIFY` (lub legacy `CLAUDE_MODEL`) |

Setup OAuth: `python scripts/gdrive_oauth_setup.py` — szczegóły w [`GOOGLE_DRIVE.md`](GOOGLE_DRIVE.md).



## Artifacty



```

pon→pi | wt→pi | sro→pi | czw→pi | pt→pi → niedziela→thu → sync Drive → pon prep→mon → pon send→tue → wt send→fri

```



Poniedziałek 17:00 (discovery): `de-gu-wyniki-fri` → `de-gu-wyniki-pi` (nowy tydzień). Wtorek–piątek: kontynuacja z `pi`. Niedziela backfill: najnowszy `de-gu-wyniki-pi` (piątek). Poniedziałek rano: prep (07:00) przed wysyłką (09:00); wieczorem (17:00) start kolejnego tygodnia discovery.

**Sync Drive** (pon 06:00 PL) pobiera **`de-gu-wyniki-thu`** z niedzielnego backfillu — kolejność: `thu` → `mon` → `tue` → `fri`. Nie używa `fri`/`tue` z poprzedniej wysyłki, dopóki istnieje `thu`.



## Załącznik PPTX na runnerze



Workflowy send ustawiają:



`MFG_EMAIL_ATTACHMENT_PATH=assets/campaign/MFG_Referenzliste_Einzelhandel.pptx`



Przed wysyłką workflow **pobiera świeży PPTX** ze Slides (`scripts/export_mfg_slides_attachment.py`).  
Źródło: [Google Slides MFG](https://docs.google.com/presentation/d/1kBnp5x0pdgXZSPzVte9e92IUgn2A5gSe/edit) (OAuth `GDRIVE_OAUTH_*` na GHA).



## Ręczne uruchomienie



Pełny cykl (PC, czeka na każdy krok). Przy **timeout 720 min** discovery (status failure) skrypt **kontynuuje**, jeśli run zapisał artefakt `de-gu-wyniki-pi` (`-StrictDiscovery` = stare zachowanie, przerwij):



```powershell

powershell -ExecutionPolicy Bypass -File scripts\run_full_pipeline_gha.ps1 -ForceResend

```



Pojedyncze kroki (`gh`):



```powershell

gh workflow run "GU discovery" -R Bigmax1993/Wyszukiwarka-partnerow
gh workflow run "GU discovery" -R Bigmax1993/Wyszukiwarka-partnerow -f discovery_phase=mon
gh workflow run "GU discovery" -R Bigmax1993/Wyszukiwarka-partnerow -f discovery_phase=tue
gh workflow run "GU discovery" -R Bigmax1993/Wyszukiwarka-partnerow -f discovery_phase=wed
gh workflow run "GU discovery" -R Bigmax1993/Wyszukiwarka-partnerow -f discovery_phase=thu
gh workflow run "GU discovery" -R Bigmax1993/Wyszukiwarka-partnerow -f discovery_phase=fri
gh workflow run "GU discovery" -R Bigmax1993/Wyszukiwarka-partnerow -f resume_artifact_run_id=RUN_ID

gh workflow run "GU niedziela backfill" -R Bigmax1993/Wyszukiwarka-partnerow

gh workflow run "Sync wyniki Google Drive" -R Bigmax1993/Wyszukiwarka-partnerow

gh workflow run "GU poniedzialek prep" -R Bigmax1993/Wyszukiwarka-partnerow

gh workflow run "GU poniedzialek send" -R Bigmax1993/Wyszukiwarka-partnerow -f force_resend=true

gh workflow run "GU wtorek send" -R Bigmax1993/Wyszukiwarka-partnerow -f force_resend=true

```



Kolejność: discovery (pon–pt) → backfill → sync Drive → prep → pon send → wt send.

Po piątkowym discovery (ręcznie):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\resume_pipeline_after_pi.ps1 -PiRunId RUN_ID
```



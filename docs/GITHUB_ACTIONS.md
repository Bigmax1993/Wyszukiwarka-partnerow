# GitHub Actions — kampania GU

Repozytorium: [Wyszukiwarka-partnerow](https://github.com/Bigmax1993/Wyszukiwarka-partnerow)

## Pipeline automatyczny (3 kroki)

```
sobota discovery → niedziela backfill → pon 04:30 excel email → pon 08:00 prep
```

**Bez** kampanii MFG (home.pl) i **bez** sync Google Drive.

## Workflowy

| Workflow | Plik | Trigger | Co robi |
|----------|------|---------|---------|
| **Tests** | `tests.yml` | push, PR | unit + integracja + regresja + API live (Serper, Anthropic) |
| **CI Deploy** | `ci-deploy.yml` | push | smoke + walidacja `SERPER_API_KEY` |
| **GU sobota discovery** | `de_gu_wed.yml` | cron, ręcznie | Rotacja 1 Bundesland → `de-gu-wyniki-wed` |
| **GU niedziela backfill** | `de_gu_thu.yml` | cron, ręcznie | Verify + backfill + Excel → `de-gu-wyniki-thu` |
| **GU poniedzialek prep** | `de_gu_mon.yml` | cron, ręcznie | Rebuild Excel → `de-gu-wyniki-mon` |
| **GU poniedzialek excel email** | `de_gu_mon_excel_email.yml` | cron, ręcznie | Excel na Gmail (04:30 PL) |

### Poza automatycznym pipeline (tylko ręcznie)

| Workflow | Plik | Opis |
|----------|------|------|
| **GU poniedzialek send** | `de_gu_tue.yml` | Wysyłka maili partia 1 (wyłączone z crona) |
| **GU wtorek send** | `de_gu_fri.yml` | Wysyłka maili partia 2 (wyłączone z crona) |
| **Sync wyniki Google Drive** | `sync-google-drive.yml` | Upload `Wyniki/` (wyłączone z crona) |

## Harmonogram cron (UTC → czas PL, CEST)

| Dzień | Workflow | Cron UTC | ≈ czas PL |
|-------|----------|----------|-----------|
| **Sobota** | discovery | `10 18 * * 6` | **20:10** |
| **Niedziela** | backfill | `30 3 * * 0` | **05:30** |
| **Poniedziałek** | excel email | `30 2 * * 1` | **04:30** |
| **Poniedziałek** | prep | `0 6 * * 1` | **08:00** |

Zimą (CET): discovery `10 19 * * 6`.

## Sekrety

| Secret | Wymagany | Opis |
|--------|----------|------|
| `SERPER_API_KEY` | tak (discovery) | API Serper |
| `ANTHROPIC_API_KEY` | tak (verify/backfill) | Claude API |
| `MAIL_USER`, `MAIL_PASSWORD` | tak (pon excel) | Gmail + hasło aplikacji |
| `EXCEL_REPORT_TO` | opcjonalny | Domyślnie `svinchak1993@gmail.com` |

## Artifacty

```
sobota → wed → niedziela → thu → pon prep → mon
```

Sobota discovery kumuluje cache z `de-gu-wyniki-mon` (fallback: `de-gu-wyniki-fri`).

## Ręczne uruchomienie

Pełny cykl automatyczny (z raportem Excel Gmail):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_full_pipeline_gha.ps1
```

Pojedyncze kroki (`gh`):

```powershell
gh workflow run "GU sobota discovery" -R Bigmax1993/Wyszukiwarka-partnerow
gh workflow run "GU niedziela backfill" -R Bigmax1993/Wyszukiwarka-partnerow
gh workflow run "GU poniedzialek prep" -R Bigmax1993/Wyszukiwarka-partnerow
gh workflow run "GU poniedzialek excel email" -R Bigmax1993/Wyszukiwarka-partnerow
gh workflow run "GU poniedzialek excel email" -R Bigmax1993/Wyszukiwarka-partnerow -f dry_run=true
```

Opcjonalnie (poza pipeline):

```powershell
gh workflow run "GU poniedzialek send" -R Bigmax1993/Wyszukiwarka-partnerow -f force_resend=true
gh workflow run "GU wtorek send" -R Bigmax1993/Wyszukiwarka-partnerow -f force_resend=true
gh workflow run "Sync wyniki Google Drive" -R Bigmax1993/Wyszukiwarka-partnerow
```


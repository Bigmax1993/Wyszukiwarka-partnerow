# GitHub Actions — kampania GU

Repozytorium: [Wyszukiwarka-partnerow](https://github.com/Bigmax1993/Wyszukiwarka-partnerow)

## Workflowy

| Workflow | Plik | Trigger | Co robi |
|----------|------|---------|---------|
| **GU sobota discovery** | `de_gu_wed.yml` | cron, ręcznie | Rotacja 1 Bundesland → `de-gu-wyniki-wed` |
| **GU niedziela backfill** | `de_gu_thu.yml` | cron, ręcznie | Backfill + Excel → `de-gu-wyniki-thu` |
| **GU poniedzialek prep** | `de_gu_mon.yml` | cron, ręcznie | Rebuild Excel → `de-gu-wyniki-mon` |
| **GU poniedzialek send** | `de_gu_tue.yml` | cron, ręcznie | Wysyłka partia 1 → `de-gu-wyniki-tue` |
| **GU wtorek send** | `de_gu_fri.yml` | cron, ręcznie | Wysyłka partia 2 → `de-gu-wyniki-fri` |
| **Sync wyniki Google Drive** | `sync-google-drive.yml` | po wtorku, cron wt 12:00 UTC | Upload na Drive |

## Harmonogram cron (UTC → czas PL, CEST)

| Dzień | Workflow | Cron UTC | ≈ czas PL |
|-------|----------|----------|-----------|
| **Sobota** | discovery | `10 18 * * 6` | **20:10** |
| **Niedziela** | backfill | `30 3 * * 0` | **05:30** |
| **Poniedziałek** | prep | `0 6 * * 1` | **08:00** |
| **Poniedziałek** | send 1 | `0 10 * * 1` | **12:00** |
| **Wtorek** | send 2 | `0 7 * * 2` | **09:00** |
| **Wtorek** | sync Drive | `0 12 * * 2` | 14:00 |

Zimą (CET): discovery `10 19 * * 6`, send 1 `0 11 * * 1`.

## Artifacty

```
sobota → wed → niedziela → thu → pon prep → mon → pon send → tue → wt send → fri
```

## Ręczne uruchomienie

```powershell
gh workflow run "GU poniedzialek send" -R Bigmax1993/Wyszukiwarka-partnerow
gh workflow run "GU wtorek send" -R Bigmax1993/Wyszukiwarka-partnerow
```

Kolejność: discovery → backfill → prep → pon send → wt send → sync Drive.

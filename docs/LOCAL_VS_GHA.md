# PC (Task Scheduler) vs GitHub Actions

Krótka mapa różnic — żeby nie mieszać cadence i zakresów jobów.

## Cadence

| | GitHub Actions | PC (`register_tasks_5_dni.ps1`) |
|--|----------------|----------------------------------|
| Godziny | pon–pt 18:00, nd 06:00 (+ nd 09:00 Excel) | pon–pt 18:00, nd 06:00 |
| Okres | **co 42 dni** od `2026-09-21` (guard) | **co tydzień** (bez guarda) |
| Excel Gmail + Drive xlsx | **nd 09:00** (tylko GHA) | **brak** — nie rejestrowane |

Obowiązujące godziny PC bierze `register_tasks_5_dni.ps1`. Komentarze w nagłówkach `schedule/run_*_discovery.ps1` mogą być historyczne.

## Discovery

| | GHA | PC |
|--|-----|-----|
| Config | `run_config/mfg_gu_de.json` (16 landów) | to samo |
| Flagi | `--serper-only-discovery` (+ `--respect-cache` w kontynuacji) | to samo w `run_*_discovery.ps1` |
| Rotacja 1 land | **nie** | **nie** (tylko ręczne `--rotate-bundesland`) |
| Wyniki | artefakt `de-gu-wyniki-pi` | lokalny `Wyniki/` |

## Backfill

| | GHA (`de_gu_thu.yml`) | PC (`schedule/run_czwartek.ps1`) |
|--|----------------------|----------------------------------|
| Kiedy | chain zaraz po **pt discovery** + cron nd 06:00 | nd 06:00 Task Scheduler |
| Zakres | `--verify-pending-contacts --reverify-all-contacts` + `--run-config mfg_gu_de.json` | uproszczony: `--verify-pending-contacts` (bez pełnego reverify / bez run-config w skrypcie) |
| Artefakt | `de-gu-wyniki-thu` | lokalny `Wyniki/` |

Nazwa pliku `run_czwartek.ps1` jest legacy — to **niedzielny backfill**, nie discovery czwartku (`run_czwartek_discovery.ps1`).

## Maile / Drive

| Funkcja | GHA | PC |
|---------|-----|-----|
| Raport Excel → Gmail | nd 09:00 ON | ręcznie: `scripts/send_excel_gmail.py` |
| Upload końcowego `.xlsx` | nd 09:00 ON (`GDRIVE_FOLDER_ID`) | lokalnie przy `DISABLE_GOOGLE_DRIVE=0` |
| Pełny sync `Wyniki/` | OFF | OFF (domyślnie) |
| Send B2B | OFF (`if: false`) | OFF (`DISABLE_CONTRACTOR_EMAILS=1`) |

## Kiedy używać czego

- **Produkcja kampanii / cadence 6 tyg.:** GHA (guard + artefakty + Excel/Drive).
- **Dev / częstsze testy:** PC Task Scheduler lub ręczne `python … --run-config …`.
- **Nie zakładaj**, że PC „sam” ograniczy się do tygodnia cyklu GHA — trzeba to wyłączyć / nie rejestrować zadań poza cyklem.

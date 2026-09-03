# Google Drive — wyniki kampanii GU

> **INTEGRACJA WYŁĄCZONA** — wyniki tylko lokalnie (`Wyniki/`) / artefakty GitHub Actions.
> Kill-switch: `DISABLE_GOOGLE_DRIVE=1` (domyślnie). Rollback: ustaw `DISABLE_GOOGLE_DRIVE=0`
> i włącz ponownie workflowy `sync-google-drive.yml` / `sync-week-discovery-drive.yml`
> (usuń `if: false`).

Folder w chmurze (gdy włączysz ponownie): [GU Bauunternehmen](https://drive.google.com/drive/folders/1tP8oUi72t4EHDbE9GnHFdvfNtNsJe4xf)

ID folderu: `1tP8oUi72t4EHDbE9GnHFdvfNtNsJe4xf`

## Co trafia na Drive (gdy włączone)

| Plik / folder | Opis |
|---------------|------|
| `de_gu_bauunternehmen_cache.json` | Cache |
| `de_gu_bauunternehmen_kontakte.xlsx` | Excel |
| `de_gu_bauunternehmen_scraper.log` | Log |
| `wyslane/*.eml` | Kopie wysłanych maili |

## Sposoby uploadu (wymaga `DISABLE_GOOGLE_DRIVE=0`)

| Sposób | Kiedy |
|--------|--------|
| **GitHub Actions** | Workflow `Sync wyniki Google Drive` (obecnie DISABLED) |
| **Lokalnie** | `python scripts/gdrive_upload_wyniki.py --campaign-dir .` (NO-OP gdy flaga=1) |
| **PC + Drive for desktop** | `KANBUD_GOOGLE_DRIVE_GU_PATH` — ignorowane przy fladze=1 |

## Stała reguła sync — obecnie OFF

| Reguła | Wartość |
|--------|---------|
| **Status** | **DISABLED** (`if: false` w YAML) |
| **Kiedy (gdy ON)** | Poniedziałek 06:00 Europe/Warsaw |
| **Źródło** | Artefakt `de-gu-wyniki-thu` |

## Zmienne

| Zmienna | Opis |
|---------|------|
| `DISABLE_GOOGLE_DRIVE` | `1` (domyślnie) = ZERO Drive API / sync |
| `GDRIVE_SERVICE_ACCOUNT_JSON` | JSON konta usługi |
| `GDRIVE_SERVICE_ACCOUNT_FILE` | Ścieżka do JSON lokalnie |
| `GDRIVE_FOLDER_ID` | ID folderu GU |
| `KANBUD_GOOGLE_DRIVE_GU_PATH` | Drive for desktop (ignorowane gdy OFF) |

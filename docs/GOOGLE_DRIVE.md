# Google Drive — wyniki kampanii GU

> **INTEGRACJA WYŁĄCZONA** — wyniki tylko lokalnie (`Wyniki/`) / artefakty GitHub Actions.
>
> Kill-switch: `DISABLE_GOOGLE_DRIVE=1` (domyślnie).  
> Rollback: `DISABLE_GOOGLE_DRIVE=0` + usuń `if: false` w  
> `sync-google-drive.yml` / `sync-week-discovery-drive.yml`.

Folder w chmurze (gdy włączysz ponownie): [GU Bauunternehmen](https://drive.google.com/drive/folders/1tP8oUi72t4EHDbE9GnHFdvfNtNsJe4xf)

ID folderu: `1tP8oUi72t4EHDbE9GnHFdvfNtNsJe4xf`

## Stan discovery-only

| Element | Status |
|---------|--------|
| Upload z GHA | **DISABLED** (`if: false`) |
| `scripts/gdrive_upload_wyniki.py` | NO-OP przy fladze=1 |
| `scripts/upload_wyniki_to_drive.ps1` | NO-OP przy fladze=1 |
| `KANBUD_GOOGLE_DRIVE_GU_PATH` | ignorowane — zapis do lokalnego `Wyniki/` |
| Pobranie PPTX ze Slides | pomijane (`mfg_gu_email_attachment.py`) |

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
| **Lokalnie** | `python scripts/gdrive_upload_wyniki.py --campaign-dir .` |
| **PC + Drive for desktop** | `KANBUD_GOOGLE_DRIVE_GU_PATH` |

## Stała reguła sync — obecnie OFF

| Reguła | Wartość |
|--------|---------|
| **Status** | **DISABLED** |
| **Kiedy (gdy ON)** | Poniedziałek 06:00 Europe/Warsaw |
| **Źródło** | Artefakt `de-gu-wyniki-thu` (fallback: mon → tue → fri) |

## Zmienne

| Zmienna | Opis |
|---------|------|
| `DISABLE_GOOGLE_DRIVE` | `1` (domyślnie) = ZERO Drive API / sync |
| `GDRIVE_SERVICE_ACCOUNT_JSON` | JSON konta usługi |
| `GDRIVE_SERVICE_ACCOUNT_FILE` | Ścieżka do JSON lokalnie |
| `GDRIVE_FOLDER_ID` | ID folderu GU |
| `GDRIVE_OAUTH_*` | OAuth Desktop (upload na „Mój dysk”) |
| `KANBUD_GOOGLE_DRIVE_GU_PATH` | Drive for desktop (ignorowane gdy OFF) |
| `KANBUD_DATA_DIR` | Lokalny katalog danych (działa także przy Drive OFF) |

Setup OAuth (tylko po rollbacku): `python scripts/gdrive_oauth_setup.py`

# Google Drive — wyniki kampanii GU

## Stan aktualny

| Element | Status |
|---------|--------|
| Pełny sync `Wyniki/` (cache, log, `wyslane`) | **DISABLED** (`sync-google-drive.yml` / `sync-week-discovery-drive.yml` — `if: false` / `DISABLE_GOOGLE_DRIVE=1`) |
| Końcowy Excel po raporcie Gmail | **WŁĄCZONY** — `GU poniedzialek excel email` (nd 09:00 w tygodniu cyklu) |
| Lokalny kill-switch | `DISABLE_GOOGLE_DRIVE=1` (domyślnie); krok Excel→Drive ustawia `0` tylko dla `.xlsx` |

## Foldery

| Folder | ID | Użycie |
|--------|-----|--------|
| [GU Bauunternehmen](https://drive.google.com/drive/folders/1tP8oUi72t4EHDbE9GnHFdvfNtNsJe4xf) | `1tP8oUi72t4EHDbE9GnHFdvfNtNsJe4xf` | Domyślny GU (pełny sync / lokalnie / hardcoded w disabled workflowach) |
| Folder raportu Excel | secret `GDRIVE_FOLDER_ID` (komentarz YAML: `1JMPyphoNX_oS_EjW7LEhf103lvvtsMUL`) | Upload końcowego `de_gu_bauunternehmen_kontakte.xlsx` z nd 09:00 |

## Co trafia na Drive dziś

| Plik | Kiedy |
|------|--------|
| `de_gu_bauunternehmen_kontakte.xlsx` | Niedziela 09:00 (cykl 6-tyg.) — po Gmail, bez `dry_run` |

Cache, logi i `wyslane/` **nie** są uploadowane w tym trybie (zostają w artefaktach GHA).

## Pełny sync (OFF — rollback)

Gdy włączysz ponownie `sync-google-drive.yml`:

| Reguła | Wartość |
|--------|---------|
| Cron (gdy ON) | Poniedziałek 06:00 Europe/Warsaw (historycznie) |
| Źródło | `de-gu-wyniki-thu` |
| Fallback | `thu` → `wed` → `mon` → `tue` → `fri` |
| Folder | `1tP8oUi72t4EHDbE9GnHFdvfNtNsJe4xf` |
| Zakres | cały `Wyniki/` + opcjonalnie `wyslane/` |

Rollback: `DISABLE_GOOGLE_DRIVE=0` + usuń `if: false` w workflowach sync.

## Sposoby uploadu

| Sposób | Status |
|--------|--------|
| **GHA — excel email** | **ON** — tylko `.xlsx` → `secrets.GDRIVE_FOLDER_ID` |
| **GHA — Sync wyniki Google Drive** | DISABLED |
| **Lokalnie** | `python scripts/gdrive_upload_wyniki.py --campaign-dir .` (wymaga `DISABLE_GOOGLE_DRIVE=0`) |
| **PC + Drive for desktop** | `KANBUD_GOOGLE_DRIVE_GU_PATH` (ignorowane gdy flaga=1) |

## Zmienne / secrets

| Zmienna | Opis |
|---------|------|
| `DISABLE_GOOGLE_DRIVE` | `1` = zero Drive poza jawnym override w kroku Excel |
| `GDRIVE_FOLDER_ID` | Folder docelowy (secret wymagany dla nd 09:00) |
| `GDRIVE_OAUTH_*` | OAuth Desktop — wymagane dla nd 09:00 |
| `GDRIVE_SERVICE_ACCOUNT_JSON` / `_FILE` | Shared Drive / lokalnie |
| `GDRIVE_VERSION_XLSX` | Wersjonowanie xlsx (excel step: `0`) |
| `KANBUD_GOOGLE_DRIVE_GU_PATH` | Drive for desktop |
| `KANBUD_DATA_DIR` | Lokalny katalog danych |

Setup OAuth: `python scripts/gdrive_oauth_setup.py`

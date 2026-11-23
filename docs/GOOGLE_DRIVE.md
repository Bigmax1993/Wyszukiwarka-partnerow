# Google Drive — kampania PL spedycja (Forwarding Assistant)

## Stan aktualny

| Element | Status |
|---------|--------|
| Cache JSON + log | **tylko lokalnie w repo** (`Wyniki/`) — `pl_spedycja_data_paths.resolve_data_root` **nie** kieruje na Drive |
| Pełny sync `Wyniki/` | **DISABLED** (`if: false` + `DISABLE_GOOGLE_DRIVE=1`) |
| Końcowy Excel kontaktów | **WŁĄCZONY** — nd 09:00 (tydzień cyklu GHA) → folder poniżej |
| Załączniki maila B2B | **2 pliki** Drive (oferta + prezentacja) — pobierane przy GHA send / `export_fas_email_attachment.py` |
| Kill-switch | `DISABLE_GOOGLE_DRIVE=1` (domyślnie); krok Excel→Drive ustawia `0` tylko na upload `.xlsx` |

## Foldery / pliki Drive

| Cel | Link / ID | Użycie |
|-----|-----------|--------|
| **Końcowy Excel kontaktów** | [`1bRCAqle6BS46YEw0fScq4P095LsJUSgL`](https://drive.google.com/drive/folders/1bRCAqle6BS46YEw0fScq4P095LsJUSgL?usp=drive_link) | Upload `pl_spedycja_kontakte.xlsx` (nd 09:00). Secret GHA: `GDRIVE_FOLDER_ID`. Default w `pl_spedycja_data_paths.GOOGLE_DRIVE_FAS_FOLDER_ID` (alias legacy: `GOOGLE_DRIVE_GU_*`). |
| **Załącznik 1 — oferta** | [`1t6m-M49t4w0RuLzc8rWebwjldLUMMRW3`](https://drive.google.com/file/d/1t6m-M49t4w0RuLzc8rWebwjldLUMMRW3/view?usp=drive_link) | Oferta FAS — `EMAIL_ATTACHMENT_DRIVE_FILE_ID`. Lokalnie: `FAS_zalacznik_kampania.pptx`. |
| **Załącznik 2 — prezentacja** | [`164qbEQOTyO8VTgfZr2wtIVTY-zttk6u7`](https://drive.google.com/file/d/164qbEQOTyO8VTgfZr2wtIVTY-zttk6u7/view?usp=drive_link) | Dodatkowa prezentacja w mailach B2B — `EMAIL_ATTACHMENT_EXTRA_DRIVE_FILE_ID`. Lokalnie: `FAS_prezentacja.pptx`. |

## Co trafia na Drive dziś

| Plik | Kiedy |
|------|--------|
| `pl_spedycja_kontakte.xlsx` | Niedziela 09:00 (cykl GHA) — po raporcie Gmail, bez `dry_run` |

**Nie** na Drive: `pl_spedycja_cache.json`, logi, `wyslane/` (lokalnie / artefakty GHA).

## Lokalne ścieżki (repo)

| Plik | Ścieżka |
|------|---------|
| Cache | `Wyniki/pl_spedycja_cache.json` |
| Log | `Wyniki/pl_spedycja_scraper.log` |
| Excel (lokalny append) | `Wyniki/pl_spedycja_kontakte.xlsx` |
| Oferta B2B (cache) | `Wyniki/FAS_zalacznik_kampania.pptx` (lub `assets/campaign/`) |
| Prezentacja B2B (cache) | `Wyniki/FAS_prezentacja.pptx` (lub `assets/campaign/`) |

`Wyniki/` jest w `.gitignore` — na GitHubie zwykle artefakty workflow, nie commit.

## Pełny sync (OFF — rollback)

Gdy włączysz `sync-google-drive.yml`:

| Reguła | Wartość |
|--------|---------|
| Trigger dziś | tylko `workflow_dispatch` |
| Źródło | `pl-spedycja-wyniki-thu` (+ fallbacki) |
| Folder | ten sam co Excel: `1bRCAq…` |
| Zakres | cały `Wyniki/` + opcjonalnie `wyslane/` |

Rollback: `DISABLE_GOOGLE_DRIVE=0` + usuń `if: false` (+ opcjonalnie `schedule`).

## Sposoby uploadu

| Sposób | Status |
|--------|--------|
| **GHA — excel email** | **ON** — tylko `.xlsx` → `secrets.GDRIVE_FOLDER_ID` = `1bRCAq…` |
| **GHA — Sync wyniki** | DISABLED |
| **GHA — reprocess** | ręcznie; ten sam folder Excela; wymaga `DISABLE_GOOGLE_DRIVE=0` w kroku |
| **Lokalnie** | `python scripts/gdrive_upload_wyniki.py --campaign-dir .` (wymaga `DISABLE_GOOGLE_DRIVE=0`) |

## Zmienne / secrets

| Zmienna | Opis |
|---------|------|
| `DISABLE_GOOGLE_DRIVE` | `1` = brak Drive poza jawnym krokiem Excel |
| `GDRIVE_FOLDER_ID` | **musi** być `1bRCAqle6BS46YEw0fScq4P095LsJUSgL` (nd 09:00) |
| `GDRIVE_OAUTH_*` | OAuth — upload Excela / pobranie oferty+prezentacji |
| `GDRIVE_SERVICE_ACCOUNT_JSON` / `_FILE` | opcjonalnie (pełny sync OFF) |
| `KANBUD_DATA_DIR` | opcjonalny lokalny root (nie folder Drive) |
| `FAS_EMAIL_ATTACHMENT_PATH` | lokalna **oferta** zamiast Drive (preferowany) |
| `FAS_EMAIL_ATTACHMENT_EXTRA_PATH` | lokalna **prezentacja** (plik 2) |
| `MFG_EMAIL_ATTACHMENT_PATH` | alias legacy oferty (nadal działa) |
| `KANBUD_GOOGLE_DRIVE_FAS_PATH` | opcjonalny (PC schedule); `resolve_data_root` i tak ignoruje Drive env |

Setup OAuth: `python scripts/gdrive_oauth_setup.py`

Testy / debug ścieżek:

```powershell
python -m pytest tests/unit/test_pl_spedycja_data_paths.py tests/unit/test_pl_fas_email_attachment.py -q
python pl_spedycja_data_paths.py .
```

API live (folder Excela + załączniki B2B + Gmail SMTP/IMAP — wymaga sekretów):

```powershell
python -m pytest tests/integration/test_gmail_gdrive_api.py -m api_live -v --tb=short
```

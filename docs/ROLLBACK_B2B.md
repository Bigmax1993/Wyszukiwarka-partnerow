# Rollback — włączenie maili B2B (MFG)

Aktualnie SMTP do kontrahentów jest **OFF**. Ten checklist przywraca wysyłkę bez zakładania, że „wystarczy przywrócić schedule” — workflowy send mają dziś tylko `workflow_dispatch` i joby z `if: false`.

## 1. Flagi środowiska

- Lokalnie / secrets GHA: `DISABLE_CONTRACTOR_EMAILS=0`
- Upewnij się, że masz SMTP: `MAIL_USER`, `MAIL_PASSWORD` (oraz opcjonalnie `MAIL_CC`, `MAIL_SENDER_NAME`)
- Okno wysyłki: na GHA zwykle `DISABLE_SEND_WINDOW=1`

## 2. Workflowy send

Pliki:

- `.github/workflows/de_gu_tue.yml` — **GU poniedzialek send** (partia 1)
- `.github/workflows/de_gu_fri.yml` — **GU wtorek send** (partia 2)

Kroki:

1. Usuń `if: false` z jobów send.
2. (Opcjonalnie) dodaj `schedule:` / chain z discovery — dziś go **nie ma** do „przywrócenia”; trzeba dodać od zera albo odpalać `gh workflow run`.
3. Sprawdź sekrety SMTP/IMAP wymagane przez YAML (często `MAIL_*`; nie mylić z samym raportem Excel).

## 3. Treść i załącznik

- Treść DE: `mfg_gu_inquiry_email_de.py`
- PPTX lokalny: `assets/campaign/MFG_Referenzliste_Einzelhandel.pptx`
- Źródło Slides: [MFG Referenzliste](https://docs.google.com/presentation/d/1kBnp5x0pdgXZSPzVte9e92IUgn2A5gSe/edit)
- Cc: **tylko** z `MAIL_CC` — bez automatycznego `office@mfg-fliesen.de`

## 4. Test przed produkcją

```powershell
$env:KANBUD_PROJECT_ROOT = "$PWD\libs"
$env:DISABLE_CONTRACTOR_EMAILS = "0"

python de_gu_bauunternehmen_scraper.py --dry-run-email --send-emails-only
```

Potem mała partia ręcznie (`workflow_dispatch` lub lokalnie `--send-emails-only`) zanim włączysz cron/chain.

## 5. Pełny Drive (osobna decyzja)

Maile B2B ≠ pełny sync Drive. Sync `Wyniki/`:

- `DISABLE_GOOGLE_DRIVE=0`
- usuń `if: false` w `sync-google-drive.yml` / `sync-week-discovery-drive.yml`
- szczegóły: [`GOOGLE_DRIVE.md`](GOOGLE_DRIVE.md)

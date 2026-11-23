# B2B maile — stan i wyłączenie (PL FAS)

## Stan aktualny (GHA)

Wysyłka B2B jest **włączona na GitHub Actions** według kolejności tygodnia cyklu (guard **co tydzień**):

| Krok | Kiedy (Europe/Warsaw) | Workflow |
|------|----------------------|----------|
| Discovery | pon–pt 18:00 | `pl_fas_pi.yml` |
| Backfill | pt chain / nd 06:00 | `pl_fas_thu.yml` |
| Excel + Drive xlsx | nd 09:00 | `pl_fas_mon_excel_email.yml` |
| **Send partia 1** | **pon 09:00** (rano, tydzień po Excelu) | `pl_fas_tue.yml` + `FAS_GUARD_MODE=send_followup` |
| **Send partia 2** | **wt 09:00** | `pl_fas_fri.yml` + `FAS_GUARD_MODE=send_followup` |

Lokalnie / PC: domyślnie nadal OFF (`DISABLE_CONTRACTOR_EMAILS=1` w `.env`).

## Wyłączenie B2B (rollback OFF)

1. W `pl_fas_tue.yml` i `pl_fas_fri.yml`: ustaw `DISABLE_CONTRACTOR_EMAILS: "1"` **oraz** `if: false` na jobach `guard`/`send` (albo usuń `schedule:`).
2. W UI Actions ewentualnie Disable workflow.
3. Lokalnie: zostaw `DISABLE_CONTRACTOR_EMAILS=1`.

## Wymagane sekrety (send ON)

- `MAIL_USER`, `MAIL_PASSWORD` (SMTP)
- `GDRIVE_OAUTH_*` (pobranie **obu** PPTX) albo pliki w `assets/campaign/`
- Enable workflowów send w UI, jeśli były `disabled_manually`

## Treść i załączniki

- Treść: `fas_spedycja_inquiry_email_pl.py`
- Załączniki (oba w każdym mailu B2B):
  - oferta [`1t6m-M49…`](https://drive.google.com/file/d/1t6m-M49t4w0RuLzc8rWebwjldLUMMRW3/view?usp=drive_link) → `FAS_zalacznik_kampania.pptx`
  - prezentacja [`164qbEQO…`](https://drive.google.com/file/d/164qbEQOTyO8VTgfZr2wtIVTY-zttk6u7/view?usp=drive_link) → `FAS_prezentacja.pptx`
- Moduł: `pl_fas_email_attachment.ensure_fas_email_attachments`
- Eksport: `python scripts/export_fas_email_attachment.py`
- Cc: `svinchak1993@gmail.com` (`FAS_OFFICE_CC_EMAIL`) + opcjonalne `MAIL_CC`

## Test ręczny

```powershell
$env:DISABLE_CONTRACTOR_EMAILS = "0"
python pl_fas_spedycja_scraper.py --dry-run-email --send-emails-only
```

Albo Actions → **PL spedycja poniedzialek send** → `workflow_dispatch`.

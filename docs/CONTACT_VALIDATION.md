# Walidacja kontaktu 1:1 — Excel / gap-fill / Claude cleanup

Stan na **2026-11-26**. Kod: `pl_fas_spedycja_scraper.py`, `gap_fill_serper.py`, `claude_prompts.py`, `claude_row_cleanup.py`, `pl_spedycja_filter.py`.

---

## Bramka Excel (Kontakte)

Do arkusza wchodzi tylko wiersz z:

| Pole | Reguła |
|---|---|
| **E-mail** | `_excel_email_ok` — zawiera `@`; nie junk/`noreply`; filtr commercial |
| **Telefon** | `_excel_phone_ok` — 9–15 cyfr; PL 9 krajowo lub ≥11 z `48`/`0048`; **nie** daty/`0000…`/`0123456789` |
| **WWW** | sensowna domena firmowa (nie Maps / katalog) |

Flagi: `EXPORT_PIPELINE_ROWS_WITHOUT_EMAIL = False`, `EXPORT_PIPELINE_ROWS_WITHOUT_PHONE = False`.

JSON cache (`pl_spedycja_cache.json`) może trzymać wizytówki Maps bez maila (`needs_enrich` / `still_gap`).

---

## Pipeline danych

1. **Maps Faza A** → JSON (nazwa, adres, często telefon Maps, czasem www) — zwykle **bez** maila.  
2. **Gap-fill Serper (Faza B)** — szuka www + maila; start **+1 h po discovery** (nie cron 20:00).  
3. **Claude row cleanup** (przed Excel) — czyści **cały rekord**.  
4. **`coerce_cleanup_result_1to1`** — każde pole musi przejść te same reguły co kod; inaczej fallback / puste.  
5. **`pick_best_pl_phone`** — z bloba (daty/NIP/+48) wybiera jeden numer PL przechodzący walidację.

---

## Claude cleanup — schema JSON

```json
{
  "company_name_clean": "",
  "address": "",
  "phone": "",
  "email": "",
  "website": "",
  "bundesland": "",
  "handelsketten": "",
  "url": ""
}
```

Prompt: sekcja **„WALIDACJA 1:1 CAŁEGO REKORDU”** w `build_row_cleanup_prompt`.  
Flaga: `ENABLE_CLAUDE_ROW_CLEANUP = True` (`scraper_web_config.py`).

---

## Typowe przyczyny `still_gap` (nocny full 26.11)

| Przyczyna | Uwagi |
|---|---|
| Mail OK, telefon śmieciowy | Najczęstsze — daty/NIP w `phones_found`; leczy `pick_best` / Claude |
| WAF / Cloudflare / 403 | Crawl pomijany |
| RemoteDisconnected | SiteGround itd. — bez Playwright fallback |
| Email pick BRAK | Złe źródło Serper / katalog |

---

## ICP / domeny

Markery typu `trans.eu` w URL: dopasowanie **host-boundary** (`_url_has_domain_marker`) — `antrans.eu` **nie** jest mylone z giełdą Trans.eu.

---

## Testy

```powershell
python -m pytest tests/unit/test_pick_best_pl_phone.py `
  tests/unit/test_coerce_cleanup_1to1.py `
  tests/unit/test_excel_requires_email.py `
  tests/unit/test_filter_antrans_domain.py `
  tests/test_claude_prompts.py -q
```

---

*Deploy Contabo: commit `cd4ae76` (2026-11-26).*

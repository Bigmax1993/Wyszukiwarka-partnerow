# Konwersacja — 2026-11-26

Notatka z sesji (Contabo / discovery / gap-fill / Claude 1:1 / Excel).

---

## 1. Status rano

- Nocny `gap-fill/serper-full` (~09:20): `attempted=126`, `enriched=22`, `still_gap=103`.
- **discovery/czwartek:** 07:00 → **09:41** exit 0; cache **295** contacts (+94 vs start dnia ~201).
- Excel rano: **12** firm z pełnym kontaktem (mail+telefon).

---

## 2. Gap-fill +1 h po discovery (zamiast 20:00)

**Decyzja:** po `END discovery` automatycznie gap-fill z opóźnieniem **1 h**; cron **20:00 wyłączony**.

- `schedule_gap_fill_after_discovery` (`GAP_FILL_DELAY_SECONDS=3600`, `GAP_FILL_MAX=80`)
- Catch-up dziś: **~10:52:25** CET

Dok.: [`CONTABO_SCHEDULE.md`](CONTABO_SCHEDULE.md). Commit: `ef3b58b`.

---

## 3. Dlaczego mało w Excelu vs 295 w JSON

Maps Faza A nie daje maila → większość `pending_gap_fill`.  
Gap-fill: często **mail OK**, ale telefon = blob śmieci (daty/NIP) → `still_gap` / brak w Excelu.

---

## 4. Claude czyści CAŁY rekord 1:1

- Prompt: „WALIDACJA 1:1 CAŁEGO REKORDU” (nazwa, adres, phone, **email**, www/url, województwo, segmenty)
- `coerce_cleanup_result_1to1` — post-check jak kod Excel/gap
- `pick_best_pl_phone` — wybór +48 z bloba; odrzut dat (`17/03/1994`)

Dok.: [`CONTACT_VALIDATION.md`](CONTACT_VALIDATION.md), [`CLAUDE_PROMPTS.md`](CLAUDE_PROMPTS.md).  
Commits: `d5e8fd1`, `ad8db15`, `dd50a20`.

---

## 5. Fix Antrans ≠ Trans.eu + eksport pełnych kontaktów

- `_url_has_domain_marker` w `pl_spedycja_filter.py` (host-boundary)
- `row_from_cache_contact`: promote email/phone/www base; ułatwienie eksportu enriched GU

Commit: `f0154bb`.

---

## 6. Uzupełnienie JSON + Excel (Contabo)

Po cleanup / pick_best / odblokowaniu ICP:

| Metryka | Wartość (~10:25 CET) |
|---|---|
| Cache contacts | **295** |
| Cache email+telefon | **~34–36** |
| Excel Kontakte | **36** |

~10 firm z mailem nadal bez numeru przechodzącego walidację (Balans, Budmat, CHOMAR, …) — wymaga ponownego źródła telefonu / gap-fill.

---

## 7. Testy + deploy

- **358 passed**, 2 skipped (`cd4ae76` — fix Excel integration + asercja promptu verify)
- Contabo: deploy `cd4ae76` (Wyniki zachowane; crontab bez 20:00)

---

## 8. Harmonogram pon–pt (aktualny)

```
04:00     cache verify
07:00     discovery (--respect-cache)
~+1 h     gap-fill Serper (max 80)
20:00     (brak)
```

Pon: 06:30 Excel mail, 06:45 Drive.

---

*Koniec notatki 2026-11-26 (~10:31 CET).*

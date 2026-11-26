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

- `schedule_gap_fill_after_discovery` (`GAP_FILL_DELAY_SECONDS=3600`, `GAP_FILL_MAX=150`)
- Catch-up dziś: **~10:52:25** CET (tura startowała z max=80; limit podbity do **150** ~11:03)

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
~+1 h     gap-fill Serper (max 150)
20:00     (brak)
```

Pon: 06:30 Excel mail, 06:45 Drive.

---

## 9. Rotacja województw (kolejne discovery)

Po Mazowieckim kolejność: **Zachodniopomorskie → Lubuskie → Wielkopolskie**  
(`gu_bundesland_rotation.py`, commit `92f307d`, deploy Contabo OK).

Dotyczy **następnego** discovery — bieżący gap-fill bez zmian.  
Dziś discovery szło jeszcze **BUNDESWEIT 16 woj.** (brak pliku stanu rotacji w `Wyniki/`).

---

## 10. Czas / throughput (szacunek z logów)

**1 województwo łącznie (Maps + gap-fill Serper/www):**

| Etap | Czas |
|---|---|
| Maps Faza A → JSON | ~45–90 min |
| Pauza przed gap-fill | +1 h |
| Gap-fill (~3–5 min/firma) | ~1,5–6 h (zależnie od kolejki / max) |

Wall-clock: zwykle **~4–7 h** / woj.

**Tydzień pon–pt (domknięte = mail+telefon):**  
discovery może przejść ~5 woj., ale solidnie domknięte raczej **~1–2 woj./tydzień**  
→ cała Polska **~2,5–4 mies.** (przy ~1–2/tydzień).

Excel Kontakte **~11:30 CET:** nadal **36** (gap-fill z 10:52 max=80 jeszcze w toku).

---

## 11. Oczekiwania zasięgu vs rynek

- Szacunek rynku „~120 tys. spedycji” / 50–100 tys. z tego pipeline’u: **nieosiągalne** (Maps Local Pack + miasta + cache + filtr mail/telefon).
- Realny rząd wielkości: **setki – niskie tysiące** leadów z kontaktem; wystarczy pod outbound / pierwszą sprzedaż.
- Pełne bazy REGON/PKD są płatne — stąd sens taniego lejka Maps/Serper mimo mniejszego zasięgu.

---

---

## 12. Pełne geo: wszystkie miasta + powiaty

**Decyzja:** dorzucone od razu (nie czekać na 2. pętlę).

- Moduł `pl_geo_locations.py` (~**1007 miast**, ~**381 powiatów** / 16 woj.)
- Regeneracja: `scripts/generate_pl_geo_locations.py` (+ snapshoty w `data/`)
- `BUNDESLAND_CONFIG`: `cities` + `powiaty`
- Maps: wszystkie miasta (5 fraz) + powiaty (2 frazy)
- Serper landkreis: wszystkie powiaty
- Cap fraz Serper: **8000**; limit discovery Contabo: **12 h** (`43200s`)

Szacunek Maps 1 woj. (np. Mazowieckie ~539 fraz): często **>6–12 h** wall — resume / kolejny dzień dociąga resztę przy `--respect-cache`.

---

---

## 13. Od jutra (2026-11-27): rotacja 1 woj. na Contabo

- `run_discovery.sh` / resume: **`--rotate-bundesland`**
- Stan: `next_index=2` → **Zachodniopomorskie** (po Mazowieckim, zgodnie z §9)
- Pełne geo + limit 12 h już na serwerze

---

*Koniec notatki 2026-11-26 (~11:55 CET).*

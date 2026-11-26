# Konwersacja — 2026-11-26

Notatka z sesji (Contabo / discovery czwartek / gap-fill harmonogram).

---

## 1. Status rano

- **09:47:** pipeline idle.
- Nocny `gap-fill/serper-full` skończony (~09:20): `attempted=126`, `enriched=22`, `still_gap=103`.
- **discovery/czwartek:** 07:00 → **09:41** exit 0; cache ~295 contacts.

---

## 2. Gap-fill +1 h po discovery (zamiast 20:00)

**Decyzja:** po zakończeniu pętli discovery automatycznie gap-fill z opóźnieniem **1 h**; wieczorny cron **20:00 wyłączony**.

Implementacja:

- `schedule/contabo/common.sh` — `schedule_gap_fill_after_discovery` (`GAP_FILL_DELAY_SECONDS=3600`, `GAP_FILL_MAX=80`, flock, log `gap_fill_delayed.log`)
- `run_discovery.sh` / `run_discovery_resume.sh` — wywołanie po `END discovery`
- `install_crontab.sh` — usunięty wpis `0 20 * * 1-5 … run_gap_fill.sh`
- `run_gap_fill.sh` — domyślne `GAP_FILL_MAX=80`

Wdrożenie Contabo + push GitHub: commit `ef3b58b`.

**Catch-up dziś** (discovery już było przed zmianą): delayed start **~10:52:25** CET.

Trwała dokumentacja harmonogramu: `docs/CONTABO_SCHEDULE.md`.

---

## 3. Aktualny plan dnia (pon–pt)

```
04:00     cache verify
07:00     discovery (--respect-cache)
~+1 h     gap-fill Serper (max 80)  ← po faktycznym końcu discovery
20:00     (brak — wyłączone)
```

Poniedziałek dodatkowo: 06:30 Excel mail, 06:45 Drive.

---

## 4. Claude czyści CAŁY rekord 1:1 pod walidację

**Problem:** gap-fill/Excel dostawały śmieci (telefony-daty, noreply, /kontakt w www, złe segmenty).

**Fix:**
- prompt cleanup: „WALIDACJA 1:1 CAŁEGO REKORDU” (nazwa, adres, phone, **email**, www/url, województwo, segmenty)
- `coerce_cleanup_result_1to1` — po Claude każde pole musi przejść te same reguły co kod; inaczej fallback/puste
- `pick_best_pl_phone` + filtr junk mail; sync pól przed Excel

*Koniec notatki 2026-11-26.*

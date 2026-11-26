# Harmonogram Contabo — PL FAS (Wyszukiwarka-partnerow)

Host: `109.199.122.178` · katalog: `/opt/bots/Wyszukiwarka-partnerow`  
Crontab: `schedule/contabo/install_crontab.sh` (blok `# BEGIN/END wyszukiwarka-partnerow`).

Strefa serwera: Europe/Berlin (CET/CEST ≈ Warsaw).

---

## Cron

| Kiedy | Job | Skrypt |
|---|---|---|
| **04:00** codziennie | Cache verify (+ mail START/OK/ALERT) | `run_cache_verify.sh` |
| **06:30** poniedziałek | Excel → mail | `run_excel_report.sh mail` |
| **06:45** poniedziałek | Excel → Google Drive (nadpisanie) | `run_excel_report.sh drive` |
| **07:00** pon–pt | Discovery Maps/Serper (`--respect-cache`) | `run_discovery.sh <dzień>` |
| **+1 h po końcu discovery** | Gap-fill Serper (Faza B) | `schedule_gap_fill_after_discovery` → `run_gap_fill.sh` |
| **06:00** niedziela | Backfill | `run_backfill.sh` |
| **09:00** pon/wt | Send B2B (domyślnie NO-OP: `DISABLE_CONTRACTOR_EMAILS=1`) | `run_send.sh` |
| ***/15** | Pipeline watchdog | `scripts/pipeline_watchdog.py` |

**Wyłączone:** stały cron gap-fill o **20:00** (od 2026-11-26).

---

## Gap-fill po discovery

Po `END discovery` skrypt `run_discovery.sh` (oraz resume) wywołuje
`schedule_gap_fill_after_discovery` z `schedule/contabo/common.sh`:

1. Czeka `GAP_FILL_DELAY_SECONDS` (domyślnie **3600** = 1 h).
2. Odpalą `run_gap_fill.sh` pod `flock` (`logs/gap_fill_delayed.lock`).
3. Log: `logs/gap_fill_delayed.log` + `logs/gap_fill_serper.log`.
4. Maile pipeline START/OK/ALERT jak przy innych jobach.

Zmienne (opcjonalnie w `.env`):

| Zmienna | Domyślnie | Opis |
|---|---|---|
| `GAP_FILL_DELAY_SECONDS` | `3600` | Opóźnienie po discovery |
| `GAP_FILL_MAX` | `80` | Max kontaktów w jednej turze Fazy B |
| `SCRAPER_MAX_RUNTIME_SECONDS` | discovery `21600` / gap-fill `7200` | Twardy limit czasu |
| `GAP_FILL_AFTER_MAPS` | `0` | Nie łączyć Fazy B w tym samym procesie co Maps |

---

## Polityka Excel vs JSON

- **Kontakte (Excel):** tylko firmy z **e-mailem i telefonem** (≥9 cyfr PL).
- **JSON cache:** wizytówki Maps (`needs_enrich` / `still_gap`) mogą być bez maila.
- Skrajna ostateczność po gap-fill: rekord zostaje w JSON, **nie** w Excelu.

---

## Reinstalacja crontab

```bash
cd /opt/bots/Wyszukiwarka-partnerow
./schedule/contabo/install_crontab.sh
crontab -l | sed -n '/BEGIN wyszukiwarka-partnerow/,/END wyszukiwarka-partnerow/p'
```

---

*Aktualizacja: 2026-11-26 — gap-fill +1 h po discovery, bez cron 20:00.*

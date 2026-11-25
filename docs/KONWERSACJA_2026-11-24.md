# Konwersacja — 2026-11-24

Notatka z sesji (Wyszukiwarka-partnerow / Contabo / wycena).

---

## 1. Testy całego systemu

- Uruchomiono `scripts\RUN_ALL_TESTS.ps1 -SkipApiLive`.
- Naprawiono asercję w `tests/test_gu_discovery_regression.py` (`RetailChainSerperRotationRegression.test_discovery_terms_include_rotating_chains`): frazy bez segmentu (np. `spedycja Warszawa`) są dozwolone; nadal wymagane ≥3 frazy z segmentem i ≥3 różne segmenty.
- Wynik: **7/7 OK** (py_compile, unit, integracja, regresja GU, Excel/Gmail, smoke, send_excel dry-run). API live pominięte.

---

## 2. Wdrożenie na Contabo

- Host: `109.199.122.178` (ten sam VPS co FAS).
- Katalog: `/opt/bots/Wyszukiwarka-partnerow`.
- Skrypt: `python scripts/deploy_contabo.py` (SSH klucz `~/.ssh/id_ed25519_small`).
- Dodane:
  - `scripts/deploy_contabo.py`
  - `schedule/contabo/*.sh` (discovery, backfill, send, excel, install_crontab, common)
  - `.gitattributes` (LF dla `*.sh`)
- Cron: pon–pt **07:00** discovery · nd **06:00** backfill · pon/wt **09:00** send · nd **09:00** Excel.
- Flagi na serwerze (bez dubli z GHA):
  - `DISABLE_CONTRACTOR_EMAILS=1`
  - `DISABLE_EXCEL_REPORT_EMAIL=1`
  - `DISABLE_GOOGLE_DRIVE=1`
- Smoke `--test` na Contabo: OK.
- Stan wieczorem 24.11: pipeline **nie** biegł; następny discovery **środa 07:00**. Użytkownik: zostawić tak.

---

## 3. Powiadomienia e-mail (START / OK / ALERT)

- Odbiorca: `svinchak1993@gmail.com` (`PIPELINE_NOTIFY_TO`).
- Pliki:
  - `scripts/pipeline_notify.py`
  - `scripts/pipeline_watchdog.py` (cron co 15 min — stale job)
  - aktualizacja `schedule/contabo/run_*.sh` + `common.sh` + crontab
  - `tests/unit/test_pipeline_notify.py` (2 passed)
- Kill-switch: `DISABLE_PIPELINE_NOTIFY=1`.
- Wysłano testowe maile START + OK z Contabo — OK.
- Send/Excel w trybie NO-OP **nie** spamują mailami statusu.

---

## 4. Ustalenia produktowe (rozmowa)

- System **pomaga jako generator leadów** PL spedycji pod outreach FAS; nie zastępuje sprzedaży / follow-upu.
- **Nie** jest narzędziem do szukania pracy spedytora (ew. tylko pośrednio lista firm).
- Na Contabo: discovery ON; B2B/Excel OFF (GHA zostaje produkcją maili).

---

## 5. Wycena rynkowa (jednorazowa sprzedaż + wdrożenie)

Pierwsza wycena (software-house’owa) uznana za zawyżoną.

**Skorygowana, bliżej PL solo / bez track recordu sprzedaży produktu:**

| Pakiet | Realistycznie |
|--------|----------------|
| Sam kod | 4–8 tys. zł |
| Kod + Contabo + cron + notify | **10–18 tys. zł** |
| + docs/szkolenie/30 dni | 15–25 tys. zł |

- Start rozmowy: ~**15 tys.** · zejście do ~**12** · walk-away ~**8–10 tys.** (wdrożony Contabo).
- Retainer utrzymania (opcjonalnie): ~1–1,5 tys. zł/mc.
- Killer prompt wyceny: zapisany w czacie; wykonany i potem skorygowany w dół na prośbę użytkownika.

---

## 6. Komendy / ścieżki na później

```powershell
# testy lokalne
powershell -ExecutionPolicy Bypass -File scripts\RUN_ALL_TESTS.ps1 -SkipApiLive

# redeploy Contabo
python scripts\deploy_contabo.py
```

Contabo: `/opt/bots/Wyszukiwarka-partnerow` · logi: `logs/` · state: `logs/pipeline_state.json`.

---

*Zapisano na prośbę użytkownika — 2026-11-24.*

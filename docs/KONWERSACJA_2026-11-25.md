# Konwersacja — 2026-11-25

Notatka z sesji (Wyszukiwarka-partnerow / Contabo / Maps / Excel / Głogów).

---

## 1. Push na GitHub + harmonogram Contabo

- Wypchnięto zmiany Maps Phase A + Serper gap-fill: commit `717a37f` na `master`.
- Repo: https://github.com/Bigmax1993/Wyszukiwarka-partnerow
- Potwierdzenie: po gap-fill (cron **20:00**) job kończy się; kolejnego dnia roboczego o **07:00** startuje discovery (crontab Contabo, nie GHA).

---

## 2. Cache verify o 04:00 + discovery z `--respect-cache`

**Wymaganie:** codziennie ok. 04:00 weryfikować cache; discovery 07:00 ma go respektować.

Dodane / zmienione:

- `scripts/verify_pl_cache.py` — health JSON + stempel `Wyniki/.cache_verified_for_discovery.json`
- `schedule/contabo/run_cache_verify.sh` — cron 04:00 + mail START/OK/ALERT → `svinchak1993@gmail.com`
- `schedule/contabo/run_discovery.sh` — zawsze `--respect-cache`
- `schedule/contabo/install_crontab.sh` — wpis `0 4 * * * … run_cache_verify.sh`
- testy: `tests/unit/test_verify_pl_cache.py`

Wdrożone na Contabo; testowy mail START cache/verify wysłany OK.

---

## 3. Excel w poniedziałek (mail + Drive) — bez kolizji z discovery

**Problem:** discovery 07:00 i Excel 07:30 nakładały się (wyścig przy zapisie xlsx).

**Ustalony harmonogram Contabo (poniedziałek):**

| Godzina | Job |
|---|---|
| **06:30** | mail z Excelem (`run_excel_report.sh mail`) |
| **06:45** | upload Google Drive (`run_excel_report.sh drive`) |
| **07:00** | discovery |

- `DISABLE_EXCEL_REPORT_EMAIL=0` na Contabo.
- Drive: ten sam plik `pl_spedycja_kontakte.xlsx` (**nadpisywany**, `GDRIVE_VERSION_XLSX=0`) — nie nowy plik co tydzień.
- Folder Drive (OAuth Contabo): https://drive.google.com/drive/folders/1JMPyphoNX_oS_EjW7LEhf103lvvtsMUL  
  (folder z docs `1bRCAq…` niedostępny dla tego OAuth — 404).
- GHA schedule Excel wyłączony (tylko `workflow_dispatch`), żeby nie dublować Contabo.

Commity m.in.: `185fb29`, `bb1f0ee`, `0312af7`.

---

## 4. Discovery Maps — status dnia

- Job: `discovery/sroda-maps` (`--respect-cache`), limit **6 h**.
- Resume ok. **14:53** → koniec **15:50** exit 0 (mail OK).
- Wieczór **20:00**: cron gap-fill (max 40) → koniec **23:04** (`enriched=6`, `still_gap=33`).
- Przyczyna słabego enrich: odrzut ICP kasował maile; Serper często dawał katalogi (`hurthandel` / `spedycjalista`); WAF/404.
- Cache po dniu: ~**169** contacts; Excel chwilowo ~**120** wierszy (głównie bez maila — Faza A).

---

## 5. Głogów — Antrans i Arra Group

**Stan początkowy:** w Excelu ~4–5 firm z Głogowa (Relon, Intertrans, Perennial…); **Antrans** i **Arra Group** brak w Excelu i cache, mimo że to lokalne firmy transportowe/spedycyjne.

Zapytania Maps dla Głogowa już poszły — Local Pack ich nie zwrócił.

**Naprawy:**

1. Bug filtra: domena `antrans.eu` mylona z giełdą `trans.eu` (substring).  
   Fix: `_host_matches_blocked_marker` w `commercial_contact_filter.py` (domeny z kropką = exact/subdomena).
2. Seed: `scripts/seed_known_glogow_firms.py`  
   - Antrans — https://antrans.eu — `antrans@antrans.eu` — Transportowa 6, Głogów  
   - Arra Group — https://www.arra-group.com — `salesPL@arra-group.com` — Piastowska 5, Głogów  
3. Seed queries Maps: `KNOWN_MAPS_SEED_QUERIES` w `pl_spedycja_keywords.py` (`Antrans Głogów`, `Arra Group Głogów`).
4. Wdrożenie Contabo: obie firmy w **cache** i arkuszu **Kontakte**.

Testy filtra: `tests/unit/test_commercial_contact_filter.py` (15 passed, w tym granica `antrans` vs `trans.eu`).

---

## 6. Testy (lokalnie / Contabo)

- Suite unit: **143 passed** (po izolacji `verify_pl_cache` od `KANBUD_DATA_DIR`).
- Contabo po deployach: verify/cache/commercial filter OK; Antrans+Arra w cache i Excelu; discovery działa.

---

## 7. Aktualny cron Contabo (PL FAS)

```
04:00 codziennie     cache verify (+ mail)
06:30 poniedziałek   Excel → mail
06:45 poniedziałek   Excel → Google Drive
07:00 pon–pt         discovery (--respect-cache)
20:00 pon–pt         gap-fill Serper
06:00 niedziela      backfill
09:00 pon/wt         send B2B (DISABLE_CONTRACTOR_EMAILS=1)
*/15                 pipeline watchdog
```

Host: `109.199.122.178` · katalog: `/opt/bots/Wyszukiwarka-partnerow`.

---

## 8. Excel = tylko pełny kontakt (e-mail + telefon)

**Wymaganie użytkownika:** każda firma w Excelu ma mieć **e-mail oraz telefon**; luki uzupełniać agresywnie; tylko w skrajnej ostateczności rekord zostaje w JSON i nie trafia do Excela.

Zmiany w kodzie:

- `EXPORT_PIPELINE_ROWS_WITHOUT_EMAIL = False`
- `EXPORT_PIPELINE_ROWS_WITHOUT_PHONE = False`
- `build_export_rows` / `save_excel` — bramka `_kontakte_row_has_required_contacts` (mail + telefon ≥9 cyfr PL, filtr śmieci)
- Maps Faza A nadal zapisuje wizytówki do **JSON** (`needs_enrich`) bez maila
- `row_from_cache_contact` — promuje `emails_found` → `email_target`
- eligibility: kontakt z mailem nie jest blokowany samym `retail_verified`/strict chain

Testy: `tests/unit/test_excel_requires_email.py`.

Po przebudowie Contabo Excel spadł do firm z pełnym kontaktem (początkowo 2: Antrans, BLP) — reszta w JSON do gap-fill.

---

## 9. Gap-fill — poprawki + pełna tura nocna

**Bug:** przy „ICP nie OK” `enrich_row_with_contacts` **kasował** maile i wracał wcześnie.  
**Fix:** nadal crawl + extract kontaktów; dla leadów Maps pick maila nie jest blokowany samym ICP.

Inne:

- `contact_has_gap` = brak maila **lub** telefonu **lub** WWW
- omijanie katalogów w `_pick_best_website` (`hurthandel`, `spedycjalista`, `panoramafirm`…)
- polityka opisana w arkuszu **Info** Excela

**Ręczny full gap-fill na Contabo** (23:25):

- reset TTL luk (~165), kolejka **126**, `--max 170`, limit **6 h**
- log: `logs/gap_fill_serper_full.log`
- job state: `gap-fill/serper-full`

**Maile pipeline:** ręczny `nohup` ominął `run_gap_fill.sh` → brak START.  
Dogrywka: `scripts/contabo_notify_gap_fill_full.sh` — START wysłany 23:30 + waiter OK/ALERT na koniec.

---

## 10. Maile B2B / interwał

- Cron send pon/wt 09:00 istnieje, ale **`DISABLE_CONTRACTOR_EMAILS=1`** → NO-OP.
- Gdy włączone: jitter **22–58 s** między mailami (`EMAIL_SEND_DELAY_*`).
- ~600 maili ≈ **7–9 h** (szacunek).
- Osobno: pon 06:30 = tylko raport Excel do właściciela, nie outreach.

---

## 11. Semantyka Excela ( Contakte )

| Arkusz | Rola |
|---|---|
| Info | Instrukcja APPEND / polityka kontaktu |
| Kontakte | CRM: tylko firmy z e-mail + telefon |
| Wojewodztwa | Geo (bez maila/tel), zsynchronizowane z Kontakte |

Deduplikacja Kontakte: e-mail → URL → nazwa+region.

---

## 12. Pliki kluczowe z tej sesji

| Plik | Rola |
|---|---|
| `google_maps_scraper.py` | Faza A Maps → JSON `needs_enrich` |
| `gap_fill_serper.py` | Faza B Serper gap-fill + polityka luk |
| `pl_fas_spedycja_scraper.py` | Bramka Excel email+telefon; enrich bez kasowania maili |
| `scripts/verify_pl_cache.py` | Weryfikacja cache 04:00 |
| `scripts/seed_known_glogow_firms.py` | Seed Antrans / Arra Group |
| `scripts/contabo_start_gap_fill_full.sh` | Ręczny full gap-fill Contabo |
| `scripts/contabo_notify_gap_fill_full.sh` | Dogrywka maili START/OK dla full gap-fill |
| `commercial_contact_filter.py` | Fix `trans.eu` vs `antrans.eu` |
| `pl_spedycja_keywords.py` | `KNOWN_MAPS_SEED_QUERIES` |
| `schedule/contabo/run_*.sh` | Cron Contabo |
| `tests/unit/test_excel_requires_email.py` | Testy bramki kontaktu w Excelu |

---

## 13. Grand Logistics — ręczny seed (RemoteDisconnected)

- Gap-fill: `http://grandlogistics.pl/` → **3× RemoteDisconnected** → crawl 0 stron → `still_gap` (telefon Maps OK: `+48 609 442 744`).
- Claude **nie odrzucił** ICP — brak maila przez padnięty HTTP klienta.
- Użytkownik w Chrome znalazł `/kontakt/`: `biuro@grandlogistics.pl`, `sales@grandlogistics.pl`, ten sam telefon, adres Bądzów 108, Jerzmanowa.
- Ręczny upsert do cache + Excel (bez Claude row-cleanup — cleanup ucinał `+48 609…` do `09 442 744` i bramka telefonu odrzucała wiersz).
- Stan Excela po seedzie: **Antrans**, **BLP**, **GRAND Logistics** (3 firmy z pełnym kontaktem). ~120 wizytówek Maps nadal w JSON do gap-fill.

**Diagnoza hostingu:** z Contabo `curl` HTTPS działa (nginx / SiteGround), Python `requests` / część profili `curl_cffi` Chrome → reset; Safari/Edge impersonate i Playwright → OK. Typowy filtr TLS/bota.

**Decyzja:** na razie **bez** zmiany crawla (`curl_cffi` / Playwright fallback) — zostaje `requests` + ręczne dopiski w skrajnych przypadkach.

---

## 14. Kolizja 04:00 verify vs nocny gap-fill-full

- Brak `flock` między jobami — **nie zabijają się**, ale mogą iść równolegle.
- Gap-fill-full start 23:25, limit 6 h → max ~05:25; verify cron **04:00** może wejść w trakcie.
- Ryzyko: wyścig przy odczycie/zapisie `pl_spedycja_cache.json` + nadpisanie `pipeline_state.json`.
- **Decyzja użytkownika:** zostawić jak jest (verify o 04:00 normalnie).

---

## 15. Inne ustalenia wieczorne

- Polityka luk: najpierw gap-fill; Excel tylko mail+telefon; JSON = skrajna ostateczność.
- B2B send nadal OFF (`DISABLE_CONTRACTOR_EMAILS=1`); interwał 22–58 s gdy włączone.
- Full gap-fill leci w tle (`gap_fill_serper_full.log`); po końcu mail OK/ALERT z waitera.
- 04:00 cache verify: zostawione równolegle z gap-fill (bez flock).

---

## 16. Sync Excel z cache (mail+telefon) — koniec dnia

Stan cache (bez `merged_into`): ~126 firm; **mail+telefon ≈ 5** (+ Grand ręcznie).

Użytkownik: te 5 z JSON mają być w Excelu. Sync Contabo z wyłączonym Claude row-cleanup (cleanup psuł telefony).

**Excel Kontakte po syncu (6 firm):**

1. Antrans Sp. z o.o. Sp. k. — `antrans@antrans.eu` / `+48 695 950 300`
2. BLP SP. Z O.O. — `quotation@blp.pl` / `+48243624010`
3. GRAND Logistics Sp. z o.o. — `biuro@grandlogistics.pl` / `+48 609 442 744`
4. Relon Logistics Sp. z o.o. — `kontakt@relon.pl` / `+48736318412`
5. Arra Group Sp. z o.o. — `salesPL@arra-group.com` / `+48 535 507 071`
6. GOTRANSPORT Sp. z o.o. — `biuro@gotransport.pl` / `486601443`

**Powiadomienie końca:** pierwszy waiter padł; restart `scripts/contabo_waiter_gap_fill_end.sh` (~23:50) — po końcu gap-fill-full mail OK/ALERT → `svinchak1993@gmail.com`.

---

*Aktualizacja wieczorna 2026-11-25 (~23:50 CET).*

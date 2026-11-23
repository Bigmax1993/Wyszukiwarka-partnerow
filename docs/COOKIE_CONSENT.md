# Cookie consent (Playwright, PL)

Plik: [`playwright_cookie_consent.py`](../playwright_cookie_consent.py)

Po co: wiele stron PL chowa telefony / e-maile za CMP. Zwykły `requests` dostaje
HTML bez kontaktów — Playwright klika **Akceptuj** i oddaje pełniejszy DOM
do parsera w scraperze.

## Zakres

| Tak | Nie |
|-----|-----|
| Banery cookie / RODO (PL first) | CAPTCHA / „nie jestem robotem” |
| CMP: Borlabs, Cookiebot, OneTrust, Usercentrics, Complianz, Klaro, … | Interakcja z mapami |
| Locale `pl-PL`, `Europe/Warsaw`, `Accept-Language: pl` | Omijanie paywalli |

Flaga: `ENABLE_PLAYWRIGHT_COOKIE_CONSENT` (`scraper_web_config`; domyślnie ON).

## Przepływ w scraperze

```text
requests → parse HTML
  → should_use_playwright_cookie_fallback(page_text, html)?
       nie → zostaw parsed
       tak → Chromium pl-PL → klik „Akceptuj” → parse_contacts_from_html ponownie
```

API publiczne:

| Funkcja | Rola |
|---------|------|
| `should_use_playwright_cookie_fallback` | czy w ogóle odpalać Chromium |
| `fetch_html_with_cookie_consent` | headless fetch + dismiss banera |
| `apply_playwright_cookie_fallback` | hook po `requests` (używany przez scraper) |
| `debug_cookie_consent_decision` | diagnostyka sygnałów banera / CMP |
| `debug_accept_label` | klasyfikacja etykiety przycisku |

Kolejność kliknięć w `_dismiss_cookie_banner`:

1. selektory ID/klas CMP  
2. dokładny tekst PL (`Akceptuj wszystkie`, …)  
3. `get_by_role` + regex  
4. skan do 50 przycisków  

Świadomie **nie** klika: Odrzuć / Tylko niezbędne / Ustawienia.

## Wymagania

```powershell
pip install -r requirements.txt
playwright install chromium
```

## Testy

```powershell
python -m pytest tests/unit/test_playwright_cookie_consent.py -q
```

Pokrycie: wykrywanie banera, etykiety Akceptuj/Odrzuć, `apply_*` z mockiem fetch
(bez prawdziwego Chromium w CI unit).

## Diagnostyka (debug)

```powershell
python playwright_cookie_consent.py --text "Akceptuj wszystkie cookies" --label "Akceptuj wszystkie"
python playwright_cookie_consent.py --html-file .\sample.html --label "Tylko niezbędne"
python playwright_cookie_consent.py --fetch https://przyklad-firma.pl
```

Albo z kodu:

```powershell
python -c "from playwright_cookie_consent import debug_cookie_consent_decision; print(debug_cookie_consent_decision('Akceptuj wszystkie cookies', button_label='Akceptuj'))"
```

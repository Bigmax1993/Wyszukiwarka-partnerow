# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# MODUŁ: google_maps_scraper.py
# CO ROBI: Faza A discovery PL FAS — scrapuje Google Maps (Local Pack / wizytówki)
#   przez Selenium + Chrome i zwraca surowe hity firm (nazwa, adres, telefon, WWW, maps_url).
# ROLA W PIPELINE:
#   1) pl_fas_spedycja_scraper.discover_places_with_serper (gdy ENABLE_GOOGLE_MAPS_DISCOVERY)
#      woła search_google_maps(query) zamiast Serper /search|/places,
#   2) maps_hits_to_discovery_rows mapuje hity → wiersze discovery z
#      discovery_source=google_maps, gap_status=needs_enrich (bez crawla / Serpera),
#   3) Faza B (gap_fill_serper.py) później uzupełnia e-mail/WWW przez Serper.
# DLACZEGO MAPS A NIE SERPER SEARCH:
#   Zwykły Serper /search na małe miasta (np. Głogów) często wraca katalogi / pusto;
#   Local Pack Maps pokazuje realne firmy (Relon, Trans-Euro, Olimpia…) jak w Chrome użytkownika.
# ZALEŻNOŚCI:
#   selenium, webdriver_manager.chrome; systemowy Google Chrome / Chromium
#   (CHROME_BIN) — na Contabo: google-chrome-stable; snap chromium-browser bywa niestabilny.
# WEJŚCIE: fraza jak „firma spedycyjna Głogów” (bez FTL/LTL — Local Pack ich nie lubi).
# WYJŚCIE: list[dict] hitów; potem list[dict] wierszy discovery.
# EFEKTY UBOCZNE: uruchamia headless Chrome, zużywa CPU/RAM, może trafić na consent/CAPTCHA.
# BŁĘDY: timeout / brak feedu → []; awaria drivera → wyjątek do wołającego (scraper loguje).
# ENV:
#   CHROME_BIN / GOOGLE_CHROME_BIN — ścieżka do binarki Chrome,
#   GOOGLE_MAPS_HEADLESS=0|1 — wymuszenie trybu okienkowego / headless,
#   DISPLAY — jeśli ustawiony, domyślnie nie-headless (lokalny desktop).
# CLI SMOKE: python google_maps_scraper.py "firma spedycyjna Głogów"
# ============================================================
"""
Discovery firm przez scraping Google Maps (Selenium + Chrome).

Faza A kampanii PL FAS / spedycja: zbiera wizytówki z Local Packa
(nazwa, adres, telefon, opcjonalne WWW, URL Maps), bez Serpera i bez
crawla stron firmowych. Wynik jest kompatybilny z lejkiem discovery
w ``pl_fas_spedycja_scraper`` (pola url/www/nazwa/adres/telefon +
``discovery_source`` / ``gap_status``).

Uwaga operacyjna: selektory DOM Maps zmieniają się; przy pustych wynikach
sprawdź consent, headless Chrome na VPS i czy fraza nie zawiera FTL/LTL.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from urllib.parse import quote_plus, urljoin

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Logger modułu — scraper może podać własny logger do search_google_maps.
LOG = logging.getLogger("google_maps_scraper")

# --- Stałe czasowe / limity (strojenie pod VPS Contabo) -------------------
# Ile wizytówek max wyciągnąć z jednego zapytania (scroll + wejście w detale).
DEFAULT_MAX_RESULTS = 20
# Timeout na pełne załadowanie strony (drv.get / page load).
PAGE_LOAD_TIMEOUT = 45
# Ile sekund czekać na feed wyników albo panel pojedynczej firmy.
RESULT_WAIT_TIMEOUT = 25
# Ile razy przewinąć listę wyników w lewej kolumnie (lazy-load kolejnych kart).
SCROLL_PAUSES = 8
# Pauza między scrollami — za krótka = niepełna lista; za długa = wolny run.
SCROLL_SLEEP_S = 1.2
# Pauza po wejściu w pojedynczą wizytówkę zanim czytamy DOM szczegółów.
DETAIL_SLEEP_S = 1.0

# Teksty przycisków zgody cookie / consent (PL + EN + DE).
# Google czasem pokazuje consent w iframe — patrz _click_consent_if_present.
_CONSENT_TEXTS = (
    "Accept all",
    "I agree",
    "Accept",
    "Zaakceptuj wszystko",
    "Zgadzam się",
    "Akceptuję",
    "Alle akzeptieren",
    "Akceptuj",
)


# >>> OPIS FUNKCJI: funkcja _chrome_binary_candidates
# Cel: zebrać uporządkowaną listę możliwych ścieżek do binarki Chrome/Chromium
#   na Windows/Linux/Contabo (env, systemowe ścieżki, cache Playwright).
# Parametry: brak.
# Zwraca: list[str] — kandydaci (mogą nie istnieć na dysku; filtruje _resolve_chrome_binary).
# Efekty uboczne: odczyt env i Path.home(); bez I/O sieciowego.
# Błędy: brak (nieskończone globy po prostu nic nie dodają).
def _chrome_binary_candidates() -> list[str]:
    """
    Lista kandydatów binarki Chrome/Chromium (env → system → Playwright).

    Kolejność na liście nie jest jeszcze rankingiem jakości — ranking robi
    ``_resolve_chrome_binary`` (snap chromium-browser jest celowo nisko).
    """
    env = (os.environ.get("CHROME_BIN") or os.environ.get("GOOGLE_CHROME_BIN") or "").strip()
    out: list[str] = []
    if env:
        out.append(env)
    out.extend(
        [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/snap/bin/chromium",
        ]
    )
    # Playwright Chromium (Contabo / CI) — często jedyna stabilna binarka headless
    # gdy systemowy chromium to wrapper snap (DevToolsActivePort).
    home = Path.home()
    for base in (
        home / ".cache" / "ms-playwright",
        Path("/root/.cache/ms-playwright"),
    ):
        if not base.exists():
            continue
        for chrome in base.glob("chromium-*/chrome-linux/chrome"):
            out.append(str(chrome))
        for chrome in base.glob("chromium_headless_shell-*/chrome-linux/headless_shell"):
            out.append(str(chrome))
    return out


# >>> OPIS FUNKCJI: funkcja _resolve_chrome_binary
# Cel: wybrać najlepszą istniejącą binarkę Chrome do Selenium na tej maszynie.
# Parametry: brak (czyta env CHROME_BIN / GOOGLE_CHROME_BIN).
# Zwraca: str | None — absolutna ścieżka albo None (Selenium spróbuje default PATH).
# Priorytet (niższy score = lepszy): Playwright → google-chrome → chromium →
#   chromium-browser (snap, często pada na VPS).
# Efekty uboczne: Path.is_file() na kandydatach.
# Błędy: brak — przy pustej liście zwraca None.
def _resolve_chrome_binary() -> str | None:
    """
    Wybiera binarkę Chrome z rankingiem stabilności pod headless VPS.

    Jawny ``CHROME_BIN`` zawsze wygrywa (ops Contabo ustawia
    ``/usr/bin/google-chrome-stable`` w ``common.sh`` / ``.env``).
    """
    env = (os.environ.get("CHROME_BIN") or os.environ.get("GOOGLE_CHROME_BIN") or "").strip()
    if env and Path(env).is_file():
        return env
    # Prefer Playwright / real chrome over Ubuntu snap chromium-browser
    ranked: list[tuple[int, str]] = []
    for path in _chrome_binary_candidates():
        if not path or not Path(path).is_file():
            continue
        score = 50
        low = path.lower()
        if "ms-playwright" in low:
            score = 10
        elif "google-chrome" in low:
            score = 20
        elif low.endswith("/chromium") and "browser" not in low:
            score = 30
        elif "chromium-browser" in low:
            score = 90
        ranked.append((score, path))
    if not ranked:
        return None
    ranked.sort()
    return ranked[0][1]


# >>> OPIS FUNKCJI: funkcja build_chrome_driver
# Cel: utworzyć gotową sesję Selenium Chrome pod scraping Maps (headless na VPS).
# Parametry:
#   headless (bool|None) — None = auto (headless gdy brak DISPLAY, chyba że
#     GOOGLE_MAPS_HEADLESS wymusza 0/1).
# Zwraca: webdriver.Chrome — wołający MUSI zrobić driver.quit() (search_google_maps
#   robi to w finally, gdy sam stworzył driver).
# Kroki: ChromeOptions (sandbox/GPU/lang pl-PL/UA) → binary_location →
#   ChromeDriverManager().install() → webdriver.Chrome; przy SessionNotCreated
#   retry z --single-process/--no-zygote i binarką Playwright.
# Efekty uboczne: pobranie chromedriver (webdriver_manager), start procesu Chrome.
# Błędy: SessionNotCreatedException i inne — po jednym retry propagowane wyżej.
def build_chrome_driver(*, headless: bool | None = None) -> webdriver.Chrome:
    """
    Chrome + Chromedriver (webdriver_manager). Headless domyślnie poza DISPLAY.

    Flagami VPS (``--no-sandbox``, ``--disable-dev-shm-usage``) omijamy typowe
    problemy Contabo/Docker. ``--remote-debugging-port=0`` pomaga przy błędzie
    „DevToolsActivePort file doesn't exist”.
    """
    if headless is None:
        headless = not bool((os.environ.get("DISPLAY") or "").strip())
        if (os.environ.get("GOOGLE_MAPS_HEADLESS") or "").strip() in ("0", "false", "False"):
            headless = False
        if (os.environ.get("GOOGLE_MAPS_HEADLESS") or "").strip() in ("1", "true", "True"):
            headless = True

    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-setuid-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--remote-debugging-port=0")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=pl-PL")
    # Ogranicza flagę „controlled by automated software” (Maps i tak wie, że to bot).
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_argument(
        "--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    binary = _resolve_chrome_binary()
    if binary:
        options.binary_location = binary

    # Snap chromium-browser często pada (DevToolsActivePort) — preferuj Playwright chrome
    if binary and "chromium-browser" in binary and not (os.environ.get("CHROME_BIN") or "").strip():
        for path in _chrome_binary_candidates():
            if "ms-playwright" in path and Path(path).is_file():
                options.binary_location = path
                binary = path
                break

    service = Service(ChromeDriverManager().install())
    try:
        driver = webdriver.Chrome(service=service, options=options)
    except Exception:
        # drugi rzut: Playwright chromium + dodatkowe flagi VPS
        options.add_argument("--single-process")
        options.add_argument("--no-zygote")
        for path in _chrome_binary_candidates():
            if "ms-playwright" in path and Path(path).is_file():
                options.binary_location = path
                break
        driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
    return driver


# >>> OPIS FUNKCJI: funkcja _click_consent_if_present
# Cel: zamknąć baner zgody Google (consent), także gdy siedzi w iframe.
# Parametry: driver (webdriver.Chrome) — aktywna sesja na maps.google.com.
# Zwraca: None.
# Kroki: do 6 iframe'ów → _click_consent_buttons w kontekście frame;
#   potem ponownie na default_content.
# Efekty uboczne: kliknięcie przycisku, krótki sleep w _click_consent_buttons.
# Błędy: wszystkie wyjątki przełączania frame są łykane — brak consent ≠ crash.
def _click_consent_if_present(driver: webdriver.Chrome) -> None:
    """
    Próbuje zaakceptować cookies/consent przed czytaniem wyników Maps.

    Bez tego feed wyników często nie renderuje się w headless (pusty timeout).
    """
    # Consent czasem w iframe
    try:
        frames = driver.find_elements(By.CSS_SELECTOR, "iframe")
        for frame in frames[:6]:
            try:
                driver.switch_to.frame(frame)
                if _click_consent_buttons(driver):
                    driver.switch_to.default_content()
                    return
            except Exception:
                pass
            finally:
                try:
                    driver.switch_to.default_content()
                except Exception:
                    pass
    except Exception:
        pass
    _click_consent_buttons(driver)


# >>> OPIS FUNKCJI: funkcja _click_consent_buttons
# Cel: znaleźć i kliknąć pierwszy widoczny przycisk zgody po tekście z _CONSENT_TEXTS.
# Parametry: driver — bieżący kontekst (strona główna lub iframe).
# Zwraca: bool — True jeśli kliknięto choć jeden przycisk.
# Efekty uboczne: click + sleep 0.6s.
# Błędy: wyjątki pojedynczego przycisku → continue (kolejny tekst / przycisk).
def _click_consent_buttons(driver: webdriver.Chrome) -> bool:
    """Kliknij „Zaakceptuj / Accept all” jeśli przycisk jest widoczny w DOM."""
    clicked = False
    for text in _CONSENT_TEXTS:
        try:
            buttons = driver.find_elements(
                By.XPATH,
                f"//button[contains(., '{text}')] | //form//button[contains(., '{text}')]",
            )
            for btn in buttons:
                try:
                    if btn.is_displayed():
                        btn.click()
                        clicked = True
                        time.sleep(0.6)
                        break
                except Exception:
                    continue
            if clicked:
                break
        except Exception:
            continue
    return clicked


# >>> OPIS FUNKCJI: funkcja _maps_search_url
# Cel: zbudować URL wyszukiwania Google Maps z locale PL.
# Parametry: query (str) — np. „firma spedycyjna Głogów”.
# Zwraca: str — https://www.google.com/maps/search/<urlencoded>?hl=pl
# Efekty uboczne / błędy: brak (quote_plus obsługuje Unicode).
def _maps_search_url(query: str) -> str:
    """URL Local Pack / search dla frazy (hl=pl)."""
    return f"https://www.google.com/maps/search/{quote_plus(query)}?hl=pl"


# >>> OPIS FUNKCJI: funkcja _scroll_results_feed
# Cel: dociągnąć kolejne karty w lewej liście wyników (role=feed) przez scroll.
# Parametry: driver; pauses (int) — ile razy scroll do dołu (domyślnie SCROLL_PAUSES).
# Zwraca: None. Brak feedu → no-op (pojedyńczy wynik Maps nie ma listy).
# Efekty uboczne: execute_script scrollTop; sleep SCROLL_SLEEP_S między iteracjami.
# Błędy: NoSuchElementException → return; błąd JS → break pętli.
def _scroll_results_feed(driver: webdriver.Chrome, pauses: int = SCROLL_PAUSES) -> None:
    """
    Przewija panel wyników, żeby Maps dograł kolejne wizytówki (lazy-load).

    Bez scrolla dostajemy zwykle tylko pierwsze ~3–7 kart z Local Packa.
    """
    try:
        feed = driver.find_element(By.CSS_SELECTOR, 'div[role="feed"]')
    except NoSuchElementException:
        return
    for _ in range(pauses):
        try:
            driver.execute_script(
                "arguments[0].scrollTop = arguments[0].scrollHeight;", feed
            )
        except Exception:
            break
        time.sleep(SCROLL_SLEEP_S)


# >>> OPIS FUNKCJI: funkcja _listing_anchors
# Cel: znaleźć linki do wizytówek (/maps/place/) w aktualnym DOM listy.
# Parametry: driver.
# Zwraca: list elementów WebElement (anchorów). Preferuje klasę a.hfpxzc
#   (stabilniejsza w 2024/2025); fallback: dowolne a[href*="/maps/place/"].
# Efekty uboczne / błędy: brak (pusta lista gdy DOM inny — wołający dostanie 0 hitów).
def _listing_anchors(driver: webdriver.Chrome) -> list:
    """Anchory kart wyników w feedzie Maps."""
    anchors = driver.find_elements(By.CSS_SELECTOR, 'a.hfpxzc[href*="/maps/place/"]')
    if anchors:
        return anchors
    return driver.find_elements(By.CSS_SELECTOR, 'a[href*="/maps/place/"]')


# >>> OPIS FUNKCJI: funkcja _text_or_empty
# Cel: bezpiecznie odczytać text lub aria-label elementu CSS; brak → "".
# Parametry: driver; css (str) — selektor.
# Zwraca: str (strip). NoSuchElementException → "".
def _text_or_empty(driver: webdriver.Chrome, css: str) -> str:
    """Tekst elementu albo pusty string (bez wyjątków do góry)."""
    try:
        el = driver.find_element(By.CSS_SELECTOR, css)
        return (el.text or el.get_attribute("aria-label") or "").strip()
    except NoSuchElementException:
        return ""


# >>> OPIS FUNKCJI: funkcja _attr_or_empty
# Cel: bezpiecznie odczytać atrybut DOM (np. href) po CSS; brak → "".
# Parametry: driver; css; attr (np. \"href\").
# Zwraca: str. NoSuchElementException → "".
def _attr_or_empty(driver: webdriver.Chrome, css: str, attr: str) -> str:
    """Atrybut elementu albo pusty string."""
    try:
        el = driver.find_element(By.CSS_SELECTOR, css)
        return (el.get_attribute(attr) or "").strip()
    except NoSuchElementException:
        return ""


# >>> OPIS FUNKCJI: funkcja _extract_detail
# Cel: z otwartego panelu szczegółów wizytówki wyciągnąć pola firmowe.
# Parametry: driver — musi być na stronie /maps/place/... (h1.DUwDvf widoczny).
# Zwraca: dict z kluczami:
#   name, address, phone, website, maps_url, rating, reviews
#   (wartości str; puste gdy brak w DOM).
# Selektory (kruche — Maps je zmienia):
#   h1.DUwDvf — nazwa,
#   button[data-item-id=\"address\"] — adres (aria-label „Adres: …”),
#   button[data-item-id^=\"phone:tel:\"] — telefon,
#   a[data-item-id=\"authority\"] — oficjalna WWW,
#   div.F7nice — ocena / liczba opinii.
# Efekty uboczne: brak nawigacji (tylko odczyt DOM).
# Błędy: brak elementów → pola puste, nie rzuca.
# UWAGA: lat/lon NIE są tu parsowane (URL często ma !3d!4d — Faza A ich nie używa;
#   geo filtr w scraperie jest OFF; lokalizacja = miasto w query + adres tekstowy).
def _extract_detail(driver: webdriver.Chrome) -> dict:
    """
    Parsuje prawy/centralny panel szczegółów firmy na Google Maps.

    ``website`` z Google goto / google.* jest odrzucane — to nie jest strona firmy.
    ``maps_url`` to current_url bez parametrów ``&…`` (stabilniejszy klucz cache).
    """
    name = _text_or_empty(driver, "h1.DUwDvf") or _text_or_empty(driver, "h1")
    address = ""
    try:
        btn = driver.find_element(By.CSS_SELECTOR, 'button[data-item-id="address"]')
        address = (btn.get_attribute("aria-label") or btn.text or "").strip()
        address = re.sub(r"^Adres:\s*", "", address, flags=re.I).strip()
    except NoSuchElementException:
        address = _text_or_empty(driver, 'button[data-item-id="address"]')

    phone = ""
    try:
        btn = driver.find_element(By.CSS_SELECTOR, 'button[data-item-id^="phone:tel:"]')
        phone = (btn.get_attribute("aria-label") or btn.text or "").strip()
        phone = re.sub(r"^Telefon:\s*", "", phone, flags=re.I).strip()
    except NoSuchElementException:
        pass

    website = _attr_or_empty(driver, 'a[data-item-id="authority"]', "href")
    if website:
        website = urljoin(driver.current_url, website)
    if website and "google." in website.lower():
        website = ""

    rating = ""
    reviews = ""
    try:
        rating_el = driver.find_element(By.CSS_SELECTOR, 'div.F7nice span[aria-hidden="true"]')
        rating = (rating_el.text or "").strip()
    except NoSuchElementException:
        pass
    try:
        rev_el = driver.find_element(By.CSS_SELECTOR, 'div.F7nice span[aria-label*="opini"]')
        reviews = (rev_el.get_attribute("aria-label") or rev_el.text or "").strip()
    except NoSuchElementException:
        pass

    maps_url = (driver.current_url or "").split("&")[0].strip()
    return {
        "name": name,
        "address": address,
        "phone": phone,
        "website": website,
        "maps_url": maps_url,
        "rating": rating,
        "reviews": reviews,
    }


# >>> OPIS FUNKCJI: funkcja search_google_maps
# Cel: główne API modułu — dla frazy wyszukać firmy na Google Maps i zwrócić listę hitów.
# Parametry:
#   query (str) — fraza Local Pack (preferuj „firma spedycyjna {miasto}”, bez FTL/LTL),
#   max_results (int) — limit wizytówek (domyślnie DEFAULT_MAX_RESULTS),
#   driver (Chrome|None) — None = stwórz i zamknij własny; podany = reuse (testy),
#   logger (Logger|None) — None = LOG modułu.
# Zwraca: list[dict] — każdy element jak _extract_detail (name/address/phone/…).
#   Pusta lista przy pustym query, timeoutcie albo braku hitów.
# Przebieg:
#   1) build URL + drv.get
#   2) consent
#   3) wait: feed LUB h1 szczegółów LUB anchory place
#   4a) brak feedu → pojedynczy wynik (_extract_detail) i return
#   4b) scroll feed → zbierz hrefy place → dla każdego get(href) + _extract_detail
# Efekty uboczne: sesja Chrome (jeśli own_driver), requesty do Google, logi INFO/WARNING.
# Błędy: TimeoutException → [] + warning; błąd pojedynczego detail → log + continue;
#   wyjątek build_chrome_driver propagowany. finally zawsze quit() własnego drivera.
def search_google_maps(
    query: str,
    *,
    max_results: int = DEFAULT_MAX_RESULTS,
    driver: webdriver.Chrome | None = None,
    logger: logging.Logger | None = None,
) -> list[dict]:
    """
    Szuka firm na Google Maps dla ``query``.

    Zwraca listę dictów (name/address/phone/website/maps_url/...).
    Własny ``driver`` — nie jest zamykany (testy / reuse).
    """
    log = logger or LOG
    q = (query or "").strip()
    if not q:
        return []

    own_driver = driver is None
    drv = driver or build_chrome_driver()
    results: list[dict] = []
    seen: set[str] = set()
    try:
        url = _maps_search_url(q)
        log.info("Google Maps: %s", q)
        drv.get(url)
        time.sleep(1.0)
        _click_consent_if_present(drv)
        try:
            WebDriverWait(drv, RESULT_WAIT_TIMEOUT).until(
                EC.any_of(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div[role="feed"]')),
                    EC.presence_of_element_located((By.CSS_SELECTOR, "h1.DUwDvf")),
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, 'a[href*="/maps/place/"]')
                    ),
                )
            )
        except TimeoutException:
            log.warning("Google Maps: brak wyników / timeout dla %s", q)
            return []

        # Pojedynczy wynik — od razu panel szczegółów (Maps czasem skipuje listę)
        if not drv.find_elements(By.CSS_SELECTOR, 'div[role="feed"]'):
            detail = _extract_detail(drv)
            if detail.get("name"):
                key = (detail.get("website") or detail.get("maps_url") or detail["name"]).lower()
                if key not in seen:
                    seen.add(key)
                    results.append(detail)
            return results

        _scroll_results_feed(drv)
        anchors = _listing_anchors(drv)
        hrefs: list[tuple[str, str]] = []
        for a in anchors:
            href = (a.get_attribute("href") or "").strip()
            name = (a.get_attribute("aria-label") or "").strip()
            if not href or href in seen:
                continue
            seen.add(href)
            hrefs.append((href, name))
            if len(hrefs) >= max_results:
                break

        # Wejście w każdą wizytówkę osobno — lista ma tylko nazwę/href;
        # telefon i WWW są w panelu szczegółów.
        for href, list_name in hrefs:
            try:
                drv.get(href)
                time.sleep(DETAIL_SLEEP_S)
                try:
                    WebDriverWait(drv, 12).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "h1.DUwDvf"))
                    )
                except TimeoutException:
                    pass
                detail = _extract_detail(drv)
                if not detail.get("name") and list_name:
                    detail["name"] = list_name
                if not detail.get("maps_url"):
                    detail["maps_url"] = href
                if detail.get("name"):
                    results.append(detail)
            except Exception as exc:
                log.warning("Google Maps detail fail %s: %s", href[:80], exc)
                continue
        return results
    finally:
        if own_driver:
            try:
                drv.quit()
            except Exception:
                pass


# >>> OPIS FUNKCJI: funkcja maps_hits_to_discovery_rows
# Cel: zmapować surowe hity Maps → wiersze discovery zgodne z pl_fas_spedycja_scraper
#   (Faza A: zapis do contacts JSON bez Serper/crawl).
# Parametry:
#   term (str) — fraza wyszukiwania (trafia do fraza/kategoria),
#   hits (list[dict]) — wynik search_google_maps.
# Zwraca: list[dict] wierszy z polami m.in.:
#   nazwa, adres, telefon, www/url, official_website (tylko realna WWW),
#   maps_url, discovery_source=\"google_maps\", gap_status=\"needs_enrich\",
#   lat_center/lon_center puste (nieparsowane).
# Reguły:
#   - bez name lub bez (website|maps_url) → pomijamy hit,
#   - official_website puste gdy brak WWW albo link google.*,
#   - www/url = realna WWW albo fallback maps_url (klucz pending).
# Efekty uboczne / błędy: brak.
def maps_hits_to_discovery_rows(term: str, hits: list[dict]) -> list[dict]:
    """
    Mapuje hit Maps → wiersz discovery (url/www/nazwa/adres/telefon).

    ``gap_status=needs_enrich`` sygnalizuje Fazę B (gap_fill_serper), że rekord
    czeka na e-mail / sensowną WWW — bez crawla w tej fazie.
    """
    rows: list[dict] = []
    for hit in hits:
        name = (hit.get("name") or "").strip()
        website = (hit.get("website") or "").strip()
        maps_url = (hit.get("maps_url") or "").strip()
        link = website or maps_url
        if not name or not link:
            continue
        address = (hit.get("address") or "").strip()
        phone = (hit.get("phone") or "").strip()
        snippet = " ".join(x for x in (address, phone) if x)
        real_www = website if website and "google." not in website.lower() else ""
        rows.append(
            {
                "fraza": term,
                "nazwa": name,
                "company_name_raw": name,
                "company_name_clean": name,
                "ocena": hit.get("rating") or "",
                "liczba_opinii": hit.get("reviews") or "",
                "kategoria": term,
                "adres": address,
                "full_address": address,
                "page_snippet": f"{name} {snippet}".strip(),
                "status": "",
                "telefon": phone,
                "www": real_www or link,
                "url": real_www or link,
                "official_website": real_www,
                "maps_url": maps_url,
                "lat_center": "",
                "lon_center": "",
                "discovery_source": "google_maps",
                "gap_status": "needs_enrich",
            }
        )
    return rows


# >>> OPIS FUNKCJI: blok __main__
# Cel: ręczny smoke test z CLI bez odpalania całego scrapera.
# Użycie: python google_maps_scraper.py [fraza…]
#   bez argumentów → „firma spedycyjna Głogów”
# Efekty uboczne: start Chrome, print JSON hitów na stdout.
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    q = " ".join(sys.argv[1:]) or "firma spedycyjna Głogów"
    hits = search_google_maps(q, max_results=8)
    print(json.dumps(hits, ensure_ascii=False, indent=2))

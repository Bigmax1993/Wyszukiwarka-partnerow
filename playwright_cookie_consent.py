# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Uzupełnienie opisu modułu playwright_cookie_consent (komentarz; docstring poniżej opisuje zakres).
#   Rola w pipeline: opcjonalny fallback pobierania strony — gdy zwykły requests zwrócił HTML zasłonięty
#   banerem cookie (CMP), headless Chromium klika akceptację i oddaje pełniejszy DOM parserowi kontaktów.
#   Zależności: logging, re, typing; Playwright importowany leniwie (brak → pusty HTML);
#   scraper_web_config.ENABLE_PLAYWRIGHT_COOKIE_CONSENT (przy braku importu domyślnie włączone).
#   Wejście: tekst/HTML strony, URL, logger. Wyjście: bool (czy odpalić / czy kliknięto) lub HTML (str);
#   funkcje diagnostyczne zwracają dict. Błędy Playwrighta są logowane na debug i nie przerywają pipeline.
# ============================================================
"""
Playwright: wyłącznie zamknięcie banerów cookie (bez CAPTCHA, bez map).

Po co: wiele stron PL spedycyjnych chowa telefony / e-maile za CMP
(Borlabs, Cookiebot, OneTrust, Usercentrics, Complianz…). Zwykły `requests`
dostaje HTML bez treści kontaktów — Playwright klika „Akceptuj” i oddaje
pełniejszy DOM do parsera kontaktów.

Zakres:
  - tylko zgoda cookie (PL first, potem EN/DE fallback),
  - locale przeglądarki ``pl-PL`` / ``Europe/Warsaw``,
  - bez omijania CAPTCHA i bez interakcji z mapami.

Flaga: ``ENABLE_PLAYWRIGHT_COOKIE_CONSENT`` z `scraper_web_config`
(przy braku importu domyślnie włączone).
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

try:
    from scraper_web_config import ENABLE_PLAYWRIGHT_COOKIE_CONSENT
except ImportError:
    ENABLE_PLAYWRIGHT_COOKIE_CONSENT = True

# Wykrywanie banera – najpierw typowe polskie sformułowania + nazwy CMP.
# Używane w `should_use_playwright_cookie_fallback` (czy w ogóle odpalać Chromium).
_PL_COOKIE_MARKERS: tuple[str, ...] = (
    "cookie",
    "cookies",
    "ciasteczka",
    "ciasteczek",
    "ustawienia cookie",
    "ustawienia cookies",
    "ustawienia plików cookie",
    "polityka cookie",
    "polityka cookies",
    "polityka plików cookie",
    "informacja o cookies",
    "baner cookie",
    "cookie-banner",
    "cookie banner",
    "zgoda na cookies",
    "zgoda na przetwarzanie",
    "prywatność",
    "polityka prywatności",
    "ustawienia prywatności",
    "preferencje prywatności",
    "rodo",
    "zgoda",
    "zgody",
    "zarządzaj zgodami",
    "consent",
    "akceptuj wszystkie",
    "zaakceptuj wszystkie",
    "akceptuję wszystkie",
    "akceptuj cookies",
    "akceptuj ciasteczka",
    "zezwól na cookies",
    "tylko niezbędne",
    "niezbędne cookies",
    "wymagane cookies",
    "borlabs-cookie",
    "onetrust",
    "cookiebot",
    "usercentrics",
    "klaro",
    "ccm19",
    "cmplz",
    "etracker",
    "privacy-manager",
)

# Zapasowo (EN / DE) – gdy strona PL serwuje angielski/niemiecki baner.
_FALLBACK_COOKIE_MARKERS: tuple[str, ...] = (
    "accept all",
    "cookie settings",
    "alle akzeptieren",
    "akzeptieren",
)

# Fragmenty HTML typowych wtyczek — wykrywanie nawet gdy tekst widoczny jest pusty
# (baner w shadow DOM / lazy inject).
_CMP_HTML_HINTS: tuple[str, ...] = (
    "onetrust-accept",
    "CybotCookiebotDialogBodyButtonAccept",
    "CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
    "cookiebot",
    "CybotCookiebot",
    "cmplz-cookiebanner",
    "cmplz-accept",
    "borlabs-cookie",
    "borlabs-cookie-btn-accept",
    "usercentrics",
    "uc-accept-all",
    "fc-cta-consent",
    "sp_message_container",
    "ccm--accept",
    "ccm-widget",
    "klaro",
    "klaro-cookie-notice",
    "privacy-manager",
    "cookie-law-info",
    "cli_settings_button",
)

# CAPTCHA / anti-bot — ten moduł NIE rozwiązuje challenge’y; tylko pomaga
# nie mylić ich z banerem cookie przy samym wykrywaniu.
_CAPTCHA_MARKERS: tuple[str, ...] = (
    "recaptcha",
    "g-recaptcha",
    "hcaptcha",
    "unusual traffic",
    "robot check",
    "i am not a robot",
    "nie jestem robotem",
    "potwierdź, że nie jesteś robotem",
)

# Etykiety przycisku „Akceptuj” (dokładne match) — kolejność: najczęstsze CMP PL.
_PL_ACCEPT_EXACT: tuple[str, ...] = (
    "Akceptuj wszystkie",
    "Zaakceptuj wszystkie",
    "Akceptuję wszystkie",
    "Akceptuj wszystkie pliki cookie",
    "Akceptuj wszystkie cookies",
    "Akceptuj",
    "Zaakceptuj",
    "Akceptuję",
    "Zgadzam się",
    "Wyrażam zgodę",
    "OK",
    "Okay",
    "Rozumiem",
    "Akceptuj cookies",
    "Akceptuj ciasteczka",
    "Zezwól",
    "Zezwól na wszystkie",
    "Zapisz i zamknij",
    "Zapisz & zamknij",
    "Kontynuuj",
    "Dalej",
)

# Luźniejszy regex etykiet akceptacji (cały tekst przycisku, ^…$).
_PL_ACCEPT_BUTTON_RE = re.compile(
    r"^("
    r"akceptuj\s+wszystkie(\s+pliki)?\s*cookies?|"
    r"akceptuj\s+wszystkie(\s+ciasteczka)?|"
    r"zaakceptuj\s+wszystkie|"
    r"akceptuję\s+wszystkie|"
    r"akceptuj\s+cookies?|"
    r"akceptuj\s+ciasteczka|"
    r"zezwól\s+na\s+wszystkie|"
    r"akceptuj|"
    r"zaakceptuj|"
    r"akceptuję|"
    r"zgadzam\s+się|"
    r"wyrażam\s+zgodę|"
    r"rozumiem|"
    r"zapisz\s*[&+]\s*zamknij|"
    r"zapisz\s+i\s+zamknij|"
    r"zezwól|"
    r"kontynuuj|"
    r"dalej|"
    r"^ok(?:ay)?$"
    r")\s*$",
    re.IGNORECASE,
)

# Etykiety, których NIE wolno klikać (odrzucenie / ustawienia / „tylko niezbędne”).
_PL_REJECT_BUTTON_RE = re.compile(
    r"odrzu[cć]|"
    r"odm[oó]w|"
    r"nie\s+akceptuj|"
    r"tylko\s+(?:niezbędne|wymagane|techniczne)|"
    r"tylko\s+istotne|"
    r"ustawienia|"
    r"wybór|"
    r"dostosuj|"
    r"konfiguruj|"
    r"więcej\s+opcji|"
    r"szczegóły|"
    r"zarządzaj|"
    r"reject|"
    r"decline|"
    r"refuse|"
    r"settings|"
    r"preferences|"
    r"ablehnen|"
    r"einstellungen",
    re.IGNORECASE,
)

# Selektory ID/klas typowych wtyczek WordPress / CMP (najszybsza ścieżka kliknięcia).
_PL_CONSENT_SELECTORS: tuple[str, ...] = (
    "#onetrust-accept-btn-handler",
    "#CybotCookiebotDialogBodyButtonAccept",
    "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
    "button[data-testid='uc-accept-all-button']",
    "button[data-testid='uc-accept-all']",
    ".uc-accept-all-button",
    ".borlabs-cookie-btn-accept-all",
    ".borlabs-cookie-btn[data-cookie-accept-all]",
    "a.borlabs-cookie-btn-accept-all",
    "button.cmplz-accept",
    ".cmplz-btn.cmplz-accept",
    ".cmplz-accept",
    "#cookie_action_close_header",
    ".cc-allow",
    ".cc-btn.cc-allow",
    "[data-cookie-accept]",
    "[data-cookie-accept-all]",
    ".fc-cta-consent",
    ".ccm--accept-all",
    ".ccm-widget button.ccm--accept-all",
    "#ccm-widget .ccm--accept-all",
    ".klaro .cm-btn-success",
    "button.klaro-cookie-notice-button",
    ".cli_action_button.cli_accept_button",
    "#cookie-law-info-again",
    "button.privacy-manager-accept",
    "button[data-accept-cookies]",
    "button[aria-label*='akceptuj' i]",
    "button[aria-label*='zgadzam' i]",
    "a[aria-label*='akceptuj' i]",
)

# Playwright get_by_role(name=regex) — gdy dokładny tekst się rozjeżdża (nbsp, case).
_PL_ROLE_BUTTON_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"akceptuj\s+wszystkie(\s+pliki)?\s*cookies?",
        r"akceptuj\s+wszystkie",
        r"zaakceptuj\s+wszystkie",
        r"^akceptuj$",
        r"^zaakceptuj$",
        r"akceptuj\s+cookies?",
        r"^zgadzam\s+się$",
        r"^rozumiem$",
        r"^zezwól$",
    )
)

_DEFAULT_TIMEOUT_MS = 22_000
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_ACCEPT_LANGUAGE = "pl-PL,pl;q=0.9,en;q=0.5"


def should_use_playwright_cookie_fallback(page_text: str, html: str = "") -> bool:
    """
    Decyduje, czy w ogóle odpalać Chromium po zwykłym `requests`.

    Po co: Playwright jest drogi (czas / CPU) — wołamy go tylko gdy w tekście
    strony lub HTML widać baner cookie / CMP. Sama CAPTCHA bez markera cookie
    nie wystarcza (i tak jej nie omijamy).

    Zwraca ``True`` = warto spróbować `fetch_html_with_cookie_consent`.
    """
    t = (page_text or "").lower()
    h = (html or "").lower()[:14_000]
    combined = f"{t} {h}"
    has_cookie = (
        any(m in combined for m in _PL_COOKIE_MARKERS)
        or any(m in combined for m in _FALLBACK_COOKIE_MARKERS)
        or any(hint in h for hint in _CMP_HTML_HINTS)
    )
    if not has_cookie:
        return False
    if any(m in combined for m in _CAPTCHA_MARKERS) and not has_cookie:
        return False
    return True


def _is_reject_label(label: str) -> bool:
    """
    Czy etykieta przycisku wygląda na odrzucenie / ustawienia / „tylko niezbędne”.

    Po co: unikamy klikania w ścieżkę, która zamyka baner bez zgody marketingowej
    albo otwiera panel preferencji zamiast akceptacji.
    """
    return bool(label and _PL_REJECT_BUTTON_RE.search(label))


def _is_polish_accept_label(label: str) -> bool:
    """
    Czy etykieta to akceptacja zgody (dokładna lista PL albo regex).

    Odrzuca puste / zbyt długie napisy (>90 znaków — zwykle cały akapit RODO)
    oraz wszystko, co `_is_reject_label` uznaje za „nie klikaj”.
    """
    if not label or len(label) > 90:
        return False
    t = label.strip()
    if _is_reject_label(t):
        return False
    if t in _PL_ACCEPT_EXACT:
        return True
    return bool(_PL_ACCEPT_BUTTON_RE.match(t))


def _click_locator_safe(locator, logger: logging.Logger) -> bool:
    """
    Bezpieczne kliknięcie pierwszego elementu z lokalizatora Playwright.

    Kroki: brak elementów → False; odczyt etykiety; skip reject; akceptacja PL
    albo wąski fallback EN/DE (``accept all`` / ``alle akzeptieren``); click.
    Wyjątki loguje na ``debug`` i zwraca ``False`` (nie wywala całego fetcha).
    """
    try:
        if locator.count() == 0:
            return False
        el = locator.first
        try:
            label = (el.inner_text(timeout=600) or "").strip()[:90]
        except Exception:
            label = ""
        if label and _is_reject_label(label):
            return False
        if label and not _is_polish_accept_label(label):
            # Inne języki tylko jeśli wygląda jak globalne „accept all”
            if not re.match(
                r"^(accept all|accept cookies|i agree|alle akzeptieren)$",
                label,
                re.I,
            ):
                return False
        el.click(timeout=3000)
        return True
    except Exception as e:
        logger.debug("Playwright cookie click: %s", e)
        return False


def _click_by_exact_polish_text(page, logger: logging.Logger) -> bool:
    """
    Klika przycisk/link po dokładnej polskiej etykiecie z `_PL_ACCEPT_EXACT`.

    Próbuje kolejno: ``get_by_role(button)``, ``get_by_role(link)``,
    potem CSS ``:has-text(...)``. Pierwszy udany click kończy pętlę.
    """
    for phrase in _PL_ACCEPT_EXACT:
        try:
            btn = page.get_by_role("button", name=phrase, exact=True)
            if _click_locator_safe(btn, logger):
                return True
        except Exception:
            pass
        try:
            link = page.get_by_role("link", name=phrase, exact=True)
            if _click_locator_safe(link, logger):
                return True
        except Exception:
            pass
        try:
            loc = page.locator(
                f"button:has-text('{phrase}'), a:has-text('{phrase}'), "
                f"[role='button']:has-text('{phrase}')"
            )
            if _click_locator_safe(loc, logger):
                return True
        except Exception:
            continue
    return False


# >>> OPIS FUNKCJI: funkcja _click_by_polish_role_regex
# Cel: kliknąć przycisk akceptacji cookie dopasowany regexem nazwy roli (warianty fleksyjne, np.
# „Akceptuj wszystkie cookies”). Parametry: page — strona Playwright; logger.
# Zwraca: bool — True po pierwszym udanym kliknięciu (przez _click_locator_safe), inaczej False.
# Efekty uboczne: klik w przeglądarce. Błędy: wyjątki dla pojedynczego wzorca są ignorowane (continue).
def _click_by_polish_role_regex(page, logger: logging.Logger) -> bool:
    """
    Klika ``button`` po regexie nazwy (gdy dokładny tekst się nie zgadza).

    Pokrywa warianty ze spacjami / fleksją („Akceptuj wszystkie cookies”).
    """
    for pat in _PL_ROLE_BUTTON_PATTERNS:
        try:
            loc = page.get_by_role("button", name=pat)
            if _click_locator_safe(loc, logger):
                return True
        except Exception:
            continue
    return False


def _click_pl_selectors(page, logger: logging.Logger) -> bool:
    """
    Klika znane selektory ID/klas CMP (OneTrust, Cookiebot, Borlabs, …).

    Najszybsza ścieżka: nie zależy od widocznego tekstu, tylko od markup
    wtyczki. Pierwszy udany lokalizator wygrywa.
    """
    for sel in _PL_CONSENT_SELECTORS:
        try:
            loc = page.locator(sel)
            if _click_locator_safe(loc, logger):
                return True
        except Exception:
            continue
    return False


def _click_buttons_scan_polish(page, logger: logging.Logger) -> bool:
    """
    Ostateczność: skanuje do 50 elementów ``role=button`` i klika pierwszą
    etykietę uznaną za polską akceptację.

    Wolniejsze, ale łapie customowe banery bez standardowych klas CMP.
    """
    try:
        buttons = page.get_by_role("button")
        n = min(buttons.count(), 50)
    except Exception:
        return False

    for i in range(n):
        try:
            btn = buttons.nth(i)
            text = (btn.inner_text(timeout=500) or "").strip()
        except Exception:
            continue
        if not _is_polish_accept_label(text):
            continue
        try:
            btn.click(timeout=3000)
            return True
        except Exception:
            continue
    return False


def _dismiss_cookie_banner(page, logger: logging.Logger) -> bool:
    """
    Orkiestracja zamknięcia banera na już załadowanej stronie Playwright.

    Kolejność (od najpewniejszej / najtańszej):
      1. selektory CMP,
      2. dokładny tekst PL,
      3. role + regex,
      4. skan wszystkich buttonów.

    Zwraca ``True`` gdy którykolwiek krok kliknął akceptację.
    """
    steps = (
        _click_pl_selectors,
        _click_by_exact_polish_text,
        _click_by_polish_role_regex,
        _click_buttons_scan_polish,
    )
    for step in steps:
        if step(page, logger):
            return True
    return False


def fetch_html_with_cookie_consent(
    url: str,
    logger: logging.Logger,
    *,
    timeout_ms: int = _DEFAULT_TIMEOUT_MS,
) -> str:
    """
    Uruchamia headless Chromium (pl-PL), klika zgodę cookie, zwraca HTML.

    Po co: źródło DOM dla parsera kontaktów, gdy `requests` dostał stronę
    zasłoniętą banerem. Przy wyłączonej fladze / braku Playwrighta / błędzie
    nawigacji zwraca pusty string (caller zostaje przy starym parse).

    Kontekst: UA desktop Chrome, ``locale=pl-PL``, ``Europe/Warsaw``,
    ``Accept-Language`` PL. Po ``goto`` krótkie czekanie na inject CMP,
    potem `_dismiss_cookie_banner` i `page.content()`.
    """
    if not ENABLE_PLAYWRIGHT_COOKIE_CONSENT:
        return ""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.info(
            "Playwright niedostępny (pip install playwright && playwright install chromium)"
        )
        return ""

    html = ""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context(
                    user_agent=_USER_AGENT,
                    locale="pl-PL",
                    timezone_id="Europe/Warsaw",
                    extra_http_headers={"Accept-Language": _ACCEPT_LANGUAGE},
                )
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                page.wait_for_timeout(1100)
                _dismiss_cookie_banner(page, logger)
                page.wait_for_timeout(700)
                html = page.content()
            finally:
                browser.close()
    except Exception as e:
        logger.warning("Playwright cookie consent %s: %s", url, e)
    return html


def apply_playwright_cookie_fallback(
    url: str,
    logger: logging.Logger,
    html: str,
    parsed: dict[str, Any],
    parse_contacts_from_html: Callable[[str, str], dict],
    *,
    on_step: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """
    Hook scrapera: po `requests` + pierwszym parse — opcjonalny retry przez Playwright.

    Warunki: flaga włączona + `should_use_playwright_cookie_fallback`.
    Gdy Chromium zwróci HTML, wynik leci przez ten sam ``parse_contacts_from_html``
    co pipeline (maile, telefony, snippet). Przy niepowodzeniu zwraca oryginalne
    ``parsed`` bez zmian.

    ``on_step`` — opcjonalny callback UI/konsoli („Baner cookie (PL)…”).
    """
    if not ENABLE_PLAYWRIGHT_COOKIE_CONSENT:
        return parsed
    page_text = parsed.get("page_text", "")
    if not should_use_playwright_cookie_fallback(page_text, html):
        return parsed
    if on_step:
        on_step("Baner cookie (PL) – Playwright, tylko zgoda")
    pw_html = fetch_html_with_cookie_consent(url, logger)
    if not pw_html:
        return parsed
    return parse_contacts_from_html(url, pw_html)


def debug_accept_label(label: str) -> dict[str, Any]:
    """
    Diagnostyka jednej etykiety przycisku (czy klikniemy / czy reject).

    Po co: przy customowym banerze widać od razu, czy tekst wpada w
    `_PL_ACCEPT_EXACT` / regex akceptacji, czy w reject (Ustawienia / Odrzuć).
    """
    raw = label or ""
    stripped = raw.strip()
    return {
        "label": stripped[:120],
        "len": len(stripped),
        "too_long": len(stripped) > 90,
        "is_reject": _is_reject_label(stripped),
        "exact_accept": stripped in _PL_ACCEPT_EXACT,
        "regex_accept": bool(_PL_ACCEPT_BUTTON_RE.match(stripped)) if stripped else False,
        "is_polish_accept": _is_polish_accept_label(stripped),
        "would_click": _is_polish_accept_label(stripped),
    }


def debug_cookie_consent_decision(
    page_text: str = "",
    html: str = "",
    *,
    button_label: str = "",
) -> dict[str, Any]:
    """
    Narzędzie diagnostyczne: czy Playwright cookie fallback się odpali i dlaczego.

    Po co: przy leacie bez maili widać, czy HTML w ogóle wygląda na baner CMP,
    które markery / hinty trafiły, czy jest CAPTCHA, oraz (opcjonalnie) jak
    klasyfikowana jest etykieta przycisku.

    Nie uruchamia Chromium — tylko te same reguły co `should_use_*` / etykiety.
    """
    t = (page_text or "").lower()
    h = (html or "").lower()[:14_000]
    combined = f"{t} {h}"

    pl_hits = [m for m in _PL_COOKIE_MARKERS if m in combined]
    fallback_hits = [m for m in _FALLBACK_COOKIE_MARKERS if m in combined]
    cmp_hits = [hint for hint in _CMP_HTML_HINTS if hint in h]
    captcha_hits = [m for m in _CAPTCHA_MARKERS if m in combined]

    would_run = should_use_playwright_cookie_fallback(page_text, html)
    out: dict[str, Any] = {
        "enable_flag": bool(ENABLE_PLAYWRIGHT_COOKIE_CONSENT),
        "would_run_playwright": would_run,
        "page_text_len": len(page_text or ""),
        "html_len": len(html or ""),
        "pl_marker_hits": pl_hits[:20],
        "fallback_marker_hits": fallback_hits,
        "cmp_html_hits": cmp_hits[:20],
        "captcha_hits": captcha_hits,
        "has_cookie_signal": bool(pl_hits or fallback_hits or cmp_hits),
        "accept_exact_sample": list(_PL_ACCEPT_EXACT[:8]),
        "consent_selectors_count": len(_PL_CONSENT_SELECTORS),
    }
    if button_label:
        out["button"] = debug_accept_label(button_label)
    return out


def _cli_debug(argv: list[str] | None = None) -> int:
    """
    CLI: ``python playwright_cookie_consent.py [--text …] [--html-file …] [--label …]``.

    Opcjonalnie ``--fetch URL`` — realny Chromium (wymaga Playwright), potem
    diagnostyka na pobranym HTML.
    """
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(
        description="Debug banera cookie / CMP (playwright_cookie_consent)."
    )
    parser.add_argument("--text", default="", help="Widoczny tekst strony / snippet")
    parser.add_argument("--html-file", default=None, help="Ścieżka do pliku HTML")
    parser.add_argument("--html", default="", help="Surowy fragment HTML (krótki)")
    parser.add_argument("--label", default="", help="Etykieta przycisku do klasyfikacji")
    parser.add_argument(
        "--fetch",
        default=None,
        metavar="URL",
        help="Pobierz HTML przez Playwright i zdiagnozuj (wolniejsze)",
    )
    args = parser.parse_args(argv)

    html = args.html or ""
    if args.html_file:
        html = Path(args.html_file).read_text(encoding="utf-8", errors="replace")

    fetch_meta: dict[str, Any] = {}
    if args.fetch:
        log = logging.getLogger("cookie_consent_cli")
        logging.basicConfig(level=logging.INFO)
        pw_html = fetch_html_with_cookie_consent(args.fetch, log)
        fetch_meta = {
            "fetch_url": args.fetch,
            "fetch_html_len": len(pw_html or ""),
            "fetch_ok": bool(pw_html),
        }
        if pw_html:
            html = pw_html

    payload = debug_cookie_consent_decision(
        args.text,
        html,
        button_label=args.label,
    )
    if fetch_meta:
        payload["fetch"] = fetch_meta
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli_debug())

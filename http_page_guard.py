# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Moduł: http_page_guard — wykrywanie blokad WAF / Cloudflare / CAPTCHA przy pobieraniu stron.
#
# CO ROBI
#   Na podstawie kodu HTTP, nagłówków, treści HTML i tekstu wyjątków rozpoznaje, że strona jest chroniona
#   (Cloudflare, WAF, CAPTCHA, rate limit) i że dalsze ponawianie żądań nie ma sensu. Udostępnia wyjątek
#   PageAccessBlocked, zbiór kodów WAF_HTTP_STATUS_CODES, detektor HTML (is_waf_html), detektor łączny
#   (is_waf_blocked) oraz kod przyczyny (waf_block_reason).
#
# ROLA W PIPELINE
#   Etap „page fetch / crawl”: scraper i website_full_crawl pomijają zablokowaną witrynę (zamiast
#   retry), a w logach zapisywany jest powód (np. http_403, waf_html, cloudflare_522).
#
# ZALEŻNOŚCI: stdlib re, typing. Brak importów z reszty projektu (moduł liściowy).
#
# WEJŚCIE / WYJŚCIE
#   Funkcje przyjmują (keyword-only) exc / response / html i zwracają bool (is_waf_*) lub str (powód).
#   Nie wykonują żadnych żądań sieciowych i nie mają stanu.
# ============================================================
"""Wykrywanie Cloudflare / WAF / CAPTCHA — pomijanie stron zamiast retry."""
from __future__ import annotations

import re
from typing import Any


# >>> OPIS FUNKCJI: klasa PageAccessBlocked
# Klasa wyjątku: sygnalizuje, że strona jest chroniona (WAF/Cloudflare/CAPTCHA) i należy ją pominąć
# bez ponawiania. Dziedziczy po Exception; nie niesie dodatkowych pól — komunikat przekazuje wywołujący.
class PageAccessBlocked(Exception):
    """Strona chroniona (Cloudflare itp.) — bez ponawiania żądań."""


# Kody HTTP typowe dla Cloudflare i podobnych reverse proxy
WAF_HTTP_STATUS_CODES = frozenset(
    {
        401,
        403,
        429,
        503,
        520,
        521,
        522,
        523,
        524,
        525,
        526,
        527,
        530,
    }
)

_WAF_STRONG_HTML_MARKERS = (
    "cf-browser-verification",
    "challenge-platform",
    "cdn-cgi/challenge",
    "checking your browser",
    "just a moment",
    "enable javascript and cookies",
    "attention required! | cloudflare",
    "ray id:",
    "__cf_chl",
    "cf-chl-bypass",
    "perimeterx",
    "datadome",
    "incapsula incident",
    "sucuri website firewall",
    "distilnetworks",
    "bot protection",
)

_WAF_WEAK_HTML_MARKERS = (
    "cloudflare",
    "captcha",
    "hcaptcha",
    "recaptcha",
    "turnstile",
    "access denied",
    "forbidden",
    "ddos protection",
)

_WAF_ERROR_TEXT_MARKERS = (
    "cloudflare",
    "servererror",
    "522",
    "521",
    "520",
    "captcha",
    "too many requests",
    "access denied",
    "forbidden",
    "bot detected",
    "waf",
)


# >>> OPIS FUNKCJI: funkcja _status_from_response
# Cel: wyciągnąć kod HTTP z obiektu odpowiedzi. Parametry: response (Any) — np. requests.Response lub None.
# Zwraca: int (status_code) albo None, gdy brak odpowiedzi lub atrybutu. Efekty uboczne: brak.
# Błędy: ValueError/TypeError, gdy status_code nie da się zrzutować na int (nie łapane).
def _status_from_response(response: Any) -> int | None:
    if response is None:
        return None
    code = getattr(response, "status_code", None)
    return int(code) if code is not None else None


# >>> OPIS FUNKCJI: funkcja _status_from_exception
# Cel: ustalić kod HTTP związany z wyjątkiem. Parametry: exc (BaseException).
# Zwraca: int — status z exc.response (jeśli jest), a w drugiej kolejności pierwszy kod z listy
#   (401/403/429/503/520–527/530) znaleziony regexem w tekście wyjątku; None, gdy nic nie znaleziono.
# Efekty uboczne: brak. Błędy: brak własnej obsługi.
def _status_from_exception(exc: BaseException) -> int | None:
    resp = getattr(exc, "response", None)
    code = _status_from_response(resp)
    if code is not None:
        return code
    text = str(exc).lower()
    m = re.search(
        r"\b(401|403|429|503|520|521|522|523|524|525|526|527|530)\b",
        text,
    )
    return int(m.group(1)) if m else None


# >>> OPIS FUNKCJI: funkcja _headers_blob
# Cel: spłaszczyć nagłówki odpowiedzi do jednego tekstu małymi literami ("klucz:wartość ..."), by łatwo
#   szukać znaczników Cloudflare (cloudflare, cf-ray, cf-mitigated).
# Parametry: response (Any). Zwraca: str ("" gdy brak odpowiedzi/nagłówków).
# Efekty uboczne: brak. Błędy: dowolny wyjątek przy odczycie nagłówków jest łapany → "".
def _headers_blob(response: Any) -> str:
    if response is None:
        return ""
    try:
        items = getattr(response, "headers", None)
        if items is None:
            return ""
        return " ".join(f"{k}:{v}" for k, v in items.items()).lower()
    except Exception:
        return ""


# >>> OPIS FUNKCJI: funkcja is_waf_html
# Cel: rozpoznać, czy treść HTML to strona blokady/weryfikacji, a nie normalna witryna.
# Parametry: html (str) — analizowane jest pierwsze 80 000 znaków (lower()).
# Zwraca: bool — True gdy występuje mocny znacznik (np. "just a moment", "cf-browser-verification",
#   "datadome") albo gdy dokument jest krótki (< 20 000 znaków; min. 80) i zawiera >= 2 słabe znaczniki
#   (cloudflare, captcha, recaptcha, access denied…). Pusty html → False.
# Efekty uboczne/błędy: brak.
def is_waf_html(html: str) -> bool:
    """Treść wygląda na stronę blokady / weryfikacji, nie na normalną witrynę."""
    if not html:
        return False
    sample = html[:80000].lower()
    if any(m in sample for m in _WAF_STRONG_HTML_MARKERS):
        return True
    if len(html) < 80:
        return False
    weak = sum(1 for m in _WAF_WEAK_HTML_MARKERS if m in sample)
    return weak >= 2 and len(html) < 20000


# >>> OPIS FUNKCJI: funkcja is_waf_blocked
# Cel: zbiorczo zdecydować, czy żądanie zostało zablokowane przez WAF/Cloudflare/CAPTCHA.
# Parametry (keyword-only): exc (BaseException|None) — wyjątek żądania; response (Any) — obiekt odpowiedzi;
#   html (str|None) — treść (jeśli None, brana z response.text).
# Zwraca: bool — True gdy: kod HTTP należy do WAF_HTTP_STATUS_CODES; nagłówki wskazują Cloudflare
#   przy statusie >= 400 lub braku statusu; treść wygląda na stronę blokady; wyjątek niesie kod WAF albo
#   tekst typu 520/521/522/cloudflare; samo html wygląda jak WAF. Inaczej False.
# Efekty uboczne: brak. Błędy: nie rzuca (poza rzutowaniem statusu w _status_from_response).
def is_waf_blocked(
    *,
    exc: BaseException | None = None,
    response: Any = None,
    html: str | None = None,
) -> bool:
    if response is not None:
        status = _status_from_response(response)
        if status in WAF_HTTP_STATUS_CODES:
            return True
        hdr = _headers_blob(response)
        if "cloudflare" in hdr or "cf-ray" in hdr or "cf-mitigated" in hdr:
            if status is None or status >= 400:
                return True
        body = html if html is not None else getattr(response, "text", "") or ""
        if body and is_waf_html(body):
            return True

    if exc is not None:
        status = _status_from_exception(exc)
        if status in WAF_HTTP_STATUS_CODES:
            return True
        low = str(exc).lower()
        if any(m in low for m in _WAF_ERROR_TEXT_MARKERS):
            if status in WAF_HTTP_STATUS_CODES or status in (403, 429, 503) or status is None:
                if "522" in low or "521" in low or "520" in low or "cloudflare" in low:
                    return True
                if status in WAF_HTTP_STATUS_CODES:
                    return True

    if html and is_waf_html(html):
        return True
    return False


# >>> OPIS FUNKCJI: funkcja waf_block_reason
# Cel: zwrócić krótki kod przyczyny blokady do logów/statystyk.
# Parametry (keyword-only): exc, response, html — jak w is_waf_blocked.
# Zwraca: str — "http_<kod>", "waf_html", "cloudflare_522", "cloudflare", "cloudflare_headers" albo
#   domyślnie "waf_blocked" (kolejność sprawdzeń jak w kodzie).
# Efekty uboczne/błędy: brak.
def waf_block_reason(
    *,
    exc: BaseException | None = None,
    response: Any = None,
    html: str | None = None,
) -> str:
    status = _status_from_response(response) or (
        _status_from_exception(exc) if exc else None
    )
    if status in WAF_HTTP_STATUS_CODES:
        return f"http_{status}"
    if html and is_waf_html(html):
        return "waf_html"
    if exc is not None:
        low = str(exc).lower()
        if "522" in low:
            return "cloudflare_522"
        if "cloudflare" in low:
            return "cloudflare"
    hdr = _headers_blob(response)
    if "cloudflare" in hdr or "cf-ray" in hdr:
        return "cloudflare_headers"
    return "waf_blocked"

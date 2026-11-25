# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Uzupełnienie opisu modułu website_full_crawl (komentarz; docstring poniżej opisuje przepływ BFS).
#   Zależności: bs4.BeautifulSoup, email_targeting.get_registrable_domain, stdlib (os, collections.deque,
#   dataclasses, urllib.parse); claude_page_text importowany leniwie w format_crawl_text_for_claude.
#   Wejście: startowy URL firmy oraz wstrzykiwane callbacki scrapera (fetch_page_html, parse_html_page,
#   normalize_website, on_step). Wyjście: WebsiteCrawlResult (pages, urls_visited, urls_skipped, capped).
#   Sieć: sam moduł nie wykonuje żądań — robi to wstrzyknięty fetch_page_html. Limit stron:
#   MAX_SITE_CRAWL_PAGES (80; env SITE_CRAWL_MAX_PAGES, minimum 10).
# ============================================================
"""
Pełny crawl witryny (ta sama domena) przed weryfikacją Claude.

Co robi ten moduł
-----------------
Zbiera HTML z **wielu podstron jednej firmy** (BFS, tylko ta sama domena
rejestracyjna), parsuje każdą stronę callbackiem scrapera i składa wynik
pod Claude / filtr ICP — żeby weryfikacja nie opierała się tylko na homepage.

Przepływ::

    start URL → kolejka BFS → fetch_page_html → parse_html_page
              → extract_all_internal_links (ta sama domena)
              → format_crawl_text_for_claude (tekst do LLM)

Limity: ``MAX_SITE_CRAWL_PAGES`` (domyślnie 80, env ``SITE_CRAWL_MAX_PAGES``).
Pomija PDF/obrazy/CSS/JS, ``mailto:``, feedy WordPress itd.
Nazwa modułu bez zmian.
"""
from __future__ import annotations

import os
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Callable
from urllib.parse import urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup  # pyright: ignore[reportMissingModuleSource]

from email_targeting import get_registrable_domain

# Bezpieczny limit — małe witryny spedycyjne zwykle << 80 podstron.
# Env ``SITE_CRAWL_MAX_PAGES`` może podnieść/obciąć (min. 10).
MAX_SITE_CRAWL_PAGES = 80
_SITE_CRAWL_MAX_ENV = (os.environ.get("SITE_CRAWL_MAX_PAGES") or "").strip()
if _SITE_CRAWL_MAX_ENV.isdigit():
    MAX_SITE_CRAWL_PAGES = max(10, int(_SITE_CRAWL_MAX_ENV))

# Rozszerzenia plików — nie kolejujemy jako „strony HTML” do parse/Claude.
_SKIP_PATH_EXTENSIONS = (
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".zip",
    ".rar",
    ".7z",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".mp4",
    ".mp3",
    ".avi",
    ".css",
    ".js",
    ".xml",
    ".json",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".ico",
)

# Ścieżki / schematy poza treścią oferty (API WP, feed, protokoły nie-HTTP).
_SKIP_PATH_MARKERS = (
    "/wp-json/",
    "/feed/",
    "/xmlrpc",
    "mailto:",
    "tel:",
    "javascript:",
)


# >>> OPIS FUNKCJI: klasa WebsiteCrawlResult
# Klasa danych (dataclass) — wynik jednego crawla BFS po witrynie:
#   pages (dict URL → słownik z parsera: e-maile, telefony, page_text, contact_urls…),
#   urls_visited (kolejność udanych fetch+parse), urls_skipped (pusty HTML lub błąd parsowania),
#   capped (True, gdy po osiągnięciu limitu stron kolejka nie była pusta).
# Wszystkie pola mają wartości domyślne (puste kolekcje/False), więc WebsiteCrawlResult() = „pusty wynik”.
@dataclass
class WebsiteCrawlResult:
    """
    Wynik jednego BFS po witrynie.

    ``pages``: URL → dict z parsera (maile, telefony, page_text, contact_urls…).
    ``urls_visited``: kolejność udanych fetch+parse.
    ``urls_skipped``: pusty HTML / błąd parse.
    ``capped``: True gdy kolejka nie pusta po limicie stron.
    """

    pages: dict[str, dict] = field(default_factory=dict)
    urls_visited: list[str] = field(default_factory=list)
    urls_skipped: list[str] = field(default_factory=list)
    capped: bool = False


# >>> OPIS FUNKCJI: funkcja website_crawl_result_to_dict
# Cel: serializacja wyniku crawla do struktury JSON-owalnej (do cache).
# Parametry: result (WebsiteCrawlResult). Zwraca: dict (dataclasses.asdict — głęboka kopia pól).
# Efekty uboczne: brak. Błędy: TypeError, gdy result nie jest dataclassą.
def website_crawl_result_to_dict(result: WebsiteCrawlResult) -> dict:
    """Serializacja do cache JSON (``asdict``)."""
    return asdict(result)


# >>> OPIS FUNKCJI: funkcja website_crawl_result_from_dict
# Cel: odtworzenie WebsiteCrawlResult z cache.
# Parametry: data (dict) — zapis z website_crawl_result_to_dict (pola mogą być niekompletne).
# Zwraca: WebsiteCrawlResult; dla danych niebędących dict — pusty wynik. Brakujące pola → puste kolekcje.
# Efekty uboczne: brak. Błędy: nie rzuca dla typowych braków (używa "or" i rzutowań).
def website_crawl_result_from_dict(data: dict) -> WebsiteCrawlResult:
    """
    Deserializacja z cache — odporna na braki pól / zły typ.

    Nie-dict → pusty ``WebsiteCrawlResult`` (bezpieczny no-op dla callera).
    """
    if not isinstance(data, dict):
        return WebsiteCrawlResult()
    return WebsiteCrawlResult(
        pages=dict(data.get("pages") or {}),
        urls_visited=list(data.get("urls_visited") or []),
        urls_skipped=list(data.get("urls_skipped") or []),
        capped=bool(data.get("capped")),
    )


# >>> OPIS FUNKCJI: funkcja _normalize_crawl_url
# Cel: oczyścić kandydata URL i zdecydować, czy wolno go dodać do kolejki BFS.
# Parametry: raw_url (str); site_domain (keyword-only, str) — domena rejestracyjna crawlowanej firmy;
#   normalize_website (callable str→str) — normalizator scrapera (może zwrócić "" = odrzuć).
# Zwraca: znormalizowany URL (str) albo "" gdy: pusty/kotwica/mailto/tel/javascript, nie http(s),
#   normalizator odrzucił, występuje marker ze _SKIP_PATH_MARKERS (wp-json, feed…), rozszerzenie z
#   _SKIP_PATH_EXTENSIONS (pdf, obrazy, css, js…), lub domena rejestracyjna jest inna niż site_domain.
# Efekty uboczne: brak. Błędy: wyjątki z normalize_website nie są łapane.
def _normalize_crawl_url(
    raw_url: str,
    *,
    site_domain: str,
    normalize_website: Callable[[str], str],
) -> str:
    """
    Czyści kandydata URL do kolejki BFS albo zwraca ``\"\"`` (odrzut).

    Wymaga http(s), usuwa fragment ``#…``, odpala ``normalize_website`` scrapera,
    filtruje rozszerzenia / markery skip oraz **obcą domenę** (tylko
    ``get_registrable_domain == site_domain``).
    """
    url = (raw_url or "").strip()
    if not url or url.startswith(("#", "mailto:", "tel:", "javascript:")):
        return ""
    if not url.startswith(("http://", "https://")):
        return ""
    url, _frag = urldefrag(url)
    normalized = normalize_website(url)
    if not normalized:
        return ""
    low = normalized.lower()
    for marker in _SKIP_PATH_MARKERS:
        if marker in low:
            return ""
    path = (urlparse(normalized).path or "").lower()
    for ext in _SKIP_PATH_EXTENSIONS:
        if path.endswith(ext):
            return ""
    if get_registrable_domain(normalized) != site_domain:
        return ""
    return normalized


# >>> OPIS FUNKCJI: funkcja extract_all_internal_links
# Cel: zebrać unikalne linki wewnętrzne strony (HTML + opcjonalne extra_urls z parsera).
# Parametry: page_url (str) — baza dla urljoin; html (str) — treść strony; site_domain (keyword-only, str);
#   normalize_website (callable); extra_urls (list[str]|None) — np. contact_urls z parsera.
# Zwraca: list[str] — najpierw extra_urls, potem <a href> (BeautifulSoup, parser html.parser),
#   bez duplikatów, po przejściu przez _normalize_crawl_url.
# Efekty uboczne: brak. Błędy: niepoprawny HTML jest tolerowany przez BeautifulSoup.
def extract_all_internal_links(
    page_url: str,
    html: str,
    *,
    site_domain: str,
    normalize_website: Callable[[str], str],
    extra_urls: list[str] | None = None,
) -> list[str]:
    """
    Zbiera unikalne linki wewnętrzne z HTML (+ opcjonalne ``extra_urls``).

    ``extra_urls`` zwykle z parsera (np. ``contact_urls``: /kontakt, /o-nas).
    ``page_url`` służy do ``urljoin`` względnych ``href``. Kolejność: najpierw
    extra, potem ``<a href>`` z BeautifulSoup — bez duplikatów.
    """
    out: list[str] = []
    seen: set[str] = set()

    # >>> OPIS FUNKCJI: funkcja extract_all_internal_links._add
    # Pomocnicza (zagnieżdżona): normalizuje kandydata i dopisuje go do listy wynikowej, jeśli jest
    # niepusty i jeszcze nie widziany. Parametry: candidate (str). Zwraca None.
    # Efekty uboczne: mutuje domknięte out i seen. Błędy: jak _normalize_crawl_url.
    def _add(candidate: str) -> None:
        normalized = _normalize_crawl_url(
            candidate, site_domain=site_domain, normalize_website=normalize_website
        )
        if normalized and normalized not in seen:
            seen.add(normalized)
            out.append(normalized)

    for candidate in extra_urls or []:
        _add(candidate)

    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup.find_all("a", href=True):
        href = (tag.get("href") or "").strip()
        if not href:
            continue
        _add(urljoin(page_url, href))

    return out


# >>> OPIS FUNKCJI: funkcja format_crawl_text_for_claude
# Cel: cienki wrapper — składa tekst crawla dla Claude, delegując do claude_page_text.format_crawl_text_for_claude.
# Parametry: result (WebsiteCrawlResult); purpose (keyword-only, "verify"/"contact"); per_section_max_chars
#   (keyword-only, int|None) — limit znaków na sekcję (None/0 → CRAWL_SECTION_MAX_CHARS).
# Zwraca: str — sekcje "=== URL ===" oddzielone pustą linią.
# Efekty uboczne: leniwy import claude_page_text (omija cykl importów). Błędy: jak funkcja docelowa.
def format_crawl_text_for_claude(
    result: WebsiteCrawlResult,
    *,
    purpose: str = "verify",
    per_section_max_chars: int | None = None,
) -> str:
    """
    Składa tekst z ``WebsiteCrawlResult`` pod prompt Claude (verify / extract).

    Deleguje do ``claude_page_text.format_crawl_text_for_claude`` — ten moduł
    tylko trzyma kontrakt wyniku crawla; limity znaków są w warstwie Claude.
    """
    from claude_page_text import (
        CRAWL_SECTION_MAX_CHARS,
        format_crawl_text_for_claude as _format_for_claude,
    )

    return _format_for_claude(
        result,
        purpose=purpose,
        per_section_max_chars=per_section_max_chars or CRAWL_SECTION_MAX_CHARS,
    )


# >>> OPIS FUNKCJI: funkcja crawl_entire_website
# Cel: BFS po całej domenie startowego URL (strona → parsowanie → nowe linki wewnętrzne).
# Parametry: website (str) — URL startowy; logger; fetch_page_html (callable url→html, "" = błąd/pusto);
#   parse_html_page (callable (url, html)→dict); normalize_website (callable); on_step (callable|None) —
#   raport postępu "Website-Crawl i/max: url"; max_pages (int, domyślnie MAX_SITE_CRAWL_PAGES).
# Zwraca: WebsiteCrawlResult. Pusty wynik, gdy URL startowy lub jego domena rejestracyjna jest nieprawidłowa.
# Efekty uboczne: wywołania sieciowe wykonywane PRZEZ fetch_page_html; logowanie (info) błędów parsowania
#   i informacji o limicie; callback on_step. capped=True, jeśli po limicie kolejka nie jest pusta.
# Błędy: wyjątek z parse_html_page jest łapany (log info, URL → urls_skipped); odpowiedź niebędąca dict
#   traktowana jak {}. Wyjątki z fetch_page_html nie są łapane tutaj (zakłada się, że callback zwraca "" przy błędzie).
def crawl_entire_website(
    website: str,
    logger,
    *,
    fetch_page_html: Callable[[str], str],
    parse_html_page: Callable[[str, str], dict],
    normalize_website: Callable[[str], str],
    on_step: Callable[[str], None] | None = None,
    max_pages: int = MAX_SITE_CRAWL_PAGES,
) -> WebsiteCrawlResult:
    """
    BFS po całej domenie startowego URL.

    Każda strona: ``fetch_page_html`` → ``parse_html_page`` → odkryj linki
    wewnętrzne (HTML + ``contact_urls`` z parse) → dorzuć do kolejki.
    Zależności fetch/parse/normalize wstrzykuje scraper (requests, cookie
    Playwright, ten sam parser kontaktów co hot-path).

    ``on_step`` — opcjonalny progress UI. Przy wyczerpaniu limitu ustawia
    ``result.capped`` i loguje ile URL zostało w kolejce.
    """
    start = normalize_website(website)
    if not start:
        return WebsiteCrawlResult()

    site_domain = get_registrable_domain(start)
    if not site_domain:
        return WebsiteCrawlResult()

    result = WebsiteCrawlResult()
    queue: deque[str] = deque([start])
    queued: set[str] = {start}

    while queue and len(result.urls_visited) < max_pages:
        url = queue.popleft()
        if url in result.pages:
            continue

        if on_step:
            on_step(
                f"Website-Crawl {len(result.urls_visited) + 1}/{max_pages}: {url}"
            )

        html = fetch_page_html(url)
        if not html:
            result.urls_skipped.append(url)
            continue

        try:
            parsed = parse_html_page(url, html)
        except Exception as exc:
            logger.info("Website-Crawl: błąd parse %s: %s", url, exc)
            result.urls_skipped.append(url)
            continue

        if not isinstance(parsed, dict):
            parsed = {}

        result.pages[url] = parsed
        result.urls_visited.append(url)

        for link in extract_all_internal_links(
            url,
            html,
            site_domain=site_domain,
            normalize_website=normalize_website,
            extra_urls=list(parsed.get("contact_urls") or []),
        ):
            if link not in queued and link not in result.pages:
                queued.add(link)
                queue.append(link)

    if queue:
        result.capped = True
        logger.info(
            "Website-Crawl: limit %s stron (w kolejce zostało %s)",
            max_pages,
            len(queue),
        )

    return result

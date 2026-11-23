# -*- coding: utf-8 -*-
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


def website_crawl_result_to_dict(result: WebsiteCrawlResult) -> dict:
    """Serializacja do cache JSON (``asdict``)."""
    return asdict(result)


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

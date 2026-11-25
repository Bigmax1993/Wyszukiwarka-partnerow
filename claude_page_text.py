# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Moduł: claude_page_text — przygotowanie tekstu z crawla witryny pod prompty Claude.
#
# CO ROBI
#   Sortuje adresy URL tak, aby najpierw trafiały sekcje istotne (oferta / usługi spedycji dla
#   weryfikacji ICP albo kontakt / impressum dla ekstrakcji kontaktów), przycina tekst każdej sekcji
#   (CRAWL_SECTION_MAX_CHARS = 2000 znaków), buduje nagłówek kontekstu (firma, www, wynik Serper,
#   liczba stron, priorytetowe ścieżki) i „automatyczne dowody” — krótkie linie z treści zawierające
#   słowa kluczowe spedycji (FTL, LTL, ADR, flota, grupaż, …).
#
# ROLA W PIPELINE
#   Etap między pełnym crawlem domeny (website_full_crawl) a wywołaniem Claude (page verify /
#   contact extract). Czyste funkcje tekstowe, bez I/O i bez wywołań API.
#
# ZALEŻNOŚCI: website_full_crawl.WebsiteCrawlResult (typ wejściowy); stdlib re, urllib.parse.
#   Uwaga: website_full_crawl importuje tę funkcję leniwie (wewnątrz funkcji), co omija cykl importów.
#
# WEJŚCIE / WYJŚCIE
#   Wejście: lista URL / WebsiteCrawlResult / tekst crawla w formacie sekcji "=== URL ===".
#   Wyjście: posortowane listy URL, skrócone teksty (str), nagłówek (str), wyciąg dowodów (str).
#   Część stałych tekstowych w nagłówkach (FIRMA, SEITEN IM CRAWL, "(keine)") jest po niemiecku —
#   pozostałość po kampanii DE; format jest zgodny z promptami, więc nie został zmieniony.
# ============================================================
"""Przygotowanie tekstu crawla dla Claude (sortowanie URL, nagłówek, dowody)."""
from __future__ import annotations

import re
from urllib.parse import urlparse

from website_full_crawl import WebsiteCrawlResult

# Priorytet URL pod page-verify: oferta / usługi spedycji przed blogiem.
_VERIFY_URL_TIERS: tuple[tuple[str, ...], ...] = (
    (
        "oferta",
        "uslugi",
        "usługi",
        "spedycja",
        "transport",
        "fracht",
        "flota",
        "referenc",
        "o-nas",
        "o-firmie",
        "onas",
    ),
    ("o-nas", "o-firmie", "about", "firma", "przedsiębiorstwo"),
    (
        "ftl",
        "ltl",
        "adr",
        "europa",
        "logistyka",
        "forwarding",
    ),
    ("kontakt", "dane-firmy", "impressum", "contact"),
)

_CONTACT_URL_TIERS: tuple[tuple[str, ...], ...] = (
    ("kontakt", "dane-firmy", "dane_firmy", "o-firmie", "biuro", "impressum", "contact"),
    ("o-nas", "about", "firma"),
    ("oferta", "uslugi", "usługi"),
)

# Linie dowodów wklejane u góry promptu verify (PL FAS).
_EVIDENCE_KEYWORDS = (
    "spedycja",
    "spedytor",
    "freight",
    "forwarding",
    "ftl",
    "ltl",
    "fracht",
    "transport",
    "grupaż",
    "grupaz",
    "adr",
    "chłodnia",
    "chlodnia",
    "europa",
    "oferta",
    "flota",
    "naczepa",
    "dyspozytor",
    "organizacja transportu",
    "całopojazdowy",
    "calopojazdowy",
)
CRAWL_SECTION_MAX_CHARS = 2000


# >>> OPIS FUNKCJI: funkcja sort_crawl_urls_for_claude
# Cel: uporządkować URL-e crawla tak, by w prompcie najpierw pojawiły się najbardziej użyteczne podstrony.
# Parametry: urls (list[str]); purpose (keyword-only, str, domyślnie "verify") — "contact" wybiera
#   progi _CONTACT_URL_TIERS (kontakt/impressum przed ofertą), każda inna wartość → _VERIFY_URL_TIERS
#   (oferta/usługi/spedycja przed „o nas”, segmentami FTL/LTL/ADR i kontaktem).
# Zwraca: nowa lista (sorted) — klucz: (numer progu, url lower); URL bez dopasowania: strona główna
#   (pusta ścieżka) po progach, a pozostałe na samym końcu.
# Efekty uboczne: brak (oryginalna lista nie jest mutowana). Błędy: None w elementach jest tolerowane.
def sort_crawl_urls_for_claude(urls: list[str], *, purpose: str = "verify") -> list[str]:
    """Kolejność sekcji w prompcie: verify=referenzen/karriere, contact=impressum."""
    tiers = _CONTACT_URL_TIERS if purpose == "contact" else _VERIFY_URL_TIERS

    # >>> OPIS FUNKCJI: funkcja sort_crawl_urls_for_claude._score
    # Pomocnicza (zagnieżdżona): klucz sortowania pojedynczego URL. Parametry: url (str). Zwraca: krotkę
    # (numer progu, url lower) — niższy numer = ważniejsza podstrona (pierwszy próg, którego wzorzec
    # występuje w URL). Bez dopasowania: (len(tiers), url) dla strony głównej (pusta ścieżka) albo
    # (len(tiers)+1, url) dla pozostałych. Efekty uboczne/błędy: brak.
    def _score(url: str) -> tuple[int, str]:
        low = (url or "").lower()
        for tier, patterns in enumerate(tiers):
            if any(p in low for p in patterns):
                return (tier, low)
        path = (urlparse(url).path or "/").strip("/")
        if not path:
            return (len(tiers), low)
        return (len(tiers) + 1, low)

    return sorted(urls, key=_score)


# >>> OPIS FUNKCJI: funkcja truncate_crawl_section_text
# Cel: ograniczyć długość tekstu pojedynczej sekcji crawla.
# Parametry: text (str|None); max_chars (keyword-only, int, domyślnie 2000).
# Zwraca: str — tekst po strip(); jeśli dłuższy niż max_chars, ucięty do max_chars-3 znaków + "...".
# Efekty uboczne: brak. Błędy: brak (None → ""). Uwaga: max_chars<3 daje wycinek z ujemnym indeksem.
def truncate_crawl_section_text(text: str, *, max_chars: int = CRAWL_SECTION_MAX_CHARS) -> str:
    """Skróć tekst sekcji crawla do max_chars (z wielokropkiem)."""
    raw = (text or "").strip()
    if len(raw) <= max_chars:
        return raw
    return raw[: max_chars - 3] + "..."


# >>> OPIS FUNKCJI: funkcja extract_crawl_section_urls
# Cel: odczytać adresy z nagłówków sekcji "=== https://... ===" w tekście crawla.
# Parametry: page_text (str|None); limit (keyword-only, int, domyślnie 8) — maks. liczba URL.
# Zwraca: list[str] — URL-e w kolejności występowania (regex), albo [] gdy brak markera "=== http".
# Efekty uboczne/błędy: brak.
def extract_crawl_section_urls(page_text: str, *, limit: int = 8) -> list[str]:
    """URL-e z nagłówków sekcji ``=== https://… ===`` w tekście crawla."""
    if "=== http" not in (page_text or ""):
        return []
    return re.findall(r"=== (https?://\S+) ===", page_text)[:limit]


# >>> OPIS FUNKCJI: funkcja build_claude_context_header
# Cel: zbudować wielolinijkowy nagłówek kontekstu dla promptów Claude.
# Parametry: company_name (str); website (str); serper_blob (keyword-only, str) — wynik/snippet z Serper
#   (do 800 znaków); pages_crawled (int) — liczba stron w crawlu (0 = pomiń linię); priority_urls
#   (list[str]|None) — priorytetowe URL-e (do 8; wypisywane jako ścieżki względem website).
# Zwraca: str — linie "FIRMA:", "WEBSITE:", opcjonalnie "SERPER-KONTEXT:", "SEITEN IM CRAWL:",
#   "PRIORITAETS-URLS:" połączone znakiem nowej linii.
# Efekty uboczne: brak. Błędy: brak (None w polach tekstowych jest tolerowane tam, gdzie użyto "or").
def build_claude_context_header(
    company_name: str,
    website: str,
    *,
    serper_blob: str = "",
    pages_crawled: int = 0,
    priority_urls: list[str] | None = None,
) -> str:
    """Nagłówek kontekstu dla promptów Claude (firma, www, Serper, crawl)."""
    lines = [
        f"FIRMA: {company_name}",
        f"WEBSITE: {website}",
    ]
    serper = (serper_blob or "").strip()
    if serper:
        lines.append(f"SERPER-KONTEXT: {serper[:800]}")
    if pages_crawled:
        lines.append(f"SEITEN IM CRAWL: {pages_crawled}")
    if priority_urls:
        site = (website or "").rstrip("/")
        short_parts: list[str] = []
        for url in priority_urls[:8]:
            path = (url or "").replace(site, "").strip("/") or "/"
            short_parts.append(path)
        lines.append(f"PRIORITAETS-URLS: {', '.join(short_parts)}")
    return "\n".join(lines)


# >>> OPIS FUNKCJI: funkcja build_automatic_evidence_excerpt
# Cel: wyłuskać z tekstu crawla krótkie „dowody” działalności spedycyjnej na górę promptu verify.
# Parametry: page_text (str|None) — tekst crawla (w formacie sekcji "=== URL ===" lub zwykły);
#   max_lines (keyword-only, int, domyślnie 30) — limit linii wyniku.
# Zwraca: str — linie "• [url] fragment" (fragment <= 240 znaków, min. 12 znaków, zawiera słowo z
#   _EVIDENCE_KEYWORDS, deduplikacja po pierwszych 120 znakach); "(keine)" dla pustego wejścia;
#   "(keine automatischen Treffer)" gdy nic nie dopasowano.
# Efekty uboczne: brak (wewnętrzna funkcja pomocnicza _maybe_add dopisuje do lokalnych list). Błędy: brak.
def build_automatic_evidence_excerpt(page_text: str, *, max_lines: int = 30) -> str:
    """Krótkie linie z crawl-a pasujące do retail/GU — na górze promptu verify."""
    raw = (page_text or "").strip()
    if not raw:
        return "(keine)"

    lines: list[str] = []
    seen: set[str] = set()

    # >>> OPIS FUNKCJI: funkcja build_automatic_evidence_excerpt._maybe_add
    # Pomocnicza (zagnieżdżona): dodaje fragment do listy dowodów, jeśli po normalizacji białych znaków ma
    # >= 12 znaków, zawiera słowo kluczowe z _EVIDENCE_KEYWORDS i nie jest duplikatem (klucz = pierwsze 120
    # znaków). Parametry: prefix (str) — np. "[url] "; fragment (str). Zwraca None.
    # Efekty uboczne: mutuje domknięte lines i seen. Błędy: brak.
    def _maybe_add(prefix: str, fragment: str) -> None:
        frag = " ".join(fragment.split()).strip()
        if len(frag) < 12:
            return
        low = frag.lower()
        if not any(k in low for k in _EVIDENCE_KEYWORDS):
            return
        key = frag[:120]
        if key in seen:
            return
        seen.add(key)
        lines.append(f"• {prefix}{frag[:240]}")

    if "=== http" in raw:
        sections = re.split(r"(?=\n=== https?://)", "\n" + raw)
        for sec in sections:
            sec = sec.strip()
            if not sec:
                continue
            m = re.match(r"=== (https?://\S+) ===\s*(.*)", sec, re.DOTALL)
            if not m:
                continue
            url, body = m.group(1), m.group(2)
            for part in re.split(r"[\n\r]+", body):
                _maybe_add(f"[{url}] ", part)
                if len(lines) >= max_lines:
                    break
            if len(lines) >= max_lines:
                break
    else:
        for part in re.split(r"[\n\r.!?]+", raw):
            _maybe_add("", part)
            if len(lines) >= max_lines:
                break

    return "\n".join(lines) if lines else "(keine automatischen Treffer)"


# >>> OPIS FUNKCJI: funkcja format_crawl_text_for_claude
# Cel: złożyć końcowy tekst crawla dla Claude: posortowane sekcje "=== URL ===" + przycięty tekst.
# Parametry: result (WebsiteCrawlResult) — wynik BFS; purpose (keyword-only, "verify"|"contact");
#   per_section_max_chars (keyword-only, int, domyślnie 2000).
# Zwraca: str — sekcje oddzielone pustą linią; puste strony pomijane; "" gdy brak tekstu.
# Efekty uboczne: brak. Błędy: brak (brakująca strona w result.pages traktowana jak pusty dict).
def format_crawl_text_for_claude(
    result: WebsiteCrawlResult,
    *,
    purpose: str = "verify",
    per_section_max_chars: int = CRAWL_SECTION_MAX_CHARS,
) -> str:
    """Tekst crawla: sortowanie URL + limit znaków na sekcję."""
    urls = sort_crawl_urls_for_claude(result.urls_visited, purpose=purpose)
    parts: list[str] = []
    for url in urls:
        page = result.pages.get(url) or {}
        text = truncate_crawl_section_text(
            page.get("page_text") or "", max_chars=per_section_max_chars
        )
        if text:
            parts.append(f"=== {url} ===\n{text}")
    return "\n\n".join(parts)

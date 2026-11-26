# -*- coding: utf-8 -*-
"""
Faza B — Gap-fill kontaktów z Maps (Faza A) przez Serper /search.

Skanuje cache["contacts"] pod kątem luk (brak email / sensownej WWW / telefonu),
buduje zapytania "{nazwa} {miasto} spedycja", woła Serper, potem istniejący
lej enrich (crawl → extract; ICP nie kasuje kontaktów) i merge w ten sam rekord.

Polityka Excela: pełny kontakt (e-mail + telefon) → Kontakte.
Skrajna ostateczność: po wyczerpaniu gap-fill rekord zostaje w JSON
(``still_gap`` / ``needs_enrich``) i nie trafia do Excela.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import requests

LOG = logging.getLogger("gap_fill_serper")

GAP_STATUS_NEEDS_ENRICH = "needs_enrich"
GAP_STATUS_ENRICHED = "enriched"
GAP_STATUS_STILL_GAP = "still_gap"

GAP_FILL_MAX_DEFAULT = 40
GAP_FILL_MAX_QUERIES_PER_CONTACT = 2
GAP_FILL_STILL_GAP_TTL_DAYS = 7
GAP_FILL_SERPER_NUM = 8

_CITY_FROM_POSTAL = re.compile(
    r"\b\d{2}-\d{3}\s+([A-ZĄĆĘŁŃÓŚŹŻ][A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż\-]+"
    r"(?:\s+[A-ZĄĆĘŁŃÓŚŹŻ][A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż\-]+)?)"
)
_CITY_FROM_TERM = re.compile(
    r"\b(Głogów|Glogow|Wrocław|Warszawa|Kraków|Poznań|Gdańsk|Łódź|"
    r"Szczecin|Lublin|Bydgoszcz|Białystok|Katowice|Gdynia|Częstochowa|"
    r"Radom|Sosnowiec|Toruń|Kielce|Rzeszów|Gliwice|Zabrze|Olsztyn|"
    r"Bielsko-Biała|Bytom|Zielona Góra|Rybnik|Ruda Śląska|Opole|"
    r"Tychy|Gorzów|Elbląg|Płock|Wałbrzych|Włocławek|Tarnów|Chorzów|"
    r"Koszalin|Kalisz|Legnica|Grudziądz|Słupsk|Jaworzno|"
    r"Jastrzębie-Zdrój|Nowy Sącz)\b",
    re.I,
)


def _env_int(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def is_maps_url(url: str) -> bool:
    low = (url or "").lower()
    return "google." in low and "/maps" in low


def has_sensible_website(info: dict) -> bool:
    www = (info.get("official_website") or info.get("www") or "").strip()
    if not www:
        return False
    return not is_maps_url(www)


def has_email(info: dict) -> bool:
    target = (info.get("email_target") or info.get("email") or "").strip()
    if target and "@" in target:
        return True
    found = info.get("emails_found") or ""
    if isinstance(found, (list, tuple, set)):
        return any("@" in str(x) for x in found)
    return "@" in str(found)


def has_phone(info: dict) -> bool:
    phone = (info.get("telefon") or info.get("phones_found") or info.get("phone") or "")
    if not phone:
        return False
    try:
        import pl_fas_spedycja_scraper as s

        picked = s.pick_best_pl_phone(phone)
        if picked:
            return True
        if isinstance(phone, (list, tuple, set)):
            phone = next((str(x).strip() for x in phone if str(x).strip()), "")
        else:
            phone = str(phone).split(",", 1)[0].strip()
        return bool(s._excel_phone_ok(phone))
    except Exception:
        digits = re.sub(r"\D", "", str(phone))
        return len(digits) >= 9


def contact_has_gap(info: dict) -> bool:
    """Luka: brak e-maila LUB brak telefonu LUB brak sensownej WWW."""
    if not isinstance(info, dict):
        return False
    if has_email(info) and has_phone(info) and has_sensible_website(info):
        return False
    if not has_email(info):
        return True
    if not has_phone(info):
        return True
    if not has_sensible_website(info):
        return True
    return False


def _enriched_within_ttl(
    info: dict, *, ttl_days: int = GAP_FILL_STILL_GAP_TTL_DAYS
) -> bool:
    raw = (info.get("enriched_at") or "").strip()
    if not raw:
        return False
    try:
        at = datetime.fromisoformat(raw)
    except ValueError:
        return False
    return datetime.now() - at < timedelta(days=ttl_days)


def queries_tried_within_ttl(
    info: dict, *, ttl_days: int = GAP_FILL_STILL_GAP_TTL_DAYS
) -> set[str]:
    """Query już odpalone w TTL — nie spamować tych samych w still_gap."""
    if not _enriched_within_ttl(info, ttl_days=ttl_days):
        return set()
    raw = info.get("serper_gap_queries") or []
    if not isinstance(raw, list):
        return set()
    return {str(q).strip().lower() for q in raw if str(q).strip()}


def filter_queries_outside_ttl(info: dict, queries: list[str]) -> list[str]:
    tried = queries_tried_within_ttl(info)
    if not tried:
        return list(queries)
    return [q for q in queries if q.strip().lower() not in tried]


def extract_city_hint(info: dict) -> str:
    addr = (info.get("full_address") or info.get("adres") or "").strip()
    m = _CITY_FROM_POSTAL.search(addr)
    if m:
        return m.group(1).strip()
    term = (info.get("discovery_search_term") or "").strip()
    m2 = _CITY_FROM_TERM.search(term)
    if m2:
        return m2.group(1).strip()
    m3 = _CITY_FROM_TERM.search(addr)
    if m3:
        return m3.group(1).strip()
    # ostatni segment adresu po przecinku
    if "," in addr:
        tail = addr.split(",")[-1].strip()
        tail = re.sub(r"^\d{2}-\d{3}\s+", "", tail).strip()
        if 2 <= len(tail) <= 40 and not tail.lower().startswith("ul"):
            return tail
    return ""


def company_name_of(info: dict) -> str:
    return (
        info.get("company_name_clean")
        or info.get("company_name")
        or info.get("company_name_raw")
        or info.get("nazwa")
        or ""
    ).strip()


def build_gap_fill_queries(info: dict, *, max_queries: int = GAP_FILL_MAX_QUERIES_PER_CONTACT) -> list[str]:
    name = company_name_of(info)
    if not name:
        return []
    city = extract_city_hint(info)
    variants: list[str] = []
    if city:
        variants.extend(
            [
                f"{name} {city} spedycja",
                f"{name} {city} firma spedycyjna",
            ]
        )
    else:
        variants.extend(
            [
                f"{name} spedycja Polska",
                f"{name} firma spedycyjna",
            ]
        )
    # dedupe zachowując kolejność
    seen: set[str] = set()
    out: list[str] = []
    for q in variants:
        qn = " ".join(q.split())
        if qn.lower() in seen:
            continue
        seen.add(qn.lower())
        out.append(qn)
        if len(out) >= max_queries:
            break
    return out


def should_attempt_gap_fill(info: dict) -> bool:
    """Czy rekord ma lukę i są jeszcze świeże query (TTL) albo WWW do crawla."""
    if not isinstance(info, dict):
        return False
    if (info.get("merged_into") or "").strip():
        return False
    if not contact_has_gap(info):
        return False
    # Jest WWW, brak maila → enrich bez nowych Serper query
    if has_sensible_website(info) and not has_email(info):
        return True
    qs = filter_queries_outside_ttl(info, build_gap_fill_queries(info))
    return bool(qs)


def iter_gap_contacts(
    contacts: dict[str, Any],
    *,
    max_n: int | None = None,
) -> list[tuple[str, dict]]:
    rows: list[tuple[str, dict]] = []
    for key, info in (contacts or {}).items():
        if not isinstance(info, dict):
            continue
        if not should_attempt_gap_fill(info):
            continue
        rows.append((key, info))
    # najpierw needs_enrich z Maps
    rows.sort(
        key=lambda kv: (
            0 if (kv[1].get("gap_status") or "") == GAP_STATUS_NEEDS_ENRICH else 1,
            0 if (kv[1].get("discovery_source") or "") == "google_maps" else 1,
            company_name_of(kv[1]).lower(),
        )
    )
    if max_n is not None:
        rows = rows[:max_n]
    return rows


def find_contact_key_by_domain(
    contacts: dict[str, Any],
    website: str,
    *,
    scraper_mod: Any,
    exclude_key: str = "",
) -> str | None:
    """
    Jeśli domena już istnieje w contacts — zwróć klucz właściciela (bez tworzenia nowego).
    """
    www = scraper_mod.normalize_website(website or "")
    if not www or is_maps_url(www):
        return None
    base = scraper_mod.website_base_url(www) or www
    dom = scraper_mod.get_registrable_domain(base)
    if not dom:
        return None
    # dokładny klucz bazowy
    for cand in (base, www, base.rstrip("/"), www.rstrip("/")):
        if cand and cand in contacts and cand != exclude_key:
            return cand
    for key, info in (contacts or {}).items():
        if key == exclude_key or not isinstance(info, dict):
            continue
        if (info.get("merged_into") or "").strip():
            continue
        key_dom = ""
        if not is_maps_url(key):
            key_dom = scraper_mod.get_registrable_domain(key)
        info_www = info.get("official_website") or info.get("www") or ""
        info_dom = (
            scraper_mod.get_registrable_domain(info_www) if info_www else ""
        )
        if dom and (key_dom == dom or info_dom == dom):
            return key
    return None


def store_gap_fill_result(
    contacts: dict[str, Any],
    source_key: str,
    updated: dict,
    *,
    scraper_mod: Any,
) -> str:
    """
    Zapis wyniku Fazy B: tylko uzupełnij istniejący rekord domeny; nie twórz duplikatu.
    Zwraca klucz docelowy.
    """
    www = (updated.get("official_website") or "").strip()
    owner = (
        find_contact_key_by_domain(
            contacts, www, scraper_mod=scraper_mod, exclude_key=source_key
        )
        if www and not is_maps_url(www)
        else None
    )
    if owner:
        merged = merge_enrichment_into_contact(
            contacts.get(owner) or {},
            updated,
            queries=list(updated.get("serper_gap_queries") or []),
            website=www,
        )
        # zachowaj maps_url z source jeśli owner nie ma
        if not (merged.get("maps_url") or "").strip():
            merged["maps_url"] = (updated.get("maps_url") or "").strip() or (
                contacts.get(source_key) or {}
            ).get("maps_url", "")
        contacts[owner] = merged
        if source_key != owner and source_key in contacts:
            stub = dict(contacts[source_key])
            stub["merged_into"] = owner
            stub["gap_status"] = merged.get("gap_status") or GAP_STATUS_ENRICHED
            stub["enriched_at"] = merged.get("enriched_at") or datetime.now().isoformat()
            stub["serper_gap_queries"] = list(merged.get("serper_gap_queries") or [])
            contacts[source_key] = stub
        # posprzątaj wpis www utworzony ubocznie przez enrich
        base = scraper_mod.website_base_url(www) or www
        if base in contacts and base not in (owner, source_key):
            # fold + usuń duplikat tylko gdy to świeża kopia bez unikalnych danych
            other = contacts[base]
            if (other.get("merged_into") or "") == owner or not has_email(other):
                contacts[owner] = merge_enrichment_into_contact(
                    contacts[owner],
                    other,
                    queries=list(contacts[owner].get("serper_gap_queries") or []),
                    website=www,
                )
                del contacts[base]
        return owner

    contacts[source_key] = updated
    if www and not is_maps_url(www):
        base = scraper_mod.website_base_url(www) or www
        # enrich mógł dopisać contacts[base] — scal z powrotem do source_key
        if base in contacts and base != source_key:
            contacts[source_key] = merge_enrichment_into_contact(
                contacts[source_key],
                contacts[base],
                queries=list(updated.get("serper_gap_queries") or []),
                website=www,
            )
            del contacts[base]
        # NIE twórz osobnego klucza domeny — jeden rekord (source_key), www w polach
    return source_key


def serper_search_candidates(
    query: str,
    *,
    cache: dict,
    logger: logging.Logger,
    num: int = GAP_FILL_SERPER_NUM,
) -> list[dict]:
    """Serper /search → lista {link, title, snippet}. Używa budżetu dziennego scrapera."""
    import pl_fas_spedycja_scraper as s

    q = (query or "").strip()
    if not q:
        return []
    bucket = cache.setdefault("serper_gap_fill", {})
    if q in bucket and isinstance(bucket[q], dict):
        cached_rows = bucket[q].get("rows")
        if isinstance(cached_rows, list):
            return [dict(r) for r in cached_rows]

    api_key = s.get_serper_api_key()
    if not api_key:
        logger.warning("Gap-fill: brak SERPER_API_KEY")
        return []
    if s.is_serper_limit_reached_today(cache) or s.is_serper_api_exhausted(cache):
        logger.warning("Gap-fill: limit/exhaust Serper")
        return []
    _today, _used, remaining = s.get_remaining_daily_serper_limit(cache)
    if remaining <= 0:
        return []

    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    payload = {
        "q": q,
        "gl": s.SERPER_COUNTRY,
        "hl": s.SERPER_LANGUAGE,
        "num": num,
    }
    try:
        s.console_step(f"Gap-fill Serper: {q}")
        s.increase_daily_serper_counter(cache, 1)
        resp = s.request_with_retry(
            requests.post,
            s.SERPER_API_URL,
            logger,
            headers=headers,
            json=payload,
            timeout=s.SERPER_TIMEOUT,
        )
        data = resp.json()
    except Exception as e:
        if s.handle_serper_api_failure(cache, e, logger):
            return []
        logger.warning("Gap-fill Serper error '%s': %s", q, e)
        return []

    rows: list[dict] = []
    seen: set[str] = set()
    for item in data.get("organic") or []:
        link = s.normalize_website(item.get("link") or "")
        if not link or link in seen or is_maps_url(link):
            continue
        seen.add(link)
        rows.append(
            {
                "link": link,
                "title": (item.get("title") or "").strip(),
                "snippet": (item.get("snippet") or "").strip(),
            }
        )
    bucket[q] = {"rows": rows, "at": datetime.now().isoformat()}
    return rows


def _pick_best_website(
    candidates: list[dict],
    *,
    company_name: str,
    scraper_mod: Any,
) -> str:
    if not candidates:
        return ""
    scored = []
    for c in candidates:
        link = c.get("link") or ""
        if not link or is_maps_url(link):
            continue
        if not scraper_mod.is_poland_pl_candidate(
            link, c.get("title") or "", c.get("snippet") or ""
        ):
            continue
        if not scraper_mod.is_serper_only_pending_candidate(
            url=link,
            name=company_name or (c.get("title") or ""),
            text=f"{c.get('title', '')} {c.get('snippet', '')}",
            search_term=f"{company_name} spedycja",
        ):
            # luźniej: jeśli nazwa firmy pojawia się w title — OK
            title = (c.get("title") or "").lower()
            if company_name and company_name.split()[0].lower() not in title:
                continue
        score = scraper_mod.score_serper_candidate(
            link,
            c.get("title") or "",
            c.get("snippet") or "",
            company_name,
        )
        scored.append((score, link))
    if not scored:
        # fallback: pierwszy .pl nie-katalog
        for c in candidates:
            link = c.get("link") or ""
            host = (urlparse(link).netloc or "").lower()
            if host.endswith(".pl") and not is_maps_url(link):
                return scraper_mod.website_base_url(link) or link
        return ""
    scored.sort(key=lambda x: x[0], reverse=True)
    best = scored[0][1]
    return scraper_mod.website_base_url(best) or best


def contact_to_pipeline_row(key: str, info: dict, *, website: str = "") -> dict:
    name = company_name_of(info)
    www = website or (info.get("official_website") or "")
    if www and is_maps_url(www):
        www = website or ""
    maps_url = (info.get("maps_url") or "").strip()
    url = www or maps_url or key
    return {
        "url": url,
        "www": www or url,
        "official_website": www,
        "maps_url": maps_url,
        "nazwa": name,
        "company_name_clean": name,
        "company_name_raw": info.get("company_name_raw") or name,
        "full_address": info.get("full_address") or info.get("adres") or "",
        "adres": info.get("full_address") or info.get("adres") or "",
        "telefon": info.get("telefon") or info.get("phones_found") or "",
        "page_snippet": info.get("page_snippet") or "",
        "fraza": info.get("discovery_search_term") or "",
        "kategoria": info.get("discovery_search_term") or "",
        "discovery_source": info.get("discovery_source") or "google_maps",
        "gap_status": info.get("gap_status") or GAP_STATUS_NEEDS_ENRICH,
        "email_target": info.get("email_target") or "",
        "bundesland": info.get("discovery_wojewodztwo") or info.get("bundesland") or "",
    }


def merge_enrichment_into_contact(
    info: dict,
    enriched: dict,
    *,
    queries: list[str],
    website: str = "",
) -> dict:
    """Aktualizuje ten sam rekord contacts — gap_status / email / www / telefon."""
    out = dict(info)
    www = (
        website
        or enriched.get("official_website")
        or enriched.get("www")
        or out.get("official_website")
        or ""
    )
    if www and not is_maps_url(www):
        out["official_website"] = www
        out["www"] = www
    email = (enriched.get("email_target") or out.get("email_target") or "").strip()
    if email:
        out["email_target"] = email
    phones = (
        enriched.get("phones_found")
        or enriched.get("telefon")
        or out.get("phones_found")
        or out.get("telefon")
        or ""
    )
    if phones:
        try:
            import pl_fas_spedycja_scraper as s

            picked = s.pick_best_pl_phone(phones)
        except Exception:
            picked = ""
        clean = picked or phones
        out["phones_found"] = clean
        out["telefon"] = clean if picked else phones
    for k in (
        "retail_verified",
        "verification_reason",
        "retail_chains_found",
        "is_small_firm",
        "is_gu",
        "gu_marker",
        "emails_found",
        "contact_sources",
        "page_snippet",
        "company_name_clean",
        "company_name",
    ):
        if enriched.get(k) not in (None, ""):
            out[k] = enriched[k]
    out["serper_gap_queries"] = list(queries)
    out["enriched_at"] = datetime.now().isoformat()
    if not contact_has_gap(out):
        out["gap_status"] = GAP_STATUS_ENRICHED
        out["email_status"] = (
            "queued" if email else (out.get("email_status") or "pending_www_verify")
        )
        if out["email_status"] == "pending_gap_fill":
            out["email_status"] = "pending_www_verify"
    else:
        out["gap_status"] = GAP_STATUS_STILL_GAP
        out["email_status"] = "pending_gap_fill"
    return out


def gap_fill_one_contact(
    key: str,
    info: dict,
    *,
    cache: dict,
    logger: logging.Logger,
) -> dict:
    """Jedna firma: Serper queries → www → enrich → merge."""
    import pl_fas_spedycja_scraper as s

    name = company_name_of(info)
    all_queries = build_gap_fill_queries(info)
    queries = filter_queries_outside_ttl(info, all_queries)
    prev_queries = list(info.get("serper_gap_queries") or [])
    used_queries: list[str] = []
    website = ""
    if has_sensible_website(info):
        website = s.normalize_website(info.get("official_website") or "")

    if not website:
        if not queries:
            updated = dict(info)
            updated["gap_status"] = GAP_STATUS_STILL_GAP
            updated["email_status"] = "pending_gap_fill"
            return updated
        for q in queries:
            used_queries.append(q)
            cands = serper_search_candidates(q, cache=cache, logger=logger)
            website = _pick_best_website(cands, company_name=name, scraper_mod=s)
            if website:
                s.console_step(f"Gap-fill WWW: {name} → {website}")
                break
    else:
        # crawl istniejącego WWW — bez nowego Serper (albo 0 query w TTL)
        used_queries = []

    # zachowaj historię query w TTL + nowe
    merged_query_history: list[str] = []
    seen_q: set[str] = set()
    for q in prev_queries + used_queries:
        ql = str(q).strip()
        if not ql or ql.lower() in seen_q:
            continue
        seen_q.add(ql.lower())
        merged_query_history.append(ql)

    if not website and not has_sensible_website(info):
        updated = dict(info)
        updated["serper_gap_queries"] = merged_query_history
        updated["enriched_at"] = datetime.now().isoformat()
        updated["gap_status"] = GAP_STATUS_STILL_GAP
        updated["email_status"] = "pending_gap_fill"
        return updated

    row = contact_to_pipeline_row(key, info, website=website)
    # enrich zapisuje pod row["url"] — potem store_gap_fill_result scala domenę
    enriched = s.enrich_row_with_contacts(row, cache, logger, force_refresh=True)
    # jeśli enrich dopisał contacts[website], nie zostawiaj go jako osobnego leada
    contacts = cache.setdefault("contacts", {})
    if website:
        base = s.website_base_url(website) or website
        if base in contacts and base != key:
            # tymczasowo — store_gap_fill_result zdecyduje o ownerze
            pass
    return merge_enrichment_into_contact(
        info, enriched, queries=merged_query_history, website=website
    )


def run_gap_fill(
    cache: dict,
    logger: logging.Logger | None = None,
    *,
    max_contacts: int | None = None,
) -> dict[str, int]:
    """
    Faza B na całym cache["contacts"].

    Zwraca statystyki: scanned, attempted, enriched, still_gap, skipped.
    """
    import pl_fas_spedycja_scraper as s

    log = logger or LOG
    max_n = max_contacts
    if max_n is None:
        max_n = _env_int("GAP_FILL_MAX", GAP_FILL_MAX_DEFAULT)

    contacts = cache.setdefault("contacts", {})
    targets = iter_gap_contacts(contacts, max_n=max_n)
    stats = {
        "scanned": len(contacts),
        "queued": len(targets),
        "attempted": 0,
        "enriched": 0,
        "still_gap": 0,
        "skipped": 0,
        "errors": 0,
    }
    s.console_step(
        f"Gap-fill Serper: kolejka {len(targets)} / contacts={len(contacts)} (max={max_n})"
    )
    for key, info in targets:
        if s.is_serper_api_exhausted(cache) or s.is_serper_limit_reached_today(cache):
            s.console_step("Gap-fill: stop — limit Serper")
            break
        if s.request_stop_on_runtime_limit(log, console_step_fn=s.console_step):
            s.console_step("Gap-fill: stop — limit czasu")
            break
        name = company_name_of(info)
        stats["attempted"] += 1
        try:
            updated = gap_fill_one_contact(key, info, cache=cache, logger=log)
            target_key = store_gap_fill_result(
                contacts, key, updated, scraper_mod=s
            )
            status = (contacts.get(target_key) or updated).get("gap_status") or ""
            if status == GAP_STATUS_ENRICHED:
                stats["enriched"] += 1
                s.console_step(
                    f"Gap-fill OK: {name} → enriched (key={target_key[:60]})"
                )
            else:
                stats["still_gap"] += 1
                s.console_step(f"Gap-fill: {name} → still_gap")
            s.save_cache(cache, log)
        except Exception as e:
            stats["errors"] += 1
            log.exception("Gap-fill error %s: %s", key[:80], e)
            s.console_step(f"Gap-fill ERROR: {name}: {e}")
    return stats


def main(argv: list[str] | None = None) -> int:
    import sys

    import pl_fas_spedycja_scraper as s

    argv = list(argv if argv is not None else sys.argv[1:])
    # aliasy CLI: --gap-fill-only | --gap-fill-serper
    max_contacts = None
    if "--max" in argv:
        i = argv.index("--max")
        if i + 1 < len(argv):
            try:
                max_contacts = int(argv[i + 1])
            except ValueError:
                max_contacts = None
    if "--run-config" in argv:
        i = argv.index("--run-config")
        if i + 1 < len(argv):
            from pathlib import Path

            from scraper_run_config import apply_run_config_file

            cfg = Path(argv[i + 1])
            apply_run_config_file(s, cfg, Path(s.__file__).resolve().parent)

    logger = s.setup_logging()
    s.ensure_ssl_cert_env(logger)
    if not s.get_serper_api_key():
        print("Brak SERPER_API_KEY — gap-fill wymaga Serper.")
        return 2
    cache = s.load_cache(logger)
    stats = run_gap_fill(cache, logger, max_contacts=max_contacts)
    s.save_cache(cache, logger)
    # Excel sync
    cache_rows = s.build_all_rows_from_cache(cache)
    existing_rows, _ = s.load_existing_output(s.OUTPUT_FILE, logger)
    all_rows = s.merge_pipeline_rows(existing_rows, cache_rows)
    s.save_excel(all_rows, s.OUTPUT_FILE, logger, cache=cache)
    print(
        "[GAP-FILL] "
        f"scanned={stats['scanned']} queued={stats['queued']} "
        f"attempted={stats['attempted']} enriched={stats['enriched']} "
        f"still_gap={stats['still_gap']} errors={stats['errors']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

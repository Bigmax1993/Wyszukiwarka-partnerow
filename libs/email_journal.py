# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Moduł: libs/email_journal — dziennik operacji e-mail (odczyt / dopasowanie / wysyłka / skan / błąd) dla GUI.
#
# CO ROBI
#   Dopisuje zdarzenia mailowe do pliku JSON gui_data/email_journal.json (lista słowników, max 400 ostatnich),
#   udostępnia ich odczyt w formie tabeli po polsku (kolumny Godzina/Data/Typ/Opis/Szczegóły/Adres) oraz
#   czyszczenie dziennika. Dostarcza wygodne funkcje log_* dla skanu IMAP, odczytu, wysyłki i synchronizacji.
#
# ROLA W PIPELINE: obserwowalność warstwy mailowej (odpowiedzi IMAP, wysyłka SMTP) — nie wpływa na
#   logikę wysyłki; błędy zapisu nie są wyciszane (patrz funkcje).
#
# ZALEŻNOŚCI: json, datetime, pathlib, typing oraz pipeline_registry.BASE_DIR — moduł pipeline_registry NIE
#   jest częścią tego repozytorium (pochodzi z GUI Kanbud), więc import działa tylko, gdy jest dostępny na sys.path.
# WEJŚCIE: tekstowe opisy zdarzeń (kind, summary, detail, campaign, address, subject).
# WYJŚCIE: plik JSON (efekt uboczny) oraz list[dict] z list_journal_entries.
# STAŁE: KIND_READ/MATCH/SEND/SCAN/ERROR, JOURNAL_PATH, MAX_ENTRIES.
# ============================================================
"""Dziennik operacji e-mail (odczyt / wysyłka) — widoczny w GUI."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pipeline_registry import BASE_DIR

JOURNAL_PATH = BASE_DIR / "gui_data" / "email_journal.json"
MAX_ENTRIES = 400

KIND_READ = "odczyt"
KIND_MATCH = "dopasowanie"
KIND_SEND = "wysyłka"
KIND_SCAN = "skan"
KIND_ERROR = "błąd"


# >>> OPIS FUNKCJI: funkcja _load
# Cel: wczytać listę wpisów dziennika z JOURNAL_PATH. Parametry: brak.
# Zwraca: list[dict] — zawartość pliku, albo [] gdy plik nie istnieje, nie jest listą lub jest uszkodzony.
# Efekty uboczne: odczyt pliku UTF-8. Błędy: każdy wyjątek (I/O, JSON) łapany i zamieniany na [].
def _load() -> list[dict[str, Any]]:
    if not JOURNAL_PATH.exists():
        return []
    try:
        with open(JOURNAL_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        return raw if isinstance(raw, list) else []
    except Exception:
        return []


# >>> OPIS FUNKCJI: funkcja _save
# Cel: zapisać dziennik, ucinając go do MAX_ENTRIES ostatnich wpisów. Parametry: items (list[dict]).
# Zwraca: None. Efekty uboczne: tworzy katalog gui_data/ i nadpisuje JOURNAL_PATH (UTF-8, wcięcie 2).
# Błędy: OSError/TypeError nie są łapane — propagują się.
def _save(items: list[dict[str, Any]]) -> None:
    JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    trimmed = items[-MAX_ENTRIES:]
    with open(JOURNAL_PATH, "w", encoding="utf-8") as f:
        json.dump(trimmed, f, ensure_ascii=False, indent=2)


# >>> OPIS FUNKCJI: funkcja log_email_event
# Cel: dopisać pojedyncze zdarzenie do dziennika. Parametry: kind (str, KIND_*); summary (str, ucinane do 500 znaków);
# detail (keyword-only, do 1000); campaign (str); address (str); subject (do 200).
# Zwraca: None. Efekty uboczne: odczyt całego pliku, dopisanie wpisu z czasem ISO (sekundy) i zapis (nieatomowy —
# brak blokady przy współbieżnym zapisie). Błędy: błędy zapisu propagują się.
def log_email_event(
    kind: str,
    summary: str,
    *,
    detail: str = "",
    campaign: str = "",
    address: str = "",
    subject: str = "",
) -> None:
    items = _load()
    items.append(
        {
            "at": datetime.now().isoformat(timespec="seconds"),
            "kind": kind,
            "summary": summary[:500],
            "detail": (detail or "")[:1000],
            "campaign": campaign,
            "address": address,
            "subject": (subject or "")[:200],
        }
    )
    _save(items)


# >>> OPIS FUNKCJI: funkcja log_imap_scan_start
# Cel: zalogować rozpoczęcie skanowania skrzynki IMAP. Parametry: since (datetime) — data, od której szukano
# maili; campaign (str). Zwraca: None. Efekty uboczne: wpis KIND_SCAN przez log_email_event. Błędy: jak log_email_event.
def log_imap_scan_start(since: datetime, campaign: str = "") -> None:
    log_email_event(
        KIND_SCAN,
        f"Łączenie ze skrzynką Gmail — szukam maili od {since.strftime('%Y-%m-%d')}",
        campaign=campaign,
    )


# >>> OPIS FUNKCJI: funkcja log_imap_scan_end
# Cel: zalogować zakończenie skanu IMAP. Parametry: message_count (int) — liczba pobranych wiadomości; campaign (str).
# Zwraca: None. Efekty uboczne: wpis KIND_SCAN. Błędy: jak log_email_event.
def log_imap_scan_end(message_count: int, campaign: str = "") -> None:
    log_email_event(
        KIND_SCAN,
        f"Pobrano {message_count} wiadomości ze skrzynki",
        campaign=campaign,
    )


# >>> OPIS FUNKCJI: funkcja log_mail_read
# Cel: zalogować odczytany mail i to, czy dopasowano go do firmy z listy. Parametry: from_addr (str); subject (str);
# matched (keyword-only, bool); reply_status (str); company (str); campaign (str).
# Zwraca: None. Efekty uboczne: wpis KIND_MATCH („Odpowiedź od <firma> (status)”) gdy matched, inaczej KIND_READ
# („nie przypisano do listy firm”); temat ucinany do 120 znaków w polu detail. Błędy: jak log_email_event.
def log_mail_read(
    from_addr: str,
    subject: str,
    *,
    matched: bool,
    reply_status: str = "",
    company: str = "",
    campaign: str = "",
) -> None:
    subj = (subject or "(bez tematu)")[:120]
    if matched:
        co = (company or from_addr)[:80]
        st = f" ({reply_status})" if reply_status else ""
        log_email_event(
            KIND_MATCH,
            f"Odpowiedź od {co}{st}",
            detail=subj,
            address=from_addr,
            subject=subject,
            campaign=campaign,
        )
    else:
        log_email_event(
            KIND_READ,
            f"Odczytano mail od {from_addr} — nie przypisano do listy firm",
            detail=subj,
            address=from_addr,
            subject=subject,
            campaign=campaign,
        )


# >>> OPIS FUNKCJI: funkcja log_mail_sent
# Cel: zalogować wynik wysyłki maila. Parametry: to_addr (str); subject (str); mail_type (keyword-only, str, domyślnie
# "wiadomość"); campaign (str); ok (bool, True); error (str) — komunikat błędu (do 500 znaków).
# Zwraca: None. Efekty uboczne: wpis KIND_SEND przy ok=True, inaczej KIND_ERROR z treścią błędu. Błędy: jak log_email_event.
def log_mail_sent(
    to_addr: str,
    subject: str,
    *,
    mail_type: str = "wiadomość",
    campaign: str = "",
    ok: bool = True,
    error: str = "",
) -> None:
    if ok:
        log_email_event(
            KIND_SEND,
            f"Wysłano {mail_type} → {to_addr}",
            detail=(subject or "")[:200],
            address=to_addr,
            subject=subject,
            campaign=campaign,
        )
    else:
        log_email_event(
            KIND_ERROR,
            f"Nie wysłano {mail_type} → {to_addr}",
            detail=error[:500],
            address=to_addr,
            subject=subject,
            campaign=campaign,
        )


# >>> OPIS FUNKCJI: funkcja log_sync_summary
# Cel: zalogować podsumowanie synchronizacji kontaktów z mailami. Parametry: updated (int) — liczba zaktualizowanych
# kontaktów; campaign (str). Zwraca: None. Efekty uboczne: wpis KIND_SCAN. Błędy: jak log_email_event.
def log_sync_summary(updated: int, campaign: str = "") -> None:
    log_email_event(
        KIND_SCAN,
        f"Zaktualizowano {updated} kontakt(ów) na podstawie maili",
        campaign=campaign,
    )


# >>> OPIS FUNKCJI: funkcja list_journal_entries
# Cel: przygotować ostatnie wpisy do wyświetlenia w tabeli GUI. Parametry: limit (int, domyślnie 80).
# Zwraca: list[dict] — od najnowszego, z kluczami Godzina (HH:MM:SS), Data (YYYY-MM-DD), Typ (po polsku),
# Opis, Szczegóły, Adres. Efekty uboczne: odczyt pliku. Błędy: uszkodzony plik → pusta lista (przez _load).
def list_journal_entries(limit: int = 80) -> list[dict[str, Any]]:
    items = _load()
    out = []
    for row in reversed(items[-limit:]):
        at = str(row.get("at", ""))
        time_short = at[11:19] if len(at) >= 19 else at
        out.append(
            {
                "Godzina": time_short,
                "Data": at[:10] if len(at) >= 10 else "",
                "Typ": _kind_label(str(row.get("kind", ""))),
                "Opis": row.get("summary", ""),
                "Szczegóły": row.get("detail", ""),
                "Adres": row.get("address", ""),
            }
        )
    return out


# >>> OPIS FUNKCJI: funkcja _kind_label
# Cel: zamienić kod rodzaju zdarzenia na etykietę po polsku. Parametry: kind (str).
# Zwraca: str — Odczyt / Odpowiedź / Wysyłka / Skan skrzynki / Błąd, a dla nieznanego kodu sam kind.
# Efekty uboczne/błędy: brak.
def _kind_label(kind: str) -> str:
    return {
        KIND_READ: "Odczyt",
        KIND_MATCH: "Odpowiedź",
        KIND_SEND: "Wysyłka",
        KIND_SCAN: "Skan skrzynki",
        KIND_ERROR: "Błąd",
    }.get(kind, kind)


# >>> OPIS FUNKCJI: funkcja clear_journal
# Cel: wyczyścić cały dziennik. Parametry: brak. Zwraca: int — liczba usuniętych wpisów.
# Efekty uboczne: nadpisuje JOURNAL_PATH pustą listą. Błędy: błędy zapisu propagują się.
def clear_journal() -> int:
    n = len(_load())
    _save([])
    return n

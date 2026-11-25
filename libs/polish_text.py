# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Moduł: libs/polish_text — UTF-8 i polskie znaki (ąćęłńóśźż): konfiguracja środowiska, naprawa mojibake, logi.
#
# CO ROBI
#   Ustawia UTF-8 dla konsoli i subprocessów (Windows + Linux), naprawia typowe błędy kodowania
#   (np. "WojewÃ³dztwo" → "Województwo"), normalizuje i czyści teksty (NFC, usuwanie znaków kontrolnych),
#   przygotowuje treść maila (zachowanie akapitów, konwersja plain → HTML) oraz tworzy loggery z konsolą/plikiem UTF-8.
#
# ROLA W PIPELINE
#   Warstwa pomocnicza wokół wszystkich etapów: czyszczenie nazw firm/pól przed zapisem do Excela, bezpieczne
#   logowanie polskich znaków i przygotowanie treści wiadomości przed wysyłką.
#   kanbud_bootstrap sprawdza istnienie tego pliku jako znacznika poprawnej struktury repozytorium.
#
# ZALEŻNOŚCI: stdlib (io, logging, os, re, sys, unicodedata, pathlib, typing, urllib.parse; html lokalnie).
# STAN GLOBALNY: _CONFIGURED (flaga jednorazowej konfiguracji UTF-8).
# WEJŚCIE/WYJŚCIE: funkcje tekstowe przyjmują str/Any i zwracają str; setup_* zwracają logging.Logger.
# ============================================================
"""
UTF-8 i polskie znaki (ąćęłńóśźż) — konfiguracja środowiska, naprawa kodowania, logi, subprocess.
"""
from __future__ import annotations

import io
import logging
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import unquote

_CONFIGURED = False

_MOJIBAKE_MARKERS = (
    "Ä…",
    "Ä™",
    "Ä‡",
    "Å‚",
    "Å„",
    "Ã³",
    "Å›",
    "Åº",
    "Å¼",
    "Ä",
    "Å",
    "Ã",
    "â€",
    "Ä‡",
    "Å›",
    "Ä…",
)

_POLISH_CHARS_RE = re.compile(r"[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]")


# >>> OPIS FUNKCJI: funkcja configure_utf8_environment
# Cel: jednorazowo ustawić UTF-8 dla procesu. Parametry: brak. Zwraca: None (kolejne wywołania nic nie robią).
# Efekty uboczne: os.environ.setdefault PYTHONUTF8=1 i PYTHONIOENCODING=utf-8; na Windows wywołuje
# "chcp 65001"; przekonfigurowuje stdout/stderr/stdin (reconfigure, a przy braku — owija bufor w TextIOWrapper,
# errors="replace"). Błędy: wszystkie wyjątki są łapane i ignorowane (konfiguracja best-effort).
def configure_utf8_environment() -> None:
    """Ustawia UTF-8 dla konsoli, subprocess i domyślnego I/O (Windows + Linux)."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    if sys.platform == "win32":
        try:
            os.system("chcp 65001 >nul 2>&1")
        except Exception:
            pass

    for stream_name in ("stdout", "stderr", "stdin"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            try:
                buf = getattr(stream, "buffer", None)
                if buf is not None:
                    wrapper = io.TextIOWrapper(
                        buf,
                        encoding="utf-8",
                        errors="replace",
                        line_buffering=stream_name != "stdin",
                    )
                    setattr(sys, stream_name, wrapper)
            except Exception:
                pass


# >>> OPIS FUNKCJI: funkcja fix_polish_mojibake
# Cel: naprawić tekst zniekształcony przez złe dekodowanie UTF-8 jako latin-1/cp1252. Parametry: text (str|None).
# Zwraca: str — poprawiony tekst; wejście bez markerów mojibake lub z poprawnymi polskimi znakami zwracane bez zmian;
# "" dla pustego. Efekty uboczne: brak. Błędy: UnicodeEncode/DecodeError są łapane (próbuje latin-1, potem cp1252,
# na końcu zwraca oryginał).
def fix_polish_mojibake(text: str) -> str:
    """Naprawia typowe błędy kodowania (np. WojewÃ³dztwo → Województwo)."""
    if not text:
        return ""
    s = str(text)
    if _POLISH_CHARS_RE.search(s) and not any(m in s for m in ("Ã", "Ä", "Å")):
        return s
    if not any(m in s for m in _MOJIBAKE_MARKERS):
        return s
    try:
        fixed = s.encode("latin-1").decode("utf-8")
        if fixed and fixed != s:
            return fixed
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    try:
        fixed = s.encode("cp1252").decode("utf-8")
        if fixed and fixed != s:
            return fixed
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return s


# >>> OPIS FUNKCJI: funkcja normalize_unicode_text
# Cel: znormalizować dowolną wartość do tekstu NFC. Parametry: value (Any) — None daje "".
# Zwraca: str — po fix_polish_mojibake, urllib.parse.unquote (dekodowanie %XX) i unicodedata.normalize("NFC").
# Efekty uboczne: brak. Błędy: brak własnej obsługi. Uwaga: unquote zmienia też legalne ciągi z "%".
def normalize_unicode_text(value: Any) -> str:
    if value is None:
        return ""
    text = fix_polish_mojibake(str(value))
    text = unquote(text)
    return unicodedata.normalize("NFC", text)


# >>> OPIS FUNKCJI: funkcja sanitize_special_text
# Cel: wyczyścić tekst z znaków kontrolnych, zachowując polskie litery (np. nazwa firmy do Excela).
# Parametry: value (Any). Zwraca: str — po normalize_unicode_text, znaki kontrolne zamienione na spację,
# białe znaki zredukowane do pojedynczych spacji, obcięte brzegowe " -|". Efekty uboczne/błędy: brak.
def sanitize_special_text(value: Any) -> str:
    """Czyści tekst z kontrolnych znaków; zachowuje polskie litery."""
    text = normalize_unicode_text(value)
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", " ", text)
    text = " ".join(text.split())
    return text.strip(" -|")


# >>> OPIS FUNKCJI: funkcja sanitize_email_body
# Cel: wyczyścić treść maila, zachowując akapity (w odróżnieniu od sanitize_special_text). Parametry: value (Any).
# Zwraca: str — końce linii ujednolicone do \n, znaki kontrolne usunięte, spacje w liniach zredukowane,
# całość po strip. Efekty uboczne/błędy: brak.
def sanitize_email_body(value: Any) -> str:
    """Czyści treść maila — zachowuje akapity (\\n), w przeciwieństwie do sanitize_special_text."""
    text = normalize_unicode_text(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
    lines = [" ".join(line.split()) for line in text.split("\n")]
    return "\n".join(lines).strip()


# >>> OPIS FUNKCJI: funkcja email_plain_to_html
# Cel: zamienić tekst z pustymi liniami na HTML z akapitami (czytelny w webmailu/Outlooku). Parametry: plain (str).
# Zwraca: str — <div> z blokami <p> (html.escape, nowe linie → <br>), czcionka Calibri 11pt; "<div></div>" gdy brak treści.
# Efekty uboczne/błędy: brak (czysta funkcja).
def email_plain_to_html(plain: str) -> str:
    """Plain text z pustymi liniami → HTML z akapitami (webmail home.pl / Outlook)."""
    import html as html_module

    blocks: list[str] = []
    for block in re.split(r"\n\s*\n", (plain or "").strip()):
        block = block.strip()
        if not block:
            continue
        inner = html_module.escape(block).replace("\n", "<br>\n")
        blocks.append(
            '<p style="margin:0 0 12px 0;line-height:1.45;">' f"{inner}</p>"
        )
    if not blocks:
        return "<div></div>"
    return (
        '<div style="font-family:Calibri,Arial,Helvetica,sans-serif;'
        'font-size:11pt;color:#000000;">'
        + "".join(blocks)
        + "</div>"
    )


# >>> OPIS FUNKCJI: funkcja normalize_row_dict
# Cel: znormalizować klucze i wartości tekstowe wiersza (dict). Parametry: row (dict).
# Zwraca: nowy dict — klucze str i wartości str przechodzą przez normalize_unicode_text, pozostałe typy bez zmian.
# Efekty uboczne/błędy: brak (oryginał nie jest mutowany).
def normalize_row_dict(row: dict) -> dict:
    out: dict = {}
    for key, val in row.items():
        k = normalize_unicode_text(key) if isinstance(key, str) else key
        if isinstance(val, str):
            out[k] = normalize_unicode_text(val)
        else:
            out[k] = val
    return out


# >>> OPIS FUNKCJI: funkcja utf8_subprocess_env
# Cel: zbudować środowisko dla subprocesów z wymuszonym UTF-8. Parametry: brak.
# Zwraca: dict — kopia os.environ z PYTHONUTF8=1 i PYTHONIOENCODING=utf-8. Efekty uboczne/błędy: brak.
def utf8_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


# >>> OPIS FUNKCJI: funkcja create_stream_handler
# Cel: utworzyć handler logowania na stdout z gwarancją konfiguracji UTF-8. Parametry: brak.
# Zwraca: logging.StreamHandler(sys.stdout). Efekty uboczne: wywołuje configure_utf8_environment. Błędy: brak.
def create_stream_handler() -> logging.StreamHandler:
    configure_utf8_environment()
    return logging.StreamHandler(sys.stdout)


# >>> OPIS FUNKCJI: funkcja setup_script_logging
# Cel: skonfigurować logger skryptu scrapera (konsola UTF-8 + opcjonalny plik UTF-8). Parametry: name (str);
# log_file (Path|str|None) — gdy podany, tworzy katalog nadrzędny i dopisuje logi do pliku.
# Zwraca: logging.Logger (poziom INFO, format "czas [LEVEL] wiadomość"). Efekty uboczne: czyści istniejące handlery
# loggera (handlers.clear()), konfiguruje UTF-8, tworzy plik/katalogi. Błędy: OSError przy tworzeniu pliku nie jest łapany.
def setup_script_logging(name: str, log_file: Path | str | None = None) -> logging.Logger:
    """Logger ze skryptów scraperów (konsola UTF-8 + plik UTF-8)."""
    configure_utf8_environment()
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    ch = create_stream_handler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(str(log_path), encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger


# >>> OPIS FUNKCJI: funkcja setup_module_logging
# Cel: prosty logger dla skryptów pomocniczych (sync_*, przypomnienia). Parametry: name (str).
# Zwraca: logging.Logger (INFO); handler konsolowy dodawany tylko, gdy logger nie ma jeszcze handlerów.
# Efekty uboczne: configure_utf8_environment. Błędy: brak.
def setup_module_logging(name: str) -> logging.Logger:
    """Prosty logger dla sync_*.py / send_email_reminders.py."""
    configure_utf8_environment()
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        h = create_stream_handler()
        h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(h)
    return logger

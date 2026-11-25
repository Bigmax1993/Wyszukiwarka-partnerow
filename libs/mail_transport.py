# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Moduł: libs/mail_transport — wspólna warstwa poczty SMTP/IMAP (home.pl lub Gmail) sterowana zmiennymi środowiskowymi.
#
# CO ROBI
#   Wybiera hosty/porty SMTP i IMAP (domyślnie serwer.home.pl; dla adresów gmail.com — smtp/imap.gmail.com),
#   scala listy Cc/Bcc, wysyła wiadomości przez yagmail (z załącznikami lub bez), a po udanej wysyłce
#   archiwizuje kopię: plik .eml w folderze wyslane/ (oraz załączniki w wyslane/zalaczniki/) i dopisanie
#   do folderu Wysłane na serwerze IMAP (m.in. wykrywanie nazw Wysłane/Sent/Gesendet, próba utworzenia).
#
# ROLA W PIPELINE
#   Ostatni etap („optional B2B email”) i raport Excel: send_smtp_email / send_smtp_email_with_attachments
#   są wywoływane przez scraper i skrypty (np. send_excel_gmail.py). Kill switch DISABLE_CONTRACTOR_EMAILS
#   jest sprawdzany w warstwie wyżej (scraper_env.is_contractor_emails_disabled), nie w tym module.
#
# ZALEŻNOŚCI
#   polish_text (sanitize_email_body, sanitize_special_text), scraper_env (ENV_*, get_env_value, dane poczty),
#   stdlib (imaplib, mimetypes, shutil, email.*, logging, time, re, pathlib); leniwie: yagmail (zewnętrzny),
#   email_journal.log_mail_sent oraz project_config.get_data_root.
# WEJŚCIE: adresy, temat, treść, ścieżki załączników, logger, kontekst (mail_type, campaign).
# WYJŚCIE: send_* zwracają (ok: bool, info: str); pozostałe funkcje — str/int/list/Path/None zgodnie z opisem.
# BŁĘDY: wysyłka nie rzuca wyjątków do wywołującego (zwraca (False, komunikat)); archiwizacja jest „best-effort”.
# ============================================================
"""
Wspólna warstwa poczty: SMTP/IMAP (home.pl lub Gmail) z zmiennych środowiskowych.
"""
from __future__ import annotations

import logging
import mimetypes
import re
import imaplib
import shutil
import time
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path
from typing import Any

from polish_text import sanitize_email_body, sanitize_special_text
from scraper_env import (
    ENV_GMAIL_APP_PASSWORD,
    ENV_GMAIL_USER,
    ENV_IMAP_HOST,
    ENV_IMAP_PORT,
    ENV_IMAP_SSL,
    ENV_MAIL_ARCHIVE_IMAP,
    ENV_MAIL_BCC,
    ENV_MAIL_CC,
    ENV_MAIL_PASSWORD,
    ENV_MAIL_SENDER_NAME,
    ENV_MAIL_USER,
    ENV_SMTP_HOST,
    ENV_SMTP_PORT,
    ENV_SMTP_SSL,
    get_env_value,
    get_mail_password,
    get_mail_sender_name,
    get_mail_user,
)

_DEFAULT_HOMEPL_SMTP = "serwer.home.pl"
_DEFAULT_HOMEPL_IMAP = "serwer.home.pl"
_DEFAULT_SMTP_PORT_SSL = 465
_DEFAULT_SMTP_PORT_STARTTLS = 587
_DEFAULT_IMAP_PORT_SSL = 993


# >>> OPIS FUNKCJI: funkcja _truthy
# Cel: zinterpretować tekst jako flagę. Parametry: raw (str). Zwraca: bool — True dla 1/true/yes/tak/on
# (po strip, bez wielkości liter). Efekty uboczne/błędy: brak.
def _truthy(raw: str) -> bool:
    return str(raw or "").strip().lower() in ("1", "true", "yes", "tak", "on")


# >>> OPIS FUNKCJI: funkcja _mail_address
# Cel: znormalizowany adres skrzynki nadawczej. Parametry: brak. Zwraca: str — get_mail_user() po strip i lower(), "" gdy brak.
# Efekty uboczne/błędy: jak get_env_value.
def _mail_address() -> str:
    return (get_mail_user() or "").strip().lower()


# >>> OPIS FUNKCJI: funkcja _is_gmail_address
# Cel: rozpoznać adres Gmail. Parametry: addr (str). Zwraca: bool — True, gdy niepusty i zawiera @gmail.com lub @googlemail.com.
# Efekty uboczne/błędy: brak.
def _is_gmail_address(addr: str) -> bool:
    return bool(addr) and ("@gmail.com" in addr or "@googlemail.com" in addr)


# >>> OPIS FUNKCJI: funkcja get_smtp_host
# Cel: ustalić host SMTP. Parametry: brak. Zwraca: str — SMTP_HOST z env; gdy brak i nadawca ma adres Gmail:
# "smtp.gmail.com"; w innym przypadku "" (wtedy yagmail użyje własnych domyślnych). Efekty uboczne/błędy: odczyt env.
def get_smtp_host() -> str:
    host = get_env_value(ENV_SMTP_HOST).strip()
    if host:
        return host
    if _is_gmail_address(_mail_address()):
        return "smtp.gmail.com"
    return ""


# >>> OPIS FUNKCJI: funkcja get_imap_host
# Cel: ustalić host IMAP. Parametry: brak. Zwraca: str — IMAP_HOST z env; dla Gmail "imap.gmail.com";
# w pozostałych przypadkach domyślnie "serwer.home.pl". Efekty uboczne/błędy: odczyt env.
def get_imap_host() -> str:
    host = get_env_value(ENV_IMAP_HOST).strip()
    if host:
        return host
    if _is_gmail_address(_mail_address()):
        return "imap.gmail.com"
    return _DEFAULT_HOMEPL_IMAP


# >>> OPIS FUNKCJI: funkcja mail_provider_label
# Cel: czytelna etykieta dostawcy poczty do logów/GUI. Parametry: brak.
# Zwraca: str — "home.pl", "Gmail", host SMTP, domena adresu nadawcy lub "" (kolejność jak w kodzie).
# Efekty uboczne/błędy: odczyt env.
def mail_provider_label() -> str:
    smtp = get_smtp_host().lower()
    addr = _mail_address()
    if "home.pl" in smtp or (addr and addr.endswith("@home.pl")):
        return "home.pl"
    if _is_gmail_address(addr) or "gmail" in smtp:
        return "Gmail"
    if smtp:
        return smtp
    if addr and "@" in addr:
        domain = addr.split("@", 1)[1]
        return domain or "SMTP"
    return ""


# >>> OPIS FUNKCJI: funkcja _smtp_port
# Cel: ustalić port SMTP. Parametry: brak. Zwraca: int — SMTP_PORT (jeśli cyfry); inaczej 465, gdy SMTP_SSL jest
# włączone, a w pozostałych przypadkach 587 (STARTTLS). Efekty uboczne/błędy: odczyt env.
def _smtp_port() -> int:
    raw = get_env_value(ENV_SMTP_PORT).strip()
    if raw.isdigit():
        return int(raw)
    if _truthy(get_env_value(ENV_SMTP_SSL)):
        return _DEFAULT_SMTP_PORT_SSL
    return _DEFAULT_SMTP_PORT_STARTTLS


# >>> OPIS FUNKCJI: funkcja _imap_port
# Cel: ustalić port IMAP. Parametry: brak. Zwraca: int — IMAP_PORT (jeśli cyfry) lub 993. Efekty uboczne/błędy: odczyt env.
def _imap_port() -> int:
    raw = get_env_value(ENV_IMAP_PORT).strip()
    if raw.isdigit():
        return int(raw)
    return _DEFAULT_IMAP_PORT_SSL


# >>> OPIS FUNKCJI: funkcja _smtp_use_ssl
# Cel: zdecydować, czy użyć SSL (a nie STARTTLS) dla SMTP. Parametry: brak.
# Zwraca: bool — wartość SMTP_SSL, jeśli ustawiona; inaczej True, gdy port == 465. Efekty uboczne/błędy: odczyt env.
def _smtp_use_ssl() -> bool:
    if get_env_value(ENV_SMTP_SSL).strip():
        return _truthy(get_env_value(ENV_SMTP_SSL))
    return _smtp_port() == _DEFAULT_SMTP_PORT_SSL


# >>> OPIS FUNKCJI: funkcja _sanitize_sender_name
# Cel: oczyścić nazwę nadawcy z nowych linii (ochrona przed wstrzyknięciem nagłówków). Parametry: name (str).
# Zwraca: str — pojedyncze spacje, bez \n. Efekty uboczne/błędy: brak.
def _sanitize_sender_name(name: str) -> str:
    return " ".join((name or "").replace("\n", " ").split()).strip()


# >>> OPIS FUNKCJI: funkcja _split_recipients
# Cel: rozbić listę odbiorców z env (separatory "," i ";"). Parametry: raw (str).
# Zwraca: list[str] — niepuste adresy po strip; [] dla pustego wejścia oraz dla wartości 0/off/false/no/nie.
# Efekty uboczne/błędy: brak.
def _split_recipients(raw: str) -> list[str]:
    if not raw:
        return []
    if str(raw).strip().lower() in ("0", "off", "false", "no", "nie"):
        return []
    parts = re.split(r"[,;]+", raw)
    return [p.strip() for p in parts if p.strip()]


# Opcjonalna stała Cc — pusta; użyj MAIL_CC w .env jeśli potrzebujesz kopii.
EMAIL_ALWAYS_CC: tuple[str, ...] = ()


# >>> OPIS FUNKCJI: funkcja merge_mail_cc_recipients
# Cel: złożyć listę Cc: adresy z MAIL_CC (przekazane jako extra_env_cc) + stała EMAIL_ALWAYS_CC (domyślnie pusta).
# Parametry: primary_to (str) — główny odbiorca (nie trafi do Cc); extra_env_cc (str) — surowy ciąg adresów.
# Zwraca: list[str] — bez duplikatów (porównanie lower) i bez adresu głównego, w kolejności wystąpienia.
# Efekty uboczne/błędy: brak (czysta funkcja).
def merge_mail_cc_recipients(primary_to: str, extra_env_cc: str = "") -> list[str]:
    """MAIL_CC z .env + EMAIL_ALWAYS_CC (bez duplikatu i bez adresu głównego odbiorcy)."""
    out: list[str] = []
    to_norm = (primary_to or "").strip().lower()
    seen: set[str] = set()
    for addr in list(_split_recipients(extra_env_cc)) + list(EMAIL_ALWAYS_CC):
        a = (addr or "").strip()
        if not a:
            continue
        key = a.lower()
        if key == to_norm or key in seen:
            continue
        seen.add(key)
        out.append(a)
    return out


# >>> OPIS FUNKCJI: funkcja get_wyslane_dir
# Cel: lokalny folder kopii wysłanych maili (.eml). Parametry: brak.
# Zwraca: Path — <get_data_root()>/wyslane; przy błędzie importu/odczytu project_config — <katalog libs>/wyslane.
# Efekty uboczne: leniwy import project_config. Błędy: dowolny wyjątek łapany → ścieżka awaryjna. Nie tworzy katalogu.
def get_wyslane_dir() -> Path:
    """Lokalny folder kopii wysłanych maili (.eml)."""
    try:
        from project_config import get_data_root

        root = get_data_root()
    except Exception:
        root = Path(__file__).resolve().parent
    return root / "wyslane"


# >>> OPIS FUNKCJI: funkcja _safe_eml_stem
# Cel: bezpieczny fragment nazwy pliku .eml. Parametry: text (str); max_len (int, 48).
# Zwraca: str — znaki spoza [\w.-] zamienione na "_", ucięte do max_len, obcięte "._" z brzegów; "mail" gdy pusty.
# Efekty uboczne/błędy: brak.
def _safe_eml_stem(text: str, max_len: int = 48) -> str:
    stem = re.sub(r"[^\w.\-]+", "_", (text or "").strip(), flags=re.UNICODE)
    return (stem[:max_len] or "mail").strip("._")


# >>> OPIS FUNKCJI: funkcja _build_sent_email_message
# Cel: zbudować obiekt EmailMessage odpowiadający wysłanej wiadomości (do archiwizacji .eml i IMAP).
# Parametry: username (str) — adres nadawcy; to_email, subject, body (str); cc (keyword-only, list[str]);
# attachment_paths (list[str]|None) — istniejące pliki dołączane z typem MIME zgadywanym przez mimetypes.
# Zwraca: EmailMessage z nagłówkami From (z nazwą nadawcy, jeśli ustawiona), To, Cc, Subject, Date, Message-ID.
# Efekty uboczne: odczyt plików załączników; nieistniejące pliki są pomijane. Błędy: błędy odczytu plików propagują się.
def _build_sent_email_message(
    username: str,
    to_email: str,
    subject: str,
    body: str,
    *,
    cc: list[str],
    attachment_paths: list[str] | None = None,
) -> EmailMessage:
    msg = EmailMessage()
    sender_name = _sanitize_sender_name(get_mail_sender_name())
    if sender_name:
        msg["From"] = f"{sender_name} <{username}>"
    else:
        msg["From"] = username
    msg["To"] = to_email
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()
    msg.set_content(body)
    for ap in attachment_paths or []:
        p = Path(ap)
        if not p.is_file():
            continue
        data = p.read_bytes()
        ctype, _enc = mimetypes.guess_type(str(p))
        if ctype and "/" in ctype:
            maintype, subtype = ctype.split("/", 1)
        else:
            maintype, subtype = "application", "octet-stream"
        msg.add_attachment(
            data,
            maintype=maintype,
            subtype=subtype,
            filename=p.name,
        )
    return msg


# >>> OPIS FUNKCJI: funkcja _save_wyslane_eml
# Cel: zapisać kopię wiadomości jako .eml oraz skopiować załączniki. Parametry: msg (EmailMessage); to_email (str);
# subject (str); attachment_paths (list[str]|None).
# Zwraca: Path do pliku <data>_<godzina>_<odbiorca>_<temat>.eml w folderze wyslane/.
# Efekty uboczne: tworzy katalogi, zapisuje .eml, a załączniki kopiuje (shutil.copy2) do wyslane/zalaczniki/<stamp>_<odbiorca>/.
# Błędy: błędy I/O propagują się (łapie je archive_sent_message).
def _save_wyslane_eml(
    msg: EmailMessage,
    to_email: str,
    subject: str,
    attachment_paths: list[str] | None,
) -> Path:
    folder = get_wyslane_dir()
    folder.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d_%H%M%S")
    recipient = _safe_eml_stem(to_email.replace("@", "_at_"))
    subj = _safe_eml_stem(subject)
    path = folder / f"{stamp}_{recipient}_{subj}.eml"
    path.write_bytes(msg.as_bytes())
    if attachment_paths:
        att_dir = folder / "zalaczniki" / f"{stamp}_{recipient}"
        att_dir.mkdir(parents=True, exist_ok=True)
        for src in attachment_paths:
            src_path = Path(src)
            if src_path.is_file():
                shutil.copy2(src_path, att_dir / src_path.name)
    return path


# >>> OPIS FUNKCJI: funkcja _imap_mailbox_names
# Cel: pobrać listę nazw folderów z serwera IMAP. Parametry: mail (imaplib.IMAP4_SSL) — zalogowane połączenie.
# Zwraca: list[str] nazw wyciągniętych z odpowiedzi LIST; [] przy błędzie lub odpowiedzi innej niż OK.
# Efekty uboczne: komenda LIST na serwerze. Błędy: wyjątek z mail.list() łapany → [].
def _imap_mailbox_names(mail: imaplib.IMAP4_SSL) -> list[str]:
    try:
        typ, data = mail.list()
    except Exception:
        return []
    if typ != "OK" or not data:
        return []
    names: list[str] = []
    for raw in data:
        if not raw:
            continue
        line = raw.decode("utf-8", errors="replace")
        if ' "' in line:
            name = line.rsplit(' "', 1)[-1].rstrip('"')
        else:
            parts = line.split(" ")
            name = parts[-1].strip('"') if parts else ""
        if name:
            names.append(name)
    return names


# >>> OPIS FUNKCJI: funkcja _resolve_sent_mailbox
# Cel: znaleźć na serwerze folder „Wysłane”. Parametry: mail (połączenie IMAP); logger (Logger|None) — do logu debug.
# Zwraca: str — nazwa folderu (najpierw dokładne dopasowanie z listy preferowanych: Wysłane/Wyslane/Sent/
# [Gmail]/Sent Mail/Gesendet…, potem dowolny folder zawierający "sent", "wys" lub "gesendet") albo None.
# Efekty uboczne: LIST na serwerze, log debug. Błędy: brak własnej obsługi (opiera się na _imap_mailbox_names).
def _resolve_sent_mailbox(
    mail: imaplib.IMAP4_SSL,
    logger: logging.Logger | None = None,
) -> str | None:
    """Znajdź folder Wysłane / Sent na serwerze IMAP."""
    mailbox_names = _imap_mailbox_names(mail)
    if logger and mailbox_names:
        logger.debug("IMAP foldery: %s", ", ".join(mailbox_names[:20]))

    preferred = (
        "Wysłane",
        "Wyslane",
        "INBOX.Wysłane",
        "INBOX.Wyslane",
        "Sent",
        "Sent Items",
        "INBOX.Sent",
        "INBOX.Sent Items",
        "[Gmail]/Sent Mail",
        "Gesendet",
        "INBOX.Gesendet",
    )
    lowered = {m.lower(): m for m in mailbox_names}
    for candidate in preferred:
        found = lowered.get(candidate.lower())
        if found:
            return found
    for name in mailbox_names:
        low = name.lower()
        if "sent" in low or "wys" in low or "gesendet" in low:
            return name
    return None


# >>> OPIS FUNKCJI: funkcja _try_create_sent_mailbox
# Cel: spróbować utworzyć folder Wysłane, gdy go brak. Parametry: mail (połączenie IMAP).
# Zwraca: str — nazwa pierwszego udanie utworzonego folderu (INBOX.Wyslane, Wyslane, INBOX.Sent, Sent) lub None.
# Efekty uboczne: komendy CREATE na serwerze. Błędy: wyjątki per kandydat łapane (continue).
def _try_create_sent_mailbox(mail: imaplib.IMAP4_SSL) -> str | None:
    for candidate in (
        "INBOX.Wyslane",
        "Wyslane",
        "INBOX.Sent",
        "Sent",
    ):
        try:
            typ, _ = mail.create(candidate)
            if typ == "OK":
                return candidate
        except Exception:
            continue
    return None


# >>> OPIS FUNKCJI: funkcja _append_to_imap_sent
# Cel: dopisać wysłaną wiadomość do folderu Wysłane na serwerze IMAP. Parametry: username, password (str);
# msg (EmailMessage); logger (Logger).
# Zwraca: bool — True po sukcesie albo gdy archiwizacja IMAP jest wyłączona (MAIL_ARCHIVE_IMAP != włączone);
# False, gdy brak IMAP_HOST, nie znaleziono folderu, APPEND nie zwrócił OK lub wystąpił błąd.
# Efekty uboczne: połączenie IMAP SSL, login, APPEND z flagą \Seen, logout w finally; logowanie ostrzeżeń.
# Błędy: wyjątki są łapane i logowane (warning) — zwracane False; błąd logout ignorowany.
def _append_to_imap_sent(
    username: str,
    password: str,
    msg: EmailMessage,
    logger: logging.Logger,
) -> bool:
    """Dopisz wysłaną wiadomość do folderu Wysłane na serwerze IMAP."""
    if not _truthy(get_env_value(ENV_MAIL_ARCHIVE_IMAP) or "1"):
        return True
    imap_host = get_imap_host()
    if not imap_host:
        logger.warning("Brak IMAP_HOST — pominięto zapis do folderu Wysłane na serwerze.")
        return False

    mail = imaplib.IMAP4_SSL(imap_host, _imap_port())
    try:
        mail.login(username, password)
        mailbox = _resolve_sent_mailbox(mail, logger)
        if not mailbox:
            mailbox = _try_create_sent_mailbox(mail)
        if not mailbox:
            names = _imap_mailbox_names(mail)
            logger.warning(
                "Nie znaleziono folderu Wysłane/Sent na IMAP (dostępne: %s). "
                "Kopia jest w folderze lokalnym: %s",
                ", ".join(names[:12]) or "(brak listy)",
                get_wyslane_dir(),
            )
            return False
        payload = msg.as_bytes()
        typ, data = mail.append(
            mailbox,
            "\\Seen",
            imaplib.Time2Internaldate(time.time()),
            payload,
        )
        if typ != "OK":
            logger.warning(
                "IMAP APPEND do '%s' nie powiódł się: %s %s",
                mailbox,
                typ,
                data,
            )
            return False
        logger.info("Zapisano kopię w folderze Wysłane (IMAP): %s", mailbox)
        return True
    except Exception as e:
        logger.warning(
            "Błąd zapisu do folderu Wysłane (IMAP %s): %s — kopia lokalna: %s",
            imap_host,
            e,
            get_wyslane_dir(),
        )
        return False
    finally:
        try:
            mail.logout()
        except Exception:
            pass


# >>> OPIS FUNKCJI: funkcja archive_sent_message
# Cel: po udanej wysyłce SMTP zachować kopię: .eml w wyslane/ oraz wpis w IMAP Wysłane.
# Parametry: to_email, subject, body (str); logger; cc, bcc (keyword-only, list|None; bcc nie jest zapisywany
# w nagłówkach); attachment_paths (keyword-only, list|None).
# Zwraca: None. Efekty uboczne: budowa wiadomości, zapis plików, połączenie IMAP (tylko gdy jest hasło).
# Błędy: brak loginu → ciche wyjście; błąd zapisu .eml łapany i logowany (warning); błędy IMAP obsługuje _append_to_imap_sent.
def archive_sent_message(
    to_email: str,
    subject: str,
    body: str,
    logger: logging.Logger,
    *,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    attachment_paths: list[str] | None = None,
) -> None:
    """
    Po udanej wysyłce SMTP: kopia .eml w folderze wyslane/ oraz dopisanie do IMAP Wysłane.
    """
    username = get_mail_user()
    password = get_mail_password()
    if not username:
        return
    cc_list = list(cc or [])
    msg = _build_sent_email_message(
        username,
        to_email,
        subject,
        body,
        cc=cc_list,
        attachment_paths=attachment_paths,
    )
    try:
        local_path = _save_wyslane_eml(msg, to_email, subject, attachment_paths)
        logger.info("Kopia wysłanego maila (folder wyslane): %s", local_path)
    except Exception as e:
        logger.warning("Nie zapisano kopii w folderze wyslane: %s", e)
    if password:
        _append_to_imap_sent(username, password, msg, logger)


def archive_sent_email_message(
    msg: EmailMessage,
    logger: logging.Logger,
    *,
    to_email: str = "",
    subject: str = "",
    attachment_paths: list[str] | None = None,
) -> None:
    """
    Po SMTP: kopia .eml (wyslane/) + ten sam Message do folderu Wysłane (IMAP).
    Użyj tej samej instancji msg co wysłano — widać Cc, załącznik i treść w skrzynce.
    """
    username = get_mail_user()
    password = get_mail_password()
    to_email = to_email or str(msg.get("To", ""))
    subject = subject or str(msg.get("Subject", ""))
    try:
        local_path = _save_wyslane_eml(msg, to_email, subject, attachment_paths)
        logger.info("Kopia wysłanego maila (folder wyslane): %s", local_path)
    except Exception as e:
        logger.warning("Nie zapisano kopii w folderze wyslane: %s", e)
    if not password:
        logger.warning("Brak MAIL_PASSWORD — pominięto zapis IMAP Wysłane.")
        return
    if not _truthy(get_env_value(ENV_MAIL_ARCHIVE_IMAP) or "1"):
        logger.warning(
            "MAIL_ARCHIVE_IMAP=0 — wiadomość nie trafi do folderu Wysłane na serwerze. "
            "Ustaw MAIL_ARCHIVE_IMAP=1 w .env."
        )
        return
    ok = _append_to_imap_sent(username, password, msg, logger)
    if not ok:
        logger.warning(
            "Sprawdź IMAP_HOST (%s) i folder Wysłane/Sent w webmailu.",
            get_imap_host(),
        )


# >>> OPIS FUNKCJI: funkcja _yagmail_smtp
# Cel: utworzyć klienta yagmail.SMTP z konfiguracji środowiska. Parametry: brak.
# Zwraca: obiekt yagmail.SMTP — bez hosta: ustawienia domyślne yagmail; z hostem: host, port, SSL lub STARTTLS wg _smtp_use_ssl.
# Efekty uboczne: leniwy import yagmail; połączenie jest tworzone przez yagmail.
# Błędy: ImportError, gdy brak yagmail; ValueError("brak MAIL_USER / MAIL_PASSWORD (lub GMAIL_*)") bez danych logowania.
def _yagmail_smtp() -> Any:
    import yagmail  # pyright: ignore[reportMissingImports]

    username = get_mail_user()
    password = get_mail_password()
    if not (username and password):
        raise ValueError("brak MAIL_USER / MAIL_PASSWORD (lub GMAIL_*)")

    host = get_smtp_host()
    if not host:
        return yagmail.SMTP(user=username, password=password)

    port = _smtp_port()
    use_ssl = _smtp_use_ssl()
    return yagmail.SMTP(
        user=username,
        password=password,
        host=host,
        port=port,
        smtp_ssl=use_ssl,
        smtp_starttls=not use_ssl,
    )


# >>> OPIS FUNKCJI: funkcja send_smtp_email
# Cel: wysłać wiadomość tekstową przez SMTP (yagmail). Parametry: to_email, subject, body (str); logger;
# mail_type (keyword-only, str) — etykieta do logów/dziennika; campaign (keyword-only, str).
# Zwraca: (ok: bool, info: str) — (True, "gesendet") po sukcesie; (False, komunikat) przy braku yagmail,
# braku danych logowania lub błędzie wysyłki.
# Efekty uboczne: wysyłka maila z Cc (merge_mail_cc_recipients) i Bcc (MAIL_BCC), sanitizacja tematu/treści,
# archive_sent_message, log do email_journal (błąd zapisu dziennika ignorowany), logowanie.
# Błędy: wyjątki z wysyłki są łapane — warning w logu, wpis KIND_ERROR i zwrot (False, str(e)).
def send_smtp_email(
    to_email: str,
    subject: str,
    body: str,
    logger: logging.Logger,
    *,
    mail_type: str = "wiadomość",
    campaign: str = "",
) -> tuple[bool, str]:
    """Wysyłka SMTP (home.pl lub Gmail). Zwraca (ok, info)."""
    try:
        import yagmail  # pyright: ignore[reportMissingImports]  # noqa: F401
    except ImportError:
        return False, "brak yagmail (pip install yagmail)"

    username = get_mail_user()
    password = get_mail_password()
    if not (username and password):
        return False, "brak MAIL_USER / MAIL_PASSWORD"

    subject_clean = sanitize_special_text(subject)
    body_clean = sanitize_email_body(body)
    bcc = _split_recipients(get_env_value(ENV_MAIL_BCC))
    cc = merge_mail_cc_recipients(to_email, get_env_value(ENV_MAIL_CC))

    try:
        yag = _yagmail_smtp()
        kwargs: dict[str, Any] = {
            "to": to_email,
            "subject": subject_clean,
            "contents": [body_clean],
        }
        if bcc:
            kwargs["bcc"] = bcc
        if cc:
            kwargs["cc"] = cc
        yag.send(**kwargs)
        archive_sent_message(
            to_email,
            subject_clean,
            body_clean,
            logger,
            cc=cc,
            bcc=bcc,
        )
        host = get_smtp_host() or _DEFAULT_HOMEPL_SMTP
        logger.info(
            f"Wysłano {mail_type} → {to_email} via {host} | temat: {(subject or '')[:60]}"
        )
        try:
            from email_journal import log_mail_sent

            log_mail_sent(
                to_email,
                subject,
                mail_type=mail_type,
                campaign=campaign,
                ok=True,
            )
        except Exception:
            pass
        return True, "gesendet"
    except Exception as e:
        logger.warning(f"Błąd wysyłki do {to_email}: {e}")
        try:
            from email_journal import log_mail_sent

            log_mail_sent(
                to_email,
                subject,
                mail_type=mail_type,
                campaign=campaign,
                ok=False,
                error=str(e),
            )
        except Exception:
            pass
        return False, str(e)


# >>> OPIS FUNKCJI: funkcja send_smtp_email_with_attachments
# Cel: jak send_smtp_email, ale z załącznikami. Parametry: to_email, subject, body (str); attachment_paths
# (list[str|Path]) — wszystkie pliki muszą istnieć; logger; mail_type (keyword-only, domyślnie "załącznik"); campaign.
# Zwraca: (ok, info) — (True, "gesendet") po sukcesie; (False, komunikat) przy braku yagmail, danych logowania,
# nieistniejącym pliku ("brak pliku załącznika: ...") lub błędzie wysyłki.
# Efekty uboczne: wysyłka z załącznikami, archiwizacja kopii (wraz z załącznikami), wpis w email_journal, logowanie.
# Błędy: wyjątki z wysyłki łapane → warning + (False, str(e)).
def send_smtp_email_with_attachments(
    to_email: str,
    subject: str,
    body: str,
    attachment_paths: list[str | Path],
    logger: logging.Logger,
    *,
    mail_type: str = "załącznik",
    campaign: str = "",
) -> tuple[bool, str]:
    """Wysyłka SMTP z załącznikami (yagmail / Gmail app password)."""
    try:
        import yagmail  # pyright: ignore[reportMissingImports]  # noqa: F401
    except ImportError:
        return False, "brak yagmail (pip install yagmail)"

    username = get_mail_user()
    password = get_mail_password()
    if not (username and password):
        return False, "brak MAIL_USER / MAIL_PASSWORD (Gmail: hasło aplikacji)"

    files: list[str] = []
    for raw in attachment_paths or []:
        path = Path(raw)
        if not path.is_file():
            return False, f"brak pliku załącznika: {path}"
        files.append(str(path.resolve()))

    subject_clean = sanitize_special_text(subject)
    body_clean = sanitize_email_body(body)
    bcc = _split_recipients(get_env_value(ENV_MAIL_BCC))
    cc = merge_mail_cc_recipients(to_email, get_env_value(ENV_MAIL_CC))

    try:
        yag = _yagmail_smtp()
        kwargs: dict[str, Any] = {
            "to": to_email,
            "subject": subject_clean,
            "contents": [body_clean],
            "attachments": files,
        }
        if bcc:
            kwargs["bcc"] = bcc
        if cc:
            kwargs["cc"] = cc
        yag.send(**kwargs)
        archive_sent_message(
            to_email,
            subject_clean,
            body_clean,
            logger,
            cc=cc,
            bcc=bcc,
            attachment_paths=files,
        )
        host = get_smtp_host() or "smtp.gmail.com"
        attach_note = ", ".join(Path(f).name for f in files)
        logger.info(
            "Wysłano %s → %s via %s | %s | zał.: %s",
            mail_type,
            to_email,
            host,
            (subject or "")[:60],
            attach_note,
        )
        try:
            from email_journal import log_mail_sent

            log_mail_sent(
                to_email,
                subject,
                mail_type=mail_type,
                campaign=campaign,
                ok=True,
            )
        except Exception:
            pass
        return True, "gesendet"
    except Exception as e:
        logger.warning("Błąd wysyłki z załącznikiem do %s: %s", to_email, e)
        try:
            from email_journal import log_mail_sent

            log_mail_sent(
                to_email,
                subject,
                mail_type=mail_type,
                campaign=campaign,
                ok=False,
                error=str(e),
            )
        except Exception:
            pass
        return False, str(e)

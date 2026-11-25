# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Moduł: contact_extract_utils — normalizacja e-maili i telefonów oraz parser odpowiedzi „contact extract”.
#
# CO ROBI
#   Zawiera czyste funkcje (bez I/O): normalizację adresu e-mail (mailto:, parametry, interpunkcja),
#   normalizację numeru telefonu (odrzucanie krótkich/„rokowych” ciągów, formatowanie +49) oraz parser
#   JSON-a zwracanego przez Claude przy ekstrakcji kontaktów (emails, impressum_emails, phones, company_name).
#
# ROLA W PIPELINE
#   Etap „contact extract”: używany przez claude_contact_extract.py do oczyszczenia odpowiedzi LLM.
#   Wynikowe e-maile przechodzą dodatkowo przez filter_commercial_emails (odrzucenie adresów
#   nie-handlowych, np. noreply / prywatnych domen).
#
# ZALEŻNOŚCI: commercial_contact_filter.filter_commercial_emails; stdlib json, re.
# Uwaga: normalizacja telefonów zawiera relikt po kampanii niemieckiej (prefiks 49 / 0049 → +49).
#
# WEJŚCIE / WYJŚCIE
#   normalize_email_contact(str)->str ("" gdy niepoprawny), normalize_phone_contact(str)->str ("" gdy
#   odrzucony), parse_contact_extract_response(str)->dict {company_name, company_names, emails,
#   impressum_emails, phones, reason}.
# ============================================================
"""Normalizacja e-maili i telefonów ze stron www (regex / mailto)."""
from __future__ import annotations

import json
import re

from commercial_contact_filter import filter_commercial_emails

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)
_PHONE_SKIP_DIGIT_PREFIXES = ("19", "20")


# >>> OPIS FUNKCJI: funkcja normalize_email_contact
# Cel: sprowadzić surowy tekst do poprawnego adresu e-mail lub odrzucić go.
# Parametry: raw (str|None) — np. "mailto:Biuro@Firma.pl?subject=x".
# Zwraca: str — adres małymi literami "local@domain" albo "" gdy: brak "@", pusta część lokalna/domena,
#   domena bez kropki, lub długość części lokalnej poza zakresem 1–50 znaków.
# Efekty uboczne: brak. Przetwarzanie: lower+strip, usunięcie prefiksu mailto:, odcięcie ?query i #fragment,
#   zdjęcie interpunkcji wokół, usunięcie końcowej kropki domeny.
# Błędy: nie rzuca — niepoprawne dane dają "".
def normalize_email_contact(raw: str) -> str:
    low = (raw or "").strip().lower()
    low = re.sub(r"^mailto:\s*", "", low)
    low = low.split("?")[0].split("#")[0].strip(".,;:()[]{}<>\"'`")
    if "@" not in low:
        return ""
    local, _, domain = low.partition("@")
    local, domain = local.strip(), domain.strip().rstrip(".")
    if not local or not domain or "." not in domain:
        return ""
    if len(local) < 1 or len(local) > 50:
        return ""
    return f"{local}@{domain}"


# >>> OPIS FUNKCJI: funkcja normalize_phone_contact
# Cel: ujednolicić numer telefonu ze strony www i odrzucić ciągi niebędące numerami.
# Parametry: raw (str|None) — surowy tekst numeru.
# Zwraca: str — numer ze znormalizowanymi spacjami albo "" gdy: pusty, < 7 cyfr, 4/8-cyfrowy zaczynający się
#   od 19/20 (wygląda na rok/datę), lub zaczyna się od "49" i ma < 10 cyfr. Numery 0049… i 49…
#   (bez "+", min. 9 cyfr po prefiksie) są formatowane jako "+49 XXX reszta" (relikt kampanii DE).
# Efekty uboczne: brak. Błędy: nie rzuca; dane niepoprawne → "".
def normalize_phone_contact(raw: str) -> str:
    normalized = " ".join((raw or "").split()).strip(".,;:()[]")
    if not normalized:
        return ""
    digits = re.sub(r"\D", "", normalized)
    if len(digits) < 7:
        return ""
    if len(digits) in (4, 8) and digits.startswith(_PHONE_SKIP_DIGIT_PREFIXES):
        return ""
    if digits.startswith("49") and len(digits) < 10:
        return ""
    if digits.startswith("0049"):
        digits = "49" + digits[4:]
    if digits.startswith("49") and not normalized.startswith("+"):
        rest = digits[2:]
        if len(rest) >= 9:
            normalized = f"+49 {rest[:3]} {rest[3:]}".strip()
    return normalized


# >>> OPIS FUNKCJI: funkcja parse_contact_extract_response
# Cel: sparsować odpowiedź JSON Claude z ekstrakcji kontaktów do struktury pipeline.
# Parametry: text (str|None) — odpowiedź modelu; z tekstu wycinany jest obiekt JSON (regex od pierwszego "{"
#   do ostatniego "}"). Oczekiwane klucze: emails, impressum_emails, phones, company_name, reason.
# Zwraca: dict {company_name, company_names (lista 0–1), emails, impressum_emails, phones, reason};
#   e-maile znormalizowane, zdeduplikowane i przefiltrowane filter_commercial_emails, telefony
#   znormalizowane i zdeduplikowane.
# Efekty uboczne: brak (czysta funkcja).
# Błędy: JSONDecodeError przy niepoprawnym JSON; ValueError("Contact extract: not a JSON object"), gdy
#   wynik nie jest obiektem. Wyjątki propaguje do wywołującego (claude_contact_extract je łapie).
def parse_contact_extract_response(text: str) -> dict:
    raw = (text or "").strip()
    match = _JSON_BLOCK_RE.search(raw)
    payload = match.group(0) if match else raw
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("Contact extract: not a JSON object")

    emails: list[str] = []
    for item in data.get("emails") or []:
        norm = normalize_email_contact(str(item))
        if norm and norm not in emails:
            emails.append(norm)
    emails = filter_commercial_emails(emails)

    impressum_emails: list[str] = []
    for item in data.get("impressum_emails") or []:
        norm = normalize_email_contact(str(item))
        if norm and norm not in impressum_emails:
            impressum_emails.append(norm)
    impressum_emails = filter_commercial_emails(impressum_emails)

    phones: list[str] = []
    for item in data.get("phones") or []:
        norm = normalize_phone_contact(str(item))
        if norm and norm not in phones:
            phones.append(norm)

    company_name = " ".join(str(data.get("company_name") or "").split()).strip()
    reason = str(data.get("reason") or "").strip()
    company_names = [company_name] if company_name else []
    return {
        "company_name": company_name,
        "company_names": company_names,
        "emails": emails,
        "impressum_emails": impressum_emails,
        "phones": phones,
        "reason": reason,
    }

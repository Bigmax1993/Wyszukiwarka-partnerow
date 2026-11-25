# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Moduł: libs/email_custom_template — własny szablon zapytania ofertowego z GUI + dopracowanie przez Claude per firma.
#
# CO ROBI
#   Bierze treść wklejoną przez użytkownika (draft), buduje prompt Claude (PL domyślnie, DE legacy), wywołuje
#   model, parsuje JSON {subject, body} i zwraca gotowy temat oraz treść. Gdy API jest niedostępne —
#   fallback wstawia nazwę firmy do treści. NIE dotyczy maili przypominających (scraper_email_replies.build_reminder_email).
#
# ROLA W PIPELINE: opcjonalna personalizacja maila B2B przed wysyłką; scraper pyta inquiry_try_custom i, gdy
#   zwróci None, używa standardowego generatora treści.
#
# ZALEŻNOŚCI: claude_client.claude_generate_text, claude_prompts (build_custom_email_prompt_pl/_de),
#   scraper_env.get_anthropic_api_key; stdlib json, logging, re, typing.
# WEJŚCIE: draft, nazwa firmy, język, miasto/adres dostawy, logger. WYJŚCIE: krotki (subject, body) lub None.
# ============================================================
"""
Własna treść zapytania ofertowego z GUI → dopracowanie Claude per firma.
Nie dotyczy maili przypominających (scraper_email_replies.build_reminder_email).
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from claude_client import claude_generate_text
from claude_prompts import (
    build_custom_email_prompt_de,
    build_custom_email_prompt_pl,
)
from scraper_env import get_anthropic_api_key


def build_custom_draft_prompt(
    draft: str,
    company_name: str,
    lang: str = "pl",
    *,
    city_name: str = "",
    delivery_address: str = "",
) -> str:
    """
    Wybiera prompt Claude pod język szablonu.

    PL FAS: domyślnie ``pl`` → ``build_custom_email_prompt_pl``.
    ``de`` → legacy ``build_custom_email_prompt_de`` (nie używać w FAS).
    """
    draft = (draft or "").strip()
    if (lang or "pl").strip().lower() == "de":
        return build_custom_email_prompt_de(
            draft,
            company_name,
            city_name=city_name,
            delivery_address=delivery_address,
        )
    return build_custom_email_prompt_pl(
        draft,
        company_name,
        city_name=city_name,
        delivery_address=delivery_address,
    )


# >>> OPIS FUNKCJI: funkcja parse_llm_email_json
# Cel: sparsować odpowiedź Claude z JSON-em {"subject","body"}. Parametry: text (str|None) — odpowiedź (wycinany
# obiekt JSON regexem od "{" do "}"); fallback_subject (str) — temat, gdy model go nie zwrócił.
# Zwraca: (subject: str, body: str). Efekty uboczne: brak.
# Błędy: JSONDecodeError przy niepoprawnym JSON; ValueError("Claude zwróciło pusty body") gdy body jest puste.
def parse_llm_email_json(text: str, fallback_subject: str) -> tuple[str, str]:
    """Parsuj JSON Claude (subject/body); zwraca (subject, body)."""
    match = re.search(r"\{.*\}", text or "", flags=re.DOTALL)
    raw = match.group(0) if match else (text or "")
    parsed = json.loads(raw)
    subject = str(parsed.get("subject") or fallback_subject).strip()
    body = str(parsed.get("body") or "").strip()
    if not body:
        raise ValueError("Claude zwróciło pusty body")
    return subject, body


# >>> OPIS FUNKCJI: funkcja claude_generate_text_simple
# Cel: jednorazowe wywołanie Claude bez cache i bez dziennego limitu. Parametry: prompt (str);
# logger (Logger|None — domyślnie logger "email_custom_template"). Zwraca: (text, model).
# Efekty uboczne: żądanie HTTP do API (cache=None, bypass_daily_limit=True), logowanie przez claude_generate_text.
# Błędy: RuntimeError("Brak ANTHROPIC_API_KEY") gdy brak klucza; błędy sieci/API z claude_generate_text propagują się.
def claude_generate_text_simple(
    prompt: str, logger: logging.Logger | None = None
) -> tuple[str, str]:
    """Jednorazowe wywołanie Claude bez limitu dziennego cache; (text, model)."""
    api_key = get_anthropic_api_key()
    if not api_key:
        raise RuntimeError("Brak ANTHROPIC_API_KEY")
    text, model = claude_generate_text(
        prompt,
        logger or logging.getLogger("email_custom_template"),
        api_key,
        cache=None,
        bypass_daily_limit=True,
    )
    return text, model


# >>> OPIS FUNKCJI: funkcja beautify_custom_email_draft
# Cel: dopracować wklejony szablon pod konkretną firmę (zapytanie ofertowe) przy pomocy Claude.
# Parametry: draft (str) — treść użytkownika; company_name (str); lang (str, "pl"|"de", domyślnie "pl");
# fallback_subject (keyword-only, str) — temat awaryjny (domyślnie dla PL: "Maksym / Forwarding Assistant —
# szybkie pytanie do spedycji", dla DE: "Preisanfrage – <firma>"); city_name, delivery_address (keyword-only, str);
# logger (Logger|None). Zwraca: (subject, body) po parse_llm_email_json.
# Efekty uboczne: wywołanie API Claude, logowanie modelu.
# Błędy: ValueError("Pusta treść szablonu") dla pustego draftu; błędy API/JSON propagują się do wywołującego.
def beautify_custom_email_draft(
    draft: str,
    company_name: str,
    lang: str = "pl",
    *,
    fallback_subject: str = "",
    city_name: str = "",
    delivery_address: str = "",
    logger: logging.Logger | None = None,
) -> tuple[str, str]:
    """
    Dopracowuje wklejoną treść pod konkretną firmę (zapytania ofertowe).
    """
    draft = (draft or "").strip()
    if not draft:
        raise ValueError("Pusta treść szablonu")
    if not fallback_subject:
        fallback_subject = (
            f"Preisanfrage – {company_name}"
            if lang == "de"
            else "Maksym / Forwarding Assistant — szybkie pytanie do spedycji"
        )
    prompt = build_custom_draft_prompt(
        draft,
        company_name,
        lang,
        city_name=city_name,
        delivery_address=delivery_address,
    )
    text, model = claude_generate_text_simple(prompt, logger=logger)
    if logger:
        logger.info(f"Claude (własny szablon), model: {model}")
    return parse_llm_email_json(text, fallback_subject)


# >>> OPIS FUNKCJI: funkcja fallback_email_without_llm
# Cel: awaryjna wersja maila bez LLM. Parametry: draft (str); company_name (str); fallback_subject (str).
# Zwraca: (fallback_subject, body) — body = draft, a jeśli nazwy firmy nie ma w treści, dopisane "(Firma: <nazwa>)".
# Efekty uboczne/błędy: brak.
def fallback_email_without_llm(
    draft: str, company_name: str, fallback_subject: str
) -> tuple[str, str]:
    """Gdy brak API — wstaw nazwę firmy w pierwszej linii kontekstu."""
    body = draft.strip()
    if company_name and company_name not in body:
        body = f"{body}\n\n(Firma: {company_name})"
    return fallback_subject, body


def inquiry_try_custom(
    *,
    use_custom: bool,
    custom_draft: str,
    company_name: str,
    lang: str,
    logger: logging.Logger,
    subject_hint: str,
    email_context: dict[str, Any] | None = None,
    on_step: Any = None,
) -> tuple[str, str] | None:
    """
    Jeśli włączony własny szablon — zwraca (subject, body) z Claude.
    Jeśli nie — zwraca None (scraper używa standardowego generatora).
    Nie dotyczy przypomnień e-mail.
    """
    draft = (custom_draft or "").strip()
    if not use_custom or not draft:
        return None
    if on_step:
        on_step(f"E-mail z własnego szablonu (Claude, {lang}): {company_name}")
    ctx = email_context or {}
    city_name = str(ctx.get("city_name") or ctx.get("city") or "")
    delivery_address = str(ctx.get("delivery_address") or "")
    try:
        return beautify_custom_email_draft(
            draft,
            company_name,
            lang,
            fallback_subject=subject_hint,
            city_name=city_name,
            delivery_address=delivery_address,
            logger=logger,
        )
    except Exception as e:
        logger.warning(f"Claude (własny szablon) fallback: {e}")
        if get_anthropic_api_key():
            raise
        return fallback_email_without_llm(draft, company_name, subject_hint)

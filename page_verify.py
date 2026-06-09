# -*- coding: utf-8 -*-
"""Weryfikacja strony www (GU / Filialbau) — prompt, parser JSON, guardrails."""
from __future__ import annotations

import json
import re

from campaign_keyword_profile import (
    REJECT_PRIMARY_ROLES,
    gu_required_keywords_sample,
    negative_keywords_sample,
    retail_chain_keywords_sample,
    retail_context_keywords_sample,
)
from retail_store_builder_filter import (
    REQUIRED_RETAIL_CHAIN_KEYWORDS,
    detect_required_retail_chains,
    has_required_retail_chain_mention,
    is_excluded_non_gu_role,
    is_generalunternehmer,
    is_media_publisher_contact,
    is_retail_store_operator_contact,
)

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)
_REJECT_ROLES_NORMALIZED = {r.lower() for r in REJECT_PRIMARY_ROLES}


def hard_reject_page_context(
    *,
    url: str = "",
    name: str = "",
    page_text: str = "",
) -> tuple[bool, str]:
    """Twarde NO-GO — operator, media, role nie-GU."""
    blob = " ".join([name, url, page_text]).lower()
    if is_retail_store_operator_contact(url=url, text=blob):
        return True, "einzelhandel_betrieb_kein_bau"
    if is_media_publisher_contact(url=url, name=name, text=blob):
        return True, "medienportal"
    if is_excluded_non_gu_role(blob):
        return True, "excluded_non_gu_role"
    return False, ""


def build_page_verify_prompt(
    company_name: str,
    website: str,
    page_text: str,
    *,
    max_chars: int = 8000,
) -> str:
    snippet = (page_text or "")[:max_chars]
    return (
        "Du bist strenger Prüfer für B2B-Outreach an Generalunternehmer (GU) "
        "im Filialbau / Supermarktbau in Deutschland.\n\n"
        "Bewerte den Website-Auszug anhand dieser Kampagnen-Schlüsselwörter:\n\n"
        f"[WYMAGANE GU]\n{', '.join(gu_required_keywords_sample())}\n\n"
        f"[KONTEKST RETAIL / FILIALBAU]\n{', '.join(retail_context_keywords_sample())}\n\n"
        f"[SIECI HANDLOWE — Projekte]\n{', '.join(retail_chain_keywords_sample())}\n\n"
        f"[ODRZUĆ jeśli dominiert]\n{', '.join(negative_keywords_sample())}\n\n"
        f"Firma: {company_name}\nWebseite: {website}\n\n"
        "Antwort NUR als JSON (kein Markdown):\n"
        "{\n"
        '  "matched_gu_keywords": ["generalunternehmer"],\n'
        '  "matched_retail_keywords": ["filialbau"],\n'
        '  "matched_chains": ["rewe"],\n'
        '  "matched_negative_keywords": [],\n'
        '  "is_gu": true,\n'
        '  "has_retail_context": true,\n'
        '  "primary_role": "Generalunternehmer",\n'
        '  "reason": "kurz DE max 2 Sätze"\n'
        "}\n\n"
        f"Auszug:\n{snippet or '(leer)'}"
    )


def parse_page_verify_response(text: str) -> dict:
    raw = (text or "").strip()
    match = _JSON_BLOCK_RE.search(raw)
    payload = match.group(0) if match else raw
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("Page verify: not a JSON object")

    def _list(key: str) -> list[str]:
        val = data.get(key) or []
        if not isinstance(val, list):
            return []
        return [str(x).strip() for x in val if str(x).strip()]

    return {
        "matched_gu_keywords": _list("matched_gu_keywords"),
        "matched_retail_keywords": _list("matched_retail_keywords"),
        "matched_chains": [c.lower() for c in _list("matched_chains")],
        "matched_negative_keywords": _list("matched_negative_keywords"),
        "is_gu": bool(data.get("is_gu")),
        "has_retail_context": bool(data.get("has_retail_context")),
        "primary_role": str(data.get("primary_role") or "").strip(),
        "reason": str(data.get("reason") or "").strip(),
    }


def apply_page_verdict(
    llm: dict,
    *,
    page_text: str,
    serper_blob: str = "",
    require_generalunternehmer: bool = True,
) -> tuple[bool, str, list[str]]:
    """Werdykt z JSON Claude + guardrails na tekście strony."""
    blob = " ".join([page_text or "", serper_blob or ""]).lower()
    hard, hard_reason = hard_reject_page_context(page_text=blob)
    if hard:
        return False, hard_reason, []

    neg = llm.get("matched_negative_keywords") or []
    if neg:
        return False, f"claude_negative:{neg[0]}", llm.get("matched_chains") or []

    role = (llm.get("primary_role") or "").strip()
    if role and role.lower() in _REJECT_ROLES_NORMALIZED:
        return False, f"claude_role:{role}", llm.get("matched_chains") or []

    if not llm.get("is_gu"):
        return False, "claude_kein_gu", llm.get("matched_chains") or []

    if require_generalunternehmer:
        gu_text, _ = is_generalunternehmer(blob)
        gu_json = bool(llm.get("matched_gu_keywords"))
        if not gu_text and not gu_json:
            return False, "kein_generalunternehmer", llm.get("matched_chains") or []

    if not llm.get("has_retail_context"):
        return False, "claude_kein_retail", llm.get("matched_chains") or []

    required_set = set(REQUIRED_RETAIL_CHAIN_KEYWORDS)
    llm_chains = [
        c.lower()
        for c in (llm.get("matched_chains") or [])
        if c and c.lower() in required_set
    ]
    blob_chains = detect_required_retail_chains(blob)
    chains = list(dict.fromkeys(llm_chains + blob_chains))
    if not chains and not has_required_retail_chain_mention(blob):
        return False, "keine_handelskette", []

    reason = (llm.get("reason") or "claude_gu_retail").strip()
    return True, f"claude:{reason[:120]}", chains

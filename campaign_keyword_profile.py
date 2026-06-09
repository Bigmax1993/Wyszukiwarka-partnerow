# -*- coding: utf-8 -*-
"""
Wspólny słownik kampanii GU / Filialbau — używany przez Serper, regex i Claude.
"""
from __future__ import annotations

from de_gu_keywords import (
    RETAIL_CHAIN_KEYWORDS,
    SERPER_NEGATIVE_TERMS,
    SIMPLE_TERM_TEMPLATES,
    TERM_TEMPLATES,
)
from retail_store_builder_filter import (
    FILIALBAU_SPECIALIST_MARKERS,
    NON_GU_ROLE_EXCLUSION_MARKERS,
    RETAIL_STORE_BUILD_MARKERS,
    RETAIL_STORE_UMBAU_MARKERS,
    STRICT_GU_MARKERS,
)

# Role odrzucane w werdykcie LLM (primary_role)
REJECT_PRIMARY_ROLES = frozenset(
    {
        "Betreiber",
        "Händler",
        "Medienportal",
        "Architekturbüro",
        "Planungsbüro",
        "Subunternehmer",
        "Nachunternehmer",
        "Sonstiges",
    }
)

SERPER_TEMPLATE_PATTERNS: tuple[str, ...] = tuple(
    dict.fromkeys((*SIMPLE_TERM_TEMPLATES, *TERM_TEMPLATES))
)


def gu_required_keywords_sample(*, max_items: int = 12) -> list[str]:
    return list(STRICT_GU_MARKERS)[:max_items]


def retail_context_keywords_sample(*, max_items: int = 16) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for group in (
        FILIALBAU_SPECIALIST_MARKERS,
        RETAIL_STORE_BUILD_MARKERS,
        RETAIL_STORE_UMBAU_MARKERS,
    ):
        for item in group:
            key = item.strip().lower()
            if key and key not in seen:
                seen.add(key)
                out.append(item.strip())
            if len(out) >= max_items:
                return out
    return out


def retail_chain_keywords_sample(*, max_items: int = 12) -> list[str]:
    return list(RETAIL_CHAIN_KEYWORDS)[:max_items]


def negative_keywords_sample(*, max_items: int = 14) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in (*NON_GU_ROLE_EXCLUSION_MARKERS, *SERPER_NEGATIVE_TERMS[:20]):
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(item.strip())
        if len(out) >= max_items:
            break
    return out

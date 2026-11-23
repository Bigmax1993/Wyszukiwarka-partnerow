# -*- coding: utf-8 -*-
"""
Wspólny słownik kampanii PL spedycja — używany przez Serper, regex i Claude.
"""
from __future__ import annotations

from pl_spedycja_keywords import (
    SERPER_NEGATIVE_TERMS,
    SIMPLE_TERM_TEMPLATES,
    TERM_TEMPLATES,
)
from pl_spedycja_filter import (
    COURIER_REJECT_MARKERS,
    FORWARDER_ROLE_MARKERS,
    IRRELEVANT_ROLE_MARKERS,
    TRANSPORT_SEGMENT_MARKERS,
    TRANSPORT_SERVICE_MARKERS,
)

# Role odrzucane w werdykcie LLM (primary_role)
REJECT_PRIMARY_ROLES = frozenset(
    {
        "Kurier",
        "GieldaFrachtowa",
        "PortalOgloszeniowy",
        "MediaLogistyczne",
        "TylkoFlotaWlasna",
        "Producent",
        "HR",
        "Urzad",
        "Inne",
    }
)

SERPER_TEMPLATE_PATTERNS: tuple[str, ...] = tuple(
    dict.fromkeys((*SIMPLE_TERM_TEMPLATES, *TERM_TEMPLATES))
)


def gu_required_keywords_sample(*, max_items: int = 12) -> list[str]:
    return list(FORWARDER_ROLE_MARKERS)[:max_items]


def retail_context_keywords_sample(*, max_items: int = 16) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for group in (
        FORWARDER_ROLE_MARKERS,
        TRANSPORT_SERVICE_MARKERS,
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
    return list(TRANSPORT_SEGMENT_MARKERS)[:max_items]


def small_company_markers_sample(*, max_items: int = 10) -> list[str]:
    return [
        "firma rodzinna",
        "spedycja lokalna",
        "biuro w",
        "od lat na rynku",
        "właściciel",
        "wlasciciel",
        "mała firma",
        "mala firma",
        "polska spedycja",
        "regionalnie",
    ][:max_items]


def large_company_markers_sample(*, max_items: int = 14) -> list[str]:
    return [
        "Raben",
        "DB Schenker",
        "Schenker",
        "DHL",
        "DPD",
        "InPost",
        "GEODIS",
        "Kuehne",
        "Kuehne+Nagel",
        "DSV",
        "PEKAES",
        "Rohlig",
        "FM Logistic",
        "holding",
    ][:max_items]


def negative_keywords_sample(*, max_items: int = 14) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in (
        *IRRELEVANT_ROLE_MARKERS,
        *COURIER_REJECT_MARKERS,
        *SERPER_NEGATIVE_TERMS[:20],
    ):
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(item.strip())
        if len(out) >= max_items:
            break
    return out

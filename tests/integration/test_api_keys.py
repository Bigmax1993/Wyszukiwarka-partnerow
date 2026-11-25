# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# MODUŁ TESTOWY: tests/integration/test_api_keys.py
# CO ROBI: testy integracyjne 'live': sprawdzają, że klucze Serper i Anthropic działają (realne wywołania API; znacznik pytest api_live).
# ROLA W PIPELINE: kontrola konfiguracji sekretów przed uruchomieniem pipeline (zużywa minimalne kredyty).
# ZALEŻNOŚCI: pytest, requests, anthropic (leniwie), zmienne środowiskowe SERPER_API_KEY / ANTHROPIC_API_KEY.
# WEJŚCIE/WYJŚCIE: Testy pomijane (skip), gdy brak kluczy; nie zwracają wartości.
# ============================================================
"""Testy integracyjne: klucze API (Serper, Anthropic). Gmail/Drive: test_gmail_gdrive_api.py."""
from __future__ import annotations

import os

import pytest
import requests

SERPER_API_URL = "https://google.serper.dev/search"

pytestmark = pytest.mark.integration


# >>> OPIS FUNKCJI: funkcja _env
# Pomocnik testowy: odczytuje zmienną środowiskową jako obcięty string. Parametry: key (str). Zwraca: str (pusty, gdy brak). Efekty uboczne/błędy: brak.
def _env(key: str) -> str:
    return (os.environ.get(key) or "").strip()


# >>> OPIS FUNKCJI: funkcja test_serper_api_key_works
# Test: zapytanie do Serper (HTTP) zwraca 200 i odpowiedź zawiera 'organic' lub 'searchParameters'.
# Parametry: brak (funkcja pytest). Zwraca: None (wynik = przejście lub błąd testu).
# Efekty uboczne: REALNE połączenie sieciowe i zużycie kredytu Serper; pomijany bez klucza. Błędy: AssertionError lub wyjątek sieciowy.
@pytest.mark.api_live
def test_serper_api_key_works():
    api_key = _env("SERPER_API_KEY")
    if not api_key:
        pytest.skip("Brak SERPER_API_KEY")

    response = requests.post(
        SERPER_API_URL,
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        json={"q": "spedycja FTL Głogów", "gl": "pl", "hl": "pl", "num": 1},
        timeout=30,
    )
    assert response.status_code == 200, response.text[:300]
    data = response.json()
    assert "organic" in data or "searchParameters" in data


# >>> OPIS FUNKCJI: funkcja test_anthropic_api_key_works
# Test: krótkie zapytanie do Anthropic zwraca niepustą odpowiedź tekstową.
# Parametry: brak (funkcja pytest). Zwraca: None (wynik = przejście lub błąd testu).
# Efekty uboczne: REALNE połączenie sieciowe i zużycie tokenów; pomijany bez klucza. Błędy: AssertionError lub wyjątek API.
@pytest.mark.api_live
def test_anthropic_api_key_works():
    api_key = _env("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("Brak ANTHROPIC_API_KEY")

    anthropic = pytest.importorskip("anthropic")
    client = anthropic.Anthropic(api_key=api_key)
    model = os.environ.get("CLAUDE_MODEL_VERIFY", "claude-sonnet-4-6")

    message = client.messages.create(
        model=model,
        max_tokens=16,
        messages=[{"role": "user", "content": "Odpowiedz jednym s┼éowem: OK"}],
    )
    assert message.content
    assert message.content[0].text.strip()

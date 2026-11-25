# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# MODUŁ TESTOWY: tests/test_claude_client_retry.py
# CO ROBI: testy ponawiania wywołań API Claude (HTTP 503) w claude_client.claude_generate_text.
# ROLA W PIPELINE: chroni mechanizm retry/backoff używany przez wszystkie kroki Claude w pipeline.
# ZALEŻNOŚCI: unittest, unittest.mock, requests, claude_client (claude_generate_text, CLAUDE_API_RETRY_ATTEMPTS, CLAUDE_API_RETRY_WAIT_SECONDS).
# WEJŚCIE/WYJŚCIE: Moduł nie przyjmuje argumentów CLI; pytest/unittest odkrywa i uruchamia testy; nic nie zwraca (wynik = zielone/czerwone testy).
# ============================================================
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

ROOT = Path(__file__).resolve().parent.parent
LIBS = ROOT / "libs"
for p in (str(ROOT), str(LIBS)):
    if p not in sys.path:
        sys.path.insert(0, p)

from claude_client import (
    CLAUDE_API_RETRY_ATTEMPTS,
    CLAUDE_API_RETRY_WAIT_SECONDS,
    claude_generate_text,
)


# >>> OPIS FUNKCJI: klasa ClaudeApiRetryTest
# Grupa testów: retry klienta Claude przy błędach serwera.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class ClaudeApiRetryTest(unittest.TestCase):
    # >>> OPIS FUNKCJI: funkcja ClaudeApiRetryTest._ok_response
    # Pomocnik testowy: buduje atrapę udanej odpowiedzi HTTP 200 (MagicMock) z treścią {"ok": true}. Parametry: self. Zwraca: MagicMock. Efekty uboczne/błędy: brak.
    def _ok_response(self) -> MagicMock:
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "content": [{"type": "text", "text": '{"ok": true}'}],
        }
        resp.raise_for_status.return_value = None
        return resp

    # >>> OPIS FUNKCJI: funkcja ClaudeApiRetryTest.test_retries_on_api_error_then_succeeds
    # Test: dwa błędy 503, potem sukces: 3 wywołania POST, 2 pauzy o CLAUDE_API_RETRY_WAIT_SECONDS i poprawny wynik.
    # Parametry: self, _key, mock_post, mock_sleep (mocki z dekoratorów patch). Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: patche na time.sleep, requests.post i klucz API (brak sieci i realnych pauz). Błędy: AssertionError przy niespełnionej asercji.
    @patch("claude_client.time.sleep")
    @patch("claude_client.requests.post")
    @patch("claude_client.get_anthropic_api_key", return_value="test-key")
    def test_retries_on_api_error_then_succeeds(self, _key, mock_post, mock_sleep):
        err_resp = MagicMock()
        err_resp.status_code = 503
        err_resp.raise_for_status.side_effect = requests.HTTPError(
            "503 Server Error", response=err_resp
        )
        mock_post.side_effect = [err_resp, err_resp, self._ok_response()]

        text, model = claude_generate_text("ping", MagicMock(), cache={})

        self.assertEqual(mock_post.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_called_with(CLAUDE_API_RETRY_WAIT_SECONDS)
        self.assertIn("ok", text)
        self.assertTrue(model)

    # >>> OPIS FUNKCJI: funkcja ClaudeApiRetryTest.test_raises_after_three_failed_attempts
    # Test: po CLAUDE_API_RETRY_ATTEMPTS nieudanych próbach rzucany jest requests.HTTPError, a pauz jest o jedną mniej niż prób.
    # Parametry: self, _key, mock_post, mock_sleep. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: patche na time.sleep, requests.post i klucz API. Błędy: AssertionError; HTTPError oczekiwany w assertRaises.
    @patch("claude_client.time.sleep")
    @patch("claude_client.requests.post")
    @patch("claude_client.get_anthropic_api_key", return_value="test-key")
    def test_raises_after_three_failed_attempts(self, _key, mock_post, mock_sleep):
        err_resp = MagicMock()
        err_resp.status_code = 503
        err_resp.raise_for_status.side_effect = requests.HTTPError(
            "503 Server Error", response=err_resp
        )
        mock_post.return_value = err_resp

        with self.assertRaises(requests.HTTPError):
            claude_generate_text("ping", MagicMock(), cache={})

        self.assertEqual(mock_post.call_count, CLAUDE_API_RETRY_ATTEMPTS)
        self.assertEqual(mock_sleep.call_count, CLAUDE_API_RETRY_ATTEMPTS - 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)

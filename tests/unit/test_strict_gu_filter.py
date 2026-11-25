# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# MODUŁ TESTOWY: tests/unit/test_strict_gu_filter.py
# CO ROBI: testy jednostkowe filtra ICP pl_spedycja_filter: markery segmentów i roli, sygnał spedycyjny, powody odrzucenia, dowody oferty, kontakt, kandydaci Serper, adapter cache i debug.
# ROLA W PIPELINE: główne zabezpieczenie logiki kwalifikacji firm (nazwy klas z 'Gu' są legacy).
# ZALEŻNOŚCI: pytest, pl_spedycja_filter.
# WEJŚCIE/WYJŚCIE: Moduł nie przyjmuje argumentów CLI; pytest/unittest odkrywa i uruchamia testy; nic nie zwraca (wynik = zielone/czerwone testy).
# ============================================================
"""Testy jednostkowe: pl_spedycja_filter (PL spedycja)."""
from __future__ import annotations

import pytest

from pl_spedycja_filter import (
    FORWARDER_ROLE_MARKERS,
    TRANSPORT_SEGMENT_MARKERS,
    debug_filter_decision,
    has_forwarding_signal,
    has_offer_evidence,
    has_serper_trade_signal,
    is_cache_contact_not_store_builder,
    is_forwarder_role,
    is_generalunternehmer,
    is_loose_serper_discovery_candidate,
    is_retail_store_operator_contact,
    is_serper_only_pending_candidate,
    is_valid_retail_store_builder_contact,
    mentions_retail_store_build_activity_core,
    mentions_retail_store_build_activity_serper_discovery,
    portfolio_negates,
    reject_reason,
)

pytestmark = pytest.mark.unit

_OK = dict(
    email="biuro@spedycja-example.pl",
    url="https://spedycja-example.pl",
    name="Spedycja Example Sp. z o.o.",
)


# >>> OPIS FUNKCJI: klasa TestMarkersAndRole
# Grupa testów: markery segmentów i roli.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestMarkersAndRole:
    # >>> OPIS FUNKCJI: funkcja TestMarkersAndRole.test_segment_markers_include_ftl_ltl
    # Test: markery segmentów zawierają ftl i ltl.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_segment_markers_include_ftl_ltl(self):
        chains = {m for m in TRANSPORT_SEGMENT_MARKERS if len(m) >= 3}
        for expected in ("ftl", "ltl", "fracht", "europa", "niemcy"):
            assert any(expected in c for c in chains)

    # >>> OPIS FUNKCJI: funkcja TestMarkersAndRole.test_role_markers_include_spedycja
    # Test: markery roli zawierają 'spedycja'.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_role_markers_include_spedycja(self):
        assert any("spedycja" in m for m in FORWARDER_ROLE_MARKERS)

    # >>> OPIS FUNKCJI: funkcja TestMarkersAndRole.test_forwarder_role_alias
    # Test: is_forwarder_role i is_generalunternehmer dają ten sam wynik; ladenbau nie jest spedytorem.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_forwarder_role_alias(self):
        text = "Firma spedycyjna transport drogowy"
        assert is_forwarder_role(text) == is_generalunternehmer(text)
        assert is_forwarder_role(text)[0] is True
        assert is_forwarder_role("HELIA Ladenbau Filialbau")[0] is False


# >>> OPIS FUNKCJI: klasa TestForwardingSignal
# Grupa testów: sygnał spedycyjny.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestForwardingSignal:
    # >>> OPIS FUNKCJI: funkcja TestForwardingSignal.test_role_and_segment
    # Test: rola + segment tworzą sygnał spedycyjny i spełniają rdzeń (mentions_..._core).
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_role_and_segment(self):
        assert has_forwarding_signal("Firma spedycyjna. FTL Europa.")
        assert mentions_retail_store_build_activity_core(
            "Firma spedycyjna. FTL Europa."
        )

    # >>> OPIS FUNKCJI: funkcja TestForwardingSignal.test_role_and_service
    # Test: rola + usługa (transport drogowy) tworzą sygnał.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_role_and_service(self):
        assert has_forwarding_signal("Spedytor. Transport drogowy Polska.")

    # >>> OPIS FUNKCJI: funkcja TestForwardingSignal.test_role_alone_insufficient
    # Test: sama rola nie wystarcza.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_role_alone_insufficient(self):
        assert not has_forwarding_signal("Firma spedycyjna Sp. z o.o.")

    # >>> OPIS FUNKCJI: funkcja TestForwardingSignal.test_serper_discovery_looser
    # Test: filtr discovery jest łagodniejszy niż rdzeń.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_serper_discovery_looser(self):
        text = "Firma spedycyjna Warszawa"
        assert mentions_retail_store_build_activity_serper_discovery(text)
        assert not mentions_retail_store_build_activity_core(text)


# >>> OPIS FUNKCJI: klasa TestRejectReason
# Grupa testów: powody odrzucenia.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestRejectReason:
    # >>> OPIS FUNKCJI: funkcja TestRejectReason.test_courier
    # Test: kurier/paczkomaty → 'courier'.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_courier(self):
        assert reject_reason(text="InPost paczkomaty kurier") == "courier"

    # >>> OPIS FUNKCJI: funkcja TestRejectReason.test_exchange_domain
    # Test: domena giełdy transportowej/big 3PL jest odrzucana.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_exchange_domain(self):
        assert (
            reject_reason(url="https://www.timocom.com/pl", text="giełda")
            == "exchange_or_big3pl"
        )

    # >>> OPIS FUNKCJI: funkcja TestRejectReason.test_media
    # Test: media/wydawcy są odrzucane.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_media(self):
        assert (
            reject_reason(
                url="https://trans.info/artykul/1",
                name="Portal branżowy",
                text="aktualności transport",
            )
            == "media"
        )

    # >>> OPIS FUNKCJI: funkcja TestRejectReason.test_irrelevant_role
    # Test: niepasująca rola jest odrzucana.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_irrelevant_role(self):
        assert (
            reject_reason(text="oferty pracy kierowca agencja pracy")
            == "irrelevant_role"
        )

    def test_transport_firm_with_careers_not_irrelevant(self):
        # HIT-like: sekcja kariery nie zabija firmy ze spedycją/transportem.
        text = (
            "HIT Transport Międzynarodowy Spedycja i Logistyka. "
            "Transport drogowy FTL. Oferty pracy. Praca kierowca C+E."
        )
        assert reject_reason(name="HIT Transport", url="https://hittransport.pl", text=text) is None
        from pl_spedycja_filter import (
            has_retail_context_without_named_chain,
            is_excluded_non_gu_role,
        )
        from page_verify import hard_reject_page_context

        assert not is_excluded_non_gu_role(text)
        assert has_retail_context_without_named_chain(text)
        rejected, reason = hard_reject_page_context(
            url="https://hittransport.pl",
            name="HIT Transport",
            page_text=text,
        )
        assert not rejected, reason

    def test_transport_only_with_careers_not_irrelevant(self):
        # Warstwa 1: sama firma transportowa + FTL + kariera → nie śmieć.
        text = (
            "Usługi transportowe. Transport drogowy FTL Europa. "
            "Oferty pracy. Praca kierowca C+E."
        )
        assert reject_reason(text=text) is None
        from pl_spedycja_filter import is_excluded_non_gu_role
        from page_verify import hard_reject_page_context

        assert not is_excluded_non_gu_role(text)
        rejected, reason = hard_reject_page_context(page_text=text)
        assert not rejected, reason

    # >>> OPIS FUNKCJI: funkcja TestRejectReason.test_clean_forwarder
    # Test: czysty spedytor nie ma powodu odrzucenia (None).
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_clean_forwarder(self):
        assert (
            reject_reason(
                url="https://spedycja-example.pl",
                name="Spedycja Example",
                text="Firma spedycyjna FTL",
            )
            is None
        )


# >>> OPIS FUNKCJI: klasa TestOfferAndNegation
# Grupa testów: dowody oferty i negacja portfolio.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestOfferAndNegation:
    # >>> OPIS FUNKCJI: funkcja TestOfferAndNegation.test_offer_evidence
    # Test: tekst ma dowód oferty i nie ma negacji.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_offer_evidence(self):
        text = "Firma spedycyjna. Oferta: flota i trasy. FTL Europa."
        assert has_offer_evidence(text)
        assert not portfolio_negates(text)

    # >>> OPIS FUNKCJI: funkcja TestOfferAndNegation.test_portfolio_negates
    # Test: negacja portfolio jest wykrywana i znosi dowód oferty.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_portfolio_negates(self):
        text = "Spedycja FTL. Nie prowadzimy spedycji."
        assert portfolio_negates(text)
        assert not has_offer_evidence(text)


# >>> OPIS FUNKCJI: klasa TestValidContact
# Grupa testów: walidacja kontaktu.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestValidContact:
    # >>> OPIS FUNKCJI: funkcja TestValidContact.test_valid_spedycja_with_ftl
    # Test: spedycja z FTL jest poprawnym kontaktem.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_valid_spedycja_with_ftl(self):
        text = "Firma spedycyjna. Transport drogowy FTL Polska Niemcy."
        assert mentions_retail_store_build_activity_core(text)
        assert is_valid_retail_store_builder_contact(**_OK, text=text)

    # >>> OPIS FUNKCJI: funkcja TestValidContact.test_accepts_freight_forwarding
    # Test: tekst o freight forwarding jest akceptowany.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_accepts_freight_forwarding(self):
        text = (
            "Freight forwarding. Spedycja FTL. "
            "Transport międzynarodowy Europa."
        )
        assert is_valid_retail_store_builder_contact(**_OK, text=text)

    # >>> OPIS FUNKCJI: funkcja TestValidContact.test_rejects_negation
    # Test: tekst z negacją jest odrzucany.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_rejects_negation(self):
        text = "Firma spedycyjna FTL. Nie prowadzimy spedycji."
        assert not is_valid_retail_store_builder_contact(**_OK, text=text)

    # >>> OPIS FUNKCJI: funkcja TestValidContact.test_rejects_retail_operator_domain
    # Test: domeny operatorów detalicznych są rozpoznawane jako nie-ICP.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_rejects_retail_operator_domain(self):
        assert is_retail_store_operator_contact(
            url="https://www.timocom.com/pl",
            email="",
            text="Giełda transportowa oferty frachtów",
        )
        assert is_retail_store_operator_contact(
            url="https://inpost.pl",
            email="",
            text="Paczkomat śledź paczkę",
        )


# >>> OPIS FUNKCJI: klasa TestSerper
# Grupa testów: kandydaci Serper.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestSerper:
    # >>> OPIS FUNKCJI: funkcja TestSerper.test_accepts_spedycja_snippet
    # Test: snippet o spedycji jest akceptowany jako kandydat pending.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_accepts_spedycja_snippet(self):
        assert is_serper_only_pending_candidate(
            **_OK,
            text="Firma spedycyjna FTL transport drogowy Warszawa",
            search_term="spedycja FTL Warszawa",
        )

    # >>> OPIS FUNKCJI: funkcja TestSerper.test_accepts_segment_from_search_term
    # Test: segment z frazy wyszukiwania wystarcza.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_accepts_segment_from_search_term(self):
        assert is_serper_only_pending_candidate(
            **_OK,
            text="Biuro w Warszawie — kontakt",
            search_term="spedycja FTL Mazowieckie",
        )

    # >>> OPIS FUNKCJI: funkcja TestSerper.test_rejects_ladenbau
    # Test: ladenbau jest odrzucany.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_rejects_ladenbau(self):
        assert not is_serper_only_pending_candidate(
            email="",
            url="https://helia-ladenbau.de",
            name="HELIA Ladenbau GmbH",
            text="Ladenbau in Ulm",
        )

    # >>> OPIS FUNKCJI: funkcja TestSerper.test_rejects_media
    # Test: media są odrzucane.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_rejects_media(self):
        assert not is_serper_only_pending_candidate(
            url="https://www.hi-heute.de/supermarkte",
            name="hi-heute.de Verlag",
            text="Nachrichten Supermarkt",
        )

    # >>> OPIS FUNKCJI: funkcja TestSerper.test_rejects_negation
    # Test: tekst z negacją jest odrzucany.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_rejects_negation(self):
        assert not is_serper_only_pending_candidate(
            **_OK,
            text="Firma spedycyjna FTL. Nie prowadzimy spedycji.",
            search_term="spedycja FTL",
        )

    # >>> OPIS FUNKCJI: funkcja TestSerper.test_loose_is_alias
    # Test: is_loose_serper_discovery_candidate jest aliasem filtra serper-only.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_loose_is_alias(self):
        kwargs = dict(
            **_OK,
            text="Firma spedycyjna FTL Warszawa",
            search_term="spedycja FTL",
        )
        assert is_loose_serper_discovery_candidate(
            **kwargs
        ) == is_serper_only_pending_candidate(**kwargs)

    # >>> OPIS FUNKCJI: funkcja TestSerper.test_trade_signal_helper
    # Test: has_serper_trade_signal wykrywa sygnał handlowy w nazwie/tekście.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_trade_signal_helper(self):
        assert has_serper_trade_signal("biuro", "transport drogowy mazowieckie")
        assert not has_serper_trade_signal("biuro kontakt", "")


# >>> OPIS FUNKCJI: klasa TestCacheAdapter
# Grupa testów: adapter rekordów cache.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestCacheAdapter:
    # >>> OPIS FUNKCJI: funkcja TestCacheAdapter.test_pending_kept
    # Test: rekordy pending są zachowywane (nie traktowane jako instytucje).
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_pending_kept(self):
        assert (
            is_cache_contact_not_store_builder(
                "https://a.pl",
                {
                    "verification_reason": "pending_www_verify",
                    "retail_verified": False,
                },
            )
            is False
        )

    # >>> OPIS FUNKCJI: funkcja TestCacheAdapter.test_wojewodztwo_without_email_kept
    # Test: rekord z województwem, ale bez e-maila, jest zachowywany.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_wojewodztwo_without_email_kept(self):
        assert (
            is_cache_contact_not_store_builder(
                "https://a.pl",
                {
                    "discovery_wojewodztwo": "Mazowieckie",
                    "company_name_clean": "X",
                },
            )
            is False
        )

    # >>> OPIS FUNKCJI: funkcja TestCacheAdapter.test_legacy_bundesland_key_still_kept
    # Test: rekord ze starym kluczem bundesland nadal jest zachowywany.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_legacy_bundesland_key_still_kept(self):
        assert (
            is_cache_contact_not_store_builder(
                "https://a.pl",
                {
                    "discovery_bundesland": "Mazowieckie",
                    "company_name_clean": "X",
                },
            )
            is False
        )


# >>> OPIS FUNKCJI: klasa TestDebugFilterDecision
# Grupa testów: debug decyzji filtra.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestDebugFilterDecision:
    # >>> OPIS FUNKCJI: funkcja TestDebugFilterDecision.test_debug_accept_path
    # Test: debug dla akceptowanego tekstu: brak powodu odrzucenia, rola OK, sygnał spedycyjny, segment ftl.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_debug_accept_path(self):
        d = debug_filter_decision(
            **_OK,
            text="Firma spedycyjna. Transport drogowy FTL Europa.",
            search_term="spedycja FTL",
        )
        assert d["reject_reason"] is None
        assert d["role_ok"] is True
        assert d["forwarding_signal"] is True
        assert d["is_valid"] is True
        assert d["is_serper_candidate"] is True
        assert "ftl" in d["segments"]

    # >>> OPIS FUNKCJI: funkcja TestDebugFilterDecision.test_debug_reject_courier
    # Test: debug dla kuriera: reject_reason='courier', is_valid=False.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_debug_reject_courier(self):
        d = debug_filter_decision(
            email="",
            url="https://lokalny-kurier-example.pl",
            name="Lokalny Kurier",
            text="usługi kurierskie paczka same day delivery",
        )
        assert d["reject_reason"] == "courier"
        assert d["is_valid"] is False
        assert d["is_serper_candidate"] is False

    # >>> OPIS FUNKCJI: funkcja TestDebugFilterDecision.test_debug_reject_exchange_domain
    # Test: debug dla giełdy: reject_reason='exchange_or_big3pl'.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_debug_reject_exchange_domain(self):
        d = debug_filter_decision(
            email="",
            url="https://inpost.pl",
            name="InPost",
            text="paczkomaty kurier",
        )
        assert d["reject_reason"] == "exchange_or_big3pl"

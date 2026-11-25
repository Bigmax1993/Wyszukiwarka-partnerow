# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# MODUŁ TESTOWY: tests/unit/test_commercial_contact_filter.py
# CO ROBI: testy jednostkowe filtra kontaktów komercyjnych (commercial_contact_filter): urzędy, katalogi, śmieciowe adresy, nazwy instytucji, formy prawne.
# ROLA W PIPELINE: bramka jakości adresów i nazw przed Excelem/mailingiem.
# ZALEŻNOŚCI: pytest, commercial_contact_filter.
# WEJŚCIE/WYJŚCIE: Moduł nie przyjmuje argumentów CLI; pytest/unittest odkrywa i uruchamia testy; nic nie zwraca (wynik = zielone/czerwone testy).
# ============================================================
"""Testy jednostkowe: commercial_contact_filter."""
from __future__ import annotations

import pytest

from commercial_contact_filter import (
    filter_commercial_emails,
    is_junk_scraped_email,
    is_non_commercial_contact,
    is_non_commercial_email,
    is_non_commercial_name,
    is_valid_commercial_company_contact,
)

pytestmark = pytest.mark.unit


# >>> OPIS FUNKCJI: klasa TestNonCommercialEmail
# Grupa testów: adresy niekomercyjne.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestNonCommercialEmail:
    # >>> OPIS FUNKCJI: funkcja TestNonCommercialEmail.test_rejects_city_domain
    # Test: adres z domeny miejskiej (leipzig.de) jest niekomercyjny.
    # Parametry: self (+ fixtury pytest wskazane w nawiasie). Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_rejects_city_domain(self):
        assert is_non_commercial_email("info@leipzig.de")

    # >>> OPIS FUNKCJI: funkcja TestNonCommercialEmail.test_rejects_pl_gov_and_catalog
    # Test: adresy .gov.pl, urzędów i katalogów (panoramafirm, zus.pl) są odrzucane.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_rejects_pl_gov_and_catalog(self):
        assert is_non_commercial_email("kontakt@mf.gov.pl")
        assert is_non_commercial_email("biuro@um.warszawa.pl")
        assert is_non_commercial_email("info@panoramafirm.pl")
        assert is_non_commercial_email("x@zus.pl")

    # >>> OPIS FUNKCJI: funkcja TestNonCommercialEmail.test_accepts_company_domain
    # Test: adresy domen firmowych (bau-gmbh.de, trans-spedycja.pl) są akceptowane.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_accepts_company_domain(self):
        assert not is_non_commercial_email("office@bau-gmbh.de")
        assert not is_non_commercial_email("biuro@trans-spedycja.pl")
        # Nie false-positive na zwykłej firmie (um. w środku słowa domeny)
        assert not is_non_commercial_email("biuro@premium-log.pl")


# >>> OPIS FUNKCJI: klasa TestJunkScrapedEmail
# Grupa testów: śmieciowe adresy ze scrapowania.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestJunkScrapedEmail:
    # >>> OPIS FUNKCJI: funkcja TestJunkScrapedEmail.test_rejects_cookie_banner
    # Test: adres z banera cookies jest uznany za śmieć.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_rejects_cookie_banner(self):
        assert is_junk_scraped_email("akzeptieren@cookie-banner.de")

    # >>> OPIS FUNKCJI: funkcja TestJunkScrapedEmail.test_accepts_normal_email
    # Test: normalny adres firmowy nie jest śmieciem.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_accepts_normal_email(self):
        assert not is_junk_scraped_email("kontakt@firma-gmbh.de")


# >>> OPIS FUNKCJI: klasa TestCommercialContact
# Grupa testów: kontakty komercyjne vs instytucje.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestCommercialContact:
    # >>> OPIS FUNKCJI: funkcja TestCommercialContact.test_rejects_institution_name
    # Test: nazwa instytucji (Stadt Leipzig…) jest niekomercyjna.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_rejects_institution_name(self):
        assert is_non_commercial_contact(name="Stadt Leipzig, Dezernat Wirtschaft")

    # >>> OPIS FUNKCJI: funkcja TestCommercialContact.test_rejects_pl_institution_name
    # Test: polskie instytucje (urzędy, giełdy transportowe) są odrzucane.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_rejects_pl_institution_name(self):
        assert is_non_commercial_contact(name="Urząd Miasta Warszawa")
        assert is_non_commercial_contact(name="Powiatowy Urząd Pracy Gdańsk")
        assert is_non_commercial_contact(name="Giełda transportowa TIMOCOM")

    # >>> OPIS FUNKCJI: funkcja TestCommercialContact.test_name_soft_pass_pl_spedycja_not_legacy_gu
    # Test: nazwa polskiej spedycji przechodzi, a legacy 'Generalunternehmer' jest traktowany jako niekomercyjny.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_name_soft_pass_pl_spedycja_not_legacy_gu(self):
        # Soft-pass: izba + spedycja + Sp. z o.o. → firma, nie instytucja
        assert not is_non_commercial_name(
            "Izba Partner Spedycja Sp. z o.o."
        )
        # Stary soft-pass DE GU usunięty — sam Generalunternehmer + GmbH = non-commercial
        assert is_non_commercial_name("Müller Generalunternehmer GmbH")
        assert is_non_commercial_name("Generalunternehmer Filialbau")

    # >>> OPIS FUNKCJI: funkcja TestCommercialContact.test_short_name_geo_pl_without_legal_form
    # Test: krótka nazwa geograficzna bez formy prawnej (np. 'Transport Warszawa') jest odrzucana, a nazwa z Sp. z o.o. nie.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_short_name_geo_pl_without_legal_form(self):
        # ≤3 słowa, bez Sp. z o.o., geo z BUNDESLAND_CONFIG → portal/miasto
        assert is_non_commercial_name("Transport Warszawa")
        assert is_non_commercial_name("Firma Kraków")
        assert is_non_commercial_name("Leipzig Gewerbe")
        # Z formą prawną — nie ten tor (firma)
        assert not is_non_commercial_name("Trans Spedycja Sp. z o.o.")

    # >>> OPIS FUNKCJI: funkcja TestCommercialContact.test_accepts_gmbh_with_own_domain
    # Test: GmbH z własną domeną jest akceptowana jako kontakt komercyjny.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_accepts_gmbh_with_own_domain(self):
        assert is_valid_commercial_company_contact(
            email="info@sus-bau.de",
            url="https://sus-bau.de",
            name="SuS Bau GmbH",
        )

    # >>> OPIS FUNKCJI: funkcja TestCommercialContact.test_accepts_pl_sp_zoo
    # Test: polska Sp. z o.o. jest akceptowana.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_accepts_pl_sp_zoo(self):
        assert is_valid_commercial_company_contact(
            email="biuro@trans-spedycja.pl",
            url="https://trans-spedycja.pl",
            name="Trans Spedycja Sp. z o.o.",
        )

    # >>> OPIS FUNKCJI: funkcja TestCommercialContact.test_accepts_pl_sa
    # Test: polska S.A. jest akceptowana.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_accepts_pl_sa(self):
        assert is_valid_commercial_company_contact(
            email="kontakt@firma-sa.pl",
            url="https://firma-sa.pl",
            name="Logistyka Polska S.A.",
        )

    # >>> OPIS FUNKCJI: funkcja TestCommercialContact.test_accepts_pl_domain_heuristic_without_legal_form
    # Test: firma z domeną .pl bez formy prawnej jest akceptowana heurystyką.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_accepts_pl_domain_heuristic_without_legal_form(self):
        # Nazwa bez Sp. z o.o., ale domena maila z „spedycja” / „transport”
        assert is_valid_commercial_company_contact(
            email="biuro@nord-spedycja.pl",
            url="https://inna-domena.pl",
            name="Nord Partner",
        )
        assert is_valid_commercial_company_contact(
            email="biuro@abc-transport.pl",
            url="https://inna-domena.pl",
            name="ABC Partner",
        )


# >>> OPIS FUNKCJI: klasa TestFilterCommercialEmails
# Grupa testów: filtrowanie list adresów.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestFilterCommercialEmails:
    # >>> OPIS FUNKCJI: funkcja TestFilterCommercialEmails.test_deduplicates_and_filters
    # Test: filter_commercial_emails usuwa duplikaty i niekomercyjne adresy, zachowując kolejność.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_deduplicates_and_filters(self):
        raw = [
            "info@firma.de",
            "info@firma.de",
            "info@leipzig.de",
            "kontakt@bau-gmbh.de",
        ]
        out = filter_commercial_emails(raw)
        assert out == ["info@firma.de", "kontakt@bau-gmbh.de"]

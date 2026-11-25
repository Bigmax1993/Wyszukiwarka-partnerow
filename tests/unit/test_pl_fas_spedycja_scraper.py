# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# MODUŁ TESTOWY: tests/unit/test_pl_fas_spedycja_scraper.py
# CO ROBI: testy jednostkowe głównego modułu kampanii: domyślne ustawienia e-mail, aliasy, generacja treści maila, listy złych domen Serper, flagi ICP, eksport do Excela, geo PL.
# ROLA W PIPELINE: ochrona kluczowych stałych i funkcji orkiestratora przed regresją przy zmianach konfiguracji.
# ZALEŻNOŚCI: pytest, unittest.mock.patch, pl_fas_spedycja_scraper, fas_spedycja_inquiry_email_pl.
# WEJŚCIE/WYJŚCIE: Moduł nie przyjmuje argumentów CLI; pytest/unittest odkrywa i uruchamia testy; nic nie zwraca (wynik = zielone/czerwone testy).
# ============================================================
"""Testy jednostkowe: pl_fas_spedycja_scraper pod kampanię PL FAS."""
from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import pl_fas_spedycja_scraper as scraper
from fas_spedycja_inquiry_email_pl import FAS_MUST_KEEP_RATE_LINE, FAS_WEBSITE

pytestmark = pytest.mark.unit


# >>> OPIS FUNKCJI: klasa TestPlFasEmailDefaults
# Grupa testów: domyślne ustawienia e-mail i kontekst zapytania.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestPlFasEmailDefaults:
    # >>> OPIS FUNKCJI: funkcja TestPlFasEmailDefaults.test_lang_and_custom_template_defaults
    # Test: domyślnie język PL, własny szablon włączony, Serper gl/hl=pl, szkic i temat FAS.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_lang_and_custom_template_defaults(self):
        assert scraper.CUSTOM_EMAIL_LANG == "pl"
        assert scraper.USE_CUSTOM_EMAIL_TEMPLATE is True
        assert scraper.SERPER_COUNTRY == "pl"
        assert scraper.SERPER_LANGUAGE == "pl"
        assert "Forwarding Assistant" in scraper.CUSTOM_EMAIL_DRAFT
        assert FAS_MUST_KEEP_RATE_LINE in scraper.CUSTOM_EMAIL_DRAFT
        assert scraper.EMAIL_SUBJECT_TEMPLATE.startswith("Maksym / Forwarding Assistant")
        assert FAS_WEBSITE in scraper.EMAIL_SIGNATURE
        assert scraper.FIXED_EMAIL_SUBJECT_DE == scraper.FIXED_EMAIL_SUBJECT_PL

    # >>> OPIS FUNKCJI: funkcja TestPlFasEmailDefaults.test_inquiry_context_is_pl_segments
    # Test: kontekst zapytania to Polska i segmenty (ftl); aliasy legacy DE wskazują na te same wartości.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_inquiry_context_is_pl_segments(self):
        assert "Polska" in scraper.INQUIRY_REGION_PL
        assert "ftl" in scraper.INQUIRY_SEGMENTS_PL
        assert scraper.INQUIRY_REGION_DE == scraper.INQUIRY_REGION_PL
        assert scraper.RETAIL_CHAINS_DE == scraper.INQUIRY_SEGMENTS_PL


# >>> OPIS FUNKCJI: klasa TestPlFasEmailAliases
# Grupa testów: aliasy nazw i generacja treści.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestPlFasEmailAliases:
    # >>> OPIS FUNKCJI: funkcja TestPlFasEmailAliases.test_send_and_attachment_aliases
    # Test: send_email_pl_fas jest aliasem send_email_de_gu, a funkcje załączników mają aliasy.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_send_and_attachment_aliases(self):
        assert scraper.send_email_pl_fas is scraper.send_email_de_gu
        assert (
            scraper.get_email_attachments_pl_fas
            is scraper.get_email_attachments_de_gu
        )

    # >>> OPIS FUNKCJI: funkcja TestPlFasEmailAliases.test_assemble_fallback_injects_company
    # Test: fallback treści wstawia nazwę firmy, zdanie o stawce i www.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_assemble_fallback_injects_company(self):
        body = scraper._assemble_inquiry_email_body("Trans Spedycja Sp. z o.o.")
        assert "Trans Spedycja Sp. z o.o." in body
        assert FAS_MUST_KEEP_RATE_LINE in body
        assert FAS_WEBSITE in body

    # >>> OPIS FUNKCJI: funkcja TestPlFasEmailAliases.test_generate_email_content_fallback_without_api
    # Test: generate_email_content bez API zwraca temat FAS i fallbackowe ciało z nazwą firmy.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: patch na generator szablonu (brak wywołań Claude). Błędy: AssertionError przy niespełnionej asercji.
    def test_generate_email_content_fallback_without_api(self):
        log = logging.getLogger("test_pl_fas_mail")
        with patch(
            "email_custom_template.inquiry_try_custom",
            side_effect=RuntimeError("brak API"),
        ):
            subject, body = scraper.generate_email_content(
                "Trans Spedycja Sp. z o.o.",
                log,
                city_name="Głogów",
            )
        assert "Forwarding Assistant" in subject
        assert FAS_MUST_KEEP_RATE_LINE in body
        assert "Trans Spedycja" in body

    # >>> OPIS FUNKCJI: funkcja TestPlFasEmailAliases.test_generate_email_content_keeps_rate_line_from_claude
    # Test: gdy Claude zwróci treść, zdanie o stawce i podpis pozostają w mailu; temat jest z odpowiedzi.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: patch zwracający odpowiedź Claude. Błędy: AssertionError przy niespełnionej asercji.
    def test_generate_email_content_keeps_rate_line_from_claude(self):
        log = logging.getLogger("test_pl_fas_mail")
        claude_body = (
            "Cześć,\n\nTu Claude.\n\n"
            f"{FAS_MUST_KEEP_RATE_LINE}\n\n"
            "Pozdrawiam\nMaksym Swinczak\nswinczakdata.pl\n+48 516 513 965"
        )
        with patch(
            "email_custom_template.inquiry_try_custom",
            return_value=("Temat FAS test", claude_body),
        ):
            subject, body = scraper.generate_email_content("Firma X", log)
        assert subject == "Temat FAS test"
        assert FAS_MUST_KEEP_RATE_LINE in body
        assert "swinczakdata.pl" in body

    # >>> OPIS FUNKCJI: funkcja TestPlFasEmailAliases.test_sanitize_sender_name_default_fas
    # Test: pusta nazwa nadawcy → domyślna 'Maksym Swinczak, Forwarding Assistant'.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_sanitize_sender_name_default_fas(self):
        assert scraper.sanitize_sender_name("") == (
            "Maksym Swinczak, Forwarding Assistant"
        )
        assert "Forwarding Assistant" in scraper.sanitize_sender_name("   ")


# >>> OPIS FUNKCJI: klasa TestSerperBadDomainsPl
# Grupa testów: lista złych domen Serper.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestSerperBadDomainsPl:
    # >>> OPIS FUNKCJI: funkcja TestSerperBadDomainsPl.test_pl_junk_present_de_retail_absent
    # Test: lista zawiera polskie katalogi/portale (panoramafirm, gus, pracuj, raben-group) i nie zawiera domen DE retail.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_pl_junk_present_de_retail_absent(self):
        bad = scraper.SERPER_BAD_DOMAINS
        assert "panoramafirm.pl" in bad
        assert "gus.gov.pl" in bad
        assert "pracuj.pl" in bad
        assert "raben-group" in bad
        assert "aldi-sued.de" not in bad
        assert "ibau.de" not in bad
        assert "filialfinder" not in bad

    # >>> OPIS FUNKCJI: funkcja TestSerperBadDomainsPl.test_score_penalizes_panorama_and_big3pl
    # Test: score_serper_candidate karze katalog i big 3PL (ujemny wynik) względem dobrej firmy.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_score_penalizes_panorama_and_big3pl(self):
        good = scraper.score_serper_candidate(
            "https://trans-spedycja.pl",
            "Spedycja FTL",
            "firma spedycyjna",
        )
        panorama = scraper.score_serper_candidate(
            "https://panoramafirm.pl/firma/x",
            "katalog",
            "spedycja",
        )
        raben = scraper.score_serper_candidate(
            "https://www.raben-group.com",
            "Raben",
            "logistyka",
        )
        assert good > panorama
        assert good > raben
        assert panorama < 0
        assert raben < 0


# >>> OPIS FUNKCJI: klasa TestIcpFlagsAndLegalForms
# Grupa testów: flagi ICP, formy prawne, eksport.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestIcpFlagsAndLegalForms:
    # >>> OPIS FUNKCJI: funkcja TestIcpFlagsAndLegalForms.test_named_chain_means_segments_not_aldi
    # Test: wymagany 'chain' to segmenty (ftl), nie Aldi; REQUIRE_NAMED_RETAIL_CHAIN i REQUIRE_SMALL_FIRM są włączone.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_named_chain_means_segments_not_aldi(self):
        assert scraper.REQUIRE_NAMED_RETAIL_CHAIN is True
        assert scraper.REQUIRE_SMALL_FIRM is True
        text = "Firma spedycyjna FTL LTL Europa flota trasy"
        chains = scraper.detect_retail_chains_in_text(text)
        assert "ftl" in chains
        assert "aldi" not in chains

    # >>> OPIS FUNKCJI: funkcja TestIcpFlagsAndLegalForms.test_company_legal_form_pl
    # Test: formy Sp. z o.o., S.A. i GmbH są rozpoznawane.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_company_legal_form_pl(self):
        assert scraper._company_name_has_legal_form("Trans Spedycja Sp. z o.o.")
        assert scraper._company_name_has_legal_form("Logistyka Polska S.A.")
        assert scraper._company_name_has_legal_form("Kultbau GmbH")

    # >>> OPIS FUNKCJI: funkcja TestIcpFlagsAndLegalForms.test_page_mentions_ftl_ok_ladenbau_rejected
    # Test: tekst o FTL przechodzi bramkę, a tekst o ladenbau jest odrzucany.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_page_mentions_ftl_ok_ladenbau_rejected(self):
        ok, chains, _ = scraper.page_mentions_retail_store_projects(
            "Firma spedycyjna. Transport drogowy FTL LTL Europa. Realizacje, flota."
        )
        assert ok
        assert "ftl" in chains
        bad, _, _ = scraper.page_mentions_retail_store_projects(
            "Ladenbau Filialbau Neubau Gewerbe bez spedycji"
        )
        assert not bad

    # >>> OPIS FUNKCJI: funkcja TestIcpFlagsAndLegalForms.test_excel_export_row_pl_columns
    # Test: build_export_rows tworzy wiersz z kolumnami PL (Województwo, Segmenty/Spedycja) i poprawnym e-mailem.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_excel_export_row_pl_columns(self):
        rows = scraper.build_export_rows(
            [
                {
                    "nazwa": "Trans Spedycja Sp. z o.o.",
                    "company_name_clean": "Trans Spedycja Sp. z o.o.",
                    "url": "https://trans-spedycja.pl",
                    "www": "https://trans-spedycja.pl",
                    "email_target": "biuro@trans-spedycja.pl",
                    "telefon": "+48 71 123 45 67",
                    "retail_verified": True,
                    "is_gu": True,
                    "is_small_firm": True,
                    "gu_marker": "spedycja",
                    "bundesland": "Dolnoslaskie",
                    "page_snippet": "Firma spedycyjna FTL LTL",
                    "retail_chains_found": "ftl, ltl",
                }
            ]
        )
        assert len(rows) == 1
        row = rows[0]
        assert "Województwo" in row
        assert "Segmenty" in row or "Spedycja" in row
        assert row.get("E-mail") == "biuro@trans-spedycja.pl"
        assert scraper._excel_phone_ok(row.get("Telefon"))


# >>> OPIS FUNKCJI: klasa TestApplyGuExtrasIcpFromJson
# Grupa testów: flagi ICP z JSON.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestApplyGuExtrasIcpFromJson:
    # >>> OPIS FUNKCJI: funkcja TestApplyGuExtrasIcpFromJson.test_extras_toggle_small_firm_off
    # Test: apply_gu_run_config_extras wyłącza REQUIRE_NAMED_RETAIL_CHAIN i REQUIRE_SMALL_FIRM wg JSON.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: modyfikuje atrapę modułu (SimpleNamespace). Błędy: AssertionError przy niespełnionej asercji.
    def test_extras_toggle_small_firm_off(self):
        mod = SimpleNamespace(
            REQUIRE_NAMED_RETAIL_CHAIN=True,
            REQUIRE_SMALL_FIRM=True,
            REQUIRE_WEBSITE_RETAIL_VERIFICATION=True,
            _pl_spedycja_filter=None,
        )
        scraper.apply_gu_run_config_extras(
            mod,
            {
                "require_named_retail_chain": False,
                "require_small_firm": False,
            },
        )
        assert mod.REQUIRE_NAMED_RETAIL_CHAIN is False
        assert mod.REQUIRE_SMALL_FIRM is False


# >>> OPIS FUNKCJI: klasa TestGeoPlFas
# Grupa testów: geo dla Polski.
# Klasa nie ma stanu współdzielonego poza tym, co opisano przy poszczególnych testach; testy są niezależne.
class TestGeoPlFas:
    # >>> OPIS FUNKCJI: funkcja TestGeoPlFas.test_center_and_bbox_are_poland
    # Test: środek regionu i bbox leżą w Polsce; aliasy DE bbox wskazują na PL.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_center_and_bbox_are_poland(self):
        assert 49.0 <= scraper.REGION_CENTER_LAT <= 55.0
        assert 14.0 <= scraper.REGION_CENTER_LON <= 25.0
        assert scraper._coords_in_pl_bbox(
            scraper.REGION_CENTER_LAT, scraper.REGION_CENTER_LON
        )
        assert scraper.PL_BBOX_LAT_MIN == scraper.DE_DE_BBOX_LAT_MIN

    # >>> OPIS FUNKCJI: funkcja TestGeoPlFas.test_foreign_tld_excludes_de_keeps_pl
    # Test: .de jest zagraniczną domeną, .pl nie.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_foreign_tld_excludes_de_keeps_pl(self):
        assert ".pl" not in scraper._FOREIGN_TLD_SUFFIXES
        assert ".de" in scraper._FOREIGN_TLD_SUFFIXES

    # >>> OPIS FUNKCJI: funkcja TestGeoPlFas.test_poland_candidate_accepts_pl_rejects_de
    # Test: is_poland_pl_candidate akceptuje .pl, odrzuca .de; alias is_germany_de_candidate jest tą samą funkcją.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_poland_candidate_accepts_pl_rejects_de(self):
        assert scraper.is_poland_pl_candidate(
            "https://trans-spedycja.pl/oferta", "Spedycja FTL", "Głogów"
        )
        assert not scraper.is_poland_pl_candidate(
            "https://mueller-bau.de/kontakt", "GmbH", "München Bayern"
        )
        assert scraper.is_poland_pl_candidate is scraper.is_germany_de_candidate

    # >>> OPIS FUNKCJI: funkcja TestGeoPlFas.test_no_mfg_inquiry_import
    # Test: moduł nie eksportuje już legacy FIXED_GU_INQUIRY_DE.
    # Parametry: self. Zwraca: None (wynik = przejście lub błąd testu).
    # Efekty uboczne: brak (czysta logika w pamięci). Błędy: AssertionError przy niespełnionej asercji.
    def test_no_mfg_inquiry_import(self):
        assert not hasattr(scraper, "FIXED_GU_INQUIRY_DE")

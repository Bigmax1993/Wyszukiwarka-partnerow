# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Moduł (ARCHIWUM): mfg_gu_inquiry_email_de — historyczny, stały tekst maila MFG po niemiecku.
#
# CO ROBI: udostępnia jedną funkcję zwracającą nieedytowalny tekst zapytania ofertowego z dawnej
#   kampanii DE GU / Filialbau (firma MFG, sieci ALDI/REWE/…).
# ROLA W PIPELINE: żadna — plik archiwalny, nieużywany przez pl_fas_spedycja_scraper. Kanoniczny outreach
#   PL to fas_spedycja_inquiry_email_pl.py w katalogu głównym repozytorium.
# ZALEŻNOŚCI: brak importów. WEJŚCIE: brak. WYJŚCIE: str z treścią maila.
# ============================================================
"""
ARCHIWUM — stały tekst maila MFG (kampanie DE GU / Filialbau).

Nie używany przez ``pl_fas_spedycja_scraper`` / PL FAS.
Kanoniczny outreach: ``fas_spedycja_inquiry_email_pl.py`` (root repo).

Nie modyfikować przez LLM ani szablony GUI — wyłącznie ten blok (historyczny).
"""


# >>> OPIS FUNKCJI: funkcja build_fixed_gu_inquiry_de
# Cel: zwrócić stały, historyczny tekst maila MFG (DE) — bez LLM i bez parametrów.
# Parametry: brak. Zwraca: str (wieloliniowy tekst po niemiecku). Efekty uboczne: brak. Błędy: brak.
# Uwaga: treści nie modyfikować (archiwum); nie używać w kampanii PL.
def build_fixed_gu_inquiry_de() -> str:
    """Zwróć stały (historyczny) tekst maila MFG DE — bez LLM."""
    return """Sehr geehrte Damen und Herren,

ich wende mich im Namen der Firma MFG Moderner Fliesenboden GmbH an Sie. Wir sind ein spezialisiertes Bodenlegerunternehmen, dessen Schwerpunkt die Realisierung von Einzelhandelsobjekten liegt.

Unser Fokus liegt ausschließlich auf dem professionellen und termingerechten Ausbau von Fußböden (Estrich- und Rüttelboden-/Fliesenarbeiten) für namhafte Handelsketten wie ALDI, REWE, NETTO, PENNY und EDEKA. Durch unsere Spezialisierung sind uns die strengen technischen Vorgaben, Qualitätsstandards und die extremen zeitlichen Anforderungen bei der Errichtung oder Modernisierung von Lebensmittelmärkten bestens vertraut.

Dank unserer erfahrenen Kolonnen und der passenden maschinellen Ausstattung sind wir in der Lage, auch ambitionierte Bauzeitenpläne reibungslos und in höchster Qualität einzuhalten.

Gerne würden wir uns an Ihren aktuellen oder zukünftigen Ausschreibungen in diesem Segment beteiligen. Wir freuen uns über die Zusendung entsprechender Leistungsverzeichnisse oder über die Nennung des zuständigen Ansprechpartners in Ihrer Kalkulations- oder Einkaufsabteilung.

Im Anhang finden Sie unsere aktuelle Referenzliste für den Bereich Lebensmitteleinzelhandel.

Für Rückfragen stehe ich Ihnen jederzeit gerne zur Verfügung.

Mit freundlichen Grüßen

Maksym Swinczak

MFG Moderner Fliesenboden GmbH

https://www.mfg-fliesen.de/

Tel.: +49 1522 3655 399"""


FIXED_GU_INQUIRY_DE = build_fixed_gu_inquiry_de()

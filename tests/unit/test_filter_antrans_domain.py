# Test: antrans.eu nie jest mylone z giełdą trans.eu.
from __future__ import annotations

from pl_spedycja_filter import (
    _HARD_REJECT_DOMAIN_MARKERS,
    _url_has_domain_marker,
    reject_reason,
)


def test_antrans_eu_not_hard_reject_trans_eu():
    assert _url_has_domain_marker("https://antrans.eu/", _HARD_REJECT_DOMAIN_MARKERS) is False
    assert _url_has_domain_marker("https://www.antrans.eu", _HARD_REJECT_DOMAIN_MARKERS) is False
    assert _url_has_domain_marker("https://login.trans.eu/", _HARD_REJECT_DOMAIN_MARKERS) is True
    assert (
        reject_reason(
            email="antrans@antrans.eu",
            url="https://antrans.eu/",
            name="Antrans Sp. z o.o. Sp. k.",
            text="spedycja FTL LTL transport międzynarodowy",
        )
        is None
    )

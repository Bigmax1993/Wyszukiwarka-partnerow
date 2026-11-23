# -*- coding: utf-8 -*-
"""
Shim legacy: ``mfg_mail_recipients`` → ``pl_fas_mail_recipients``.

``office@mfg-fliesen.de`` odpięte. Cc biura = ``FAS_OFFICE_CC_EMAIL``
(``svinchak1993@gmail.com``).

Nowy kod::

  from pl_fas_mail_recipients import merge_fas_campaign_cc, FAS_OFFICE_CC_EMAIL
"""
from __future__ import annotations

from pl_fas_mail_recipients import (  # noqa: F401
    FAS_OFFICE_CC_EMAIL,
    merge_fas_campaign_cc,
    merge_mfg_campaign_cc,
)

# Legacy nazwa stałej — wskazuje na skrzynkę FAS, nie MFG.
MFG_OFFICE_CC_EMAIL = FAS_OFFICE_CC_EMAIL

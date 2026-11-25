# -*- coding: utf-8 -*-
# >>> OPIS MODULU ========================================
# Moduł: campaign_data_paths — cienki SHIM zgodności wstecznej (legacy).
#
# CO ROBI
#   Nie zawiera własnej logiki. Re-eksportuje cały publiczny interfejs z pl_spedycja_data_paths
#   (campaign_output_paths, resolve_data_root, wyniki_dir, wyslane_dir, ensure_data_dirs,
#   apply_data_root_to_env, debug_data_paths, aliasy GOOGLE_DRIVE_GU_* i _cli_debug), aby stare
#   importy `from campaign_data_paths import ...` działały po przejściu kampanii z GU na PL FAS.
#
# ROLA W PIPELINE: warstwa kompatybilności — realne ścieżki Wyniki/, cache, Excel i log są
#   wyliczane w pl_spedycja_data_paths.
#
# ZALEŻNOŚCI: pl_spedycja_data_paths. Funkcji własnych brak.
# URUCHOMIENIE: `python campaign_data_paths.py .` deleguje do _cli_debug() (JSON na stdout) i kończy
#   proces kodem zwróconym przez tę funkcję (SystemExit).
# ============================================================
"""
Shim legacy: ``campaign_data_paths`` → ``pl_spedycja_data_paths``.

=============================================================================
PO CO TEN PLIK
=============================================================================
Nie zawiera własnej logiki ścieżek. Re-exportuje publiczne API z
``pl_spedycja_data_paths``, żeby stare importy nadal działały::

  from campaign_data_paths import campaign_output_paths
  from campaign_data_paths import GOOGLE_DRIVE_GU_FOLDER_ID  # alias legacy

Nowy kod powinien importować bezpośrednio::

  from pl_spedycja_data_paths import campaign_output_paths
  from pl_spedycja_data_paths import GOOGLE_DRIVE_FAS_FOLDER_ID

CLI (debug ścieżek Wyniki/) — ten sam ``_cli_debug`` co kanoniczny moduł::

  python campaign_data_paths.py .
  # równoważne:
  python pl_spedycja_data_paths.py .
"""
from __future__ import annotations

from pl_spedycja_data_paths import *  # noqa: F403
from pl_spedycja_data_paths import (  # noqa: F401
    GOOGLE_DRIVE_FAS_FOLDER_ID,
    GOOGLE_DRIVE_FAS_FOLDER_URL,
    GOOGLE_DRIVE_GU_FOLDER_ID,
    GOOGLE_DRIVE_GU_FOLDER_URL,
    _cli_debug,
    apply_data_root_to_env,
    campaign_output_paths,
    debug_data_paths,
    ensure_data_dirs,
    resolve_data_root,
    wyniki_dir,
    wyslane_dir,
)

if __name__ == "__main__":
    # Pełna delegacja do debug CLI w pl_spedycja_data_paths (JSON na stdout).
    raise SystemExit(_cli_debug())

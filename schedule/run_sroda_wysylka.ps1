# =============================================================================
# PO CO: [Legacy] wysyłka w środę — zastąpione: partia 1 pon, partia 2 wt.
# Preferuj: run_poniedzialek_send.ps1 / run_wtorek.ps1 — plan: PLAN_5_DNI.md.
# =============================================================================

. "$PSScriptRoot\_common.ps1"
Write-Warning "run_sroda_wysylka.ps1 jest legacy — uzyj run_poniedzialek_send.ps1 i run_wtorek.ps1."
& (Join-Path $PSScriptRoot "run_wtorek.ps1") @args

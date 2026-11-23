# =============================================================================
# PO CO: [Legacy] przekierowanie na run_poniedzialek_send.ps1 (B2B zwykle OFF).
# Preferuj: run_poniedzialek_send.ps1 / run_wtorek.ps1 — plan: PLAN_5_DNI.md.
# =============================================================================

. "$PSScriptRoot\_common.ps1"
Write-Warning "run_piatek.ps1 jest legacy — uzyj run_poniedzialek_send.ps1 i run_wtorek.ps1."
& (Join-Path $PSScriptRoot "run_poniedzialek_send.ps1") @args

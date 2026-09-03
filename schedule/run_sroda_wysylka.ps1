# [Legacy] Wysylka w srode — zastapione: partia 1 pon, partia 2 wt.
# DISABLED by default via run_wtorek.ps1 (DISABLE_CONTRACTOR_EMAILS).

. "$PSScriptRoot\_common.ps1"
Write-Warning "run_sroda_wysylka.ps1 jest legacy — uzyj run_poniedzialek_send.ps1 i run_wtorek.ps1."
& (Join-Path $PSScriptRoot "run_wtorek.ps1") @args

# [Legacy] Przekierowanie na run_poniedzialek_send.ps1.
# DISABLED by default via run_poniedzialek_send.ps1 (DISABLE_CONTRACTOR_EMAILS).

. "$PSScriptRoot\_common.ps1"
Write-Warning "run_piatek.ps1 jest legacy — uzyj run_poniedzialek_send.ps1 i run_wtorek.ps1."
& (Join-Path $PSScriptRoot "run_poniedzialek_send.ps1") @args

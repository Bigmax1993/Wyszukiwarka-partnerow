# [Legacy] Przekierowanie na run_piatek_discovery.ps1 (piatek 20:00).

. "$PSScriptRoot\_common.ps1"
Write-Warning "run_sroda.ps1 jest legacy — uzyj run_piatek_discovery.ps1 (piatek 20:00)."
& (Join-Path $PSScriptRoot "run_piatek_discovery.ps1") @args

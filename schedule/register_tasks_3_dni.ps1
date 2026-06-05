# [Legacy] Plan 3 dni — przekierowanie na register_tasks_5_dni.ps1

param(
    [switch]$Unregister
)

Write-Warning "register_tasks_3_dni.ps1 jest legacy — uruchamiam register_tasks_5_dni.ps1"
& (Join-Path $PSScriptRoot "register_tasks_5_dni.ps1") @PSBoundParameters
exit $LASTEXITCODE

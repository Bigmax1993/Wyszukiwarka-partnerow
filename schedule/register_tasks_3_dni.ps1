# Wrapper — rejestracja zadan tygodniowych (bez wysylki maili).
# Szczegoly: scripts/register_gu_weekly_tasks.cmd

param(
    [switch]$Unregister
)

if ($Unregister) {
    foreach ($name in @(
            "Kanbud_GU_Sobota_Discovery",
            "Kanbud_GU_Niedziela_Backfill",
            "Kanbud_GU_Poniedzialek_Prep",
            "Kanbud_GU_Poniedzialek_Send",
            "Kanbud_GU_Wtorek_Send"
        )) {
        schtasks /Delete /F /TN $name 2>$null
        Write-Host "Usunieto (jesli istnialo): $name"
    }
    exit 0
}

$cmd = Join-Path (Split-Path $PSScriptRoot -Parent) "scripts\register_gu_weekly_tasks.cmd"
& $cmd
exit $LASTEXITCODE

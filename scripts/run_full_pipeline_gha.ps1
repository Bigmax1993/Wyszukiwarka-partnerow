#Requires -Version 5.1
<#
Uruchamia pipeline GU na GitHub Actions (recznie, krok po kroku).

Pipeline: discovery -> backfill -> prep -> Excel (bez wysylki maili, bez Google Drive).

  powershell -ExecutionPolicy Bypass -File scripts\run_full_pipeline_gha.ps1

Opcje:
  -SkipDiscovery   zacznij od backfill (jesli discovery juz bylo)
#>
param(
    [switch]$SkipDiscovery
)

$ErrorActionPreference = "Stop"
$Repo = "Bigmax1993/Wyszukiwarka-partnerow"

function Invoke-GhaWorkflow {
    param(
        [string]$Name,
        [hashtable]$Fields = @{}
    )
    Write-Host ""
    Write-Host "=== $Name ===" -ForegroundColor Cyan
    if ($Fields.Count -gt 0) {
        $wfArgs = @()
        foreach ($k in $Fields.Keys) {
            $wfArgs += "-f"
            $wfArgs += "${k}=$($Fields[$k])"
        }
        gh workflow run $Name -R $Repo @wfArgs
    } else {
        gh workflow run $Name -R $Repo
    }
    Start-Sleep -Seconds 12
    $runId = gh run list -R $Repo --workflow=$Name -L 1 --json databaseId -q ".[0].databaseId"
    if (-not $runId) { throw "Brak run ID dla $Name" }
    Write-Host "URL: https://github.com/$Repo/actions/runs/$runId"
    gh run watch $runId -R $Repo --exit-status
    if ($LASTEXITCODE -ne 0) {
        throw "Workflow $Name nie powiodl sie (run $runId)"
    }
    Write-Host "OK: $Name" -ForegroundColor Green
}

if (-not $SkipDiscovery) {
    Invoke-GhaWorkflow "GU sobota discovery"
}
Invoke-GhaWorkflow "GU niedziela backfill"
Invoke-GhaWorkflow "GU poniedzialek excel email" @{ dry_run = "true" }
Invoke-GhaWorkflow "GU poniedzialek prep"

Write-Host ""
Write-Host "Pipeline zakonczony (Excel w artefakcie de-gu-wyniki-mon)." -ForegroundColor Green
Write-Host "Raport Gmail (pon 04:30) jest w cronie; powyzszy krok excel email to dry-run test." -ForegroundColor Yellow
Write-Host "Kampania MFG i sync Google Drive sa poza automatycznym pipeline." -ForegroundColor Yellow

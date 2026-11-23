# =============================================================================
# PO CO: [Legacy] jednorazowy discovery — preferuj plan 5 dni (PLAN_5_DNI.md)
# albo ręcznie: python pl_fas_spedycja_scraper.py --rotate-bundesland.
# Hardcoded ścieżki pod stare środowisko PC; nie używaj w GHA.
# =============================================================================

$ErrorActionPreference = "Stop"
$Automatyczna = "C:\Users\kanbu\Documents\Automatyczna wyszukiwarka piasku i wysylka zapytania"
$Campaign = Join-Path $Automatyczna "Gu Baunterhnehmen"

$env:KANBUD_PROJECT_ROOT = "$env:USERPROFILE\Documents\piasek Gdansk"
$env:DISABLE_SEND_WINDOW = "1"
$env:SCRAPER_TIMEZONE = "Europe/Warsaw"

# Opcjonalnie: załaduj .env z piasek Gdansk (jeśli masz lokalny plik)
$dotenv = Join-Path $env:KANBUD_PROJECT_ROOT ".env"
if (Test-Path $dotenv) {
    Get-Content $dotenv | ForEach-Object {
        if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
        $n, $v = $_ -split '=', 2
        Set-Item -Path "Env:$($n.Trim())" -Value $v.Trim().Trim('"')
    }
}

Set-Location $Campaign
python pl_fas_spedycja_scraper.py --rotate-bundesland @args

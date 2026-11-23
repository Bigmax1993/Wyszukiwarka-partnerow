# =============================================================================
# PO CO: wspólne helpery Task Scheduler PC — kampania PL FAS / spedycja.
# Plan: schedule/PLAN_5_DNI.md (pon–pt discovery, nd backfill; B2B OFF).
# Kanoniczny run_config: run_config\pl_fas_spedycja.json (16 województw).
# =============================================================================

$ErrorActionPreference = "Stop"
$script:RepoRoot = Split-Path $PSScriptRoot -Parent

# Katalog kampanii (root repo). Kanoniczna nazwa FAS; alias GU poniżej.
$script:FasCampaignDir = $script:RepoRoot
$script:GuCampaignDir = $script:FasCampaignDir  # alias legacy

$script:DefaultRunConfig = "run_config\pl_fas_spedycja.json"

function Import-KanbudDotEnv {
    # Ładuje pierwsze znalezione .env (libs lub root repo) do procesu PowerShell.
    $libs = if ($env:KANBUD_PROJECT_ROOT) { $env:KANBUD_PROJECT_ROOT } else { Join-Path $RepoRoot "libs" }
    $env:KANBUD_PROJECT_ROOT = $libs
    foreach ($dotenv in @((Join-Path $libs ".env"), (Join-Path $RepoRoot ".env"))) {
        if (-not (Test-Path $dotenv)) { continue }
        Get-Content $dotenv | ForEach-Object {
            if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
            $n, $v = $_ -split '=', 2
            Set-Item -Path "Env:$($n.Trim())" -Value $v.Trim().Trim('"')
        }
        break
    }
}

function Set-KanbudGoogleDriveDataDir {
    # Przy DISABLE_GOOGLE_DRIVE=1 (domyślnie) nie mapuj wyników na folder Drive.
    # Uwaga: Python ``pl_spedycja_data_paths.resolve_data_root`` i tak ignoruje
    # KANBUD_GOOGLE_DRIVE_* przy cache/log — to tylko opcjonalny lokalny override
    # gdy ktoś świadomie wyłączy kill-switch Drive na PC.
    $driveFlag = if ($null -ne $env:DISABLE_GOOGLE_DRIVE -and $env:DISABLE_GOOGLE_DRIVE -ne "") {
        $env:DISABLE_GOOGLE_DRIVE
    } else { "1" }
    if ($driveFlag -notin @("0", "false", "False", "no", "off", "OFF")) {
        return
    }
    if ($env:KANBUD_DATA_DIR -or $env:KANBUD_GOOGLE_DRIVE_FAS_PATH -or $env:KANBUD_GOOGLE_DRIVE_GU_PATH) {
        return
    }
    $names = @("PL Spedycja Wyniki", "pl_spedycja_wyniki", "FAS Spedycja Wyniki")
    $bases = @(
        "G:\My Drive",
        (Join-Path $env:USERPROFILE "Google Drive\My Drive"),
        (Join-Path $env:USERPROFILE "Google Drive")
    )
    foreach ($base in $bases) {
        if (-not (Test-Path $base)) { continue }
        foreach ($name in $names) {
            $p = Join-Path $base $name
            if (Test-Path $p) {
                $env:KANBUD_GOOGLE_DRIVE_FAS_PATH = $p
                $env:KANBUD_GOOGLE_DRIVE_GU_PATH = $p  # alias legacy
                $env:KANBUD_DATA_DIR = $p
                return
            }
        }
    }
}

function Enter-FasCampaign {
    # Wejście w katalog kampanii PL FAS + .env + opcjonalny data dir.
    Import-KanbudDotEnv
    Set-KanbudGoogleDriveDataDir
    Set-Location $FasCampaignDir
}

# Alias legacy (stare skrypty wołały Enter-GuCampaign).
function Enter-GuCampaign {
    Enter-FasCampaign
}

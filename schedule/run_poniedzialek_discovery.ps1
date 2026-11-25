# =============================================================================
# PO CO: poniedziałek — discovery część 1 (Serper + www), bez wysyłki B2B.
# Plan: schedule/PLAN_5_DNI.md — cała Polska / 16 województw (serper-only).
# Task Scheduler: Spedycja_FAS_Poniedzialek_Discovery → pon 18:00 (Europe/Warsaw).
# =============================================================================

. "$PSScriptRoot\_common.ps1"
Enter-FasCampaign

$env:SCRAPER_TIMEZONE = "Europe/Warsaw"
$env:SCRAPER_MAX_RUNTIME_SECONDS = "21600"   # 6h: start 07:00 → stop ~13:00
Remove-Item Env:DISABLE_SEND_WINDOW -ErrorAction SilentlyContinue
Remove-Item Env:SCRAPER_IGNORE_SEND_WINDOW -ErrorAction SilentlyContinue
Remove-Item Env:DISABLE_SEND_WINDOW -ErrorAction SilentlyContinue
Remove-Item Env:SCRAPER_IGNORE_SEND_WINDOW -ErrorAction SilentlyContinue

if ($args.Count -gt 0 -and $args[0] -like "run_config\*") {
    $config = $args[0]
    $rest = @($args | Select-Object -Skip 1)
    Write-Host "[PONIEDZIALEK] Discovery (reczny run_config): $config"
    python pl_fas_spedycja_scraper.py --run-config $config @rest
} else {
    Write-Host "[PONIEDZIALEK] Discovery czesc 1: cala Polska (serper-only, 16 wojewodztw)"
    python pl_fas_spedycja_scraper.py --run-config run_config\pl_fas_spedycja.json --serper-only-discovery --no-auto-email @args
}

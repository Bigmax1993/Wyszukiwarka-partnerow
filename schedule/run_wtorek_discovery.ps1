# =============================================================================
# PO CO: wtorek — discovery część 2 (kontynuacja cache), bez wysyłki B2B.
# Plan: schedule/PLAN_5_DNI.md
# Task Scheduler: Spedycja_FAS_Wtorek_Discovery → wt 18:00 (Europe/Warsaw).
# =============================================================================

. "$PSScriptRoot\_common.ps1"
Enter-FasCampaign

$env:SCRAPER_TIMEZONE = "Europe/Warsaw"
Remove-Item Env:DISABLE_SEND_WINDOW -ErrorAction SilentlyContinue
Remove-Item Env:SCRAPER_IGNORE_SEND_WINDOW -ErrorAction SilentlyContinue

if ($args.Count -gt 0 -and $args[0] -like "run_config\*") {
    $config = $args[0]
    $rest = @($args | Select-Object -Skip 1)
    Write-Host "[WTOREK] Discovery (reczny run_config): $config"
    python pl_fas_spedycja_scraper.py --run-config $config @rest
} else {
    Write-Host "[WTOREK] Discovery czesc 2: kontynuacja (--respect-cache)"
    python pl_fas_spedycja_scraper.py --run-config run_config\pl_fas_spedycja.json --serper-only-discovery --no-auto-email --respect-cache @args
}

# PONIEDZIALEK — wysylka partia 1 (okno 8-18 wg Europe/Berlin, limit 300/dzien).
# Task Scheduler: poniedzialek 09:00 (po prep 07:00)
# DISABLED by default: DISABLE_CONTRACTOR_EMAILS=1 → NO-OP (exit 0).

. "$PSScriptRoot\_common.ps1"
Enter-GuCampaign

$flag = if ($null -ne $env:DISABLE_CONTRACTOR_EMAILS -and $env:DISABLE_CONTRACTOR_EMAILS -ne "") {
    $env:DISABLE_CONTRACTOR_EMAILS
} else { "1" }
if ($flag -notin @("0", "false", "False", "no", "off", "OFF")) {
    Write-Host "[NO-OP] Wysylka kontrahentow wylaczona (DISABLE_CONTRACTOR_EMAILS=$flag). Exit 0." -ForegroundColor Yellow
    exit 0
}

$env:SCRAPER_TIMEZONE = "Europe/Berlin"
Remove-Item Env:DISABLE_SEND_WINDOW -ErrorAction SilentlyContinue
Remove-Item Env:SEND_WINDOW_START_HOUR -ErrorAction SilentlyContinue
Remove-Item Env:SEND_WINDOW_END_HOUR -ErrorAction SilentlyContinue

Write-Host "[PONIEDZIALEK] Wysylka maili partia 1 (--send-emails-only, okno 8-18 Berlin)..."
python de_gu_bauunternehmen_scraper.py --send-emails-only @args

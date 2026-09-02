# PONIEDZIALEK — wysylka Excela GU na Gmail (04:30).
# Task Scheduler / GitHub Actions: poniedzialek 04:30

. "$PSScriptRoot\_common.ps1"
Enter-GuCampaign

$env:SCRAPER_TIMEZONE = "Europe/Warsaw"

Write-Host "[PONIEDZIALEK 04:30] Wysylka Excel GU na Gmail..."
python scripts/send_excel_gmail.py @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

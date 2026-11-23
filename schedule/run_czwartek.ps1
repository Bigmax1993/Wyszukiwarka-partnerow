# =============================================================================
# PO CO: niedziela — backfill e-maili + rebuild Excela (bez Serpera, bez B2B).
# Plan: schedule/PLAN_5_DNI.md (skrypt historycznie „czwartek”, cron = nd).
# Task Scheduler: Spedycja_FAS_Niedziela_Backfill → nd 06:00 (Europe/Warsaw).
# Jeśli pt nie skończył discovery — najpierw run_piatek_discovery.ps1.
# =============================================================================

. "$PSScriptRoot\_common.ps1"
Enter-FasCampaign

$env:SCRAPER_TIMEZONE = "Europe/Warsaw"
Remove-Item Env:DISABLE_SEND_WINDOW -ErrorAction SilentlyContinue

Write-Host "[NIEDZIELA] Weryfikacja www (pending z discovery pon-pt)..."
python pl_fas_spedycja_scraper.py --verify-pending-contacts

Write-Host "[NIEDZIELA] Backfill e-maili z cache..."
python pl_fas_spedycja_scraper.py --backfill-emails-from-cache

Write-Host "[NIEDZIELA] Rebuild Excel z cache..."
python pl_fas_spedycja_scraper.py --rebuild-from-cache

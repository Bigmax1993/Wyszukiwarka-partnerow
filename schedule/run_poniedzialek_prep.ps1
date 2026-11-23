# =============================================================================
# PO CO: poniedziałek — prep (rebuild Excel z cache, bez wysyłki B2B).
# Plan: schedule/PLAN_5_DNI.md — NIE rejestrowane w Task Scheduler (OFF).
# Ręcznie przed ewentualną wysyłką; domyślnie B2B OFF.
# =============================================================================

. "$PSScriptRoot\_common.ps1"
Enter-FasCampaign

$env:SCRAPER_TIMEZONE = "Europe/Warsaw"
Remove-Item Env:DISABLE_SEND_WINDOW -ErrorAction SilentlyContinue

Write-Host "[PONIEDZIALEK] Rebuild Excel z cache (bez wysylki)..."
python pl_fas_spedycja_scraper.py --rebuild-from-cache @args

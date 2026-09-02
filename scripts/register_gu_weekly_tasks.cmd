@echo off
REM Rejestracja zadan tygodniowych GU (sob-nd-pon) — bez wysylki maili.
REM Uruchom jako administrator.

set SCHEDULE=%~dp0..\schedule
set PS=powershell.exe

echo Rejestracja Kanbud_GU_Sobota_Discovery (sob 20:10)...
schtasks /Create /F /TN "Kanbud_GU_Sobota_Discovery" /TR "%PS% -NoProfile -ExecutionPolicy Bypass -File \"%SCHEDULE%\run_sroda.ps1\"" /SC WEEKLY /D SAT /ST 20:10

echo Rejestracja Kanbud_GU_Niedziela_Backfill (nd 06:00)...
schtasks /Create /F /TN "Kanbud_GU_Niedziela_Backfill" /TR "%PS% -NoProfile -ExecutionPolicy Bypass -File \"%SCHEDULE%\run_czwartek.ps1\"" /SC WEEKLY /D SUN /ST 06:00

echo Rejestracja Kanbud_GU_Poniedzialek_Prep (pon 08:00)...
schtasks /Create /F /TN "Kanbud_GU_Poniedzialek_Prep" /TR "%PS% -NoProfile -ExecutionPolicy Bypass -File \"%SCHEDULE%\run_poniedzialek_prep.ps1\"" /SC WEEKLY /D MON /ST 08:00

echo Rejestracja Kanbud_GU_Poniedzialek_ExcelEmail (pon 04:30)...
schtasks /Create /F /TN "Kanbud_GU_Poniedzialek_ExcelEmail" /TR "%PS% -NoProfile -ExecutionPolicy Bypass -File \"%SCHEDULE%\run_poniedzialek_excel_email.ps1\"" /SC WEEKLY /D MON /ST 04:30

echo.
echo Usuwanie legacy zadan wysylki (jesli istnieja)...
for %%T in (Kanbud_GU_Poniedzialek_Send Kanbud_GU_Wtorek_Send) do schtasks /Delete /F /TN "%%T" 2>nul

echo Gotowe. Plan: sob discovery ^| nd backfill ^| pon 04:30 Excel Gmail ^| pon 08:00 prep

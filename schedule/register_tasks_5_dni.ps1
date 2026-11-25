# =============================================================================
# PO CO: rejestracja zadań Harmonogramu Windows — PL FAS lokalnie.
# Plan: pon–pt 07:00 discovery | nd 06:00 backfill | pon/wt 09:00 B2B send.
# Nazwy tasków: Spedycja_FAS_* (kanoniczne). Przy rejestracji / -Unregister
# usuwane są też stare Kanbud_GU_* (oraz wyłączone prep/legacy send).
# Uruchom PowerShell jako administrator.
# Nie zmienia run_config\pl_fas_spedycja.json.
# =============================================================================

param(
    [switch]$Unregister
)

$ScheduleDir = $PSScriptRoot
$Pwsh = (Get-Command powershell.exe).Source

function Register-WeekdayTask {
    param(
        [string]$Name,
        [string]$Script,
        [string]$Weekday,
        [string]$Time
    )
    $action = New-ScheduledTaskAction -Execute $Pwsh -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Script`""`
    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Weekday -At $Time
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    Register-ScheduledTask -TaskName $Name -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
    Write-Host "OK: $Name -> $Weekday $Time"
}

# Discovery lokalnie 07:00 (okno 7–13 via SCRAPER_MAX_RUNTIME) + reszta jak GHA.
$tasks = @(
    @{ Name = "Spedycja_FAS_Poniedzialek_Discovery"; Script = Join-Path $ScheduleDir "run_poniedzialek_discovery.ps1"; Day = "Monday"; Time = "07:00" }
    @{ Name = "Spedycja_FAS_Wtorek_Discovery"; Script = Join-Path $ScheduleDir "run_wtorek_discovery.ps1"; Day = "Tuesday"; Time = "07:00" }
    @{ Name = "Spedycja_FAS_Sroda_Discovery"; Script = Join-Path $ScheduleDir "run_sroda_discovery.ps1"; Day = "Wednesday"; Time = "07:00" }
    @{ Name = "Spedycja_FAS_Czwartek_Discovery"; Script = Join-Path $ScheduleDir "run_czwartek_discovery.ps1"; Day = "Thursday"; Time = "07:00" }
    @{ Name = "Spedycja_FAS_Piatek_Discovery"; Script = Join-Path $ScheduleDir "run_piatek_discovery.ps1"; Day = "Friday"; Time = "07:00" }
    @{ Name = "Spedycja_FAS_Niedziela_Backfill"; Script = Join-Path $ScheduleDir "run_czwartek.ps1"; Day = "Sunday"; Time = "06:00" }
    @{ Name = "Spedycja_FAS_Poniedzialek_Send"; Script = Join-Path $ScheduleDir "run_poniedzialek_send.ps1"; Day = "Monday"; Time = "09:00" }
    @{ Name = "Spedycja_FAS_Wtorek_Send"; Script = Join-Path $ScheduleDir "run_wtorek.ps1"; Day = "Tuesday"; Time = "09:00" }
)

# Stare nazwy Kanbud_GU_* (aktywne + wyłączone prep/send) — zawsze sprzątane.
$legacyKanbudGuTasks = @(
    "Kanbud_GU_Poniedzialek_Discovery",
    "Kanbud_GU_Wtorek_Discovery",
    "Kanbud_GU_Sroda_Discovery",
    "Kanbud_GU_Czwartek_Discovery",
    "Kanbud_GU_Piatek_Discovery",
    "Kanbud_GU_Niedziela_Backfill",
    "Kanbud_GU_Poniedzialek_Prep",
    "Kanbud_GU_Poniedzialek_Send",
    "Kanbud_GU_Wtorek_Send",
    "Kanbud_GU_Piatek_Send",
    "Kanbud_GU_Sroda_Send",
    "Kanbud_GU_Sobota_Discovery",
    "Kanbud_GU_Czwartek_Backfill"
)

# Opcjonalny alias PL (nie rejestrowany; tylko do sprzątania jeśli ktoś ręcznie dodał).
$legacySpedycjaPlTasks = @(
    "Spedycja_PL_Poniedzialek_Discovery",
    "Spedycja_PL_Wtorek_Discovery",
    "Spedycja_PL_Sroda_Discovery",
    "Spedycja_PL_Czwartek_Discovery",
    "Spedycja_PL_Piatek_Discovery",
    "Spedycja_PL_Niedziela_Backfill"
)

# NIE dodawaj tu Poniedzialek_Send / Wtorek_Send — są w $tasks.
$disabledTasks = @(
    "Spedycja_FAS_Poniedzialek_Prep",
    "Spedycja_FAS_Piatek_Send",
    "Spedycja_FAS_Sroda_Send",
    "Spedycja_FAS_Sobota_Discovery",
    "Spedycja_FAS_Czwartek_Backfill"
)

function Unregister-TaskNames {
    param([string[]]$Names, [string]$Label = "")
    foreach ($name in $Names) {
        Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
        if ($Label) {
            Write-Host "Usunieto ($Label): $name"
        } else {
            Write-Host "Usunieto: $name"
        }
    }
}

if ($Unregister) {
    Unregister-TaskNames -Names ($tasks | ForEach-Object { $_.Name })
    Unregister-TaskNames -Names $legacyKanbudGuTasks -Label "legacy Kanbud_GU"
    Unregister-TaskNames -Names $legacySpedycjaPlTasks -Label "legacy Spedycja_PL"
    Unregister-TaskNames -Names $disabledTasks -Label "disabled"
    exit 0
}

foreach ($t in $tasks) {
    Register-WeekdayTask -Name $t.Name -Script $t.Script -Weekday $t.Day -Time $t.Time
}

# Po rejestracji FAS: usuń stare GU / PL aliasy / wyłączone prep-send.
Unregister-TaskNames -Names $legacyKanbudGuTasks -Label "legacy Kanbud_GU"
Unregister-TaskNames -Names $legacySpedycjaPlTasks -Label "legacy Spedycja_PL"
Unregister-TaskNames -Names $disabledTasks -Label "disabled"

Write-Host "Gotowe. Sprawdz taskschd.msc (Spedycja_FAS_*)"
Write-Host "Plan: pon-pt 07:00 discovery | nd 06:00 backfill | pon/wt 09:00 B2B send"
Write-Host "Excel nd 09:00 nadal tylko GHA. Stare Kanbud_GU_* usuniete."

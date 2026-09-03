# Rejestracja zadan Harmonogramu Windows — discovery-only (bez send / Drive / prep).
# Uruchom PowerShell jako administrator.

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

# pon–pt 18:00 discovery + nd 06:00 backfill. Prep/send NIE rejestrowane.
$tasks = @(
    @{ Name = "Kanbud_GU_Poniedzialek_Discovery"; Script = Join-Path $ScheduleDir "run_poniedzialek_discovery.ps1"; Day = "Monday"; Time = "18:00" }
    @{ Name = "Kanbud_GU_Wtorek_Discovery"; Script = Join-Path $ScheduleDir "run_wtorek_discovery.ps1"; Day = "Tuesday"; Time = "18:00" }
    @{ Name = "Kanbud_GU_Sroda_Discovery"; Script = Join-Path $ScheduleDir "run_sroda_discovery.ps1"; Day = "Wednesday"; Time = "18:00" }
    @{ Name = "Kanbud_GU_Czwartek_Discovery"; Script = Join-Path $ScheduleDir "run_czwartek_discovery.ps1"; Day = "Thursday"; Time = "18:00" }
    @{ Name = "Kanbud_GU_Piatek_Discovery"; Script = Join-Path $ScheduleDir "run_piatek_discovery.ps1"; Day = "Friday"; Time = "18:00" }
    @{ Name = "Kanbud_GU_Niedziela_Backfill"; Script = Join-Path $ScheduleDir "run_czwartek.ps1"; Day = "Sunday"; Time = "06:00" }
)

$disabledTasks = @(
    "Kanbud_GU_Poniedzialek_Prep",
    "Kanbud_GU_Poniedzialek_Send",
    "Kanbud_GU_Wtorek_Send",
    "Kanbud_GU_Piatek_Send",
    "Kanbud_GU_Sroda_Send",
    "Kanbud_GU_Sobota_Discovery",
    "Kanbud_GU_Czwartek_Backfill"
)

if ($Unregister) {
    foreach ($t in $tasks) {
        Unregister-ScheduledTask -TaskName $t.Name -Confirm:$false -ErrorAction SilentlyContinue
        Write-Host "Usunieto: $($t.Name)"
    }
    foreach ($legacy in $disabledTasks) {
        Unregister-ScheduledTask -TaskName $legacy -Confirm:$false -ErrorAction SilentlyContinue
        Write-Host "Usunieto (legacy): $legacy"
    }
    exit 0
}

foreach ($t in $tasks) {
    Register-WeekdayTask -Name $t.Name -Script $t.Script -Weekday $t.Day -Time $t.Time
}

foreach ($name in $disabledTasks) {
    Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
}

Write-Host "Gotowe. Sprawdz taskschd.msc (Kanbud_GU_*)"
Write-Host "Plan: pon-pt 18:00 discovery | nd 06:00 backfill | nd 09:00 Excel na Gmail (tylko GHA)"
Write-Host "Prep/send/Drive NIE rejestrowane."

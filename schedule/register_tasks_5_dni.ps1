# Rejestracja zadan Harmonogramu Windows (plan: pon-pt discovery, nd backfill, pon prep+send, wt send).
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

# Discovery + backfill + prep. Taski SEND celowo NIE rejestrowane (discovery-only;
# skrypty send i tak są NO-OP przy DISABLE_CONTRACTOR_EMAILS=1).
$tasks = @(
    @{ Name = "Kanbud_GU_Poniedzialek_Discovery"; Script = Join-Path $ScheduleDir "run_poniedzialek_discovery.ps1"; Day = "Monday"; Time = "17:00" }
    @{ Name = "Kanbud_GU_Wtorek_Discovery"; Script = Join-Path $ScheduleDir "run_wtorek_discovery.ps1"; Day = "Tuesday"; Time = "15:00" }
    @{ Name = "Kanbud_GU_Sroda_Discovery"; Script = Join-Path $ScheduleDir "run_sroda_discovery.ps1"; Day = "Wednesday"; Time = "19:00" }
    @{ Name = "Kanbud_GU_Czwartek_Discovery"; Script = Join-Path $ScheduleDir "run_czwartek_discovery.ps1"; Day = "Thursday"; Time = "20:00" }
    @{ Name = "Kanbud_GU_Piatek_Discovery"; Script = Join-Path $ScheduleDir "run_piatek_discovery.ps1"; Day = "Friday"; Time = "16:00" }
    @{ Name = "Kanbud_GU_Niedziela_Backfill"; Script = Join-Path $ScheduleDir "run_czwartek.ps1"; Day = "Sunday"; Time = "06:00" }
    @{ Name = "Kanbud_GU_Poniedzialek_Prep"; Script = Join-Path $ScheduleDir "run_poniedzialek_prep.ps1"; Day = "Monday"; Time = "07:00" }
)

$disabledSendTasks = @(
    "Kanbud_GU_Poniedzialek_Send",
    "Kanbud_GU_Wtorek_Send",
    "Kanbud_GU_Piatek_Send",
    "Kanbud_GU_Sroda_Send"
)

if ($Unregister) {
    foreach ($t in $tasks) {
        Unregister-ScheduledTask -TaskName $t.Name -Confirm:$false -ErrorAction SilentlyContinue
        Write-Host "Usunieto: $($t.Name)"
    }
    foreach ($legacy in @(
            "Kanbud_GU_Sobota_Discovery",
            "Kanbud_GU_Czwartek_Backfill"
        ) + $disabledSendTasks) {
        Unregister-ScheduledTask -TaskName $legacy -Confirm:$false -ErrorAction SilentlyContinue
        Write-Host "Usunieto (legacy/send): $legacy"
    }
    exit 0
}

foreach ($t in $tasks) {
    Register-WeekdayTask -Name $t.Name -Script $t.Script -Weekday $t.Day -Time $t.Time
}

# Upewnij się, że stare taski send nie wiszą w Harmonogramie.
foreach ($name in $disabledSendTasks) {
    Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
}

Write-Host "Gotowe. Sprawdz taskschd.msc (Kanbud_GU_*)"
Write-Host "Plan discovery-only: pon-pt discovery | nd backfill | pon prep 7 (BEZ send / BEZ Drive)"
Write-Host "Send taski NIE rejestrowane (DISABLE_CONTRACTOR_EMAILS=1). Rollback: ustaw flage=0 i przywroc taski recznie."

#Requires -Version 5.1
<#
Pobiera najnowszy artefakt GU i wgrywa na Google Drive (OAuth lub konto uslugowe).

  powershell -ExecutionPolicy Bypass -File scripts\upload_wyniki_to_drive.ps1

Bez OAuth Desktop JSON otworzy folder na Pulpicie + link do Drive (reczny drag-drop).
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root
$Repo = "Bigmax1993/Wyszukiwarka-partnerow"
$DriveFolder = "1tP8oUi72t4EHDbE9GnHFdvfNtNsJe4xf"

Write-Host "=== Pobieram artefakt de-gu-wyniki-fri z GitHub ===" -ForegroundColor Cyan
$runId = gh run list -R $Repo --workflow="GU wtorek send" -L 1 --json databaseId,conclusion -q '.[0].databaseId'
if (-not $runId) { throw "Brak run GU wtorek send" }
$tmp = Join-Path $env:TEMP "gu-drive-upload"
Remove-Item $tmp -Recurse -Force -EA SilentlyContinue
New-Item -ItemType Directory -Path $tmp | Out-Null
gh run download $runId -R $Repo -n de-gu-wyniki-fri -D $tmp

New-Item -ItemType Directory -Force -Path "$Root\Wyniki" | Out-Null
New-Item -ItemType Directory -Force -Path "$Root\wyslane" | Out-Null
Copy-Item "$tmp\Wyniki\*" "$Root\Wyniki\" -Force
if (Test-Path "$tmp\wyslane") {
    Copy-Item "$tmp\wyslane\*" "$Root\wyslane\" -Recurse -Force
}
Write-Host "OK: Wyniki + wyslane w repo" -ForegroundColor Green

$oauthClient = Join-Path $Root "secrets\gdrive-oauth-client.json"
if (Test-Path $oauthClient) {
    Write-Host "=== Upload przez OAuth ===" -ForegroundColor Cyan
    python -m pip install -q -r requirements-drive.txt
    python scripts\gdrive_oauth_setup.py --client-json $oauthClient 2>$null
    $env:GDRIVE_SERVICE_ACCOUNT_FILE = ""
    python scripts\gdrive_upload_wyniki.py --campaign-dir .
    if ($LASTEXITCODE -eq 0) {
        Write-Host "GOTOWE: https://drive.google.com/drive/folders/$DriveFolder" -ForegroundColor Green
        exit 0
    }
}

$env:GDRIVE_SERVICE_ACCOUNT_FILE = Join-Path $Root "secrets\gdrive-service-account.json"
if (Test-Path $env:GDRIVE_SERVICE_ACCOUNT_FILE) {
    Write-Host "=== Proba uploadu (konto uslugowe) ===" -ForegroundColor Cyan
    python -m pip install -q -r requirements-drive.txt
    python scripts\gdrive_upload_wyniki.py --campaign-dir .
    if ($LASTEXITCODE -eq 0) {
        Write-Host "GOTOWE: https://drive.google.com/drive/folders/$DriveFolder" -ForegroundColor Green
        exit 0
    }
}

$desktop = Join-Path ([Environment]::GetFolderPath("Desktop")) "GU_Wyniki_Niemcy"
Remove-Item $desktop -Recurse -Force -EA SilentlyContinue
New-Item -ItemType Directory -Path "$desktop\Wyniki" -Force | Out-Null
Copy-Item "$Root\Wyniki\*" "$desktop\Wyniki\" -Force
if (Test-Path "$Root\wyslane") {
    Copy-Item "$Root\wyslane" "$desktop\wyslane" -Recurse -Force
}
Write-Host ""
Write-Host "API upload zablokowany (konto uslugowe nie ma quota na Moj dysk)." -ForegroundColor Yellow
Write-Host "Pliki gotowe na Pulpicie: $desktop" -ForegroundColor Green
Write-Host "Otwieram folder Drive - przeciagnij Wyniki + wyslane:" -ForegroundColor Cyan
Start-Process "https://drive.google.com/drive/folders/$DriveFolder"
Start-Process explorer.exe $desktop
Write-Host ""
Write-Host "Trwaly fix: utworz OAuth Desktop w NOWYM projekcie Google Cloud," -ForegroundColor Cyan
Write-Host "zapisz jako secrets\gdrive-oauth-client.json i uruchom:" -ForegroundColor Cyan
Write-Host "  python scripts\gdrive_oauth_setup.py" -ForegroundColor White
exit 2

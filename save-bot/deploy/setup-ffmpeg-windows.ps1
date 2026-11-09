# Windows uchun portativ FFmpeg o'rnatuvchi skript.
# Ishlatish (PowerShell):
#   powershell -ExecutionPolicy Bypass -File C:\save-bot\deploy\setup-ffmpeg-windows.ps1
# Natija: C:\save-bot\tools\ffmpeg\bin\ffmpeg.exe
# Bot bu papkani avtomatik topadi (FFMPEG_LOCATION shart emas).

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$toolsDir = Join-Path $projectRoot "tools"
$targetDir = Join-Path $toolsDir "ffmpeg"
$zipPath = Join-Path $toolsDir "ffmpeg.zip"
$tmpDir = Join-Path $toolsDir "_ffmpeg_tmp"

if (Test-Path (Join-Path $targetDir "bin\ffmpeg.exe")) {
    Write-Host "FFmpeg allaqachon ornatilgan: $targetDir"
    exit 0
}

New-Item -ItemType Directory -Force $toolsDir | Out-Null

Write-Host "FFmpeg yuklanmoqda (~110 MB)..."
curl.exe -L --fail --silent --show-error -o $zipPath `
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
if ($LASTEXITCODE -ne 0) { throw "Yuklab olishda xato: $LASTEXITCODE" }

Write-Host "Arxiv ochilmoqda..."
if (Test-Path $tmpDir) { Remove-Item -Recurse -Force $tmpDir }
Expand-Archive -Path $zipPath -DestinationPath $tmpDir -Force

$inner = Get-ChildItem $tmpDir -Directory | Select-Object -First 1
if (-not $inner) { throw "Arxiv tuzilishi tushunarsiz" }

if (Test-Path $targetDir) { Remove-Item -Recurse -Force $targetDir }
Move-Item $inner.FullName $targetDir
Remove-Item -Recurse -Force $tmpDir, $zipPath

& (Join-Path $targetDir "bin\ffmpeg.exe") -version | Select-Object -First 1
Write-Host ""
Write-Host "Tayyor: $targetDir"
Write-Host "Endi botni qayta ishga tushiring: python C:\save-bot\bot.py"

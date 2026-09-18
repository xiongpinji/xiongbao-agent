# SPDX-License-Identifier: MIT
# Fetch wb-bench-office-v1.0 from HuggingFace into vendor/workbuddy-bench/datasets/
# Dataset stays gitignored; only the extract path is used by llm_lite scoring.
#
# Usage:
#   powershell -File scripts/fetch_office_dataset.ps1
#   powershell -File scripts/fetch_office_dataset.ps1 -Force

param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$DestDir = Join-Path $Root "vendor\workbuddy-bench\datasets"
$ExtractDir = Join-Path $DestDir "wb-bench-office-v1.0"
$TarGz = Join-Path $DestDir "wb-bench-office-v1.0.tar.gz"
$Url = "https://huggingface.co/datasets/tencent/workbuddy-bench/resolve/main/wb-bench-office-v1.0.tar.gz"

New-Item -ItemType Directory -Force -Path $DestDir | Out-Null

if ((Test-Path (Join-Path $ExtractDir "tasks")) -and -not $Force) {
    $n = (Get-ChildItem (Join-Path $ExtractDir "tasks") -Directory).Count
    Write-Host "office dataset already present: $n tasks under $ExtractDir"
    exit 0
}

if ($Force -and (Test-Path $ExtractDir)) {
    Remove-Item -Recurse -Force $ExtractDir
}

Write-Host "Downloading $Url ..."
Invoke-WebRequest -Uri $Url -OutFile $TarGz -UseBasicParsing

Write-Host "Extracting to $DestDir ..."
# Prefer tar (Windows 10+); fall back to .NET if needed
tar -xzf $TarGz -C $DestDir
if (-not (Test-Path (Join-Path $ExtractDir "tasks"))) {
    Write-Error "extract failed: tasks/ missing under $ExtractDir"
    exit 1
}

$n = (Get-ChildItem (Join-Path $ExtractDir "tasks") -Directory).Count
Write-Host "OK: $n office tasks ready at $ExtractDir"
Write-Host "Next: python -S -m octop.contrib.workbuddy.bench.cli --office --live-llm --limit 3 --pass-rate 0.3"

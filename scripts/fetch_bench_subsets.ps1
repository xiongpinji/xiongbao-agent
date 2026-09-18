# SPDX-License-Identifier: MIT
# Fetch Harbor bench subsets from HuggingFace into vendor/workbuddy-bench/datasets/
#
# Usage:
#   powershell -File scripts/fetch_bench_subsets.ps1
#   powershell -File scripts/fetch_bench_subsets.ps1 -Subset office
#   powershell -File scripts/fetch_bench_subsets.ps1 -Subset code,web -Force
#   powershell -File scripts/fetch_bench_subsets.ps1 -ListOnly

param(
    [string]$Subset = "office,code,web,sec",
    [switch]$Force,
    [switch]$ListOnly
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$DestDir = Join-Path $Root "vendor\workbuddy-bench\datasets"
$BaseUrl = "https://huggingface.co/datasets/tencent/workbuddy-bench/resolve/main"

$Map = @{
    office = "wb-bench-office-v1.0"
    code   = "wb-bench-code-v1.0"
    web    = "wb-bench-web-v1.0"
    sec    = "wb-bench-sec-v1.0"
}

New-Item -ItemType Directory -Force -Path $DestDir | Out-Null

function Show-Status {
    foreach ($key in @("office", "code", "web", "sec")) {
        $name = $Map[$key]
        $extract = Join-Path $DestDir $name
        $tasks = Join-Path $extract "tasks"
        if (Test-Path $tasks) {
            $n = (Get-ChildItem $tasks -Directory -ErrorAction SilentlyContinue).Count
            Write-Host ("{0,-8} OK  {1} tasks  {2}" -f $key, $n, $extract)
        } else {
            Write-Host ("{0,-8} --  missing  {1}" -f $key, $extract)
        }
    }
}

if ($ListOnly) {
    Show-Status
    exit 0
}

$wanted = $Subset.Split(",") | ForEach-Object { $_.Trim().ToLower() } | Where-Object { $_ }
foreach ($key in $wanted) {
    if (-not $Map.ContainsKey($key)) {
        Write-Error "unknown subset: $key (expected office|code|web|sec)"
        exit 1
    }
    $name = $Map[$key]
    $extract = Join-Path $DestDir $name
    $tar = Join-Path $DestDir "$name.tar.gz"
    $url = "$BaseUrl/$name.tar.gz"

    if ((Test-Path (Join-Path $extract "tasks")) -and -not $Force) {
        $n = (Get-ChildItem (Join-Path $extract "tasks") -Directory).Count
        Write-Host "$key already present: $n tasks under $extract"
        continue
    }

    if ($Force -and (Test-Path $extract)) {
        Remove-Item -Recurse -Force $extract
    }

    Write-Host "Downloading $url ..."
    Invoke-WebRequest -Uri $url -OutFile $tar -UseBasicParsing

    Write-Host "Extracting $name ..."
    tar -xzf $tar -C $DestDir
    if (-not (Test-Path (Join-Path $extract "tasks"))) {
        Write-Error "extract failed: tasks/ missing under $extract"
        exit 1
    }
    $n = (Get-ChildItem (Join-Path $extract "tasks") -Directory).Count
    Write-Host "OK: $key → $n tasks at $extract"
}

Write-Host ""
Write-Host "Status:"
Show-Status
Write-Host "Next: python -S -m octop.contrib.workbuddy.bench.cli --list-subsets --dry-sample-only"

# SPDX-License-Identifier: MIT
# Fetch public WorkBuddy CDN / docs snapshots into vendor/workbuddy-cdn-snapshot/
#
# Usage:
#   powershell -File scripts/fetch_cdn_snapshot.ps1
#   powershell -File scripts/fetch_cdn_snapshot.ps1 -Force

param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Dest = Join-Path $Root "vendor\workbuddy-cdn-snapshot"
New-Item -ItemType Directory -Force -Path $Dest | Out-Null

# Public, non-secret URLs (docs / marketing). Product binaries are NOT mirrored.
$Urls = @(
    @{ Name = "overview.html"; Url = "https://www.codebuddy.cn/docs/workbuddy/Overview" },
    @{ Name = "skills.html"; Url = "https://www.codebuddy.cn/docs/workbuddy/Skills" },
    @{ Name = "bench_readme.md"; Url = "https://raw.githubusercontent.com/Tencent/workbuddy-bench/main/README.md" }
)

$manifest = @()
foreach ($item in $Urls) {
    $out = Join-Path $Dest $item.Name
    if ((Test-Path $out) -and -not $Force) {
        Write-Host "skip existing $($item.Name)"
        $manifest += @{ name = $item.Name; url = $item.Url; status = "exists" }
        continue
    }
    Write-Host "GET $($item.Url)"
    try {
        Invoke-WebRequest -Uri $item.Url -OutFile $out -UseBasicParsing
        $manifest += @{ name = $item.Name; url = $item.Url; status = "ok"; bytes = (Get-Item $out).Length }
    } catch {
        Write-Host "WARN: failed $($item.Name): $_"
        $manifest += @{ name = $item.Name; url = $item.Url; status = "error"; error = "$_" }
    }
}

$manifestPath = Join-Path $Dest "manifest.json"
($manifest | ConvertTo-Json -Depth 4) | Set-Content -Path $manifestPath -Encoding UTF8
Write-Host "Wrote $manifestPath"
Get-ChildItem $Dest | ForEach-Object { Write-Host ("  {0}  {1}" -f $_.Name, $_.Length) }

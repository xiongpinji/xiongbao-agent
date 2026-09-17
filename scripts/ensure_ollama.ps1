# SPDX-License-Identifier: MIT
"""Ensure Ollama serve is up for local LLM smoke (Windows helper).

Usage::

    powershell -File scripts/ensure_ollama.ps1
"""

$ErrorActionPreference = "Continue"
$exe = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
if (-not (Test-Path $exe)) {
    Write-Host "FAIL: ollama.exe not found at $exe"
    exit 1
}

$models = Join-Path $env:USERPROFILE ".ollama\models"
New-Item -ItemType Directory -Force -Path $models | Out-Null
$env:OLLAMA_MODELS = $models
$env:OLLAMA_HOST = "127.0.0.1:11434"

try {
    $null = Invoke-RestMethod "http://127.0.0.1:11434/api/tags" -TimeoutSec 3
    Write-Host "OK: ollama already serving"
    exit 0
} catch {
    Write-Host "starting ollama serve (OLLAMA_MODELS=$models)…"
}

$cmd = "set OLLAMA_MODELS=$models&& set OLLAMA_HOST=127.0.0.1:11434&& `"$exe`" serve"
Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $cmd -WindowStyle Hidden | Out-Null
Start-Sleep -Seconds 6

try {
    $tags = Invoke-RestMethod "http://127.0.0.1:11434/api/tags" -TimeoutSec 8
    $names = @($tags.models | ForEach-Object { $_.name })
    Write-Host ("OK: ollama up, models=[{0}]" -f ($names -join ", "))
    if ($names.Count -eq 0) {
        Write-Host "HINT: pull a small model, e.g. ollama pull qwen2.5:1.5b"
        exit 3
    }
    exit 0
} catch {
    Write-Host "FAIL: ollama still unreachable: $($_.Exception.Message)"
    Write-Host "HINT: if C:\ollama_models is a broken junction, remove it or override OLLAMA_MODELS"
    exit 2
}

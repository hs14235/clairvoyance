<#
.SYNOPSIS
  Start the Clairvoyance API on Windows with real Qwen (Ollama) and faster-whisper.
  Checks everything first and tells you exactly what to fix.

.EXAMPLE
  .\scripts\start-api.ps1                     # picks qwen2.5:7b (16 GB+ RAM) or qwen2.5:1.5b
  .\scripts\start-api.ps1 -Model qwen2.5:3b   # any Ollama tag
  .\scripts\start-api.ps1 -Stub               # no models, same as CI and the Pages demo
  .\scripts\start-api.ps1 -WhisperModel base  # faster, less accurate speech-to-text
#>
param(
    [string]$Model = "",
    [string]$WhisperModel = "small",
    [string]$Language = "en",   # "auto" to detect the spoken language
    [switch]$Stub
)
$ErrorActionPreference = "Stop"
$OllamaUrl = "http://127.0.0.1:11434"

function Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Fail($msg) { Write-Host "XX  $msg" -ForegroundColor Red; exit 1 }
function Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }

Set-Location (Join-Path $PSScriptRoot "..\apps\api")

# --- Python -----------------------------------------------------------------
Step "Checking Python"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Fail "Python not found. Install Python 3.12 (winget install --id Python.Python.3.12), then open a new terminal."
}
$pyVersion = (& python -c "import sys; print('%d.%d' % sys.version_info[:2])").Trim()
if ([version]$pyVersion -lt [version]"3.11") {
    Fail "Python $pyVersion is too old; faster-whisper's audio decoder needs 3.11+. Install 3.12 and retry."
}
Ok "Python $pyVersion"

if (-not (Test-Path ".venv")) {
    Step "Creating .venv"
    python -m venv .venv
}
. .\.venv\Scripts\Activate.ps1
Step "Installing Python packages (quick when already installed)"
python -m pip install --quiet --disable-pip-version-check -r requirements-dev.txt -r requirements-voice.txt
if ($LASTEXITCODE -ne 0) { Fail "pip install failed (see above)." }

if ($Stub) {
    $env:LLM_PROVIDER = "stub"
    $env:STT_PROVIDER = "stub"
} else {
    # --- Model choice ---------------------------------------------------------
    if (-not $Model) {
        $ramGb = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
        $Model = if ($ramGb -ge 16) { "qwen2.5:7b" } else { "qwen2.5:1.5b" }
        Ok "$ramGb GB RAM -> using $Model (override with -Model)"
    }

    # --- Ollama ---------------------------------------------------------------
    Step "Checking Ollama"
    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        Fail "Ollama not found. Install it with: winget install --id Ollama.Ollama   (then open a new terminal)"
    }
    $up = $false
    try { Invoke-RestMethod "$OllamaUrl/api/version" -TimeoutSec 3 | Out-Null; $up = $true } catch {}
    if (-not $up) {
        Write-Host "    Ollama isn't running; starting it in the background..."
        Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
        for ($i = 0; $i -lt 20 -and -not $up; $i++) {
            Start-Sleep -Seconds 1
            try { Invoke-RestMethod "$OllamaUrl/api/version" -TimeoutSec 2 | Out-Null; $up = $true } catch {}
        }
        if (-not $up) { Fail "Ollama didn't start. Open the Ollama app from the Start menu, then rerun this script." }
    }
    Ok "Ollama is running at $OllamaUrl"

    $tags = (Invoke-RestMethod "$OllamaUrl/api/tags").models.name
    $wanted = if ($Model.Contains(":")) { $Model } else { "${Model}:latest" }
    if ($tags -notcontains $wanted) {
        Step "Pulling $Model (one time download)"
        ollama pull $Model
        if ($LASTEXITCODE -ne 0) { Fail "ollama pull $Model failed. Check the tag at https://ollama.com/library/qwen2.5" }
    }
    Ok "$Model is pulled"

    # An empty prompt loads the model into memory, so the first chat isn't the slow one.
    Step "Loading $Model into memory (can take a minute on CPU)"
    $load = @{ model = $Model; prompt = ""; keep_alive = "30m" } | ConvertTo-Json
    try {
        Invoke-RestMethod "$OllamaUrl/api/generate" -Method Post -Body $load -ContentType "application/json" -TimeoutSec 300 | Out-Null
        Ok "Model loaded"
    } catch {
        Write-Host "    Couldn't preload the model ($($_.Exception.Message)). The first reply will be slower." -ForegroundColor Yellow
    }

    $env:LLM_PROVIDER = "openai"
    $env:LLM_BASE_URL = "$OllamaUrl/v1"
    $env:LLM_MODEL = $Model
    $env:STT_PROVIDER = "faster-whisper"
    $env:STT_MODEL = $WhisperModel
    $env:STT_LANGUAGE = $Language
}

Write-Host ""
Write-Host "LLM=$env:LLM_PROVIDER $env:LLM_MODEL  STT=$env:STT_PROVIDER $env:STT_MODEL" -ForegroundColor Green
Write-Host "API docs:   http://localhost:8000/docs"
Write-Host "Health:     http://localhost:8000/api/v1/status"
Write-Host "Smoke test: .\scripts\smoke-test.ps1   (in a second terminal)"
Write-Host "Whisper loads in the background; the first run downloads it (~0.5 GB for 'small')."
Write-Host ""
uvicorn src.main:app --reload

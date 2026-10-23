<#
.SYNOPSIS
  Start the Clairvoyance API on Windows with real Qwen (Ollama) and faster-whisper.

.EXAMPLE
  .\scripts\start-api.ps1                     # qwen2.5:3b + Whisper small
  .\scripts\start-api.ps1 -Model qwen2.5:7b   # better replies, needs ~8 GB free RAM
  .\scripts\start-api.ps1 -Stub               # no models, same as CI and the Pages demo
#>
param(
    [string]$Model = "qwen2.5:3b",
    [string]$WhisperModel = "small",
    [switch]$Stub
)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\apps\api")

if (-not (Test-Path ".venv")) { python -m venv .venv }
. .\.venv\Scripts\Activate.ps1
python -m pip install --quiet -r requirements-dev.txt -r requirements-voice.txt

if ($Stub) {
    $env:LLM_PROVIDER = "stub"
    $env:STT_PROVIDER = "stub"
} else {
    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        throw "Ollama not found. Install it with: winget install --id Ollama.Ollama  (then open a new terminal)"
    }
    ollama pull $Model
    $env:LLM_PROVIDER = "openai"
    $env:LLM_BASE_URL = "http://localhost:11434/v1"
    $env:LLM_MODEL = $Model
    $env:STT_PROVIDER = "faster-whisper"
    $env:STT_MODEL = $WhisperModel
}

Write-Host "LLM=$env:LLM_PROVIDER ($env:LLM_MODEL)  STT=$env:STT_PROVIDER  ->  http://localhost:8000/docs"
uvicorn src.main:app --reload

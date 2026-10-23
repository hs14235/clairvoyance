<#
.SYNOPSIS
  End-to-end check of a running API: Windows speaks a sentence into a WAV file,
  the API transcribes it with Whisper, then Qwen replies. Prints what each step
  returned and how long it took.

.EXAMPLE
  .\scripts\smoke-test.ps1
  .\scripts\smoke-test.ps1 -Sentence "I feel hopeless and I can't go on"   # should flag takeover
#>
param(
    [string]$Api = "http://localhost:8000",
    [string]$Sentence = "I have been feeling really anxious about my exams and I can't sleep."
)
$ErrorActionPreference = "Stop"

Write-Host "==> Status" -ForegroundColor Cyan
try {
    $status = Invoke-RestMethod "$Api/api/v1/status" -TimeoutSec 10
} catch {
    Write-Host "XX  API not reachable at $Api. Start it first: .\scripts\start-api.ps1" -ForegroundColor Red
    exit 1
}
foreach ($part in "llm", "stt") {
    $s = $status.$part
    $color = if ($s.ok) { "Green" } else { "Red" }
    Write-Host ("    {0}: {1} - {2}" -f $part, $s.provider, $s.detail) -ForegroundColor $color
}

Write-Host "==> Speaking test sentence to a WAV file (Windows SAPI voice)" -ForegroundColor Cyan
$wav = Join-Path $env:TEMP "clairvoyance-smoke.wav"
$voice = New-Object -ComObject SAPI.SpVoice
$stream = New-Object -ComObject SAPI.SpFileStream
$stream.Open($wav, 3)   # 3 = create for writing
$voice.AudioOutputStream = $stream
[void]$voice.Speak($Sentence)
$stream.Close()
Write-Host "    said: $Sentence"

Write-Host "==> Transcribing" -ForegroundColor Cyan
$sw = [Diagnostics.Stopwatch]::StartNew()
# curl.exe ships with Windows 10+; Invoke-RestMethod -Form needs PowerShell 7.
$out = Join-Path $env:TEMP "clairvoyance-smoke.json"
$code = & curl.exe -s -o $out -w "%{http_code}" -F "audio=@$wav;type=audio/wav" "$Api/api/v1/speech/transcribe"
$sw.Stop()
$body = Get-Content $out -Raw
if ($code -ne "200") {
    Write-Host "XX  transcribe returned $code : $body" -ForegroundColor Red
    exit 1
}
$heard = ($body | ConvertFrom-Json).text
Write-Host ("    heard: {0}   ({1:N1}s)" -f $heard, $sw.Elapsed.TotalSeconds) -ForegroundColor Green

Write-Host "==> Asking Qwen" -ForegroundColor Cyan
$sw.Restart()
$req = @{ message = $heard } | ConvertTo-Json
$reply = Invoke-RestMethod "$Api/api/v1/chat/message" -Method Post -Body $req -ContentType "application/json" -TimeoutSec 300
$sw.Stop()
Write-Host ("    reply: {0}   ({1:N1}s)" -f $reply.text_response, $sw.Elapsed.TotalSeconds) -ForegroundColor Green
Write-Host ("    sentiment={0} intensity={1} gesture={2} takeover={3}" -f `
    $reply.sentiment, $reply.intensity, $reply.animation_trigger, $reply.human_takeover_flag)
if ($reply.model_fallback) {
    Write-Host "XX  That was the canned fallback line, not Qwen. See the API terminal for the reason." -ForegroundColor Red
    exit 1
}
Write-Host "All good: speech -> Whisper -> Qwen works." -ForegroundColor Green

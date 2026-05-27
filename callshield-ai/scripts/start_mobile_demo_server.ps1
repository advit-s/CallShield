$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $projectRoot

$env:CALLSHIELD_ASR_BACKEND="huggingface"
$env:CALLSHIELD_ASR_OFFLINE="true"
$env:CALLSHIELD_HF_ASR_LOCAL_DIR="models\hf_asr\Oriserve__Whisper-Hindi2Hinglish-Swift"

Write-Host "Starting CallShield mobile demo server..." -ForegroundColor Cyan
Write-Host "ASR backend: $env:CALLSHIELD_ASR_BACKEND"
Write-Host "ASR offline:  $env:CALLSHIELD_ASR_OFFLINE"
Write-Host "ASR model:    $env:CALLSHIELD_HF_ASR_LOCAL_DIR"

if (-not (Test-Path $env:CALLSHIELD_HF_ASR_LOCAL_DIR)) {
    Write-Warning "Offline ASR model folder was not found. The server can still start, but ASR may be unavailable."
}

Write-Host "Checking offline ASR model load..." -ForegroundColor Cyan
& .\.venv\Scripts\python.exe -c "import os; from callshield.engine.asr import ASRTranscriber, DEFAULT_HF_ASR_MODEL, resolve_hf_asr_model; model=resolve_hf_asr_model(DEFAULT_HF_ASR_MODEL, local_dir=os.environ.get('CALLSHIELD_HF_ASR_LOCAL_DIR')); t=ASRTranscriber(model_name=model, backend='huggingface', local_files_only=True); raise SystemExit(0 if t.model is not None else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "Offline ASR model failed to load. Fix the model/dependencies before starting the mobile demo server."
}

& .\.venv\Scripts\python.exe main.py server

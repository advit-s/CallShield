# CallShield Real-World Testing Guide

This guide is for a small, ethical pilot before you show CallShield to Truecaller or any hiring team.

## Rule Zero

Use only audio you are allowed to analyze:

- Your own voice samples.
- Friends/family samples with clear consent.
- Scripted scam simulations with participants who know they are being recorded.
- Public datasets with permission to use them.

Do not record or analyze private calls without consent.

## What To Test

Build a small pilot set first:

| Set | Target Count | Purpose |
|-----|--------------|---------|
| Normal real calls | 20-50 | Measure false positives |
| Scripted scam calls | 20-50 | Measure scam-language recall |
| TTS/synthetic voice samples | 20-50 | Measure deepfake audio sensitivity |
| WhatsApp/compressed audio | 20-50 | Measure compression robustness |
| Noisy phone-speaker recordings | 20-50 | Measure real-world degradation |
| Hindi/Hinglish samples | 20-50 | Measure local-market relevance |

Keep each condition separate in the report. A model can perform well on clean ASVspoof audio and still struggle on compressed phone audio.

## Label CSV Format

Create a CSV like:

```csv
audio_path,transcript,is_scam,is_deepfake,notes
samples/normal_001.wav,"Hi beta, reached home safely.",0,0,normal family call
samples/scam_001.wav,"My phone is dead, send money urgently.",1,0,scripted scam
samples/fake_001.wav,"Do not verify, send the money now.",1,1,synthetic voice
```

Labels:

```text
is_scam: 0 normal, 1 scam
is_deepfake: 0 real voice, 1 synthetic/cloned/TTS
```

An example file is included at `samples/pilot_labels.example.csv`.

## Run Without ASR

Use this when you already have transcripts:

```powershell
.\.venv\Scripts\python.exe scripts\run_real_world_audio_test.py `
  --audio-dir samples\pilot_audio `
  --transcripts-csv samples\pilot_labels.csv `
  --out-json reports\real_world_pilot.json `
  --out-csv reports\real_world_pilot.csv
```

## Run With Whisper ASR

Use this when you only have audio:

```powershell
.\.venv\Scripts\python.exe scripts\run_real_world_audio_test.py `
  --audio-dir samples\pilot_audio `
  --asr `
  --whisper-model base `
  --out-json reports\real_world_pilot_asr.json `
  --out-csv reports\real_world_pilot_asr.csv
```

For Hindi/Hinglish tests:

```powershell
.\.venv\Scripts\python.exe scripts\run_real_world_audio_test.py `
  --audio-dir samples\hindi_hinglish `
  --asr `
  --language hi `
  --out-json reports\real_world_hindi_hinglish.json
```

## Privacy Options

By default, the script does not store full local paths or full transcripts. Add these only for your private debugging:

```powershell
--include-paths --include-transcripts
```

For deduplication:

```powershell
--hash-audio
```

## What To Report

For a Truecaller-style demo, report:

```text
Scam NLP recall/FPR on scripted real-world calls
Deepfake weak/strong threshold behavior
False positives on normal real calls
Performance on compressed/noisy audio
Hindi/Hinglish behavior
Failure examples and next fixes
```

## Minimum Honest Claim

Use this wording:

```text
CallShield has a trained and calibrated audio-deepfake prototype validated on ASVspoof 2019/2021, plus a scam-language risk engine. Real-world phone-call validation is in pilot testing.
```

Avoid:

```text
Production-ready deepfake detector.
Works on all calls.
Truecaller replacement.
```

## Good Pilot Target

Before outreach, aim for:

```text
100+ consented real-world samples
Normal-call FPR below 10%
Scam-language recall above 85%
Deepfake hard-threshold FPR below 10-15%
Clear failure analysis
```

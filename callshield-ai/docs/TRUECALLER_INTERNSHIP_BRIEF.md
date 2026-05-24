# CallShield: Truecaller Internship Project Brief

## One-Line Pitch

CallShield is a scam-call intelligence prototype that combines conversation-risk detection with trained audio-deepfake detection to warn users when a call becomes dangerous.

## Why It Fits Truecaller

Truecaller already helps users identify who is calling. CallShield explores the next layer: what is happening inside the call.

The system focuses on:

- Scam-language cues such as urgency, secrecy, money requests, OTP/PIN requests, and authority threats.
- Audio-deepfake evidence from a trained log-mel CNN.
- Conservative fusion so audio alone does not over-trigger high-risk warnings.
- Privacy-first handling with no raw audio storage by default.

## What I Built

```text
Python/FastAPI backend
Python SDK
Scam NLP/rule engine for English, Hindi, and Hinglish cues
Risk fusion and calibration engine
Safe verification challenge generator
Audio feature extraction with log-mel spectrograms
CNN deepfake detector trained on ASVspoof data
Evaluation scripts, leakage checks, balanced evaluation, and model manifest
Demo dashboard
Real-world pilot testing CLI
Android mobile PoC for speakerphone/test-call microphone streaming
```

## Current Evidence

Scam NLP conversation-risk evaluation:

```text
Recall: 100.0%
False Positive Rate: 2.0%
Accuracy: 99.0%
Precision: 0.980
F1: 0.990
```

Audio-deepfake evaluation:

```text
2021 fine-tuned -> 2021 held-out:
Accuracy: 98.0%
F1: 98.7%
ROC-AUC: 99.8%
EER: 2.1%

2021 fine-tuned -> 2019 test:
Accuracy: 95.8%
F1: 97.1%
ROC-AUC: 99.2%
EER: 4.2%

Balanced 2021 test:
Accuracy: 97.4%
F1: 97.4%
ROC-AUC: 99.8%
EER: 1.9%
```

Important limitation:

```text
The model is trained and calibrated on ASVspoof 2019/2021. It is not yet validated on real phone-call audio, WhatsApp-compressed audio, or noisy Hindi/Hinglish scam calls.
```

## Technical Design

```text
Audio upload / transcript
        |
        v
ASR transcript if needed
        |
        +--> Scam language engine
        |
        +--> Log-mel CNN deepfake detector
        |
        v
Risk fusion + calibration
        |
        v
User-facing warning + explanation + verification challenge
```

## Safety Design

Deepfake audio uses two thresholds:

```text
score < 0.1979       -> ignore audio deepfake signal
0.1979 <= score < 0.5 -> weak/suspicious audio evidence
score >= 0.5         -> strong deepfake evidence
```

Product rule:

```text
Deepfake high + scam language low = soft warning
Deepfake high + scam language high = strong warning
Deepfake low + scam language high = strong warning
```

This avoids claiming that a voice model alone can decide whether a call is a scam.

## Demo Commands

Run API:

```powershell
.\.venv\Scripts\python.exe main.py server
```

Model status:

```powershell
Invoke-RestMethod http://localhost:8000/model-status | ConvertTo-Json -Depth 5
```

Scam NLP test:

```powershell
.\.venv\Scripts\python.exe main.py test
```

Real-world pilot:

```powershell
.\.venv\Scripts\python.exe scripts\run_real_world_audio_test.py `
  --audio-dir samples\pilot_audio `
  --transcripts-csv samples\pilot_labels.csv `
  --out-json reports\real_world_pilot.json `
  --out-csv reports\real_world_pilot.csv
```

Android mobile PoC:

```text
Open android/CallShieldMobile in Android Studio
Run backend with .\.venv\Scripts\python.exe main.py server
Use http://10.0.2.2:8000 on emulator or http://YOUR_LAPTOP_LAN_IP:8000 on a phone
```

## What I Want To Learn At Truecaller

- Real-world telecom-scale spam/scam signal engineering.
- Voice, ASR, and call metadata robustness under noisy mobile conditions.
- Privacy-preserving ML evaluation and deployment.
- How consumer trust and false-positive control are handled at product scale.

## 30-Day Internship Plan

Week 1:

```text
Understand Truecaller's scam/spam call problem framing, privacy constraints, and evaluation criteria.
```

Week 2:

```text
Build a stronger real-world evaluation harness for call audio, transcripts, compression, and language variation.
```

Week 3:

```text
Improve robustness with audio augmentations: noise, telephony bandwidth, compression, re-recording, and Hinglish samples.
```

Week 4:

```text
Deliver an evidence-backed prototype report: metrics, failure cases, product guardrails, and next model roadmap.
```

## Outreach Message

Subject:

```text
Internship interest: Scam-call intelligence + audio deepfake prototype
```

Message:

```text
Hi Truecaller team,

I built CallShield, a scam-call intelligence prototype that combines scam-language detection with a trained audio-deepfake detector. The goal is to go beyond caller identity and detect when the conversation itself becomes risky.

Current prototype:
- Python/FastAPI backend and SDK
- English/Hindi/Hinglish scam-cue engine
- Risk fusion and safe verification challenges
- Trained log-mel CNN deepfake model
- Evaluation hygiene: leakage checks, cross-domain tests, balanced tests, model manifest
- Real-world pilot CLI for consented call/audio samples
- Android PoC that streams speakerphone/test-call microphone chunks to the backend

Best ASVspoof held-out result: 98.7% F1, 99.8% ROC-AUC, 2.1% EER.
I am careful not to overclaim: the mobile PoC demonstrates the integration path, while direct private in-call audio capture would require a platform-compliant telecom/OEM/VoIP integration. The next step is real-world phone-call and compressed-audio validation.

I would love to intern with Truecaller and learn how scam/spam detection, privacy, and reliability are handled at real product scale. I can share the repo, reports, and a short demo.

Regards,
Advit
```

## Portfolio Summary

Use this in your resume:

```text
Built CallShield, a scam-call intelligence prototype combining multilingual scam-language detection, calibrated risk fusion, and a trained audio-deepfake CNN. Added ASVspoof 2019/2021 training and evaluation, leakage checks, balanced testing, model manifest, FastAPI endpoints, SDK, Android microphone-streaming PoC, and real-world pilot tooling.
```

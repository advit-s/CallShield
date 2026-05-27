# Real-World CallShield Test Report

Use this template after testing real speakerphone or consented call audio. Keep scam NLP, ASR quality, and deepfake behavior separate so the result is easy to defend.

## Session

- Date:
- Tester:
- Device:
- Backend URL:
- ASR backend:
- Deepfake checkpoint:
- Environment: quiet room / noisy room / WhatsApp / cellular speakerphone / generated audio

## Test Matrix

| ID | Scenario | Language | Audio source | Expected risk | Transcript quality | Risk score | Warning | Deepfake score | Deepfake false alarm | Notes |
|---|---|---|---|---|---|---:|---|---:|---|---|
| RW-001 | Normal family call | Hinglish | Speakerphone | Safe |  |  |  |  |  |  |
| RW-002 | Money urgency scam phrase | English/Hinglish | Speakerphone | Suspicious/high |  |  |  |  |  |  |
| RW-003 | Silent/noisy room | none | Microphone | Safe/no speech |  |  |  |  |  |  |

## ASR Quality

- Correct transcript chunks:
- Empty/no-speech chunks:
- Hallucinated/gibberish chunks:
- Main failure examples:

## Scam Detection

- True positives:
- False negatives:
- False positives:
- Most useful cues:

## Audio Deepfake Behavior

- Real human audio scores:
- Synthetic/generator audio scores:
- Deepfake false alarm count:
- Audio-only review cases:

## Final Decision

- Ready for demo:
- Needs retraining:
- Needs ASR tuning:
- Notes for Truecaller-style integration:

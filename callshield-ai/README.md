# CallShield AI v2.0 - Scam Call Intelligence Engine

> **Caller ID tells you who might be calling. CallShield tells you whether the conversation is becoming dangerous.**

## What is CallShield?

CallShield is a real-time scam call intelligence layer. It analyzes live call conversations to detect scam behavior — urgency, coercion, money demands, synthetic voices — and warns users before they fall victim.

**Key insight:** Even if the caller ID looks normal, the conversation itself can be dangerous.

## Architecture (Three-Signal Fusion)

| Signal | Priority | What it detects |
|--------|---------|-----------------|
| **Scam Language** | 35% | Urgency, coercion, money demands, threats, secrecy |
| **Deepfake Audio** | 25% | AI-generated/synthetic voice |
| **Identity Mismatch** | 20% | Voice doesn't match trusted profile |
| **Urgency** | 10% | Excessive pressure to act immediately |
| **Verification Failure** | 10% | Failed challenge-response prompts |

**Risk Formula:**
```
risk = 0.35×scam + 0.25×deepfake + 0.20×identity + 0.10×urgency + 0.10×verification + rule_bonus
```

## Risk Bands

| Score | Band | Action |
|-------|------|--------|
| 0-30 | Safe | No action needed |
| 31-60 | Suspicious | Be cautious. Consider verification question |
| 61-80 | High Risk | Do not send money. Hang up and verify |
| 81-100 | Critical | HANG UP. Report. Call back known number |

## Quick Start

### 1. Start the Server
```bash
cd callshield-ai
pip install -r requirements.txt
python3 main.py server
```

Open [http://localhost:8000/demo](http://localhost:8000/demo) for the dashboard.

### 2. SDK Usage
```python
from callshield.sdk import CallShieldSDK

sdk = CallShieldSDK()
result = sdk.analyze_transcript("Mera phone dead hai, abhi ₹25,000 bhejo")

print(f"Risk: {result.risk_score}/100 ({result.risk_band})")
print(f"Type: {result.scam_type}")
print(f"Action: {result.recommended_action}")
```

### 3. Run Tests
```bash
python3 main.py test
# 100 scenarios (50 normal + 50 scam)
# Reports: Accuracy, Precision, Recall, F1, FPR
```

## Project Structure

```
callshield/
  engine/           # Core analysis engine
    scam_nlp.py     # Scam language detection (EN/HI/Hinglish)
    fusion.py         # Risk fusion engine
    privacy.py        # Privacy utilities
    audio.py          # VAD + preprocessing
    deepfake.py       # Deepfake detection
    asr.py            # Whisper transcription
    speaker.py        # Speaker verification
  api/              # FastAPI backend
    server.py         # API endpoints
    schemas.py        # Pydantic models
    config.py         # Configuration
  sdk/              # Python SDK
    callshield.py     # SDK wrapper
  dashboard/        # Demo dashboard
    index.html
  tests/            # Test suite
    scenarios_normal.py
    scenarios_scam.py
    test_evaluation.py
```

## API Endpoints

| Endpoint | Description |
|----------|--------|
| `POST /analyze-transcript` | Analyze call transcript for scam patterns |
| `POST /analyze-audio` | Analyze uploaded audio (full pipeline) |
| `POST /score-call` | Full call analysis |
| `POST /verify-speaker` | Enroll speaker for voice verification |
| `POST /submit-feedback` | User feedback for model improvement |
| `GET /call-summary/{id}` | Full call analysis report |
| `GET /health` | Health + model status |

## Scam Categories Detected

- Family emergency scams
- Bank/KYC fraud
- Police/legal threat scams
- Tech support scams
- Job/investment scams
- OTP/PIN/password requests
- UPI/payment requests
- Remote access requests
- Secrecy pressure
- Alternate number claims

## Privacy-First Design

- No raw audio stored by default
- Phone numbers hashed (SHA-256)
- Speaker enrollment requires consent
- Temporal files only
- Explainable, user-controlled warnings
- Call-back recommendation (not auto-blocking)

## Example Output

```json
{
  "risk_score": 56.2,
  "risk_band": "suspicious",
  "scam_type": "family_emergency",
  "detected_cues": [
    "family_emergency: i'm in trouble",
    "alternate_number_claim: my phone is dead",
    "secrecy_pressure: don't tell anyone"
  ],
  "explanation": "Caller using urgency and secrecy. Claims to be family from unknown number requesting money.",
  "recommended_action": "Be cautious. Consider asking a verification question. Do not share financial details."
}
```

## B2B Integration

CallShield can be integrated as:
- **Telecom layer**: Real-time call analysis + warning overlay
- **Bank layer**: Transaction hold on high-risk calls
- **App layer**: Truecaller-style caller warning
- **SDK**: Python SDK for custom apps

## License

MIT License - Hackathon/Research Use

---

**Built for:** Hackathon Demo → Product Pitch
**Positioning:** "Conversation intelligence layer that makes caller ID smarter by understanding what happens after the call starts."

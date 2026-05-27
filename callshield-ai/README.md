# CallShield AI v2.4.0 - Scam Call Intelligence Prototype

> Caller ID tells you who might be calling. CallShield tells you whether the conversation is becoming dangerous.

CallShield is a real-time scam call intelligence layer. It analyzes call conversations for scam behavior such as urgency, coercion, money demands, secrecy pressure, and identity manipulation.

## Project In One Minute

CallShield AI is a prototype scam-call safety system. It listens to a call or test audio stream, transcribes the speech, detects scam-language patterns, checks for synthetic or replayed voice evidence, and fuses those signals into a human-readable risk alert.

The project is designed around one practical question:

```text
Is this conversation becoming risky enough that the user should stop, verify, or refuse the request?
```

Current outputs include:

- scam type, warning level, confidence, and matched cues
- deepfake score and calibrated audio signal strength
- fused risk score from `0` to `100`
- recommended safety action
- live transcript and backend log-mel spectrogram in the Android test app
- API dashboard for transcript/audio testing and model status

This is a strong research/demo prototype, not a production call-blocking product yet.

## What Has Been Built

- **Scam NLP engine:** rule-and-context based detector for family emergency scams, UPI/payment demands, OTP/PIN/password requests, KYC/bank fraud, police/legal threats, tech support scams, job/investment scams, remote access scams, secrecy pressure, and alternate-number claims.
- **Audio deepfake pipeline:** 16 kHz mono audio, 4-second chunks, 128-bin log-mel spectrograms, z-score normalization, CNN inference, checkpoint loading, and calibration.
- **Combined deepfake training:** model trained with ASVspoof 2019, ASVspoof 2021, and ADD 2023 Track 1.2 data using balanced sampling.
- **Risk fusion:** combines scam language, calibrated audio evidence, urgency, identity pressure, and verification risk while avoiding high-risk alerts from weak audio-only evidence.
- **Privacy-first API:** FastAPI backend with transcript/audio analysis routes, model status, health checks, feedback, call summary, privacy deletion paths, and safer handling of uploaded audio.
- **Android test app:** microphone chunk streaming, live transcript display, backend log-mel spectrogram display, final call alert, speakerphone capture assist, and Cloudflare Tunnel support through a public backend URL.
- **Documentation and GitHub hygiene:** large datasets, checkpoints, APKs, ASR snapshots, logs, and local artifacts are kept out of GitHub by `.gitignore`.

## System Architecture

```text
Audio or transcript input
        |
        v
FastAPI backend
        |
        +--> ASR transcript extraction
        +--> Scam NLP detection
        +--> Log-mel deepfake CNN
        +--> Calibration and two-threshold audio gating
        +--> Risk fusion
        |
        v
JSON risk report + dashboard/mobile UI
```

For mobile demos, the Android app does not contain the Python backend. It records microphone chunks and sends them to the backend URL. For remote review, that backend URL can be a Cloudflare Tunnel URL pointing to the server running on your PC.

## Current Honest Status

CallShield is ready for:

- technical walkthroughs
- portfolio/GitHub review
- mentor or evaluator demo
- controlled local and remote demos with consented audio
- continued ML experimentation and real-world pilot planning

CallShield is not yet validated for:

- production phone-call deployment
- WhatsApp/VoIP compressed calls
- noisy real-world Indian/Hinglish scam calls
- unknown in-the-wild voice-cloning tools
- direct private cellular call-audio capture on normal Android phones

## Current Model Status

| Module | Status |
|--------|--------|
| Scam language NLP | Implemented |
| Risk fusion | Implemented |
| Calibration | Implemented |
| Challenge prompts | Implemented |
| Privacy layer | Implemented |
| ASR | Available with Whisper or the local Hugging Face Hindi/Hinglish snapshot |
| Deepfake audio | Deployed checkpoint trained and calibrated |
| Speaker verification | Placeholder |

The deepfake pipeline includes log-mel feature extraction, a CNN architecture, API integration, training scripts, GPU training, combined ASVspoof/ADD training, separate domain evaluations, and a calibrated fusion threshold.

## Deepfake Model Status

Deepfake model status is runtime-dependent.

Before `models/deepfake_mel_cnn.pt` exists, CallShield reports `pipeline_implemented_no_trained_model`, returns `deepfake_score: null`, and keeps `used_in_fusion: false`. After a checkpoint is trained and loaded, CallShield reports `trained_model_loaded`.

The deployed model is canonical:

```text
models/deepfake_mel_cnn.pt = deployed checkpoint
models/deepfake_calibration.json = calibration for that checkpoint
```

`models/deepfake_mel_cnn.pt` is currently copied from `models/archives/deepfake_mel_cnn_combined_2019_2021_add2023.pt`. The loaded runtime threshold profile is:

```text
score < 0.161376953125       -> audio signal ignored
0.161376953125 <= score < 0.5 -> weak/suspicious audio evidence
score >= 0.5                 -> strong deepfake evidence
```

The soft threshold was selected from the combined model's ASVspoof 2021 balanced evaluation at target FPR <= 10%. The hard threshold avoids overreacting to weak audio evidence.

Current combined-model evaluation snapshot:

| Evaluation | Accuracy | F1 | ROC-AUC | EER | FPR |
|------------|----------|----|---------|-----|-----|
| ASVspoof 2021 balanced | 97.88% | 97.89% | 99.85% | 1.8% | 3.05% |
| ASVspoof 2019 | 94.94% | 96.42% | 99.13% | 4.44% | 2.12% |
| ADD 2023 Track 1.2 balanced | 97.45% | 97.51% | 99.97% | 0.9% | 5.10% |

Honesty note: the combined CSVs are file-disjoint, but not fully speaker-disjoint. These metrics are not proof of production performance on real phone-call audio, noisy WhatsApp/VoIP calls, Hindi/Hinglish scam calls, or in-the-wild scam calls.

See `models/model_manifest.json` for the deployed checkpoint, calibration file, source checkpoint, operating threshold, reports, and limitations.

## Quick Start

```bash
cd callshield-ai
pip install -r requirements.txt
python3 main.py server
```

Open [http://localhost:8000/demo](http://localhost:8000/demo) for the dashboard.

On Windows with the checked-in virtual environment, use:

```powershell
.\.venv\Scripts\python.exe main.py server
.\.venv\Scripts\python.exe main.py demo
```

## Android APK Download

The final Android test APK should be shared through GitHub Releases, not committed directly to the repo.

Latest APK download link after publishing a release:

[Download CallShieldMobile-Live-Test.apk](https://github.com/advit-s/CallShield/releases/latest/download/CallShieldMobile-Live-Test.apk)

Local APK to upload:

```text
C:\Users\advit\OneDrive\Desktop\CallShield\dist\CallShieldMobile-Live-Test.apk
```

APK SHA256:

```text
A95224CC5EB3F8CC1BE16DF91C1DEF0E0D9AE8AB57D22F12D876921A40578D45
```

To publish it from the GitHub website:

1. Open [https://github.com/advit-s/CallShield/releases](https://github.com/advit-s/CallShield/releases)
2. Click `Draft a new release`.
3. Use tag `v2.4.0`.
4. Title it `CallShield AI v2.4.0`.
5. Upload `dist\CallShieldMobile-Live-Test.apk`.
6. Publish the release.

After that, the download link above will work for reviewers and evaluators.

## Final Demo Checklist

Use this when demonstrating the full system end to end.

1. Start the backend:

```powershell
cd C:\Users\advit\OneDrive\Desktop\CallShield\callshield-ai
.\.venv\Scripts\python.exe main.py server
```

2. Confirm the model is loaded:

```powershell
Invoke-RestMethod http://localhost:8000/model-status | ConvertTo-Json -Depth 5
```

Look for:

```text
trained_model_loaded
calibrated
```

3. Open the dashboard:

```text
http://localhost:8000/demo
```

4. For remote review, start Cloudflare Tunnel in another terminal:

```powershell
cd C:\Users\advit\OneDrive\Desktop\CallShield
.\cloudflared.exe tunnel --url http://localhost:8000
```

5. Share the generated dashboard URL:

```text
https://YOUR-TUNNEL.trycloudflare.com/demo
```

6. For Android, enter only the base tunnel URL:

```text
https://YOUR-TUNNEL.trycloudflare.com
```

Then tap `Test server` and `Start test`.

Cloudflare Tunnel keeps the Python server on your machine and forwards a temporary public URL to it. Quick tunnels are for testing and development, not production deployment. Official docs: [Cloudflare Tunnel](https://developers.cloudflare.com/tunnel/) and [Quick Tunnels](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/).

## Real-World Pilot

Use the pilot runner on consented audio only:

```powershell
.\.venv\Scripts\python.exe scripts\run_real_world_audio_test.py `
  --audio-dir samples\pilot_audio `
  --transcripts-csv samples\pilot_labels.csv `
  --out-json reports\real_world_pilot.json `
  --out-csv reports\real_world_pilot.csv
```

If you do not have transcripts, run Whisper ASR:

```powershell
.\.venv\Scripts\python.exe scripts\run_real_world_audio_test.py `
  --audio-dir samples\pilot_audio `
  --asr `
  --whisper-model base `
  --out-json reports\real_world_pilot_asr.json
```

Read [docs/REAL_WORLD_TESTING.md](docs/REAL_WORLD_TESTING.md) before testing real calls. The short version: use consented audio, keep normal/scam/synthetic/compressed/noisy samples separate, and do not claim production readiness from a small pilot.

## Android Mobile PoC

Option 1 is implemented in [android/CallShieldMobile](android/CallShieldMobile). It is a backend-connected test app: the backend is required for ASR, CNN deepfake inference, risk fusion, and the real backend log-mel spectrogram displayed in the app.

The app records microphone audio in 8-second WAV chunks, shows the ASR transcript it heard, shows a log-mel spectrogram preview, and streams each chunk to:

```text
POST /analyze-audio
```

Run the backend first:

```powershell
.\.venv\Scripts\python.exe main.py server
```

Then open `android/CallShieldMobile` in Android Studio.

Use this server URL in the app:

```text
Android emulator: http://10.0.2.2:8000
Physical phone:   http://YOUR_LAPTOP_LAN_IP:8010
```

Important limitation: this is a speakerphone/test-call microphone streaming PoC. Android generally does not allow normal apps to capture private in-call audio directly. A Truecaller-style product would need a compliant telecom, OEM, accessibility, VoIP, or server-side integration path with user consent.

For a physical phone, use the LAN URL printed by `python main.py server` and tap `Test server` in the app before recording. `10.0.2.2` is emulator-only.

The app uploads one chunk at a time and skips chunks while the backend is busy, keeping the demo close to real time instead of building a delayed queue.

Live mobile safeguards:

```text
background/no-speech chunks -> ignored
ASR hallucinations -> suppressed
deepfake-only evidence -> shown, but not fused into risk without scam-like text
```

Hindi/Hinglish ASR:

If `models\hf_asr\Oriserve__Whisper-Hindi2Hinglish-Swift` exists, the server automatically uses that local Hugging Face ASR snapshot for mobile demos. You do not need to set the ASR environment variables every time.

To force the hosted Hugging Face model instead:

```powershell
$env:CALLSHIELD_ASR_BACKEND="huggingface"
$env:CALLSHIELD_HF_ASR_MODEL="Oriserve/Whisper-Hindi2Hinglish-Swift"
.\.venv\Scripts\python.exe main.py server
```

The Hugging Face model downloads on first run. Use this only when the local snapshot is not available.

Offline Hugging Face mode downloads the model once, then runs from disk:

```powershell
.\.venv\Scripts\python.exe scripts\download_hf_asr_model.py --model Oriserve/Whisper-Hindi2Hinglish-Swift

$env:CALLSHIELD_ASR_BACKEND="huggingface"
$env:CALLSHIELD_ASR_OFFLINE="true"
$env:CALLSHIELD_HF_ASR_LOCAL_DIR="models\hf_asr\Oriserve__Whisper-Hindi2Hinglish-Swift"
.\.venv\Scripts\python.exe main.py server
```

Use offline mode for demos where the laptop may not have reliable internet.

Read [docs/ANDROID_POC.md](docs/ANDROID_POC.md) and [android/CallShieldMobile/README.md](android/CallShieldMobile/README.md) for the mobile demo flow.

## GitHub Publishing Notes

The root `.gitignore` intentionally keeps heavy or sensitive local artifacts out of GitHub:

- raw datasets such as ASVspoof, ADD 2023, WaveFake, In-The-Wild, and scam-message CSV collections
- generated dataset split CSVs under `data/deepfake*`
- `.pt`, `.pth`, `.ckpt`, ONNX, TFLite, downloaded Hugging Face ASR snapshots, and model archives
- Android build outputs and APK/AAB files
- local `.env`, databases, logs, captures, recordings, and scratch audit reports

Keep `models/model_manifest.json` and calibration JSON files in the repo so readers can understand the deployed model configuration without downloading private or heavy binaries.

## Truecaller Outreach Pack

For internship outreach, use [docs/TRUECALLER_INTERNSHIP_BRIEF.md](docs/TRUECALLER_INTERNSHIP_BRIEF.md). It includes:

- one-line pitch
- Truecaller fit
- architecture
- current metrics
- honest limitations
- 30-day internship plan
- email template
- resume bullet

## SDK Usage

```python
from callshield.sdk import CallShieldSDK

sdk = CallShieldSDK()
result = sdk.analyze_transcript("Mera phone dead hai, abhi Rs 25,000 bhejo")

print(f"Risk: {result.risk_score}/100 ({result.risk_band})")
print(f"Type: {result.scam_type}")
print(f"Action: {result.recommended_action}")
print(result.model_status)
```

## Risk Fusion

Risk scoring combines scam language, trained deepfake score when available, identity mismatch, urgency, verification failure, and rule bonuses.

When no trained deepfake checkpoint exists:

```json
{
  "deepfake_score": null,
  "confidence": "unavailable",
  "model_status": "pipeline_implemented_no_trained_model",
  "used_in_fusion": false
}
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /analyze-transcript` | Analyze call transcript for scam patterns |
| `POST /analyze-audio` | Analyze uploaded audio through ASR plus text/audio pipeline |
| `POST /score-call` | Score transcript plus optional precomputed scores |
| `POST /verify-speaker` | Enroll speaker for voice verification |
| `POST /submit-feedback` | Store user feedback for review |
| `GET /call-summary/{id}` | Retrieve a call analysis report |
| `GET /model-status` | Show trained, implemented, and pending modules |
| `GET /health` | Health and module load status |

`/score-call` accepts `audio_path` only when `CALLSHIELD_DEBUG=true`. Public audio analysis should use `/analyze-audio` file upload.

Deletion endpoints require an admin API key unless `CALLSHIELD_DEMO_MODE=true`:

```powershell
$env:CALLSHIELD_ADMIN_KEY="change-this-secret"
curl -X DELETE http://localhost:8000/call-summary/CALL_ID -H "X-Admin-API-Key: change-this-secret"
```

## Deepfake Training Pipeline

Expected CSV schema:

```csv
audio_path,label,source,speaker_id
/path/to/audio.wav,0,asvspoof2019,bona_fide
/path/to/audio.wav,1,asvspoof2019,spoof
```

Labels:

```text
0 = real
1 = fake
```

CSV paths can be absolute, relative to the CSV file, relative to the project root, or relative to `CALLSHIELD_DATASET_ROOT`.

Portable dataset example:

```powershell
$env:CALLSHIELD_DATASET_ROOT="C:\Users\advit\OneDrive\Desktop\CallShield"
python scripts\prepare_asvspoof.py --root "..\ASVspoof_2019_LA" --out data\deepfake --portable-paths --path-root ".." --split-all
python scripts\validate_deepfake_dataset.py --data data\deepfake
```

Validation reports class balance, duplicate file IDs across splits, speaker overlap, and source overlap. For final metrics, keep `train.csv`, `val.csv`, and `test.csv` separate: train on train, calibrate thresholds on val, and report final metrics on untouched test.

Suggested workflow after datasets finish downloading:

```bash
python scripts/prepare_asvspoof.py --root /path/to/ASVspoof --out data/deepfake --ensure-test-split
python scripts/prepare_wavefake.py --root /path/to/WaveFake --out data/deepfake
python scripts/validate_deepfake_dataset.py --data data/deepfake
python scripts/train_deepfake_mel_cnn.py --data data/deepfake --epochs 20
python scripts/evaluate_deepfake.py --checkpoint models/deepfake_mel_cnn.pt --test data/deepfake/test.csv
```

Dry-run workflow for a small integration pass:

```bash
python scripts/prepare_asvspoof.py --root /path/to/ASVspoof --out data/deepfake --limit 40 --ensure-test-split
python scripts/validate_deepfake_dataset.py --data data/deepfake
python scripts/train_deepfake_mel_cnn.py --data data/deepfake --epochs 1 --batch-size 4 --limit 40
python scripts/evaluate_deepfake.py --checkpoint models/deepfake_mel_cnn.pt --test data/deepfake/test.csv --limit 40
```

Training writes the smoke-test checkpoint to `models/deepfake_mel_cnn.pt`.

## First Trained Deepfake Baseline

The first baseline is meant to prove the pipeline, not production-grade detection. Keep these metrics separate from scam NLP / conversation-risk metrics:

- Scam NLP evaluation: `python main.py test`
- Deepfake audio evaluation: `python scripts/evaluate_deepfake.py --checkpoint models/deepfake_mel_cnn.pt --test data/deepfake/test.csv`
- Combined fusion behavior: verify `/model-status` and `used_in_fusion` after the checkpoint loads

Evaluation writes deepfake audio metrics to `reports/deepfake_eval_v2_3_5.json` by default. Watch accuracy, precision, recall, F1, ROC-AUC, false positive rate, false negative rate, and the confusion matrix.

## Evaluation Summary

Do not call the ASVspoof 2021 random/fine-tune split external validation. It is same-domain held-out validation. External or cross-domain validation means the model is trained on one domain and tested on a different domain.

| Evaluation | Accuracy | F1 | ROC-AUC | EER | FPR |
|------------|----------|----|---------|-----|-----|
| Scam NLP conversation risk | 94.0% | 93.8% | n/a | n/a | 2.0% |
| Deepfake CNN - 2019 checkpoint on 2019 test | 94.4% | 96.2% | 98.3% | 5.6% | 10.4% |
| Deepfake CNN - 2019 checkpoint on 2021 test | 72.8% | 76.6% | 81.6% | 25.8% | 43.6% |
| Deepfake CNN - 2021 same-domain fine-tuned | 98.0% | 98.7% | 99.8% | 2.1% | 3.9% |
| Deepfake CNN - 2021 fine-tuned on 2019 test | 95.8% | 97.1% | 99.2% | 4.2% | 3.9% |
| Deepfake CNN - 2021 balanced test | 97.4% | 97.4% | 99.8% | 1.9% | 3.9% |

Current scam NLP rule evaluation is separate from audio metrics: about 94% accuracy, 97.8% precision, 90% recall, 93.8% F1, and about 2% false-positive rate on the local scenario set.

Honest claim: CallShield is trained and calibrated on ASVspoof 2019/2021 data. It is not yet validated on real phone-call audio, noisy WhatsApp/VoIP calls, or in-the-wild scam calls.

Canonical report files:

```text
models/model_manifest.json
reports/deepfake_internal_2019.json
reports/deepfake_cross_domain_2019_to_2021.json
reports/deepfake_2021_same_domain.json
reports/deepfake_eval_2019_checkpoint_on_2019_test.json
reports/deepfake_eval_2019_checkpoint_on_2021_test.json
reports/deepfake_eval_2021_finetuned_on_2019_test.json
reports/deepfake_eval_2021_finetuned_on_2021_test.json
reports/deepfake_eval_2021_balanced.json
reports/deepfake_cross_domain_summary.json
reports/deepfake_final_summary.json
```

Product rule: deepfake audio should support fusion, not dominate it. A high deepfake score with low scam-language risk should stay a soft warning; strong warnings need scam behavior or multiple corroborating signals.

## RTX 3050 GPU Training

For an NVIDIA RTX 3050 laptop, install the CUDA PyTorch wheel inside the activated virtual environment:

```powershell
python -m pip install --force-reinstall torch==2.2.0 torchaudio==2.2.0 --index-url https://download.pytorch.org/whl/cu121
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'cpu')"
```

Then run a balanced GPU baseline:

```powershell
python scripts\prepare_asvspoof.py --root "..\ASVspoof_2019_LA" --out data\deepfake --limit 5000 --balanced --ensure-test-split
python scripts\validate_deepfake_dataset.py --data data\deepfake
python scripts\train_deepfake_mel_cnn.py --data data\deepfake --epochs 10 --batch-size 32 --limit 5000 --device cuda --amp --num-workers 2
python scripts\evaluate_deepfake.py --checkpoint models\deepfake_mel_cnn.pt --test data\deepfake\test.csv --limit 1000 --device cuda --amp --num-workers 2 --out-json reports\deepfake_eval_v2_3_5_gpu_test_5000.json
```

If the laptop runs out of GPU memory, reduce `--batch-size` to `16`. If Windows multiprocessing acts up, set `--num-workers 0`.

## VS Code Workflow

Open the `callshield-ai` folder in VS Code, then use `Terminal > Run Task...`.

Recommended order:

```text
CallShield: create venv
CallShield: install requirements
CallShield: install torch CUDA 12.1
CallShield: check CUDA
v2.3.5: full deepfake smoke pipeline
CallShield: model status SDK
CallShield: server
CallShield: model status API
```

For parallel work, run:

```text
v2.3.5: parallel audio train + scam NLP eval
```

This trains the deepfake audio smoke run while evaluating the scam NLP rules. The current repo does not yet contain a trainable scam NLP model, so there are not two trainable model families to optimize in parallel yet.

## Tests

```bash
python3 -m compileall -q .
python3 -m pytest -q
python3 main.py test
```

## Privacy-First Design

- No raw audio stored by default
- Phone numbers can be hashed before storage
- Speaker enrollment requires consent
- Uploaded audio is written to a temporary file and deleted after analysis
- Transcripts are stored only when `STORE_TRANSCRIPTS=true`
- High-risk calls recommend safe callback and independent verification

## License

MIT License - Hackathon/Research Use

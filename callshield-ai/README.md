# CallShield AI v2.3.4 - Deepfake Calibration Patch

> Caller ID tells you who might be calling. CallShield tells you whether the conversation is becoming dangerous.

CallShield is a real-time scam call intelligence layer. It analyzes call conversations for scam behavior such as urgency, coercion, money demands, secrecy pressure, and identity manipulation.

## Current Model Status

| Module | Status |
|--------|--------|
| Scam language NLP | Implemented |
| Risk fusion | Implemented |
| Calibration | Implemented |
| Challenge prompts | Implemented |
| Privacy layer | Implemented |
| ASR | Available when Whisper is installed |
| Deepfake audio | First baseline trained, calibrated threshold active |
| Speaker verification | Placeholder |

The deepfake pipeline includes log-mel feature extraction, a CNN architecture, API integration, training scripts, GPU training, external ASVspoof 2021 validation, and a calibrated fusion threshold.

## Deepfake Model Status

Deepfake model status: untrained until checkpoint is trained.

Before `models/deepfake_mel_cnn.pt` exists, CallShield reports `pipeline_implemented_no_trained_model`, returns `deepfake_score: null`, and keeps `used_in_fusion: false`. After a checkpoint is trained and loaded, CallShield reports `trained_model_loaded`.

The deployed baseline uses `models/deepfake_mel_cnn.pt` with `models/deepfake_calibration.json`. The current conservative operating threshold is `0.9683`, selected from ASVspoof 2021 external validation at target FPR <= 10%. Scores below that threshold are reported as raw model scores but do not boost the deepfake fusion signal.

## Quick Start

```bash
cd callshield-ai
pip install -r requirements.txt
python3 main.py server
```

Open [http://localhost:8000/demo](http://localhost:8000/demo) for the dashboard.

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

Suggested workflow after datasets finish downloading:

```bash
python scripts/prepare_asvspoof.py --root /path/to/ASVspoof --out data/deepfake
python scripts/prepare_wavefake.py --root /path/to/WaveFake --out data/deepfake
python scripts/validate_deepfake_dataset.py --data data/deepfake
python scripts/train_deepfake_mel_cnn.py --data data/deepfake --epochs 20
python scripts/evaluate_deepfake.py --checkpoint models/deepfake_mel_cnn.pt --test data/deepfake/test.csv
```

Dry-run workflow for a small integration pass:

```bash
python scripts/prepare_asvspoof.py --root /path/to/ASVspoof --out data/deepfake --limit 40
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

Evaluation writes deepfake audio metrics to `reports/deepfake_eval_v2_3_3.json` by default. Watch accuracy, precision, recall, F1, ROC-AUC, false positive rate, false negative rate, and the confusion matrix.

## RTX 3050 GPU Training

For an NVIDIA RTX 3050 laptop, install the CUDA PyTorch wheel inside the activated virtual environment:

```powershell
python -m pip install --force-reinstall torch==2.2.0 torchaudio==2.2.0 --index-url https://download.pytorch.org/whl/cu121
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'cpu')"
```

Then run a balanced GPU baseline:

```powershell
python scripts\prepare_asvspoof.py --root "..\ASVspoof_2019_LA" --out data\deepfake --limit 5000 --balanced
python scripts\validate_deepfake_dataset.py --data data\deepfake
python scripts\train_deepfake_mel_cnn.py --data data\deepfake --epochs 10 --batch-size 32 --limit 5000 --device cuda --amp --num-workers 2
python scripts\evaluate_deepfake.py --checkpoint models\deepfake_mel_cnn.pt --test data\deepfake\val.csv --limit 1000 --device cuda --amp --num-workers 2 --out-json reports\deepfake_eval_v2_3_3_gpu_val_5000.json
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
v2.3.4: full deepfake smoke pipeline
CallShield: model status SDK
CallShield: server
CallShield: model status API
```

For parallel work, run:

```text
v2.3.4: parallel audio train + scam NLP eval
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

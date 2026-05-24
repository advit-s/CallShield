# CallShield AI Codebase Audit Report

Audit date: 2026-05-23  
Auditor role: senior software engineer, ML engineer, security reviewer, and product auditor  
Scope: full `callshield-ai` application, scripts, docs, dashboard, Android PoC, model metadata, and repository structure visible from `C:\Users\advit\OneDrive\Desktop\CallShield`

No fixes were implemented. This report is the only project file added by this audit.

## 1. Executive Summary

CallShield AI is a credible hackathon/prototype system with a working FastAPI backend, SDK, rule-based scam-language engine, calibrated risk fusion, audio-deepfake inference pipeline, training/evaluation scripts, real-world pilot tooling, an Android microphone-streaming PoC, and a usable dashboard. The default deepfake detector currently reports `trained_model_loaded`, and `/model-status` reports `calibrated` with soft threshold `0.1979` and hard threshold `0.5`.

The strongest technical areas are modularity, evaluation hygiene improvements, no-checkpoint honesty tests, and explicit ASVspoof-only limitation language in the docs. The biggest gaps are production security/privacy controls, environment reproducibility, API hardening, dashboard/backend consistency, audio robustness, and documentation precision around metrics.

The exact requested runtime checks produced mixed results:

- `python -m compileall -q .`: passed using global Python 3.14.3, but it walks the in-project `.venv`.
- `python main.py test`: passed and reported 99.0% accuracy / 100.0% recall / 2.0% FPR on the bundled 100-scenario curated text suite.
- `python -m pytest -q`: failed because the global `python` has no pytest installed.
- `.\.venv\Scripts\python.exe -m pytest -q`: passed, `21 passed in 6.67s`.
- `python main.py server`: failed because global `python` has no `uvicorn`.
- `.\.venv\Scripts\python.exe main.py server`: started successfully and served `/health`, `/model-status`, `/analyze-transcript`, `/analyze-audio`, and `/score-call`.

Readiness summary:

- Hackathon demo: ready with caveats.
- GitHub portfolio: close, after cleanup and documentation fixes.
- Professor/mentor review: ready if limitations are emphasized.
- Startup/incubator pitch: prototype only, not production-ready.
- Truecaller-style outreach: usable as an honest internship/prototype pitch, not as a production claim.
- Production deployment: not ready.

## 2. What Works Well

- The backend starts correctly under the local virtualenv and exposes the intended FastAPI endpoints.
- `/model-status` is dynamic and currently reports `deepfake.status = trained_model_loaded`, `calibration_status = calibrated`, `soft_audio_threshold = 0.1979`, `hard_audio_threshold = 0.5`.
- `/score-call` rejects `audio_path` unless `CALLSHIELD_DEBUG=true`.
- Uploaded audio is written to a temporary file and deleted in a `finally` block.
- No-checkpoint deepfake behavior is honest: `deepfake_score = None`, `used_in_fusion = False`.
- The audio pipeline actually implements 16 kHz mono loading, 4-second trim/pad, 128-bin log-mel spectrograms, z-score normalization, and a CNN with adaptive pooling.
- Training/evaluation scripts support CUDA/AMP, Windows-safe default `--num-workers 0`, balanced sampling/evaluation, confusion matrix, FPR/FNR, ROC-AUC, EER, threshold analysis, and JSON reports.
- `scripts/check_deepfake_split_leakage.py` exists and checks duplicate paths, stems, optional audio hashes, speaker overlap, and source overlap.
- Documentation now contains strong limitation language: ASVspoof metrics are not proof of production performance on real phone calls, WhatsApp/VoIP compression, noisy calls, or Hindi/Hinglish in-the-wild scam calls.

## 3. Critical Bugs

### Issue 1: Default documented Python commands do not run the app environment

- severity: critical
- file path: `README.md`
- line number: 47-53, 307-310
- what is wrong: README uses `python3 main.py server`, `python3 -m pytest -q`, and similar commands, but in this workspace `python` resolves to Python 3.14.3 without `pytest` or `uvicorn`. Exact requested commands failed for pytest and server.
- why it matters: A reviewer following the README from this Windows machine cannot start the server or run pytest unless they know to use `.\.venv\Scripts\python.exe`. Also, pinned `torch==2.2.0` is not compatible with Python 3.14, so the unqualified command path is misleading.
- exact recommended fix: Document Python 3.11 as the supported runtime, make all Windows commands use `.\.venv\Scripts\python.exe`, add a Unix/macOS equivalent, and consider adding a `Makefile`, PowerShell task, or `pyproject.toml` script entrypoints.

### Issue 2: Transcript privacy claim is violated through stored audio response explanation

- severity: critical
- file path: `callshield\api\server.py`
- line number: 264, 278, 517-530
- what is wrong: `/analyze-audio` appends `transcript[:100]` to the response `explanation`, then stores the whole response via `store_call(...)`. This means transcript text can be retained in `CALL_HISTORY` even when `STORE_TRANSCRIPTS=false`.
- why it matters: The README says transcripts are stored only when `STORE_TRANSCRIPTS=true`. This is a direct privacy mismatch and can expose sensitive call content in `/call-summary/{id}`.
- exact recommended fix: Remove transcript text from stored result fields by default. Return transcript preview only behind an explicit debug or consent flag, and store it in a separate field that `store_call` omits unless `STORE_TRANSCRIPTS=true`.

### Issue 3: Deletion endpoints are unauthenticated and can delete arbitrary in-memory call data

- severity: critical
- file path: `callshield\api\server.py`
- line number: 430-474
- what is wrong: Anyone who can reach the API can call `DELETE /call-summary/{call_id}` or `DELETE /user-data/{user_id}`. `user_id` is optional for call deletion and there is no authentication, authorization, ownership proof, CSRF protection, or API key.
- why it matters: These endpoints are framed as DPDP-style erasure controls, but exposed deletion without identity verification is a data-integrity and abuse risk.
- exact recommended fix: Gate deletion endpoints behind auth, require ownership verification, require an API key in local demo mode at minimum, and keep the current unauthenticated behavior only under an explicit `CALLSHIELD_DEMO_MODE=true`.

## 4. High-Priority Fixes

### Issue 4: CORS is wide open with credentials enabled

- severity: high
- file path: `callshield\api\server.py`
- line number: 73-79
- what is wrong: `allow_origins=["*"]` and `allow_credentials=True` are enabled together.
- why it matters: This is unsafe for any non-local deployment and can allow browser-based misuse once auth or cookies are introduced.
- exact recommended fix: Default CORS to localhost/dashboard origins only, make allowed origins configurable, and disable credentials unless a real auth flow requires them.

### Issue 5: `/analyze-audio` has no upload size or content validation

- severity: high
- file path: `callshield\api\server.py`
- line number: 218-240
- what is wrong: The endpoint reads the whole uploaded file into memory with `await audio.read()`, writes it as `.wav` regardless of actual content, and does not enforce size, duration, MIME type, extension, or decode safety limits.
- why it matters: A large upload can exhaust memory or disk; malformed files can trigger slow decoder paths or noisy errors.
- exact recommended fix: Enforce maximum request size, allowed content types/extensions, decode duration caps, streaming writes, and clear 4xx errors for invalid uploads.

### Issue 6: `/analyze-audio` loads Whisper on every request

- severity: high
- file path: `callshield\api\server.py`
- line number: 231-245
- what is wrong: `ASRTranscriber(model_name="base")` is instantiated per request. During live testing, the server printed `Loaded Whisper model: base` and the audio request took about 7.9 seconds for a 1-second silence file.
- why it matters: Per-request model loading makes the API too slow for real-time call monitoring and can cause memory churn.
- exact recommended fix: Load ASR once at startup or lazily cache a singleton, expose ASR status separately, and allow audio-only deepfake analysis without ASR when transcript is not needed.

### Issue 7: Deepfake inference analyzes only one centered 4-second window

- severity: high
- file path: `callshield\engine\audio_features.py`
- line number: 56-66
- what is wrong: Longer audio is center-cropped to 4 seconds; it is not chunked/slid across the full file. Android sends 5-second chunks, so even those are center-cropped.
- why it matters: A scam or synthetic segment outside the center window is ignored by the deepfake detector. This is especially risky for uploaded calls or live chunks.
- exact recommended fix: Implement sliding 4-second windows with overlap and aggregate scores using max/top-k/percentile, while keeping the current 4-second preprocessing for each window.

### Issue 8: No speech/silence guard before deepfake fusion

- severity: high
- file path: `callshield\engine\deepfake.py`
- line number: 180-203
- what is wrong: The detector runs on silence/no-speech audio. In the live audit, a generated 1-second silence WAV returned `deepfake_score: 1.0`, `audio_signal_strength: strong`, and `used_in_fusion: true`.
- why it matters: Silence or invalid audio can produce strong synthetic-voice evidence and confusing cues, even though final risk stayed `safe` because audio alone adds only 20 points.
- exact recommended fix: Add RMS/voiced-duration/VAD checks before inference. If speech is absent or too short, return `deepfake_score: null`, `audio_signal_strength: unavailable/no_speech`, and `used_in_fusion: false`.

### Issue 9: Risk formula is inconsistent across implementation, comments, and dashboard

- severity: high
- file path: `callshield\engine\fusion.py`
- line number: 3-9, 76-90, 129-136
- what is wrong: The module docstring says 35/25/20/10/10, comments say scam 35, deepfake 25, identity 20, but actual defaults are scam 45, deepfake 20, identity 15, urgency 10, verification 10.
- why it matters: Product claims, dashboard behavior, and reports can drift from actual scoring.
- exact recommended fix: Make a single exported weight profile and use it in README, dashboard simulation, API status, tests, and docs.

### Issue 10: Dashboard simulation uses stale fusion weights

- severity: high
- file path: `callshield\dashboard\index.html`
- line number: 538
- what is wrong: Simulated risk uses `0.35*scam + 0.25*df + 0.20*id + 0.10*urgency`, not the backend's current `0.45/0.20/0.15/0.10/0.10` profile plus rule bonus.
- why it matters: The demo can show risk behavior that does not match the backend.
- exact recommended fix: Fetch backend weights from `/model-status` or embed the current shared constants in a generated JSON config.

### Issue 11: `torch.load` is used on model files without runtime trust checks

- severity: high
- file path: `callshield\engine\deepfake.py`
- line number: 109-118
- what is wrong: PyTorch checkpoint loading uses pickle-backed `torch.load` without verifying the file hash from `models/model_manifest.json` and without `weights_only=True` where compatible.
- why it matters: Loading an untrusted or replaced `.pt` file can execute arbitrary code.
- exact recommended fix: Verify SHA-256 before loading the deployed checkpoint, restrict model paths in production, and use `torch.load(..., weights_only=True)` if the target PyTorch version supports it.

### Issue 12: Phone hashing uses a hard-coded static salt and truncates the digest

- severity: high
- file path: `callshield\engine\privacy.py`
- line number: 18-26
- what is wrong: The salt is hard-coded as `callshield_salt_v1` and the SHA-256 hash is truncated to 32 hex characters.
- why it matters: A static public salt permits offline dictionary attacks against phone numbers.
- exact recommended fix: Use an environment-provided secret pepper and HMAC-SHA256. Do not truncate unless there is a documented collision-risk decision.

### Issue 13: Speaker enrollment response claims an embedding is stored when none is created

- severity: high
- file path: `callshield\api\server.py`
- line number: 378-393
- what is wrong: `/verify-speaker` returns `status="enrolled"` and `embedding_stored=True`, but no audio, embedding extraction, persistence, or deletion linkage exists.
- why it matters: This overstates biometric functionality and privacy state.
- exact recommended fix: Rename the endpoint to consent registration or return `status="placeholder"` until actual enrollment exists. Do not claim `embedding_stored=True` without storage and erasure support.

## 5. Medium-Priority Improvements

### Issue 14: API schema for `/analyze-audio` is misleading and unused

- severity: medium
- file path: `callshield\api\schemas.py`
- line number: 39-44
- what is wrong: `AudioRequest` suggests JSON request fields, but `/analyze-audio` actually requires query parameter `call_id` and multipart field `audio`.
- why it matters: API users will send the wrong shape; this happened during audit when posting `call_id` and `file` as form fields returned 422.
- exact recommended fix: Document the multipart shape in README/OpenAPI examples, remove unused `AudioRequest`, or expose a JSON metadata field alongside the upload.

### Issue 15: Error details expose internal exception text

- severity: medium
- file path: `callshield\api\server.py`
- line number: 214-215, 281-282, 356-357
- what is wrong: API exceptions include raw `str(e)` in JSON responses.
- why it matters: File paths, dependency errors, decoder details, or model internals can leak to clients.
- exact recommended fix: Return stable user-safe error codes/messages and log detailed exceptions server-side only.

### Issue 16: Safe calls can still return scam cues and contradictory `why_flagged`

- severity: medium
- file path: `callshield\sdk\callshield.py`
- line number: 155-169, 178-209
- what is wrong: Benign context can reduce risk to `safe`, but `why_flagged` may still say "Caller uses police or legal threats" or similar. A tested benign example, "The police station called, your lost wallet is ready for pickup", scored safe but still had police/legal cue text.
- why it matters: Users and dashboard panels may see a safe band with accusatory explanations.
- exact recommended fix: If calibrated band is `safe`, make `why_flagged` neutral or include "matched weak cue but benign context lowered risk" explicitly.

### Issue 17: Explanation builder repeats duplicate cue explanations

- severity: medium
- file path: `callshield\sdk\callshield.py`
- line number: 180-207
- what is wrong: Multiple cues from one category produce repeated sentences, e.g. bank/KYC or police/legal examples repeat the same sentence three times.
- why it matters: Repetition looks unpolished and reduces trust in the explanation layer.
- exact recommended fix: Deduplicate explanation categories before rendering `why_flagged`.

### Issue 18: `remote_access_request` exists as a scam type but has no standalone pattern category

- severity: medium
- file path: `callshield\engine\scam_nlp.py`
- line number: 12-23, 45-136, 364-374
- what is wrong: `REMOTE_ACCESS_REQUEST` is defined, but `PATTERNS` has no `remote_access_request` category. Remote access phrases are folded into `tech_support_scam`.
- why it matters: Category-level reporting cannot distinguish "install AnyDesk / share screen" from general tech support impersonation.
- exact recommended fix: Add a separate `remote_access_request` pattern category and update scoring/classification tests.

### Issue 19: Scam NLP metrics are reported as 99% without labeling the suite as curated

- severity: medium
- file path: `README.md`
- line number: 227-240
- what is wrong: README lists "Scam NLP conversation risk" as 99% accuracy/F1 with 2% FPR. The user-provided project context says known current text metrics are around 94% accuracy, 90% recall, 0.978 precision, and 0.938 F1.
- why it matters: Reviewers may read the curated 100-scenario score as a general NLP benchmark.
- exact recommended fix: Label `python main.py test` as "curated scenario suite" and separately report any broader text-scam benchmark. Do not combine or replace the older metric context without explaining the dataset change.

### Issue 20: `main.py demo` is documented but not implemented

- severity: medium
- file path: `main.py`
- line number: 6-10, 81-87, 94-104
- what is wrong: Help text advertises `python3 main.py demo`, but running `python main.py demo` prints "Unknown command: demo".
- why it matters: Demo commands fail during review.
- exact recommended fix: Implement `demo` to print/open `http://localhost:8000/demo`, or remove the command from help.

### Issue 21: FastAPI reload is always enabled in `main.py server`

- severity: medium
- file path: `main.py`
- line number: 34-40
- what is wrong: `uvicorn.run(..., reload=True)` is always used.
- why it matters: Reload is useful for development but not for stable demos, Windows process control, or production.
- exact recommended fix: Make reload opt-in with `CALLSHIELD_RELOAD=true` or `--reload`.

### Issue 22: ASR tensor path leaks a temporary file

- severity: medium
- file path: `callshield\engine\asr.py`
- line number: 51-60
- what is wrong: Tensor input is saved with `delete=False` and not removed.
- why it matters: Repeated tensor transcription can leak temp audio files.
- exact recommended fix: Use `try/finally` to unlink the temp file, or use a temporary directory context.

### Issue 23: Real-world pilot script stores transcript preview by default

- severity: medium
- file path: `scripts\run_real_world_audio_test.py`
- line number: 207-215, 249
- what is wrong: The script says full transcripts are omitted unless requested, but it always stores `transcript_preview` up to 180 characters.
- why it matters: A 180-character preview can still contain OTPs, phone numbers, names, or sensitive call content.
- exact recommended fix: Default `transcript_preview` to empty unless `--include-transcript-preview` is passed; keep only hashes or labels by default.

### Issue 24: `prepare_asvspoof.py` silently overwrites duplicate audio stems

- severity: medium
- file path: `scripts\prepare_asvspoof.py`
- line number: 21-26
- what is wrong: `find_audio_files` returns a dict keyed by `path.stem`, so duplicate stems across directories overwrite earlier files.
- why it matters: ASVspoof-style datasets can contain repeated identifiers across parts/splits; silent overwrite can mislabel or drop examples.
- exact recommended fix: Map stem to a list of paths, resolve using protocol split/directory context, and report duplicate stems.

### Issue 25: WaveFake split can leak speaker/source characteristics

- severity: medium
- file path: `scripts\prepare_wavefake.py`
- line number: 53-63, 142-154
- what is wrong: Rows are randomly split without speaker grouping; `speaker_id` is always `unknown`.
- why it matters: Same speaker/content/generator family can appear across train/val/test, inflating metrics.
- exact recommended fix: Support metadata-based split keys and warn when speaker/source/generator metadata is missing.

### Issue 26: Evaluation EER is approximate and threshold-only

- severity: medium
- file path: `scripts\evaluate_deepfake.py`
- line number: 179-192
- what is wrong: EER is computed by scanning observed thresholds and averaging FPR/FNR at the closest point, without interpolation.
- why it matters: Reported EER is acceptable for prototype reporting but should be labeled approximate.
- exact recommended fix: Use `sklearn.metrics.det_curve` or ROC interpolation and label old reports as threshold-grid EER.

### Issue 27: Training script does not save a full training history report

- severity: medium
- file path: `scripts\train_deepfake_mel_cnn.py`
- line number: 378-411
- what is wrong: The best checkpoint stores final selected metrics, but there is no separate JSON/CSV history of per-epoch train/validation metrics.
- why it matters: Reproducibility and model comparison are harder.
- exact recommended fix: Add `--out-report reports/deepfake_train_*.json` with args, seed, class counts, per-epoch metrics, best epoch, and checkpoint hash.

### Issue 28: Runtime model manifest is not used by the app

- severity: medium
- file path: `models\model_manifest.json`
- line number: 1
- what is wrong: The manifest contains checkpoint/calibration hashes and limitations, but the runtime does not verify or expose this manifest.
- why it matters: The app can claim the deployed checkpoint is canonical even if the file changes.
- exact recommended fix: Load the manifest at startup, verify hashes, and expose manifest summary in `/model-status`.

## 6. Low-Priority Cleanup

### Issue 29: Stale archive, frontend, and temp files remain in the codebase

- severity: low
- file path: `archives\`, `frontend\index.html`, `web\index.html.tmp.17462.316ea19cf110`
- line number: n/a
- what is wrong: `archives` contains old app/audio/nlp/fusion code, `frontend/index.html` is an older simulation-only dashboard, and `web` contains a temp HTML file. They are not referenced by README, server, or imports.
- why it matters: Reviewers can confuse stale code with active code.
- exact recommended fix: Keep archives only if deliberately documented, move old demos under `archives/frontend/`, and delete or gitignore temp files after confirming they are not needed.

### Issue 30: No top-level `callshield\__init__.py`

- severity: low
- file path: `callshield\`
- line number: n/a
- what is wrong: Subpackages have `__init__.py`, but the root package does not.
- why it matters: Namespace packages work in modern Python, but explicit packaging is clearer for distribution and tests.
- exact recommended fix: Add a minimal `callshield\__init__.py` when packaging work begins.

### Issue 31: Import style still relies on path hacks in several scripts/tests

- severity: low
- file path: `main.py`, `scripts\*.py`, `callshield\tests\test_evaluation.py`
- line number: `main.py` 14-16; `callshield\tests\test_evaluation.py` 17-21
- what is wrong: Multiple files mutate `sys.path` for imports.
- why it matters: This is common in prototypes but fragile once packaged.
- exact recommended fix: Add packaging metadata and run code as modules, e.g. `python -m callshield...`.

### Issue 32: `.gitignore` is too small for a Python/ML repo

- severity: low
- file path: `.gitignore`
- line number: 1-3
- what is wrong: It ignores only `.claude` and ASVspoof roots. It does not document ignores for `.venv`, `__pycache__`, `.pytest_cache`, generated reports, temp files, or large model checkpoints.
- why it matters: Large or generated artifacts can be accidentally staged.
- exact recommended fix: Add standard Python/ML ignores while explicitly deciding which reports/models should be tracked or moved to Git LFS.

## 7. Security & Privacy Review

### Confirmed good behavior

- `/score-call` securely rejects `audio_path` unless `CALLSHIELD_DEBUG=true`: `callshield\api\server.py` 304-309.
- `/analyze-audio` deletes its temporary upload in `finally`: `callshield\api\server.py` 284-287.
- Transcript storage is opt-in in `store_call`: `callshield\api\server.py` 527-530, but see the critical transcript-preview issue above.
- Speaker enrollment requires explicit `consent_given=true`: `callshield\api\server.py` 381-387.
- Server logs observed during audit did not include raw transcript text, but warnings exposed internal exception text.

### Main risks

- severity: critical; file path: `callshield\api\server.py`; line number: 264, 278, 517-530; issue: transcript preview is stored through `explanation`; fix: remove transcript from stored result unless explicitly enabled.
- severity: critical; file path: `callshield\api\server.py`; line number: 430-474; issue: unauthenticated deletion endpoints; fix: add auth and ownership checks.
- severity: high; file path: `callshield\api\server.py`; line number: 73-79; issue: permissive CORS; fix: restrict origins.
- severity: high; file path: `callshield\engine\privacy.py`; line number: 18-26; issue: hard-coded phone hash salt; fix: HMAC with secret.
- severity: high; file path: `callshield\api\server.py`; line number: 218-240; issue: upload size/type not validated; fix: enforce caps and content checks.
- severity: medium; file path: `callshield\dashboard\index.html`; line number: 496-506, 596-600; issue: backend-derived content is inserted with `innerHTML`; fix: use `textContent` and explicit DOM nodes.
- severity: medium; file path: `scripts\run_real_world_audio_test.py`; line number: 213-214; issue: transcript previews stored by default; fix: make previews opt-in.

## 8. ML/Deepfake Model Review

### Confirmed implementation

- 16 kHz mono: `callshield\engine\audio_features.py` 34-54.
- 4-second trim/pad: `callshield\engine\audio_features.py` 56-66.
- 128-bin log-mel: `callshield\engine\audio_features.py` 34-40, 68-79.
- z-score normalization: `callshield\engine\audio_features.py` 81-83.
- CNN with adaptive pooling: `callshield\engine\deepfake.py` 42-60.
- Missing torch/librosa handling: `callshield\engine\deepfake.py` 13-33, 171-178.
- Checkpoint loading: `callshield\engine\deepfake.py` 107-118.
- Calibration loading: `callshield\engine\deepfake.py` 134-148.
- No-checkpoint behavior: `callshield\engine\deepfake.py` 155-169.

### Threshold honesty

- `0.1978759765625` should be described as a high-recall / target-FPR soft threshold, not as a balanced operating threshold.
- `0.5` is the hard/balanced/default threshold used for strong deepfake evidence.
- Current code implements this: below soft ignored, soft-to-hard weak, hard-and-above strong: `callshield\engine\deepfake.py` 189-203.

### ML issues and fixes

- severity: high; file path: `callshield\engine\audio_features.py`; line number: 56-66; issue: only one centered 4-second crop is used; why it matters: misses most of long audio; fix: sliding windows plus aggregation.
- severity: high; file path: `callshield\engine\deepfake.py`; line number: 180-203; issue: no speech/silence guard; why it matters: silence scored as strong synthetic in audit; fix: add VAD/RMS/min voiced duration.
- severity: high; file path: `callshield\engine\deepfake.py`; line number: 109-118; issue: no checkpoint hash verification; why it matters: model tampering and pickle risk; fix: verify manifest hash and use safer loading.
- severity: medium; file path: `callshield\engine\deepfake.py`; line number: 96-101; issue: no-checkpoint path still allocates a random CNN if torch exists; why it matters: unnecessary startup/GPU memory; fix: keep `model=None` until a checkpoint is present.
- severity: medium; file path: `android\CallShieldMobile\app\src\main\java\ai\callshield\mobile\AudioChunkStreamer.java`; line number: 19-24; issue: Android captures 5-second chunks while model crops to 4 seconds; why it matters: inconsistent live demo behavior; fix: use 4-second chunks or backend sliding aggregation.

## 9. Scam NLP Review

### Category coverage

- family emergency: implemented in `callshield\engine\scam_nlp.py` 47-53.
- UPI/payment request: implemented in `callshield\engine\scam_nlp.py` 101-108.
- OTP/PIN/password request: implemented in `callshield\engine\scam_nlp.py` 94-100.
- bank/KYC fraud: implemented in `callshield\engine\scam_nlp.py` 54-62.
- police/legal threat: implemented in `callshield\engine\scam_nlp.py` 63-72.
- tech support scam: implemented in `callshield\engine\scam_nlp.py` 73-82.
- job/investment scam: implemented in `callshield\engine\scam_nlp.py` 83-93.
- remote access scam: partially implemented inside tech support patterns, but not as a standalone category.
- secrecy pressure: implemented in `callshield\engine\scam_nlp.py` 110-118.
- alternate number claim: implemented in `callshield\engine\scam_nlp.py` 119-126.

### Combination logic

The engine is better than simple keyword matching. It has category scores, benign-context penalties, financial keyword boosts, multi-signal boosts, and explicit false-negative patches: `callshield\engine\scam_nlp.py` 169-337. However, it is still a handcrafted rule engine and should be described that way.

### Tested missed examples

The exact examples requested are now detected at least as suspicious:

- "device compromised + install software": 58.2, suspicious, soft, `tech_support_scam`.
- "work from home + earn + no risk": 46.5, suspicious, soft, `job_investment_scam`.
- "account credited + if this is not you": 75.0, high, soft, `bank_kyc_fraud`.
- "final warning + illegal activity": 65.5, high, soft, `police_legal_threat`.
- "keep very quiet + do not mention": 41.5, suspicious, soft, `secrecy_pressure`.

### False negative risks

- severity: medium; file path: `callshield\engine\scam_nlp.py`; line number: 45-136; what is wrong: missing common India scam variants such as "digital arrest", courier/FedEx parcel, TRAI/SIM deactivation, loan app recovery threats, Telegram task scam, QR collect request, refund reversal, and fake customer-care callback; why it matters: real scam language is broader than the curated suite; exact recommended fix: add regression cases first, then rules for these phrases with combination requirements.
- severity: medium; file path: `callshield\engine\scam_nlp.py`; line number: 73-82; what is wrong: remote access is not separately modeled; why it matters: product explanations lose specificity; exact recommended fix: separate `remote_access_request` category.

### False positive risks

- severity: medium; file path: `callshield\engine\scam_nlp.py`; line number: 119-126, 317-323; what is wrong: benign alternate-number claims still trigger suspicious risk; why it matters: `main.py test` had one false positive from this pattern; exact recommended fix: require urgency/payment/secrecy before alternate number becomes suspicious.
- severity: medium; file path: `callshield\sdk\callshield.py`; line number: 178-209; what is wrong: safe calls can still produce concerning `why_flagged`; why it matters: confusing UI; exact recommended fix: align explanation with calibrated band.
- severity: low; file path: `callshield\engine\scam_nlp.py`; line number: 138-153; what is wrong: benign phrases are hand-curated and can overfit the scenario suite; why it matters: brittle behavior; exact recommended fix: maintain a separate benign regression set and report false-positive categories.

## 10. API Review

### Endpoint verification

- `/health`: works under venv; returns status and module booleans.
- `/model-status`: works under venv; reports trained/calibrated deepfake state.
- `/analyze-transcript`: works when `call_id` and `transcript` are supplied.
- `/analyze-audio`: works when `call_id` is a query parameter and multipart field is named `audio`.
- `/score-call`: works for transcript-only requests and rejects `audio_path` with debug disabled.
- `/verify-speaker`: consent check works, but successful enrollment is a placeholder that overclaims storage.
- `/submit-feedback`: requires existing `call_id`, `is_scam`, and optional notes/cues.
- `/call-summary/{id}`: returns in-memory summary.
- delete endpoints: work but need auth/ownership.

### API issues

- severity: high; file path: `callshield\api\server.py`; line number: 218-240; what is wrong: upload validation missing; why it matters: abuse/DoS; exact recommended fix: add size/type/duration caps.
- severity: high; file path: `callshield\api\server.py`; line number: 231-245; what is wrong: ASR model loaded per request; why it matters: too slow; exact recommended fix: singleton/cached model.
- severity: medium; file path: `callshield\api\schemas.py`; line number: 39-44; what is wrong: unused/misleading `AudioRequest`; why it matters: API docs mismatch; exact recommended fix: document multipart request shape.
- severity: medium; file path: `callshield\api\server.py`; line number: 214-215, 281-282, 356-357; what is wrong: raw exception detail returned; why it matters: information leakage; exact recommended fix: stable error responses.

## 11. Dashboard Review

### What works

- The served dashboard at `/demo` exists and loads from `callshield\dashboard\index.html`.
- It clearly shows `Demo Simulation Mode`: line 271-274.
- It fetches `/model-status`: line 590-604.
- Transcript form calls `/analyze-transcript`: line 623-641.
- Audio form calls `/analyze-audio`: line 643-663.
- It shows risk gauge, signal bars, why flagged, transcript area, and backend result.

### Gaps

- severity: high; file path: `callshield\dashboard\index.html`; line number: 538; what is wrong: simulation risk formula is stale; why it matters: demo diverges from backend; exact recommended fix: use backend weights/config.
- severity: medium; file path: `callshield\dashboard\index.html`; line number: 496-506, 596-600; what is wrong: `innerHTML` is used for dynamic content; why it matters: avoid XSS patterns even in local demos; exact recommended fix: use `textContent`.
- severity: medium; file path: `callshield\dashboard\index.html`; line number: 271-300; what is wrong: model status is shown, but there is no dedicated privacy status or evaluation metrics panel; why it matters: user requested privacy/evaluation visibility; exact recommended fix: add privacy status and canonical metrics cards.
- severity: low; file path: `frontend\index.html`; line number: 1; what is wrong: old dashboard duplicate remains; why it matters: confusion; exact recommended fix: archive or remove after preserving if needed.

## 12. Documentation Review

### Good documentation

- README clearly separates scam NLP and deepfake audio metrics in the evaluation table.
- README includes the required limitation: not validated on real phone-call audio, WhatsApp-compressed audio, noisy calls, or Hindi/Hinglish scam-call recordings.
- `docs\REAL_WORLD_TESTING.md` gives consent-focused pilot guidance.
- `docs\ANDROID_POC.md` is honest that Android private in-call capture is restricted.
- `docs\TRUECALLER_INTERNSHIP_BRIEF.md` is generally honest about ASVspoof limitations.

### Documentation issues

- severity: critical; file path: `README.md`; line number: 47-53, 307-310; what is wrong: commands do not match the actual Windows runtime; why it matters: setup fails; exact recommended fix: document `.venv` commands and Python 3.11.
- severity: medium; file path: `README.md`; line number: 152-165; what is wrong: endpoint list does not show `/analyze-audio` query parameter and multipart field name; why it matters: users send wrong requests; exact recommended fix: add curl/PowerShell examples.
- severity: medium; file path: `README.md`; line number: 227-240; what is wrong: curated NLP metrics are not labeled as curated; why it matters: overclaim risk; exact recommended fix: label benchmark source and keep older/broader metrics separate.
- severity: medium; file path: `README.md`; line number: 22-45; what is wrong: "untrained until checkpoint is trained" is historically correct but slightly confusing when the default checkpoint is present; why it matters: readers may miss current deployed status; exact recommended fix: split "Current runtime status" from "No-checkpoint behavior".

## 13. Evaluation Honesty Review

The audio reporting is much more honest than a typical prototype. It includes same-domain, cross-domain, balanced, and limitation notes. The most important caveat remains:

CallShield's audio results are ASVspoof 2019/2021 split results. They are not proof of production performance on real phone calls, WhatsApp/VoIP compression, noisy Indian/Hinglish calls, or in-the-wild scam calls.

### Confirmed evaluation assets

- Cross-domain summary exists: `reports\deepfake_cross_domain_summary.json`.
- Leakage script exists: `scripts\check_deepfake_split_leakage.py`.
- Balanced 2021 report exists: `reports\deepfake_eval_2021_balanced.json`.
- Model manifest exists: `models\model_manifest.json`.

### Evaluation risks

- severity: medium; file path: `data\deepfake_2021_finetune\test.csv`; line number: 1; what is wrong: full 2021 test CSV is highly imbalanced in this workspace: 58,913 fake vs 2,271 real; why it matters: unbalanced metrics can obscure false positives; exact recommended fix: always show balanced metrics next to full-split metrics.
- severity: medium; file path: `scripts\check_deepfake_split_leakage.py`; line number: 120-123; what is wrong: source overlap is reported but not failed, and attack/generator overlap is not checked; why it matters: attack overlap can inflate deepfake results; exact recommended fix: add optional `attack_id`, `codec`, `generator`, and `source_system` overlap checks.
- severity: medium; file path: `reports\deepfake_eval_2021_finetuned_test.json`; line number: 2; what is wrong: older report version says `2.3.3`; why it matters: version drift in report files can confuse canonical claims; exact recommended fix: mark older reports as historical or regenerate with current script/version.

## 14. Recommended v2.3.5 Roadmap

1. Reproducibility pass:
   - Document Python 3.11.
   - Replace README `python3` commands with `.venv`/Unix equivalents.
   - Add `.gitignore` for Python caches, venvs, temp files, and generated local outputs.

2. Privacy/security pass:
   - Remove transcript preview from stored call summaries by default.
   - Add local-demo API key or auth guard for deletion endpoints.
   - Restrict CORS.
   - Replace static phone salt with secret HMAC.

3. API hardening:
   - Add file size/type/duration validation to `/analyze-audio`.
   - Cache ASR model instead of per-request loading.
   - Return clean error codes instead of raw exceptions.
   - Add README examples for multipart upload.

4. Audio robustness:
   - Add no-speech/VAD guard.
   - Add sliding 4-second window aggregation.
   - Verify manifest hash before loading checkpoint.
   - Add tests for silence, short clips, long clips, and corrupted files.

5. Fusion/dashboard consistency:
   - Centralize weight profile.
   - Update fusion docstring, README, dashboard simulation, and tests.
   - Treat weak audio as evidence only when corroborated by language/identity/urgency.

6. Scam NLP regression suite:
   - Add tests for the five requested missed examples.
   - Add benign alternate-number/police/legal/payment counterexamples.
   - Add India-specific scams: digital arrest, courier parcel, SIM deactivation, task scam, loan recovery, QR collect, refund reversal.

7. Documentation honesty:
   - Label `main.py test` as a curated scenario test.
   - Keep scam NLP and deepfake audio metrics separate.
   - Keep the ASVspoof limitation visible in README and outreach docs.

## 15. Recommended v2.4 Product Demo Roadmap

1. Real backend dashboard mode:
   - Add a live mode that uses actual `/score-call` and `/analyze-audio` outputs for every panel.
   - Add model, privacy, and evaluation status cards.
   - Add clear "simulation" vs "live backend" switch.

2. Real-world pilot report:
   - Collect 100+ consented samples across normal, scripted scam, synthetic, compressed, noisy, and Hindi/Hinglish conditions.
   - Report normal-call FPR, scam recall, deepfake soft/hard FPR, ASR failure rate, and failure examples.

3. Audio model hardening:
   - Add telephony bandwidth, re-recording, packet loss, background noise, and WhatsApp/VoIP compression augmentation.
   - Evaluate ASVspoof-trained model on real phone-like pilot audio before making outreach claims.

4. Mobile demo polish:
   - Add explicit consent screen.
   - Add server health/model-status check before recording.
   - Show no-speech/ASR unavailable states.
   - Keep chunk upload but align chunk duration with backend windowing.

5. Product safety:
   - Make warnings conservative and explainable.
   - Ensure deepfake-only evidence produces a voice caution, not a scam verdict.
   - Add feedback flow that stores minimal data and supports deletion with identity checks.

## 16. Exact Commands You Ran

```powershell
rg --files
Get-ChildItem -Force
git status --short
Get-Content -LiteralPath README.md
Get-Content -LiteralPath requirements.txt
Get-Content -LiteralPath main.py
rg --files callshield archives -g "__init__.py"
Get-Content -LiteralPath .gitignore
rg -n "TODO|FIXME|placeholder|Placeholder|pass|NotImplemented|dummy|mock|simulation|Demo Simulation|CALLSHIELD_DEBUG|STORE_TRANSCRIPTS|CORS|allow_origins|audio_path|unlink|delete|hash|consent|speaker|log|print" callshield main.py scripts frontend docs README.md
python --version
python -m compileall -q .
python main.py test
python -m pytest -q
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pytest -q
python main.py server
$env:PORT='8010'; .\.venv\Scripts\python.exe main.py server
Invoke-RestMethod -Uri http://127.0.0.1:8010/health | ConvertTo-Json -Depth 10
Invoke-RestMethod -Uri http://127.0.0.1:8010/model-status | ConvertTo-Json -Depth 10
$body = @{transcript='This is HDFC bank. Your KYC is blocked. Tell me the OTP now.'} | ConvertTo-Json; Invoke-RestMethod -Uri http://127.0.0.1:8010/analyze-transcript -Method Post -ContentType 'application/json' -Body $body | ConvertTo-Json -Depth 10
$body = @{call_id='audit-t1'; transcript='This is HDFC bank. Your KYC is blocked. Tell me the OTP now.'} | ConvertTo-Json; Invoke-RestMethod -Uri http://127.0.0.1:8010/analyze-transcript -Method Post -ContentType 'application/json' -Body $body | ConvertTo-Json -Depth 10
$body = @{call_id='audit-score-path'; transcript='Normal family check-in call'; audio_path='C:\Windows\win.ini'} | ConvertTo-Json; try { Invoke-RestMethod -Uri http://127.0.0.1:8010/score-call -Method Post -ContentType 'application/json' -Body $body | ConvertTo-Json -Depth 10 } catch { $_.ErrorDetails.Message }
$body = @{call_id='audit-score'; transcript='Your account has illegal activity. Final warning. Pay now.'} | ConvertTo-Json; Invoke-RestMethod -Uri http://127.0.0.1:8010/score-call -Method Post -ContentType 'application/json' -Body $body | ConvertTo-Json -Depth 10
.\.venv\Scripts\python.exe -c "import wave, pathlib; p=pathlib.Path('audit_silence.wav'); w=wave.open(str(p),'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(b'\x00\x00'*16000); w.close(); print(p.resolve())"
curl.exe -s -X POST -F "audio=@audit_silence.wav;type=audio/wav" "http://127.0.0.1:8010/analyze-audio?call_id=audit-audio"
Remove-Item -LiteralPath .\audit_silence.wav
Invoke-RestMethod -Uri http://127.0.0.1:8010/call-summary/audit-t1 | ConvertTo-Json -Depth 10
Invoke-RestMethod -Uri http://127.0.0.1:8010/call-summary/audit-t1 -Method Delete | ConvertTo-Json -Depth 10
try { Invoke-RestMethod -Uri http://127.0.0.1:8010/call-summary/audit-t1 | ConvertTo-Json -Depth 10 } catch { $_.ErrorDetails.Message }
$body = @{speaker_id='audit-speaker'; name='Audit User'; consent_given=$false} | ConvertTo-Json; try { Invoke-RestMethod -Uri http://127.0.0.1:8010/verify-speaker -Method Post -ContentType 'application/json' -Body $body | ConvertTo-Json -Depth 10 } catch { $_.ErrorDetails.Message }
Stop-Process -Id 74504,81940 -Force
rg -n "^" callshield\api\server.py
rg -n "^" callshield\api\schemas.py
rg -n "^" callshield\sdk\callshield.py
rg -n "^" callshield\engine\privacy.py
rg -n "^" callshield\engine\scam_nlp.py
rg -n "^" callshield\engine\fusion.py
rg -n "^" callshield\engine\calibration.py
rg -n "^" callshield\engine\deepfake.py
rg -n "^" callshield\engine\audio_features.py
rg -n "^" callshield\engine\asr.py
rg -n "^" scripts\train_deepfake_mel_cnn.py
rg -n "^" scripts\evaluate_deepfake.py
rg -n "^" scripts\check_deepfake_split_leakage.py
rg -n "^" scripts\prepare_asvspoof.py
rg -n "^" scripts\prepare_wavefake.py
rg -n "^" scripts\validate_deepfake_dataset.py
rg -n "^" callshield\engine\dataset_paths.py
Get-Content -LiteralPath models\deepfake_calibration.json
Get-Content -LiteralPath models\model_manifest.json
Get-Content -LiteralPath reports\deepfake_eval_2021_finetuned_test.json
Get-Content -LiteralPath reports\deepfake_leakage_2019_test.json
rg -n "^" callshield\tests\test_api.py
rg -n "^" callshield\tests\test_deepfake_status.py
rg -n "^" callshield\tests\test_evaluation.py
rg -n "^" callshield\tests\test_dataset_paths.py
rg -n "Demo Simulation|fetch\(|analyze-transcript|analyze-audio|score-call|model-status|health|upload|audio|metrics|deepfake|privacy|transcript|flagged|signal|backend|API|localhost|eval|ASVspoof|STORE|delete|phone|risk|onclick|addEventListener" callshield\dashboard\index.html
rg -n "^" callshield\dashboard\index.html
Get-Content -LiteralPath docs\REAL_WORLD_TESTING.md
Get-Content -LiteralPath docs\TRUECALLER_INTERNSHIP_BRIEF.md
Get-Content -LiteralPath docs\ANDROID_POC.md
rg -n "http|SERVER|analyze-audio|privacy|RECORD_AUDIO|INTERNET|chunk|delete|log|Log\.|TODO|FIXME|consent|Start|Stop" android\CallShieldMobile\app\src\main\java android\CallShieldMobile\app\src\main\AndroidManifest.xml android\CallShieldMobile\README.md
rg -n "^" android\CallShieldMobile\app\src\main\java\ai\callshield\mobile\CallShieldApiClient.java
rg -n "^" android\CallShieldMobile\app\src\main\java\ai\callshield\mobile\AudioChunkStreamer.java
rg -n "^" android\CallShieldMobile\app\src\main\java\ai\callshield\mobile\MainActivity.java
rg -n "speechbrain|transformers|torchaudio|pydantic_settings|pydantic-settings|websockets|matplotlib|pandas|soundfile|librosa|torch|fastapi|uvicorn|multipart|httpx|tqdm|sklearn|whisper" callshield scripts android README.md docs requirements.txt
python main.py demo
.\.venv\Scripts\python.exe -c "from callshield.sdk import CallShieldSDK; sdk=CallShieldSDK(); cases=['Your device is compromised. Install this software now to protect your account.','Work from home and earn 5000 per day. No risk, no investment.','Your account has been credited with Rs 50000. If this is not you, provide card details now.','This is the final warning. Your number is linked to illegal activity.','Keep this very quiet. Do not mention it to anyone.','I lost my phone and I am calling from a new number. Let us catch up later.','Please send school fees urgently; pay when convenient.','The police station called, your lost wallet is ready for pickup.']; for text in cases: r=sdk.analyze_transcript(text); print('---'); print(text); print(r.risk_score, r.risk_band, r.warning_level, r.scam_type, r.detected_cues, r.why_flagged)"
.\.venv\Scripts\python.exe -c "from callshield.sdk import CallShieldSDK; sdk=CallShieldSDK(); for s in [0.2,0.4,0.7,1.0]: r=sdk.analyze_transcript('Hi beta, how are you?', audio_deepfake_score=s); print(s, r.risk_score, r.risk_band, r.warning_level, r.detected_cues, r.why_flagged)"
(Import-Csv data\deepfake_2021_finetune\test.csv | Group-Object label | Select-Object Name,Count) | ConvertTo-Json
(Import-Csv data\deepfake\test.csv | Group-Object label | Select-Object Name,Count) | ConvertTo-Json
Get-Content -LiteralPath reports\deepfake_eval_2021_balanced.json
Get-Content -LiteralPath reports\deepfake_cross_domain_summary.json
git status --short
```

One command attempted to write a temp audio file to `C:\tmp` and failed with `PermissionError`; I then generated `audit_silence.wav` in the project folder and removed it after the upload test.

## 17. Final Readiness Rating

Overall readiness: prototype-ready, not production-ready.

- Hackathon demo: 8/10. Strong story, working local backend/dashboard, trained checkpoint, and honest limitations.
- GitHub portfolio: 7/10 after cleanup. Needs environment/docs cleanup, archive/temp file cleanup, and clearer curated-vs-real metrics.
- Professor/mentor review: 7/10. Technically coherent, with good evaluation hygiene, but should highlight privacy/API/audio caveats.
- Startup/incubator pitch: 5/10. Good prototype narrative, but real-world validation, security, and product reliability are not ready.
- Truecaller-style outreach: 6/10. Good as an internship/prototype pitch if ASVspoof and Android limitations are explicit.
- Production readiness: 2/10. Missing auth, hardened uploads, real-world validation, robust audio handling, deployment security, and persistent privacy controls.

Final assessment: CallShield AI is a strong v2.3.5 prototype with unusually good honesty around ASVspoof limitations. The next work should not chase more headline metrics first; it should harden privacy, runtime reproducibility, API safety, audio no-speech/long-audio behavior, and real-world pilot evaluation.
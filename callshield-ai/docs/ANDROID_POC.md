# Android PoC: Real-Time Mobile CallShield Demo

## What This Proves

The Android PoC proves this integration path:

```text
Phone microphone -> 8-second WAV chunks -> CallShield /analyze-audio -> live risk result
```

It is enough for a practical demo: play or speak a scam-call scenario on speakerphone and show CallShield updating from the mobile app.

## What It Does Not Prove

It does not prove direct in-call audio capture on every Android device. Android restricts normal apps from recording private call audio. For a Truecaller-style product, the production path needs consent, platform-compliant call integration, OEM/telecom/VoIP access, or on-device audio made available through approved APIs.

## Start Backend

From the `callshield-ai` folder:

```powershell
.\.venv\Scripts\python.exe main.py server
```

Check the server:

```powershell
Invoke-RestMethod http://localhost:8000/model-status | ConvertTo-Json -Depth 5
```

## Run On Android Emulator

Open:

```text
android/CallShieldMobile
```

Use this server URL inside the app:

```text
http://10.0.2.2:8000
```

## Run On Physical Phone

Find your laptop IP:

```powershell
ipconfig
```

Use the Wi-Fi IPv4 address in the app:

```text
http://192.168.x.x:8000
```

If the phone cannot connect, allow Python/Uvicorn through Windows Firewall for private networks.

The backend also prints phone-friendly LAN URLs when you run:

```powershell
.\.venv\Scripts\python.exe main.py server
```

On a physical phone, do not use `http://10.0.2.2:8000`; that address is for the Android emulator only.

## Demo Script

1. Start CallShield backend.
2. Open the Android app.
3. Enter the laptop Wi-Fi URL and tap `Test server`.
4. Start a speakerphone test call or play a consented scam-call sample.
5. Tap `Start`.
6. Tap `Stop` at the end to show the saved final alert.
7. Show chunk-by-chunk output:
   - risk score
   - heard transcript
   - warning level
   - scam type
   - log-mel spectrogram
   - deepfake score
   - audio signal strength
   - used in fusion

The mobile app uploads one chunk at a time. If the backend is still processing, it skips the next chunk. This keeps the screen close to real time even when Whisper processing is slower than the recording interval.

The log-mel spectrogram is generated server-side from the same audio chunk sent to `/analyze-audio`. It is a debugging visual for audio quality: silence should look mostly dark, speech should show structured bands, and clipping/noise will be obvious.

After `Stop`, the app saves all analyzed chunk scores in local app preferences and shows a final session alert. The alert includes max risk, average risk, suspicious chunk count, soft/hard warning count, top scam type, max deepfake score, heard evidence, and the recommended action.

## ASR And Fusion Guardrails

The live mobile endpoint is conservative:

```text
background/no-speech chunks -> ignored
common ASR hallucinations -> suppressed
deepfake-only evidence -> displayed but not fused into risk without scam-like transcript evidence
```

You can try a Hugging Face Hindi/Hinglish ASR model:

```powershell
$env:CALLSHIELD_ASR_BACKEND="huggingface"
$env:CALLSHIELD_HF_ASR_MODEL="Oriserve/Whisper-Hindi2Hinglish-Swift"
.\.venv\Scripts\python.exe main.py server
```

This may download model files on first run.

For offline demos, download once while online:

```powershell
.\.venv\Scripts\python.exe scripts\download_hf_asr_model.py --model Oriserve/Whisper-Hindi2Hinglish-Swift
```

Then start the backend without network access:

```powershell
$env:CALLSHIELD_ASR_BACKEND="huggingface"
$env:CALLSHIELD_ASR_OFFLINE="true"
$env:CALLSHIELD_HF_ASR_LOCAL_DIR="models\hf_asr\Oriserve__Whisper-Hindi2Hinglish-Swift"
.\.venv\Scripts\python.exe main.py server
```

## Pitch Wording

Use this wording:

```text
This Android proof-of-concept streams consented microphone audio to a trained CallShield backend during a live speakerphone/test-call scenario. It demonstrates the real-time integration path. Native private call-audio capture is platform restricted and would require a compliant telecom/OEM/VoIP integration.
```

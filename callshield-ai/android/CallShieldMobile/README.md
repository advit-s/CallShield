# CallShield Mobile Test App

This Android proof-of-concept is a backend-connected test app. The backend is required for live transcript output, CNN deepfake scoring, risk fusion, and the real backend log-mel spectrogram shown in the app. The Python backend must run separately for full ASR and deepfake inference; the app does not process these locally.

Pre-built APKs are published via GitHub Releases and are not committed to this repository.

The app records 8-second microphone WAV chunks and sends each chunk to the CallShield API:

```text
POST /analyze-audio?call_id=android-poc-...
```

It is meant for speakerphone or test-call simulation. Android generally does not allow normal apps to capture private in-call audio directly, so this is not a production call-recording implementation.

## Run

Start the backend from the `callshield-ai` folder:

```powershell
.\.venv\Scripts\python.exe main.py server
```

For the local Hugging Face Hindi/Hinglish ASR snapshot, use:

```powershell
.\scripts\start_mobile_demo_server.ps1
```

Open this folder in Android Studio:

```text
android/CallShieldMobile
```

Server URL:

```text
Android emulator: http://10.0.2.2:8000
Physical phone:   http://YOUR_LAPTOP_LAN_IP:8010
```

For a physical phone, make sure the phone and laptop are on the same Wi-Fi network and Windows Firewall allows inbound traffic to the backend port.

To expose the backend without port-forwarding, use Cloudflare Tunnel:

```powershell
.\cloudflared.exe tunnel --url http://localhost:8000
```

Cloudflare assigns a public `https://` URL. Share that URL with the Android device. Use HTTPS tunnels (not raw HTTP) for any remote or production review. Local `http://` on the same Wi-Fi network is fine for ad-hoc testing.

Tap `Test server` before recording. The app checks `/health` and blocks recording if the backend URL is blank, unreachable, or using the emulator-only `10.0.2.2` address on a physical phone.

## Monitoring Modes

The app has a `Real call mode` switch:

- On: incoming phone calls show a CallShield notification. Monitoring still starts only after the user taps `Start test`.
- Off: phone calls do not trigger CallShield. Use `Start test` manually for speakerphone/audio testing.

When Real Call Mode is on, CallShield also keeps a low-priority `CallShield armed` notification visible. This makes the state obvious during testing and gives Android a visible user-facing signal that the app is ready for incoming-call monitoring.

Android may ask for microphone, phone-state, and notification permissions. Allow the permissions needed for the flow you are testing.

## Scammer Audio Capture

Normal Android apps cannot directly read the private cellular call audio stream. CallShield therefore uses `Speakerphone capture assist`: when monitoring starts, it tries to route call audio to the built-in speaker and records what the microphone hears.

For best results:

- Answer the call.
- Turn on Speaker in the phone call UI.
- Keep CallShield monitoring in the foreground.
- Watch the mic level and live transcript to confirm the caller voice is being heard.

If speaker routing is blocked by the device, tap `Enable speaker assist` or manually tap Speaker in the phone app.

Troubleshooting:

- If `Mic level` stays at `0%`, Android/MIUI is not letting CallShield hear the caller. Turn on Speaker in the phone call UI, raise call volume, and keep the phone near the speaker.
- If the app says `ASR unavailable`, restart the backend with `.\scripts\start_mobile_demo_server.ps1` from the `callshield-ai` folder.
- If every chunk says empty `heard=""`, save a chunk with `Save last chunk` and test that WAV file separately before trusting the real-call result.

## Test Flow

1. Install the APK.
2. Enter the backend URL.
3. Tap `Test server`.
4. Choose `Real call mode` for incoming-call notification testing, or turn it off for manual testing.
5. Put a test call or audio playback on speakerphone.
6. Tap `Start test`.
7. Watch risk, warning, scam type, heard transcript, real backend log-mel spectrogram, deepfake score, and fusion usage update chunk by chunk.
8. Tap `End call` to save all chunk scores and show a final CallShield alert.

The app sends one audio chunk at a time. If the backend is still processing the previous chunk, the next chunk is skipped so the app stays close to real time instead of building a delayed upload queue.

The spectrogram panel displays the backend-generated log-mel preview from `/analyze-audio`. The APK does not generate its own spectrogram image locally.

Use `Save last chunk` when ASR or deepfake scoring looks wrong. The app saves the most recent WAV chunk locally under its external app files directory as `callshield-debug-chunk-...wav`; use those saved chunks for real-world debugging and retraining decisions.

When you tap `End call`, the app summarizes the whole session locally. It saves every chunk score and shows a final alert with max risk, average risk, suspicious chunk count, warning count, top scam type, max deepfake score, heard evidence, and recommended action. If a chunk is still uploading, the app waits for that result before showing the final alert.

## Real-World Test Report

Create a fresh report template after each real-world test session:

```powershell
.\.venv\Scripts\python.exe scripts\create_real_world_test_report.py
```

Fill the generated report with ASR quality, false positives, false negatives, deepfake false alarms, and notes about noisy or compressed audio.

## Honest Limitation

This app proves mobile microphone streaming into CallShield. It does not prove native in-call audio capture. A Truecaller-style integration would need platform permissions, device/OEM support, an accessibility/telecom integration strategy, or server-side carrier/VoIP audio access with consent.

# CallShield Test App

Testing-only Android app for quickly checking the local CallShield backend from an emulator or physical phone.

This app does not record audio and does not request microphone permission. Use the existing `android/CallShieldMobile` PoC when you want microphone chunk streaming.

## What It Tests

- `GET /health`
- `GET /model-status`
- `POST /analyze-transcript`
- `POST /score-call`

## Run

Start the backend from the `callshield-ai` folder:

```powershell
.\.venv\Scripts\python.exe main.py server
```

Open this folder in Android Studio:

```text
android/CallShieldTestApp
```

Server URL:

```text
Android emulator: http://10.0.2.2:8000
Physical phone:   http://YOUR_LAPTOP_LAN_IP:8000
```

For a physical phone, keep the phone and laptop on the same Wi-Fi network and allow inbound traffic to the backend port.

## Build From This Repo

The existing wrapper in `android/CallShieldMobile` can build this separate test project:

```powershell
cd android\CallShieldMobile
.\gradlew.bat -p ..\CallShieldTestApp :app:assembleDebug
```

Debug APK:

```text
android/CallShieldTestApp/app/build/outputs/apk/debug/app-debug.apk
```

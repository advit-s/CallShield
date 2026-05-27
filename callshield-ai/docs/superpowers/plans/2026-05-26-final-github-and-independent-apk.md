# Final GitHub And Backend-Connected APK Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a GitHub-safe CallShield project and a shareable Android test APK that uses the real backend for ASR, CNN deepfake inference, risk fusion, and log-mel spectrogram display.

**Architecture:** Keep the Python backend and ML training/evaluation pipeline unchanged. The Android APK must not include deterministic local response generation. Incoming-call notifications may open the app, but monitoring starts only after the user taps `Start test`. Keep generated APKs, datasets, checkpoints, downloaded ASR snapshots, and scratch reports local through the root `.gitignore`.

**Tech Stack:** Python/FastAPI backend, Java Android app, Gradle Android plugin, PowerShell build workflow.

---

### Task 1: GitHub Hygiene

**Files:**
- Modify: `C:\Users\advit\OneDrive\Desktop\CallShield\.gitignore`

- [x] Add ignore rules for root APKs, APK distribution folders, model archive binaries, audit scratch files, and generated local artifacts.
- [x] Verify `git status --short --ignored` does not show datasets, checkpoints, APKs, Gradle build outputs, local ASR snapshots, or scratch audit files as push candidates.

### Task 2: Backend-Connected Android Test App

**Files:**
- Modify: `C:\Users\advit\OneDrive\Desktop\CallShield\callshield-ai\android\CallShieldMobile\app\src\main\java\ai\callshield\mobile\MainActivity.java`
- Modify: `C:\Users\advit\OneDrive\Desktop\CallShield\callshield-ai\android\CallShieldMobile\app\src\main\java\ai\callshield\mobile\PhoneStateReceiver.java`
- Modify: `C:\Users\advit\OneDrive\Desktop\CallShield\callshield-ai\android\CallShieldMobile\app\build.gradle`

- [x] Require a backend URL before recording.
- [x] Remove deterministic local response generation.
- [x] Show only backend-returned ASR, deepfake, fusion, and spectrogram data.
- [x] Prevent incoming-call notification handling from starting monitoring automatically.
- [x] Update app version name for the live test APK.

### Task 3: Documentation

**Files:**
- Modify: `C:\Users\advit\OneDrive\Desktop\CallShield\callshield-ai\README.md`
- Modify: `C:\Users\advit\OneDrive\Desktop\CallShield\callshield-ai\android\CallShieldMobile\README.md`

- [x] Document what is GitHub-safe.
- [x] Document what is intentionally ignored.
- [x] Document that the Android APK requires the backend for live ASR, deepfake scoring, and real backend log-mel spectrogram output.

### Task 4: Verification And APK

**Commands:**
- Run: `.\.venv\Scripts\python.exe -m compileall -q .`
- Run: `.\.venv\Scripts\python.exe -m pytest -q`
- Run: `.\gradlew.bat :app:assembleDebug` from `android\CallShieldMobile`
- Copy APK to `C:\Users\advit\OneDrive\Desktop\CallShield\dist\CallShieldMobile-Live-Test.apk`

- [x] Confirm Python syntax and tests pass.
- [x] Confirm Android debug APK builds.
- [x] Confirm the copied live test APK exists.

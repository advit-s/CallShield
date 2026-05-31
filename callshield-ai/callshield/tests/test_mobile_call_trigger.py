from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ANDROID_MAIN = ROOT / "android" / "CallShieldMobile" / "app" / "src" / "main"


def test_android_declares_incoming_call_receiver():
    manifest = (ANDROID_MAIN / "AndroidManifest.xml").read_text(encoding="utf-8")

    assert "android.permission.READ_PHONE_STATE" in manifest
    assert "android.permission.POST_NOTIFICATIONS" in manifest
    assert "android.permission.MODIFY_AUDIO_SETTINGS" in manifest
    assert 'android:name=".PhoneStateReceiver"' in manifest
    assert "android.intent.action.PHONE_STATE" in manifest


def test_phone_state_receiver_never_starts_monitoring_without_user_tap():
    receiver = (
        ANDROID_MAIN
        / "java"
        / "ai"
        / "callshield"
        / "mobile"
        / "PhoneStateReceiver.java"
    ).read_text(encoding="utf-8")

    assert "TelephonyManager.EXTRA_STATE_RINGING" in receiver
    assert "CallShieldSettings.isRealCallModeEnabled(context)" in receiver
    assert "CallShieldRuntime.isActivityVisible()" in receiver
    assert "showIncomingCallNotification" in receiver
    assert "startMonitoringFromIncomingCall()" not in receiver


def test_main_activity_requires_manual_start_for_monitoring():
    activity = (
        ANDROID_MAIN
        / "java"
        / "ai"
        / "callshield"
        / "mobile"
        / "MainActivity.java"
    ).read_text(encoding="utf-8")

    assert "ACTION_OPEN_FROM_CALL_NOTIFICATION" in activity
    assert "handleNotif" in activity
    assert "EXTRA_AUTO_START_MONITORING" not in activity
    assert "handleAutoStartIntent" not in activity
    assert "startMonitoringFromIncomingCall" not in activity
    assert "modeSw" in activity
    assert "Real call mode" in activity
    assert "CallShieldArmedNotifier.showArmed" in activity
    assert "startScan" in activity
    assert "startStreaming(true)" not in activity


def test_start_button_explains_missing_backend_before_recording():
    activity = (
        ANDROID_MAIN
        / "java"
        / "ai"
        / "callshield"
        / "mobile"
        / "MainActivity.java"
    ).read_text(encoding="utf-8")

    assert "Backend URL" in activity
    assert "server_url" in activity
    assert "Toast.makeText" in activity


def test_mobile_app_can_save_last_audio_chunk_for_debugging():
    activity = (
        ANDROID_MAIN
        / "java"
        / "ai"
        / "callshield"
        / "mobile"
        / "MainActivity.java"
    ).read_text(encoding="utf-8")

    assert "AudioChunkStreamer" in activity
    assert "sendChunk" in activity


def test_mobile_app_labels_audio_only_results_as_review():
    activity = (
        ANDROID_MAIN
        / "java"
        / "ai"
        / "callshield"
        / "mobile"
        / "MainActivity.java"
    ).read_text(encoding="utf-8")

    assert "riskLabel" in activity
    assert "REVIEW" in activity
    assert "sendChunk" in activity


def test_mobile_app_uses_product_demo_information_architecture():
    activity = (
        ANDROID_MAIN
        / "java"
        / "ai"
        / "callshield"
        / "mobile"
        / "MainActivity.java"
    ).read_text(encoding="utf-8")

    assert "riskKicker" in activity
    assert "riskLabel" in activity
    assert "riskScore" in activity
    assert "sendChunk" in activity
    assert "RISK SCORE" in activity


def test_mobile_app_has_speakerphone_capture_assist():
    activity = (
        ANDROID_MAIN
        / "java"
        / "ai"
        / "callshield"
        / "mobile"
        / "MainActivity.java"
    ).read_text(encoding="utf-8")
    helper = (
        ANDROID_MAIN
        / "java"
        / "ai"
        / "callshield"
        / "mobile"
        / "CallAudioCaptureAssist.java"
    ).read_text(encoding="utf-8")

    assert "enableSpeakerphoneAssist" in activity
    assert "CallAudioCaptureAssist" in activity
    assert "release" in activity
    assert "AudioManager" in helper
    assert "TYPE_BUILTIN_SPEAKER" in helper
    assert "setSpeakerphoneOn(true)" in helper


def test_audio_streamer_prefers_voice_communication_for_call_monitoring():
    streamer = (
        ANDROID_MAIN
        / "java"
        / "ai"
        / "callshield"
        / "mobile"
        / "AudioChunkStreamer.java"
    ).read_text(encoding="utf-8")

    assert "MediaRecorder.AudioSource.VOICE_COMMUNICATION" in streamer
    assert streamer.index("VOICE_COMMUNICATION") < streamer.index("AudioSource.MIC")
    assert "Recording call-assist microphone chunks at 16 kHz" in streamer


def test_armed_notification_helper_exists():
    notifier = (
        ANDROID_MAIN
        / "java"
        / "ai"
        / "callshield"
        / "mobile"
        / "CallShieldArmedNotifier.java"
    ).read_text(encoding="utf-8")

    assert "ARMED_NOTIFICATION_ID" in notifier
    assert "setOngoing(true)" in notifier
    assert "CallShield armed" in notifier


def test_mobile_demo_server_script_sets_hf_asr_environment():
    script = (ROOT / "scripts" / "start_mobile_demo_server.ps1").read_text(encoding="utf-8")

    assert 'CALLSHIELD_ASR_BACKEND="huggingface"' in script
    assert 'CALLSHIELD_ASR_OFFLINE="true"' in script
    assert "CALLSHIELD_HF_ASR_LOCAL_DIR" in script
    assert "main.py server" in script


def test_mobile_app_requests_live_transcript_for_local_monitoring():
    client = (
        ANDROID_MAIN
        / "java"
        / "ai"
        / "callshield"
        / "mobile"
        / "CallShieldApiClient.java"
    ).read_text(encoding="utf-8")

    assert "include_transcript=true" in client


def test_mobile_app_requires_backend_and_has_no_local_simulation_mode():
    activity = (
        ANDROID_MAIN
        / "java"
        / "ai"
        / "callshield"
        / "mobile"
        / "MainActivity.java"
    ).read_text(encoding="utf-8")
    gradle = (ROOT / "android" / "CallShieldMobile" / "app" / "build.gradle").read_text(
        encoding="utf-8"
    )
    readme = (ROOT / "android" / "CallShieldMobile" / "README.md").read_text(
        encoding="utf-8"
    )

    blocked_tokens = [
        "OFFLINE" + "_DEMO_URL",
        "generate" + "Local" + "M" + "ockResponse",
        "http://" + "local",
        "offline" + "_demo",
        "offline" + "_demo_simulated",
        "M" + "OCK",
    ]
    for token in blocked_tokens:
        assert token not in activity
    assert 'versionName "2.4.0-live-test"' in gradle
    assert "backend is required" in readme
    assert "real backend log-mel spectrogram" in readme


def test_public_project_text_uses_neutral_demo_language():
    forbidden = "prof" + "essor"
    scan_roots = [
        ROOT / "README.md",
        ROOT / "android" / "CallShieldMobile" / "README.md",
        ROOT / "android" / "CallShieldMobile" / "app" / "build.gradle",
        ANDROID_MAIN / "java" / "ai" / "callshield" / "mobile" / "MainActivity.java",
        ROOT / "docs",
    ]

    offenders = []
    for root in scan_roots:
        paths = [root] if root.is_file() else root.rglob("*")
        for path in paths:
            if not path.is_file() or path.suffix.lower() not in {".java", ".md", ".gradle"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            if forbidden in text or forbidden in str(path).lower():
                offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []


def test_real_world_test_template_exists():
    template = (ROOT / "docs" / "real_world_test_report_template.md").read_text(encoding="utf-8")
    script = (ROOT / "scripts" / "create_real_world_test_report.py").read_text(encoding="utf-8")

    assert "Real-World CallShield Test Report" in template
    assert "ASR quality" in template
    assert "Deepfake false alarm" in template
    assert "create_real_world_test_report" in script

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


def test_phone_state_receiver_auto_starts_monitoring_when_allowed():
    receiver = (
        ANDROID_MAIN
        / "java"
        / "ai"
        / "callshield"
        / "mobile"
        / "PhoneStateReceiver.java"
    ).read_text(encoding="utf-8")

    assert "TelephonyManager.EXTRA_STATE_RINGING" in receiver
    assert "TelephonyManager.EXTRA_STATE_OFFHOOK" in receiver
    assert "CallShieldSettings.isRealCallModeEnabled(context)" in receiver
    assert "showIncomingCallNotification" in receiver
    assert "handlePhoneCallStartedFromReceiver" in receiver
    assert "handlePhoneCallEndedFromReceiver" in receiver


def test_main_activity_can_auto_start_and_report_real_call_monitoring():
    activity = (
        ANDROID_MAIN
        / "java"
        / "ai"
        / "callshield"
        / "mobile"
        / "MainActivity.java"
    ).read_text(encoding="utf-8")

    assert "ACTION_OPEN_FROM_CALL_NOTIFICATION" in activity
    assert "ACTION_OPEN_LAST_REPORT" in activity
    assert "handleNotif" in activity
    assert "startMonitoringFromIncomingCall" in activity
    assert "handlePhoneCallStartedFromReceiver" in activity
    assert "showFinalReport" in activity
    assert "showReportNotification" in activity
    assert "modeSw" in activity
    assert "Real call mode" in activity
    assert "CallShieldArmedNotifier.showArmed" in activity
    assert "startScan" in activity
    assert "startStreaming(true)" not in activity


def test_mobile_app_can_import_saved_call_recording_file():
    activity = (
        ANDROID_MAIN
        / "java"
        / "ai"
        / "callshield"
        / "mobile"
        / "MainActivity.java"
    ).read_text(encoding="utf-8")
    client = (
        ANDROID_MAIN
        / "java"
        / "ai"
        / "callshield"
        / "mobile"
        / "CallShieldApiClient.java"
    ).read_text(encoding="utf-8")

    assert "REQ_PICK_RECORDING" in activity
    assert "Intent.ACTION_OPEN_DOCUMENT" in activity
    assert 'pick.setType("audio/*")' in activity
    assert "Analyze Recording File" in activity
    assert "analyzeRecordingUri" in activity
    assert "recordingDisplayName" in activity
    assert "recordingMimeType" in activity
    assert "readRecordingBytes" in activity
    assert "include_transcript=true" in client
    assert "filename=\\\"" in client
    assert "Content-Type: " in client


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
    assert "Final risk level" in activity


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


def test_mobile_ui_layout_regression():
    activity = (
        ANDROID_MAIN
        / "java"
        / "ai"
        / "callshield"
        / "mobile"
        / "MainActivity.java"
    ).read_text(encoding="utf-8")

    # Backend setup helper exists
    assert "Backend URL required" in activity
    assert "Open Settings" in activity

    # Speaker Assist button exists and uses existing speaker assist logic
    assert "Speaker Assist" in activity
    assert "enableSpeakerphoneAssist" in activity

    # Save Last Chunk button exists and is not automatic
    assert "Save Last Chunk" in activity
    assert "last_chunk_" in activity

    # History delete/clear actions exist with confirmation
    assert "Clear History" in activity
    assert "deleteHistoryEntry" in activity
    assert "Delete all saved scans?" in activity
    assert "AlertDialog.Builder" in activity

    # Bottom nav still only has Scan / History / Settings
    assert "TAB_SCAN" in activity
    assert "TAB_HIST" in activity
    assert "TAB_SET" in activity
    # Ensure no other bottom tabs exist
    assert "TAB_" not in activity.replace("TAB_SCAN", "").replace("TAB_HIST", "").replace("TAB_SET", "")

    # Fake history strings are still absent
    forbidden_history = [
        "amazon", "bank", "joe",
        "+1 (415) 555-0118", "+1 (212) 555-0188",
        "+91 98765-43210", "+1 (888) 280-4331", "+1 (800) 555-0142"
    ]
    for fh in forbidden_history:
        assert fh not in activity.lower()

    # Existing method names/strings are preserved
    assert "startScan" in activity
    assert "sendChunk" in activity
    assert "showResp" in activity
    assert "finalSum" in activity
    assert "riskKicker" in activity
    assert "riskLabel" in activity
    assert "riskScore" in activity
    assert "Real call mode" in activity
    assert "CallShieldArmedNotifier.showArmed" in activity

    # Assert old UI components are not present
    assert "🔍" not in activity
    assert "📋" not in activity
    assert "⚙" not in activity
    assert "C_PURPLE" not in activity
    assert "grad(\"#0C0820\"" not in activity
    assert "grad(\"#1A0F2E\"" not in activity
    assert "THREE-SIGNAL ANALYSIS" not in activity
    assert "OVERALL RISK SCORE" not in activity
    assert "START SCAN" not in activity


def test_mobile_scan_screen_uses_compact_dashboard_information_architecture():
    activity = (
        ANDROID_MAIN
        / "java"
        / "ai"
        / "callshield"
        / "mobile"
        / "MainActivity.java"
    ).read_text(encoding="utf-8")

    expected_dashboard_labels = [
        "CallShield AI",
        "Session analyzed",
        "Three Signal Risk Analysis",
        "Audio Deepfake & Replay",
        "Scam Language Detection",
        "Identity Verification",
        "Final risk level",
        "Connection",
        "Microphone",
        "Heard by CallShield",
        "Latest result",
        "Audio fingerprint",
        "Advanced / debug",
    ]
    for label in expected_dashboard_labels:
        assert label in activity

    outdated_labels = [
        "Detection status",
        "Fragment Audio",
        "Current risk",
        "RISK SCORE",
    ]
    for label in outdated_labels:
        assert label not in activity


def test_mobile_live_ui_does_not_show_safe_when_deepfake_score_is_high():
    activity = (
        ANDROID_MAIN
        / "java"
        / "ai"
        / "callshield"
        / "mobile"
        / "MainActivity.java"
    ).read_text(encoding="utf-8")

    assert "audioReview" in activity
    assert "AUDIO REVIEW" in activity
    assert "deepfakeScore(raw) >= 0.5" in activity
    assert 'audioReview ? "AUDIO REVIEW" : riskBand(sc, band)' in activity


def test_mobile_test_connection_handles_https_and_visible_errors():
    activity = (
        ANDROID_MAIN
        / "java"
        / "ai"
        / "callshield"
        / "mobile"
        / "MainActivity.java"
    ).read_text(encoding="utf-8")

    assert 'u.startsWith("http://") || u.startsWith("https://")' in activity
    assert "URL must start with http:// or https://" in activity
    assert "Testing..." in activity
    assert "/health" in (ANDROID_MAIN / "java" / "ai" / "callshield" / "mobile" / "CallShieldApiClient.java").read_text(encoding="utf-8")
    assert "Last response in" in activity
    assert "shortErr(e)" in activity
    assert "correct port" in activity
    assert "port shown by the backend" in activity

    ok_url_body = activity.split("private boolean okUrl", 1)[1].split("private void connErr", 1)[0]
    assert "setContentView(root())" not in ok_url_body


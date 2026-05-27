package ai.callshield.mobile;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.Bundle;
import android.text.InputType;
import android.text.method.ScrollingMovementMethod;
import android.util.Base64;
import android.view.Gravity;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Date;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

public final class MainActivity extends Activity {
    private static final int REQUEST_RECORD_AUDIO = 1001;
    private static final int REQUEST_CALL_TRIGGER_PERMISSIONS = 1002;
    private static final int MAX_LOG_LINES = 28;
    private static final String PREFS = "callshield_mobile";
    private static final String PREF_SERVER_URL = "server_url";
    private static final String PREF_LAST_SESSION_SUMMARY = "last_session_summary";
    private static final String EMULATOR_SERVER_URL = "http://10.0.2.2:8000";
    public static final String ACTION_OPEN_FROM_CALL_NOTIFICATION = "ai.callshield.mobile.action.OPEN_FROM_CALL_NOTIFICATION";

    private final ExecutorService networkExecutor = Executors.newSingleThreadExecutor();
    private final CallShieldApiClient apiClient = new CallShieldApiClient();
    private final SessionAlertAnalyzer sessionAlertAnalyzer = new SessionAlertAnalyzer();
    private final AtomicInteger chunkCounter = new AtomicInteger(0);
    private final AtomicBoolean uploadInFlight = new AtomicBoolean(false);
    private final AtomicBoolean stopSummaryPending = new AtomicBoolean(false);

    private AudioChunkStreamer streamer;
    private EditText serverUrlInput;
    private Button testButton;
    private Button startButton;
    private Button stopButton;
    private Button saveLastChunkButton;
    private Button speakerAssistButton;
    private Switch modeSwitch;
    private TextView connectionText;
    private TextView statusText;
    private TextView modeStatusText;
    private TextView captureModeText;
    private TextView micLevelText;
    private TextView heardText;
    private TextView spectrogramStatusText;
    private ImageView spectrogramImage;
    private TextView liveStateText;
    private TextView timerText;
    private TextView audioSignalTitle;
    private TextView audioSignalSubtitle;
    private TextView audioSignalPill;
    private TextView languageSignalTitle;
    private TextView languageSignalSubtitle;
    private TextView languageSignalPill;
    private TextView identitySignalTitle;
    private TextView identitySignalSubtitle;
    private TextView identitySignalPill;
    private TextView riskKickerText;
    private TextView riskLevelText;
    private TextView riskScoreText;
    private TextView riskSummaryText;
    private TextView actionOneText;
    private TextView actionTwoText;
    private TextView actionThreeText;
    private TextView resultText;
    private TextView logText;
    private String sessionId;
    private String activeServerUrl;
    private long sessionStartedAtMillis;
    private byte[] lastChunkWavBytes;
    private int lastChunkIndex;
    private int quietMicTicks;
    private boolean notHearingNoticeShown;
    private boolean recordingActive;
    private boolean startedByIncomingCall;
    private boolean pendingStartAfterMicPermission;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(buildUi());
        streamer = new AudioChunkStreamer(new AudioChunkStreamer.Listener() {
            @Override
            public void onChunk(byte[] wavBytes) {
                sendChunk(wavBytes);
            }

            @Override
            public void onLevel(int percent) {
                runOnUiThread(() -> updateMicLevel(percent));
            }

            @Override
            public void onStatus(String message) {
                runOnUiThread(() -> setStatus(message));
            }

            @Override
            public void onError(Exception error) {
                runOnUiThread(() -> appendLog("Audio error: " + error.getMessage()));
            }
        });
        updateButtons(false);
        if (CallShieldSettings.isRealCallModeEnabled(this)) {
            requestCallTriggerPermissionsIfNeeded();
            CallShieldArmedNotifier.showArmed(this);
        }
        if (isPhysicalPhone() && serverUrlInput.getText().toString().contains("10.0.2.2")) {
            showEmulatorUrlWarning();
        }
        handleCallNotificationIntent(getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        handleCallNotificationIntent(intent);
    }

    @Override
    protected void onResume() {
        super.onResume();
        CallShieldRuntime.markActivityVisible(this);
    }

    @Override
    protected void onPause() {
        CallShieldRuntime.markActivityHidden(this);
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        if (streamer != null) {
            streamer.stop();
        }
        networkExecutor.shutdownNow();
        super.onDestroy();
    }

    private View buildUi() {
        int padding = dp(18);

        ScrollView scrollView = new ScrollView(this);
        scrollView.setFillViewport(true);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(padding, padding, padding, padding);
        root.setBackgroundColor(color("#060817"));
        scrollView.addView(root);

        LinearLayout hero = new LinearLayout(this);
        hero.setOrientation(LinearLayout.VERTICAL);
        hero.setPadding(dp(16), dp(16), dp(16), dp(14));
        hero.setBackground(rounded("#0C0820", "#312B67", 1, 18));
        root.addView(hero, matchWrap());

        LinearLayout header = row();
        TextView badge = new TextView(this);
        badge.setText("CS");
        badge.setGravity(Gravity.CENTER);
        badge.setTextSize(15);
        badge.setTypeface(Typeface.DEFAULT_BOLD);
        badge.setTextColor(color("#E0F2FE"));
        badge.setBackground(rounded("#172554", "#22D3EE", 1, 16));
        LinearLayout.LayoutParams badgeParams = new LinearLayout.LayoutParams(dp(48), dp(48));
        badgeParams.setMargins(0, 0, dp(12), 0);
        header.addView(badge, badgeParams);

        TextView title = new TextView(this);
        title.setText("CallShield AI");
        title.setTextSize(28);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setTextColor(Color.WHITE);
        header.addView(title, weightWrap(1));
        hero.addView(header);

        LinearLayout liveRow = row();
        liveRow.setPadding(0, dp(16), 0, dp(4));
        liveStateText = new TextView(this);
        liveStateText.setText("Ready for test call");
        liveStateText.setTextSize(15);
        liveStateText.setTextColor(color("#C4B5FD"));
        liveRow.addView(liveStateText, weightWrap(1));

        timerText = new TextView(this);
        timerText.setText("00:00");
        timerText.setTextSize(15);
        timerText.setTextColor(color("#C4B5FD"));
        timerText.setGravity(Gravity.END);
        LinearLayout.LayoutParams timerParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        );
        liveRow.addView(timerText, timerParams);
        hero.addView(liveRow);

        TextView subtitle = helperText();
        subtitle.setText("Backend-connected test app with live ASR, CNN deepfake inference, and real log-mel spectrograms.");
        subtitle.setPadding(0, dp(8), 0, 0);
        hero.addView(subtitle);

        TextView signalLabel = sectionLabel("THREE SIGNAL RISK ANALYSIS");
        signalLabel.setPadding(0, dp(18), 0, dp(8));
        root.addView(signalLabel);

        LinearLayout signals = new LinearLayout(this);
        signals.setOrientation(LinearLayout.VERTICAL);
        signals.setPadding(dp(10), dp(10), dp(10), dp(10));
        signals.setBackground(rounded("#080A1C", "#7C3AED", 1, 16));
        root.addView(signals, matchWrap());

        LinearLayout audioSignal = signalRow("Audio Deepfake & Replay", "Waiting for voice-pattern analysis", "IDLE", "#A855F7");
        LinearLayout audioTextColumn = (LinearLayout) audioSignal.getChildAt(1);
        audioSignalTitle = (TextView) audioTextColumn.getChildAt(0);
        audioSignalSubtitle = (TextView) audioTextColumn.getChildAt(1);
        audioSignalPill = (TextView) audioSignal.getChildAt(2);
        signals.addView(audioSignal, matchWrap());

        LinearLayout languageSignal = signalRow("Scam Language Detection", "Waiting for transcript analysis", "IDLE", "#22D3EE");
        LinearLayout languageTextColumn = (LinearLayout) languageSignal.getChildAt(1);
        languageSignalTitle = (TextView) languageTextColumn.getChildAt(0);
        languageSignalSubtitle = (TextView) languageTextColumn.getChildAt(1);
        languageSignalPill = (TextView) languageSignal.getChildAt(2);
        LinearLayout.LayoutParams signalGap = matchWrap();
        signalGap.setMargins(0, dp(8), 0, 0);
        signals.addView(languageSignal, signalGap);

        LinearLayout identitySignal = signalRow("Identity Verification", "Callback and safe-phrase guidance ready", "LOW", "#06B6D4");
        LinearLayout identityTextColumn = (LinearLayout) identitySignal.getChildAt(1);
        identitySignalTitle = (TextView) identityTextColumn.getChildAt(0);
        identitySignalSubtitle = (TextView) identityTextColumn.getChildAt(1);
        identitySignalPill = (TextView) identitySignal.getChildAt(2);
        LinearLayout.LayoutParams signalGapTwo = matchWrap();
        signalGapTwo.setMargins(0, dp(8), 0, 0);
        signals.addView(identitySignal, signalGapTwo);

        LinearLayout riskCard = new LinearLayout(this);
        riskCard.setOrientation(LinearLayout.VERTICAL);
        riskCard.setPadding(dp(18), dp(16), dp(18), dp(16));
        riskCard.setBackground(rounded("#100B18", "#FB7185", 1, 18));
        LinearLayout.LayoutParams riskParams = matchWrap();
        riskParams.setMargins(0, dp(18), 0, 0);
        root.addView(riskCard, riskParams);

        riskKickerText = new TextView(this);
        riskKickerText.setText("Overall risk");
        riskKickerText.setTextSize(13);
        riskKickerText.setTypeface(Typeface.DEFAULT_BOLD);
        riskKickerText.setTextColor(color("#FDBA74"));
        riskCard.addView(riskKickerText);

        riskLevelText = new TextView(this);
        riskLevelText.setText("READY");
        riskLevelText.setTextSize(29);
        riskLevelText.setTypeface(Typeface.DEFAULT_BOLD);
        riskLevelText.setTextColor(color("#FDE68A"));
        riskLevelText.setPadding(0, dp(2), 0, 0);
        riskCard.addView(riskLevelText);

        riskScoreText = new TextView(this);
        riskScoreText.setText("0/100 overall risk");
        riskScoreText.setTextSize(16);
        riskScoreText.setTypeface(Typeface.DEFAULT_BOLD);
        riskScoreText.setTextColor(color("#C4B5FD"));
        riskScoreText.setPadding(0, dp(2), 0, 0);
        riskCard.addView(riskScoreText);

        riskSummaryText = new TextView(this);
        riskSummaryText.setText("Enter your backend URL, check the connection, then start a test call.");
        riskSummaryText.setTextSize(14);
        riskSummaryText.setTextColor(Color.WHITE);
        riskSummaryText.setPadding(0, dp(8), 0, dp(10));
        riskCard.addView(riskSummaryText);

        TextView recommendedActionLabel = sectionLabel("Recommended action");
        recommendedActionLabel.setTextSize(13);
        recommendedActionLabel.setTextColor(color("#C4B5FD"));
        recommendedActionLabel.setPadding(0, dp(2), 0, dp(4));
        riskCard.addView(recommendedActionLabel);

        actionOneText = checklistLine("Avoid sharing OTP, PIN, passwords, or financial details.");
        actionTwoText = checklistLine("Verify identity using a callback to an official number.");
        actionThreeText = checklistLine("Use a safe phrase if the call feels suspicious.");
        riskCard.addView(actionOneText);
        riskCard.addView(actionTwoText);
        riskCard.addView(actionThreeText);

        TextView controlsLabel = sectionLabel("CALL CONTROLS");
        controlsLabel.setPadding(0, dp(20), 0, dp(8));
        root.addView(controlsLabel);

        LinearLayout controls = row();
        controls.setPadding(0, 0, 0, dp(8));
        startButton = actionButton("Start test", "#22D3EE", "#031B1A");
        startButton.setOnClickListener(view -> startStreaming());
        controls.addView(startButton, weightWrap(1));

        stopButton = actionButton("End call", "#6D28D9", "#FFFFFF");
        stopButton.setOnClickListener(view -> stopStreaming());
        controls.addView(stopButton, weightWrap(1));
        root.addView(controls);

        saveLastChunkButton = actionButton("Save last chunk", "#334155", "#FFFFFF");
        saveLastChunkButton.setOnClickListener(view -> saveLastChunkForDebugging());
        saveLastChunkButton.setEnabled(false);
        saveLastChunkButton.setAlpha(0.55f);
        LinearLayout.LayoutParams saveParams = matchWrap();
        saveParams.setMargins(dp(4), 0, dp(4), dp(8));
        root.addView(saveLastChunkButton, saveParams);

        LinearLayout captureCard = card();
        captureCard.addView(label("Scammer audio capture"));
        captureModeText = panel("Speakerphone capture assist is ready. Android blocks direct private call-audio capture, so CallShield listens through the microphone.");
        captureCard.addView(captureModeText, matchWrap());
        TextView captureHelp = helperText();
        captureHelp.setText("For real calls: answer the call, turn on Speaker, then keep this app monitoring. This is the safe way to hear the scammer's voice on normal Android phones.");
        captureCard.addView(captureHelp);
        speakerAssistButton = actionButton("Enable speaker assist", "#312E81", "#FFFFFF");
        speakerAssistButton.setOnClickListener(view -> enableSpeakerphoneAssist(false));
        LinearLayout.LayoutParams speakerAssistParams = matchWrap();
        speakerAssistParams.setMargins(0, dp(10), 0, 0);
        captureCard.addView(speakerAssistButton, speakerAssistParams);
        LinearLayout.LayoutParams captureParams = matchWrap();
        captureParams.setMargins(0, dp(8), 0, 0);
        root.addView(captureCard, captureParams);

        TextView evidenceLabel = sectionLabel("CALL EVIDENCE");
        evidenceLabel.setPadding(0, dp(12), 0, dp(8));
        root.addView(evidenceLabel);

        heardText = panel("Transcript: waiting for an 8-second speech chunk");
        root.addView(label("Live transcript"));
        root.addView(heardText, matchWrap());

        spectrogramStatusText = panel("Waiting for analyzed audio chunk");
        root.addView(label("Audio fingerprint"));
        root.addView(spectrogramStatusText, matchWrap());

        spectrogramImage = new ImageView(this);
        spectrogramImage.setBackground(rounded("#111827", "#1E293B", 1, 10));
        spectrogramImage.setPadding(dp(4), dp(4), dp(4), dp(4));
        spectrogramImage.setAdjustViewBounds(false);
        spectrogramImage.setScaleType(ImageView.ScaleType.FIT_XY);
        LinearLayout.LayoutParams spectrogramParams = matchWrap();
        spectrogramParams.height = dp(150);
        spectrogramParams.setMargins(0, dp(8), 0, 0);
        root.addView(spectrogramImage, spectrogramParams);

        TextView consoleLabel = sectionLabel("ADVANCED / DEBUG");
        consoleLabel.setPadding(0, dp(20), 0, dp(8));
        root.addView(consoleLabel);

        LinearLayout serverCard = card();
        serverCard.addView(label("Backend URL"));

        serverUrlInput = new EditText(this);
        serverUrlInput.setSingleLine(true);
        serverUrlInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        serverUrlInput.setImeOptions(EditorInfo.IME_ACTION_DONE);
        serverUrlInput.setText(loadServerUrl());
        serverUrlInput.setHint(isPhysicalPhone() ? "http://192.168.1.x:8010" : EMULATOR_SERVER_URL);
        serverUrlInput.setTextColor(Color.WHITE);
        serverUrlInput.setHintTextColor(color("#64748B"));
        serverUrlInput.setTextSize(18);
        serverUrlInput.setSelectAllOnFocus(false);
        serverCard.addView(serverUrlInput, matchWrap());

        TextView urlHelp = helperText();
        urlHelp.setText(isPhysicalPhone()
                ? "Use your laptop Wi-Fi URL, for example http://192.168.1.x:8010. The backend returns the ASR transcript, deepfake score, and log-mel spectrogram."
                : "Emulator: use " + EMULATOR_SERVER_URL + " or your chosen backend port.");
        serverCard.addView(urlHelp);

        LinearLayout serverButtons = row();
        testButton = actionButton("Test server", "#2E1A5F", "#FFFFFF");
        testButton.setOnClickListener(view -> testServer());
        serverButtons.addView(testButton, weightWrap(1));
        serverCard.addView(serverButtons);
        root.addView(serverCard, matchWrap());

        LinearLayout modeCard = card();
        modeCard.addView(label("Monitoring mode"));
        modeSwitch = new Switch(this);
        modeSwitch.setText("Real call mode");
        modeSwitch.setTextSize(15);
        modeSwitch.setTextColor(Color.WHITE);
        modeSwitch.setTypeface(Typeface.DEFAULT_BOLD);
        modeSwitch.setChecked(CallShieldSettings.isRealCallModeEnabled(this));
        modeSwitch.setOnCheckedChangeListener((buttonView, isChecked) -> {
            CallShieldSettings.setRealCallModeEnabled(this, isChecked);
            updateModeStatus();
            if (isChecked) {
                requestCallTriggerPermissionsIfNeeded();
                CallShieldArmedNotifier.showArmed(this);
            } else {
                CallShieldArmedNotifier.cancel(this);
            }
        });
        modeCard.addView(modeSwitch, matchWrap());

        modeStatusText = helperText();
        modeCard.addView(modeStatusText);
        LinearLayout.LayoutParams modeParams = matchWrap();
        modeParams.setMargins(0, dp(12), 0, 0);
        root.addView(modeCard, modeParams);
        updateModeStatus();

        connectionText = panel("Enter backend URL and tap Test server.");
        root.addView(label("Connection"));
        root.addView(connectionText, matchWrap());

        statusText = panel("Ready");
        root.addView(label("Status"));
        root.addView(statusText, matchWrap());

        micLevelText = panel("Mic level: waiting");
        root.addView(label("Microphone"));
        root.addView(micLevelText, matchWrap());

        resultText = panel("No chunks analyzed yet.");
        root.addView(label("Latest technical result"));
        root.addView(resultText, matchWrap());

        logText = panel("");
        logText.setMinLines(8);
        logText.setMovementMethod(new ScrollingMovementMethod());
        root.addView(label("Debug log"));
        root.addView(logText, matchWrap());

        TextView limitation = helperText();
        limitation.setText("Limitation: normal Android apps cannot directly capture private cellular call audio. Use speakerphone, a test call, or consented audio for this PoC.");
        limitation.setPadding(0, dp(16), 0, dp(6));
        root.addView(limitation);

        return scrollView;
    }

    private void testServer() {
        String serverUrl = normalizedUrl();
        if (!validateServerUrl(serverUrl)) {
            return;
        }
        saveServerUrl();
        connectionText.setText("Testing " + serverUrl + " ...");
        testButton.setEnabled(false);

        networkExecutor.submit(() -> {
            try {
                JSONObject health = apiClient.healthCheck(serverUrl);
                runOnUiThread(() -> {
                    connectionText.setText("Connected: CallShield "
                            + health.optString("version", "unknown")
                            + " (" + health.optString("status", "ok") + ")");
                    appendLog(timestamp() + " server test ok");
                });
            } catch (Exception error) {
                runOnUiThread(() -> showConnectionError(error, serverUrl));
            } finally {
                runOnUiThread(() -> testButton.setEnabled(true));
            }
        });
    }

    private void requestCallTriggerPermissionsIfNeeded() {
        ArrayList<String> permissions = new ArrayList<>();
        if (checkSelfPermission(Manifest.permission.READ_PHONE_STATE) != PackageManager.PERMISSION_GRANTED) {
            permissions.add(Manifest.permission.READ_PHONE_STATE);
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            permissions.add(Manifest.permission.POST_NOTIFICATIONS);
        }
        if (!permissions.isEmpty()) {
            requestPermissions(permissions.toArray(new String[0]), REQUEST_CALL_TRIGGER_PERMISSIONS);
        } else if (CallShieldSettings.isRealCallModeEnabled(this)) {
            CallShieldArmedNotifier.showArmed(this);
        }
    }

    private void handleCallNotificationIntent(Intent intent) {
        if (intent == null) {
            return;
        }
        boolean openedFromCallNotification = ACTION_OPEN_FROM_CALL_NOTIFICATION.equals(intent.getAction());
        if (!openedFromCallNotification) {
            return;
        }
        appendLog(timestamp() + " incoming call notification opened; tap Start test to begin monitoring");
        if (!CallShieldSettings.isRealCallModeEnabled(this)) {
            setStatus("Real call mode is off. Use Start test for manual monitoring.");
            return;
        }
        liveStateText.setText("Incoming call detected");
        setStatus("Incoming call detected. Tap Start test when you want CallShield to monitor.");
    }

    private void updateModeStatus() {
        if (modeStatusText == null || modeSwitch == null) {
            return;
        }
        if (modeSwitch.isChecked()) {
            modeStatusText.setText("Real Call Mode: incoming phone calls show a notification. Monitoring starts only when you tap Start test.");
            return;
        }
        modeStatusText.setText("Manual mode: phone calls will not start monitoring. Use Start test for speakerphone/audio testing.");
    }

    private void startStreaming() {
        startStreaming(false);
    }

    private void startStreaming(boolean fromIncomingCall) {
        if (recordingActive) {
            setStatus(fromIncomingCall ? "Incoming call detected. Monitoring already active." : "Monitoring already active.");
            return;
        }
        saveServerUrl();
        activeServerUrl = normalizedUrl();
        if (!validateServerUrl(activeServerUrl)) {
            return;
        }
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            pendingStartAfterMicPermission = fromIncomingCall;
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, REQUEST_RECORD_AUDIO);
            return;
        }
        sessionId = "android-poc-" + System.currentTimeMillis();
        sessionStartedAtMillis = System.currentTimeMillis();
        recordingActive = true;
        startedByIncomingCall = fromIncomingCall;
        lastChunkWavBytes = null;
        lastChunkIndex = 0;
        quietMicTicks = 0;
        notHearingNoticeShown = false;
        chunkCounter.set(0);
        uploadInFlight.set(false);
        stopSummaryPending.set(false);
        sessionAlertAnalyzer.reset();
        logText.setText("");
        resultText.setText("Listening for the first 8-second chunk...");
        heardText.setText("Heard: listening. Speak clearly for 8 seconds...");
        liveStateText.setText(fromIncomingCall ? "Incoming call monitoring" : "Call in progress");
        timerText.setText("00:00");
        riskLevelText.setText("ANALYZING");
        riskScoreText.setText("0/100 overall risk");
        riskSummaryText.setText("Listening for the first speech chunk and checking all three risk signals.");
        setSignal(audioSignalPill, audioSignalSubtitle, "IDLE", "Waiting for voice-pattern analysis", "#64748B");
        setSignal(languageSignalPill, languageSignalSubtitle, "IDLE", "Waiting for transcript analysis", "#64748B");
        setSignal(identitySignalPill, identitySignalSubtitle, "READY", "Safe verification guidance available", "#06B6D4");
        spectrogramStatusText.setText("Waiting for analyzed audio chunk");
        spectrogramImage.setImageDrawable(null);
        micLevelText.setText("Mic level: listening...");
        enableSpeakerphoneAssist(true);
        appendLog("Session: " + sessionId);
        streamer.start();
        updateButtons(true);
        setStatus(fromIncomingCall
                ? "Incoming call detected. Keep the call on speakerphone."
                : "Recording. Keep the call/audio on speakerphone.");
    }

    private void stopStreaming() {
        if (streamer != null) {
            streamer.stop();
        }
        recordingActive = false;
        startedByIncomingCall = false;
        CallAudioCaptureAssist.AssistResult releaseResult = CallAudioCaptureAssist.release(this);
        captureModeText.setText(releaseResult.userMessage);
        appendLog(timestamp() + " speaker assist release: " + releaseResult.logMessage);
        micLevelText.setText("Mic level: stopped");
        liveStateText.setText("Call stopped");
        riskScoreText.setText("Final analysis pending");
        updateButtons(false);
        saveServerUrl();
        stopSummaryPending.set(true);
        if (uploadInFlight.get()) {
            setStatus("Stopped. Waiting for current chunk analysis before final alert.");
        } else {
            showFinalSessionAlert();
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQUEST_RECORD_AUDIO
                && grantResults.length > 0
                && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
            boolean fromIncomingCall = pendingStartAfterMicPermission;
            pendingStartAfterMicPermission = false;
            startStreaming(fromIncomingCall);
        } else if (requestCode == REQUEST_CALL_TRIGGER_PERMISSIONS) {
            appendLog("Incoming call trigger permissions updated.");
            if (CallShieldSettings.isRealCallModeEnabled(this)) {
                CallShieldArmedNotifier.showArmed(this);
            }
        } else {
            Toast.makeText(this, "Microphone permission is required.", Toast.LENGTH_LONG).show();
        }
    }

    public void handlePhoneCallEndedFromReceiver() {
        if (recordingActive && startedByIncomingCall) {
            setStatus("Phone call ended. Saving final CallShield alert.");
            stopStreaming();
            return;
        }
        if (!recordingActive) {
            liveStateText.setText("Call ended");
            setStatus("Phone call ended.");
        }
    }

    private void enableSpeakerphoneAssist(boolean duringMonitoringStart) {
        CallAudioCaptureAssist.AssistResult result = CallAudioCaptureAssist.enable(this);
        captureModeText.setText((duringMonitoringStart ? "Speakerphone capture assist enabled. " : "")
                + result.userMessage);
        appendLog(timestamp() + " speaker assist: " + result.logMessage);
        if (!result.routed && !duringMonitoringStart) {
            Toast.makeText(this, "Tap Speaker in the phone call UI.", Toast.LENGTH_LONG).show();
        }
    }

    private void saveLastChunkForDebugging() {
        if (lastChunkWavBytes == null || lastChunkWavBytes.length == 0) {
            Toast.makeText(this, "No audio chunk available yet.", Toast.LENGTH_SHORT).show();
            return;
        }
        File directory = new File(getExternalFilesDir(null), "debug_chunks");
        if (!directory.exists() && !directory.mkdirs()) {
            Toast.makeText(this, "Could not create debug folder.", Toast.LENGTH_LONG).show();
            return;
        }

        String stamp = new SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(new Date());
        File out = new File(directory, "callshield-debug-chunk-" + stamp + "-chunk" + lastChunkIndex + ".wav");
        try (FileOutputStream stream = new FileOutputStream(out)) {
            stream.write(lastChunkWavBytes);
            Toast.makeText(this, "Saved: " + out.getName(), Toast.LENGTH_LONG).show();
            appendLog(timestamp() + " saved debug audio: " + out.getAbsolutePath());
        } catch (IOException error) {
            Toast.makeText(this, "Save failed: " + shortError(error), Toast.LENGTH_LONG).show();
            appendLog("Save last chunk failed: " + shortError(error));
        }
    }

    private void sendChunk(byte[] wavBytes) {
        String serverUrl = activeServerUrl;
        int index = chunkCounter.incrementAndGet();
        String callId = sessionId + "-chunk-" + index;

        if (!uploadInFlight.compareAndSet(false, true)) {
            runOnUiThread(() -> appendLog(timestamp() + " chunk " + index + " skipped; backend still processing"));
            return;
        }
        lastChunkWavBytes = Arrays.copyOf(wavBytes, wavBytes.length);
        lastChunkIndex = index;

        runOnUiThread(() -> {
            updateButtons(recordingActive);
            setStatus("Uploading chunk " + index + " (" + wavBytes.length / 1024 + " KB)");
            appendLog(timestamp() + " chunk " + index + " queued");
        });

        networkExecutor.submit(() -> {
            try {
                JSONObject response = apiClient.analyzeAudio(serverUrl, callId, wavBytes);
                runOnUiThread(() -> showResult(index, response));
            } catch (Exception error) {
                runOnUiThread(() -> {
                    setStatus("Upload failed");
                    showConnectionError(error, serverUrl);
                    appendLog("Chunk " + index + " failed: " + shortError(error));
                });
            } finally {
                uploadInFlight.set(false);
                if (stopSummaryPending.get()) {
                    runOnUiThread(this::showFinalSessionAlert);
                }
            }
        });
    }

    private void showResult(int chunkIndex, JSONObject json) {
        setStatus("Chunk " + chunkIndex + " analyzed");
        updateCallTimer();
        connectionText.setText("Connected. Last response in "
                + json.optDouble("processing_time_ms", 0.0)
                + " ms");

        StringBuilder out = new StringBuilder();
        out.append("Risk: ").append(json.optDouble("risk_score", 0.0)).append("/100")
                .append(" (").append(json.optString("risk_band", "unknown")).append(")\n");
        out.append("Warning: ").append(json.optString("warning_level", "none")).append("\n");
        out.append("Scam type: ").append(json.optString("scam_type", "unknown")).append("\n");
        out.append("Confidence: ").append(json.optString("confidence", "unknown")).append("\n");

        JSONObject raw = json.optJSONObject("raw_components");
        updateSpectrogram(raw);
        String heardText = extractHeardText(raw);
        String asrStatus = extractAsrStatus(raw);
        String heardDisplay = heardText.isEmpty()
                ? "[background/no speech ignored - ASR: " + asrStatus + "]"
                : heardText;
        out.append("Heard: ").append(heardDisplay).append("\n");
        out.append("ASR: ").append(asrStatus).append("\n");
        out.append("ASR quality: ").append(asrQualityLabel(raw, heardText)).append("\n");
        this.heardText.setText("Transcript: " + heardDisplay);

        JSONObject audio = raw != null ? raw.optJSONObject("audio") : null;
        if (audio != null) {
            out.append("Deepfake score: ").append(audio.optString("deepfake_score", "null")).append("\n");
            out.append("Audio signal: ").append(audio.optString("audio_signal_strength", "unknown")).append("\n");
            out.append("Used in fusion: ").append(audio.optBoolean("used_in_fusion", false)).append("\n");
            String fusionGate = audio.optString("fusion_gate", "");
            if (!fusionGate.isEmpty()) {
                out.append("Fusion gate: ").append(fusionGate).append("\n");
            }
            if (audioOnlyReview(audio, json)) {
                out.append("Audio-only signal: review, not scam risk.").append("\n");
            }
        }
        updateSignalDashboard(json, audio, heardDisplay);

        sessionAlertAnalyzer.addChunk(
                json.optDouble("risk_score", 0.0),
                json.optString("risk_band", "unknown"),
                json.optString("warning_level", "none"),
                json.optString("scam_type", "unknown"),
                heardText,
                extractDeepfakeScore(audio),
                audio != null && audio.optBoolean("used_in_fusion", false)
        );

        JSONArray cues = json.optJSONArray("detected_cues");
        if (cues != null && cues.length() > 0) {
            out.append("Cues: ").append(cues).append("\n");
        }
        String why = json.optString("why_flagged", "");
        if (!why.isEmpty()) {
            out.append("Why: ").append(why).append("\n");
        }

        resultText.setText(out.toString().trim());
        appendLog(timestamp() + " chunk " + chunkIndex + " -> "
                + json.optString("risk_band", "unknown")
                + " heard=\"" + truncate(heardText, 60) + "\"");
    }

    private void showFinalSessionAlert() {
        if (!stopSummaryPending.compareAndSet(true, false)) {
            return;
        }
        SessionAlertAnalyzer.SessionSummary summary = sessionAlertAnalyzer.summarize();
        saveLastSessionSummary(summary);
        setStatus("Stopped. Final alert: " + summary.alertTitle);
        liveStateText.setText("Session analyzed");
        riskKickerText.setText("FINAL RISK LEVEL");
        riskLevelText.setText(summary.alertTitle.toUpperCase(Locale.US));
        riskLevelText.setTextColor(summary.maxRisk >= 60.0 ? color("#FB7185") : color("#FDE68A"));
        riskScoreText.setText(summary.maxRisk + "/100 peak risk");
        riskSummaryText.setText("Analyzed " + summary.chunkCount
                + " chunks. Max risk " + summary.maxRisk
                + "/100, suspicious chunks " + summary.suspiciousChunks + ".");
        appendLog(timestamp() + " final alert saved: " + summary.alertTitle
                + " maxRisk=" + summary.maxRisk
                + " chunks=" + summary.chunkCount);

        resultText.setText("Final alert: " + summary.alertTitle + "\n\n" + summary.toDialogMessage());

        new AlertDialog.Builder(this)
                .setTitle("CallShield final alert: " + summary.alertTitle)
                .setMessage(summary.toDialogMessage())
                .setPositiveButton("OK", null)
                .setNeutralButton("View saved", (dialog, which) -> showSavedSessionSummary())
                .show();
    }

    private void saveLastSessionSummary(SessionAlertAnalyzer.SessionSummary summary) {
        getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit()
                .putString(PREF_LAST_SESSION_SUMMARY, summary.toSavedSessionText())
                .apply();
    }

    private void showSavedSessionSummary() {
        String saved = getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getString(PREF_LAST_SESSION_SUMMARY, "No saved session summary yet.");
        new AlertDialog.Builder(this)
                .setTitle("Saved CallShield session")
                .setMessage(saved)
                .setPositiveButton("OK", null)
                .show();
    }

    private double extractDeepfakeScore(JSONObject audio) {
        if (audio == null) {
            return 0.0;
        }
        Object value = audio.opt("deepfake_score");
        if (value instanceof Number) {
            return ((Number) value).doubleValue();
        }
        if (value instanceof String) {
            String text = ((String) value).trim();
            if (text.isEmpty() || "null".equalsIgnoreCase(text)) {
                return 0.0;
            }
            try {
                return Double.parseDouble(text);
            } catch (NumberFormatException ignored) {
                return 0.0;
            }
        }
        return 0.0;
    }

    private void updateSpectrogram(JSONObject raw) {
        JSONObject spectrogram = raw != null ? raw.optJSONObject("spectrogram") : null;
        if (spectrogram == null) {
            spectrogramStatusText.setText("Spectrogram: missing from backend response");
            spectrogramImage.setImageDrawable(null);
            return;
        }
        if (!spectrogram.optBoolean("available", false)) {
            spectrogramStatusText.setText("Spectrogram unavailable: "
                    + truncate(spectrogram.optString("error", "unknown error"), 90));
            spectrogramImage.setImageDrawable(null);
            return;
        }

        String imageBase64 = spectrogram.optString("image_base64", "");
        if (imageBase64.isEmpty()) {
            spectrogramStatusText.setText("Spectrogram unavailable: empty image");
            spectrogramImage.setImageDrawable(null);
            return;
        }

        try {
            byte[] bytes = Base64.decode(imageBase64, Base64.DEFAULT);
            Bitmap bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.length);
            if (bitmap == null) {
                spectrogramStatusText.setText("Spectrogram unavailable: image decode failed");
                spectrogramImage.setImageDrawable(null);
                return;
            }
            spectrogramImage.setImageBitmap(bitmap);
            spectrogramStatusText.setText("Log-mel: "
                    + spectrogram.optInt("n_mels", 0)
                    + " mel bins, "
                    + spectrogram.optInt("frames", 0)
                    + " frames, "
                    + spectrogram.optDouble("duration_seconds", 0.0)
                    + " sec");
        } catch (IllegalArgumentException error) {
            spectrogramStatusText.setText("Spectrogram unavailable: invalid image data");
            spectrogramImage.setImageDrawable(null);
        }
    }

    private void updateMicLevel(int percent) {
        updateCallTimer();
        int bars = Math.max(0, Math.min(10, (int) Math.ceil(percent / 10.0)));
        StringBuilder meter = new StringBuilder();
        for (int i = 0; i < 10; i++) {
            meter.append(i < bars ? '|' : '.');
        }
        micLevelText.setText("Mic level: " + percent + "%  " + meter);
        updateCallerAudioHearingState(percent);
    }

    private void updateCallerAudioHearingState(int percent) {
        if (!recordingActive || captureModeText == null) {
            return;
        }
        if (percent <= 1) {
            quietMicTicks += 1;
        } else {
            quietMicTicks = 0;
            if (notHearingNoticeShown && percent >= 4) {
                notHearingNoticeShown = false;
                captureModeText.setText("Hearing call audio through the microphone. Keep Speaker on and keep the phone close enough to the caller audio.");
            }
            return;
        }
        if (quietMicTicks >= 12 && !notHearingNoticeShown) {
            notHearingNoticeShown = true;
            captureModeText.setText("Not hearing caller audio. Turn on Speaker in the phone call UI, raise call volume, and keep CallShield near the phone speaker.");
            appendLog(timestamp() + " warning: mic level stayed near 0%; caller audio is not being captured");
        }
    }

    private boolean validateServerUrl(String serverUrl) {
        if (serverUrl.isEmpty()) {
            showStartBlocked(
                    "Backend URL required",
                    "Enter the backend URL and tap Test server before Start test."
            );
            return false;
        }
        if (!serverUrl.startsWith("http://") && !serverUrl.startsWith("https://")) {
            showStartBlocked(
                    "Invalid backend URL",
                    "Server URL must start with http:// or https://"
            );
            return false;
        }
        if (isPhysicalPhone() && serverUrl.contains("10.0.2.2")) {
            showEmulatorUrlWarning();
            return false;
        }
        return true;
    }

    private void showStartBlocked(String title, String message) {
        setStatus(title);
        connectionText.setText(message);
        appendLog(timestamp() + " Start test blocked: " + message);
        Toast.makeText(this, message, Toast.LENGTH_LONG).show();
    }

    private void showEmulatorUrlWarning() {
        String message = "10.0.2.2 works only on emulator. On a physical phone, use your laptop Wi-Fi IPv4, for example http://192.168.1.7:8010.";
        connectionText.setText(message);
        appendLog(message);
    }

    private void showConnectionError(Exception error, String serverUrl) {
        connectionText.setText("Cannot reach " + serverUrl
                + ". Check: backend is running, phone and laptop are on same Wi-Fi, Windows Firewall allows Python, and phone URL uses laptop IPv4.");
        appendLog("Connection error: " + shortError(error));
    }

    private String normalizedUrl() {
        return serverUrlInput.getText().toString().trim();
    }

    private String extractHeardText(JSONObject raw) {
        if (raw == null) {
            return "";
        }
        JSONObject asr = raw.optJSONObject("asr");
        if (asr != null) {
            String transcript = asr.optString("transcript", "").trim();
            if (!transcript.isEmpty()) {
                return transcript;
            }
        }
        return raw.optString("transcript", "").trim();
    }

    private String extractAsrStatus(JSONObject raw) {
        if (raw == null) {
            return "missing";
        }
        JSONObject asr = raw.optJSONObject("asr");
        if (asr == null) {
            return "missing";
        }
        String status = asr.optString("status", "unknown");
        String language = asr.optString("language", "");
        String error = asr.optString("error", "");
        if (error != null && !error.trim().isEmpty() && !"null".equalsIgnoreCase(error)) {
            return status + " - " + truncate(error.trim(), 80);
        }
        if (language != null && !language.trim().isEmpty() && !"null".equalsIgnoreCase(language)) {
            return status + " (" + language + ")";
        }
        return status;
    }

    private String asrQualityLabel(JSONObject raw, String heardText) {
        if (raw == null) {
            return "missing";
        }
        JSONObject asr = raw.optJSONObject("asr");
        if (asr == null) {
            return heardText == null || heardText.isEmpty() ? "missing" : "unknown";
        }
        String status = asr.optString("status", "unknown");
        if ("ok".equalsIgnoreCase(status) && heardText != null && !heardText.trim().isEmpty()) {
            return "usable transcript";
        }
        if ("no_speech".equalsIgnoreCase(status)) {
            return "ignored noisy/silent chunk";
        }
        if ("hallucination_suppressed".equalsIgnoreCase(status)) {
            return "hallucination suppressed";
        }
        if ("failed".equalsIgnoreCase(status) || "unavailable".equalsIgnoreCase(status)) {
            return "ASR unavailable";
        }
        return heardText == null || heardText.trim().isEmpty() ? "low confidence" : "review transcript";
    }

    private String loadServerUrl() {
        SharedPreferences prefs = getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        return prefs.getString(PREF_SERVER_URL, "");
    }

    private void saveServerUrl() {
        getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit()
                .putString(PREF_SERVER_URL, normalizedUrl())
                .apply();
    }

    private boolean isPhysicalPhone() {
        return !isLikelyEmulator();
    }

    private boolean isLikelyEmulator() {
        String fingerprint = Build.FINGERPRINT == null ? "" : Build.FINGERPRINT.toLowerCase(Locale.US);
        String model = Build.MODEL == null ? "" : Build.MODEL.toLowerCase(Locale.US);
        String product = Build.PRODUCT == null ? "" : Build.PRODUCT.toLowerCase(Locale.US);
        return fingerprint.contains("generic")
                || fingerprint.contains("emulator")
                || model.contains("emulator")
                || model.contains("sdk_gphone")
                || product.contains("sdk")
                || product.contains("emulator");
    }

    private LinearLayout row() {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        return row;
    }

    private LinearLayout card() {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(14), dp(14), dp(14), dp(14));
        card.setBackground(rounded("#111827", "#1E293B", 1, 14));
        return card;
    }

    private TextView label(String text) {
        TextView view = new TextView(this);
        view.setText(text);
        view.setTextSize(13);
        view.setTypeface(Typeface.DEFAULT_BOLD);
        view.setTextColor(color("#CBD5E1"));
        view.setPadding(0, dp(14), 0, dp(6));
        return view;
    }

    private TextView helperText() {
        TextView view = new TextView(this);
        view.setTextSize(12);
        view.setTextColor(color("#94A3B8"));
        view.setPadding(0, dp(8), 0, 0);
        return view;
    }

    private TextView panel(String text) {
        TextView view = new TextView(this);
        view.setText(text);
        view.setTextSize(14);
        view.setTextColor(color("#E5E7EB"));
        view.setBackground(rounded("#111827", "#1E293B", 1, 10));
        view.setPadding(dp(14), dp(12), dp(14), dp(12));
        return view;
    }

    private TextView sectionLabel(String text) {
        TextView view = new TextView(this);
        view.setText(text);
        view.setTextSize(12);
        view.setTypeface(Typeface.DEFAULT_BOLD);
        view.setLetterSpacing(0.08f);
        view.setTextColor(color("#C4B5FD"));
        return view;
    }

    private TextView checklistLine(String text) {
        TextView view = new TextView(this);
        view.setText("- " + text);
        view.setTextSize(13);
        view.setTextColor(color("#F8FAFC"));
        view.setPadding(0, dp(5), 0, 0);
        return view;
    }

    private LinearLayout signalRow(String title, String subtitle, String status, String accent) {
        LinearLayout item = row();
        item.setPadding(dp(12), dp(10), dp(10), dp(10));
        item.setBackground(rounded("#0E1024", "#302653", 1, 12));

        TextView icon = new TextView(this);
        icon.setText("|||");
        icon.setGravity(Gravity.CENTER);
        icon.setTextSize(15);
        icon.setTypeface(Typeface.DEFAULT_BOLD);
        icon.setTextColor(color(accent));
        icon.setBackground(rounded("#111827", accent, 1, 10));
        LinearLayout.LayoutParams iconParams = new LinearLayout.LayoutParams(dp(42), dp(42));
        iconParams.setMargins(0, 0, dp(10), 0);
        item.addView(icon, iconParams);

        LinearLayout textColumn = new LinearLayout(this);
        textColumn.setOrientation(LinearLayout.VERTICAL);
        TextView titleView = new TextView(this);
        titleView.setText(title);
        titleView.setTextSize(15);
        titleView.setTypeface(Typeface.DEFAULT_BOLD);
        titleView.setTextColor(Color.WHITE);
        textColumn.addView(titleView);

        TextView subtitleView = new TextView(this);
        subtitleView.setText(subtitle);
        subtitleView.setTextSize(12);
        subtitleView.setTextColor(color("#A5B4FC"));
        subtitleView.setPadding(0, dp(2), 0, 0);
        textColumn.addView(subtitleView);
        item.addView(textColumn, weightWrap(1));

        TextView pill = new TextView(this);
        pill.setText(status);
        pill.setGravity(Gravity.CENTER);
        pill.setTextSize(12);
        pill.setTypeface(Typeface.DEFAULT_BOLD);
        pill.setTextColor(Color.WHITE);
        pill.setPadding(dp(10), dp(5), dp(10), dp(5));
        pill.setBackground(rounded("#334155", "#64748B", 1, 14));
        item.addView(pill);

        return item;
    }

    private Button actionButton(String text, String background, String textColor) {
        Button button = new Button(this);
        button.setText(text);
        button.setAllCaps(false);
        button.setTextSize(14);
        button.setTypeface(Typeface.DEFAULT_BOLD);
        button.setTextColor(color(textColor));
        button.setBackground(rounded(background, background, 0, 10));
        button.setMinHeight(dp(48));
        return button;
    }

    private void updateSignalDashboard(JSONObject json, JSONObject audio, String heardDisplay) {
        double risk = json.optDouble("risk_score", 0.0);
        String band = json.optString("risk_band", "safe");
        String warning = json.optString("warning_level", "none");
        String scamType = json.optString("scam_type", "unknown");
        String why = json.optString("why_flagged", "");
        JSONArray cues = json.optJSONArray("detected_cues");

        double deepfakeScore = extractDeepfakeScore(audio);
        boolean audioUsed = audio != null && audio.optBoolean("used_in_fusion", false);
        boolean audioOnlyReview = audioOnlyReview(audio, json);
        String audioSignal = audio != null ? audio.optString("audio_signal_strength", "unknown") : "unknown";
        if (audioOnlyReview) {
            setSignal(audioSignalPill, audioSignalSubtitle, "REVIEW",
                    "Audio-only signal held for text corroboration", "#A855F7");
        } else if (!audioUsed) {
            setSignal(audioSignalPill, audioSignalSubtitle, "OFF", "Audio ignored by fusion gate", "#64748B");
        } else if (deepfakeScore >= 0.5) {
            setSignal(audioSignalPill, audioSignalSubtitle, "HIGH",
                    "Synthetic voice score " + String.format(Locale.US, "%.3f", deepfakeScore),
                    "#EF4444");
        } else if (deepfakeScore >= 0.1978759765625) {
            setSignal(audioSignalPill, audioSignalSubtitle, "MEDIUM",
                    "Weak audio signal score " + String.format(Locale.US, "%.3f", deepfakeScore),
                    "#F59E0B");
        } else {
            setSignal(audioSignalPill, audioSignalSubtitle, "LOW",
                    "Audio signal " + audioSignal,
                    "#22C55E");
        }

        boolean hasCues = cues != null && cues.length() > 0;
        if (!"unknown".equalsIgnoreCase(scamType) || hasCues || risk >= 35.0) {
            String languageStatus = risk >= 65.0 ? "HIGH" : "MEDIUM";
            String languageColor = risk >= 65.0 ? "#EF4444" : "#F59E0B";
            setSignal(languageSignalPill, languageSignalSubtitle, languageStatus,
                    "Detected " + ("unknown".equalsIgnoreCase(scamType) ? "suspicious language" : scamType),
                    languageColor);
        } else if (heardDisplay.startsWith("[")) {
            setSignal(languageSignalPill, languageSignalSubtitle, "LOW",
                    "No usable transcript yet", "#22C55E");
        } else {
            setSignal(languageSignalPill, languageSignalSubtitle, "LOW",
                    "Transcript checked with no scam pattern", "#22C55E");
        }

        if ("hard".equalsIgnoreCase(warning) || risk >= 65.0) {
            setSignal(identitySignalPill, identitySignalSubtitle, "HIGH",
                    "Verify by callback before acting", "#EF4444");
        } else if ("soft".equalsIgnoreCase(warning) || risk >= 35.0) {
            setSignal(identitySignalPill, identitySignalSubtitle, "MEDIUM",
                    "Use safe phrase or trusted callback", "#F59E0B");
        } else {
            setSignal(identitySignalPill, identitySignalSubtitle, "LOW",
                    "No identity pressure detected", "#22C55E");
        }

        riskKickerText.setText("RISK LEVEL");
        riskLevelText.setText(audioOnlyReview ? "AUDIO REVIEW" : displayRisk(band, risk));
        riskLevelText.setTextColor(audioOnlyReview ? color("#C084FC") : riskColor(risk, band));
        riskScoreText.setText(String.format(Locale.US, "%.1f/100 overall risk", risk));
        riskSummaryText.setText(audioOnlyReview
                ? "Audio sounded synthetic, but scam-language evidence was weak. Treat as review, not scam risk."
                : why.isEmpty()
                ? "This call is being analyzed across audio, language, and identity signals."
                : why);
        updateActions(risk, band, warning, (audioUsed || audioOnlyReview) && deepfakeScore >= 0.5);
    }

    private boolean audioOnlyReview(JSONObject audio, JSONObject json) {
        if (audio == null) {
            return false;
        }
        double risk = json.optDouble("risk_score", 0.0);
        String band = json.optString("risk_band", "safe");
        String fusionGate = audio.optString("fusion_gate", "");
        return extractDeepfakeScore(audio) >= 0.5
                && "held_for_text_corroboration".equalsIgnoreCase(fusionGate)
                && ("safe".equalsIgnoreCase(band) || risk < 35.0);
    }

    private void setSignal(TextView pill, TextView subtitle, String status, String detail, String color) {
        pill.setText(status);
        pill.setBackground(rounded(color, color, 0, 14));
        subtitle.setText(detail);
    }

    private void updateActions(double risk, String band, String warning, boolean strongAudioSignal) {
        if (risk >= 65.0 || "hard".equalsIgnoreCase(warning) || "critical".equalsIgnoreCase(band)) {
            actionOneText.setText("- Do not send money, OTP, PIN, passwords, or documents.");
            actionTwoText.setText("- End the call and verify using an official number.");
            actionThreeText.setText("- Save this session as evidence for review.");
            return;
        }
        if (risk >= 35.0 || "soft".equalsIgnoreCase(warning) || strongAudioSignal) {
            actionOneText.setText("- Pause before acting on the caller's request.");
            actionTwoText.setText("- Verify identity with a trusted callback or safe phrase.");
            actionThreeText.setText("- Treat synthetic-voice evidence as a supporting signal.");
            return;
        }
        actionOneText.setText("- Continue monitoring the call without sharing private details.");
        actionTwoText.setText("- Use callback verification if money or identity comes up.");
        actionThreeText.setText("- Stop to save all chunk scores and session analysis.");
    }

    private String displayRisk(String band, double risk) {
        if ("critical".equalsIgnoreCase(band)) {
            return "CRITICAL RISK";
        }
        if ("high".equalsIgnoreCase(band)) {
            return "HIGH RISK";
        }
        if ("suspicious".equalsIgnoreCase(band) || risk >= 35.0) {
            return "REVIEW CALL";
        }
        return "SAFE";
    }

    private int riskColor(double risk, String band) {
        if ("critical".equalsIgnoreCase(band) || risk >= 80.0) {
            return color("#F87171");
        }
        if ("high".equalsIgnoreCase(band) || risk >= 65.0) {
            return color("#FB7185");
        }
        if ("suspicious".equalsIgnoreCase(band) || risk >= 35.0) {
            return color("#F59E0B");
        }
        return color("#86EFAC");
    }

    private void updateCallTimer() {
        if (sessionStartedAtMillis <= 0L) {
            timerText.setText("00:00");
            return;
        }
        long elapsedSeconds = Math.max(0L, (System.currentTimeMillis() - sessionStartedAtMillis) / 1000L);
        long minutes = elapsedSeconds / 60L;
        long seconds = elapsedSeconds % 60L;
        timerText.setText(String.format(Locale.US, "%02d:%02d", minutes, seconds));
    }

    private GradientDrawable rounded(String fill, String stroke, int strokeDp, int radiusDp) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(color(fill));
        drawable.setCornerRadius(dp(radiusDp));
        if (strokeDp > 0) {
            drawable.setStroke(dp(strokeDp), color(stroke));
        }
        return drawable;
    }

    private LinearLayout.LayoutParams matchWrap() {
        return new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        );
    }

    private LinearLayout.LayoutParams weightWrap(int weight) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                0,
                LinearLayout.LayoutParams.WRAP_CONTENT,
                weight
        );
        params.setMargins(dp(4), 0, dp(4), 0);
        return params;
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density);
    }

    private int color(String value) {
        return Color.parseColor(value);
    }

    private void setStatus(String message) {
        statusText.setText(message);
    }

    private void appendLog(String message) {
        String existing = logText.getText().toString();
        String combined = existing.isEmpty() ? message : existing + "\n" + message;
        String[] lines = combined.split("\n");
        if (lines.length > MAX_LOG_LINES) {
            StringBuilder trimmed = new StringBuilder();
            for (int i = lines.length - MAX_LOG_LINES; i < lines.length; i++) {
                if (trimmed.length() > 0) {
                    trimmed.append('\n');
                }
                trimmed.append(lines[i]);
            }
            combined = trimmed.toString();
        }
        logText.setText(combined);
    }

    private void updateButtons(boolean recording) {
        startButton.setEnabled(!recording);
        stopButton.setEnabled(recording);
        testButton.setEnabled(!recording);
        boolean canSaveChunk = lastChunkWavBytes != null && lastChunkWavBytes.length > 0;
        saveLastChunkButton.setEnabled(canSaveChunk);
        startButton.setAlpha(recording ? 0.45f : 1.0f);
        stopButton.setAlpha(recording ? 1.0f : 0.55f);
        testButton.setAlpha(recording ? 0.45f : 1.0f);
        saveLastChunkButton.setAlpha(canSaveChunk ? 1.0f : 0.55f);
    }

    private static String truncate(String value, int maxLength) {
        if (value == null || value.length() <= maxLength) {
            return value == null ? "" : value;
        }
        return value.substring(0, maxLength - 3) + "...";
    }

    private static String shortError(Exception error) {
        String message = error.getMessage();
        if (message == null || message.trim().isEmpty()) {
            return error.getClass().getSimpleName();
        }
        return message.length() > 140 ? message.substring(0, 137) + "..." : message;
    }

    private static String timestamp() {
        return new SimpleDateFormat("HH:mm:ss", Locale.US).format(new Date());
    }
}

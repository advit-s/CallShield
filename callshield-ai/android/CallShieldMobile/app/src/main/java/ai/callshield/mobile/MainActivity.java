package ai.callshield.mobile;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
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
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

public final class MainActivity extends Activity {
    private static final int REQUEST_RECORD_AUDIO = 1001;
    private static final int MAX_LOG_LINES = 28;
    private static final String PREFS = "callshield_mobile";
    private static final String PREF_SERVER_URL = "server_url";
    private static final String PREF_LAST_SESSION_SUMMARY = "last_session_summary";
    private static final String EMULATOR_SERVER_URL = "http://10.0.2.2:8000";

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
    private TextView connectionText;
    private TextView statusText;
    private TextView micLevelText;
    private TextView heardText;
    private TextView spectrogramStatusText;
    private ImageView spectrogramImage;
    private TextView resultText;
    private TextView logText;
    private String sessionId;
    private String activeServerUrl;

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
        if (isPhysicalPhone() && serverUrlInput.getText().toString().contains("10.0.2.2")) {
            showEmulatorUrlWarning();
        }
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
        int padding = dp(20);

        ScrollView scrollView = new ScrollView(this);
        scrollView.setFillViewport(true);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(padding, padding, padding, padding);
        root.setBackgroundColor(color("#0B1120"));
        scrollView.addView(root);

        TextView eyebrow = new TextView(this);
        eyebrow.setText("LIVE MOBILE DEMO");
        eyebrow.setTextSize(12);
        eyebrow.setTypeface(Typeface.DEFAULT_BOLD);
        eyebrow.setTextColor(color("#2DD4BF"));
        eyebrow.setLetterSpacing(0.08f);
        root.addView(eyebrow);

        TextView title = new TextView(this);
        title.setText("CallShield");
        title.setTextSize(34);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setTextColor(Color.WHITE);
        title.setPadding(0, dp(4), 0, 0);
        root.addView(title);

        TextView subtitle = new TextView(this);
        subtitle.setText("Streams 8-second speakerphone/test-call microphone chunks to your local scam and deepfake detector.");
        subtitle.setTextSize(15);
        subtitle.setTextColor(color("#AAB7CF"));
        subtitle.setPadding(0, dp(8), 0, dp(20));
        root.addView(subtitle);

        LinearLayout serverCard = card();
        serverCard.addView(label("Server URL"));

        serverUrlInput = new EditText(this);
        serverUrlInput.setSingleLine(true);
        serverUrlInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        serverUrlInput.setImeOptions(EditorInfo.IME_ACTION_DONE);
        serverUrlInput.setText(loadServerUrl());
        serverUrlInput.setHint(isPhysicalPhone() ? "http://192.168.1.x:8000" : EMULATOR_SERVER_URL);
        serverUrlInput.setTextColor(Color.WHITE);
        serverUrlInput.setHintTextColor(color("#64748B"));
        serverUrlInput.setTextSize(18);
        serverUrlInput.setSelectAllOnFocus(false);
        serverCard.addView(serverUrlInput, matchWrap());

        TextView urlHelp = helperText();
        urlHelp.setText(isPhysicalPhone()
                ? "Real phone: use your laptop Wi-Fi IPv4. Run ipconfig on laptop, then enter http://IPv4:8000. Do not use 10.0.2.2 on a phone."
                : "Emulator: use http://10.0.2.2:8000. Real phone: use laptop Wi-Fi IPv4.");
        serverCard.addView(urlHelp);

        LinearLayout serverButtons = row();
        testButton = actionButton("Test server", "#334155", "#FFFFFF");
        testButton.setOnClickListener(view -> testServer());
        serverButtons.addView(testButton, weightWrap(1));
        serverCard.addView(serverButtons);
        root.addView(serverCard, matchWrap());

        LinearLayout controls = row();
        controls.setPadding(0, dp(14), 0, dp(8));
        startButton = actionButton("Start", "#14B8A6", "#031B1A");
        startButton.setOnClickListener(view -> startStreaming());
        controls.addView(startButton, weightWrap(1));

        stopButton = actionButton("Stop", "#475569", "#FFFFFF");
        stopButton.setOnClickListener(view -> stopStreaming());
        controls.addView(stopButton, weightWrap(1));
        root.addView(controls);

        connectionText = panel("Connection not tested");
        root.addView(label("Connection"));
        root.addView(connectionText, matchWrap());

        statusText = panel("Ready");
        root.addView(label("Status"));
        root.addView(statusText, matchWrap());

        micLevelText = panel("Mic level: waiting");
        root.addView(label("Microphone"));
        root.addView(micLevelText, matchWrap());

        heardText = panel("Heard: waiting for an 8-second speech chunk");
        root.addView(label("Heard by CallShield"));
        root.addView(heardText, matchWrap());

        spectrogramStatusText = panel("Waiting for analyzed audio chunk");
        root.addView(label("Log-mel spectrogram"));
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

        resultText = panel("No chunks analyzed yet.");
        root.addView(label("Latest result"));
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

    private void startStreaming() {
        saveServerUrl();
        activeServerUrl = normalizedUrl();
        if (!validateServerUrl(activeServerUrl)) {
            return;
        }
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, REQUEST_RECORD_AUDIO);
            return;
        }
        sessionId = "android-poc-" + System.currentTimeMillis();
        chunkCounter.set(0);
        uploadInFlight.set(false);
        stopSummaryPending.set(false);
        sessionAlertAnalyzer.reset();
        logText.setText("");
        resultText.setText("Listening for the first 8-second chunk...");
        heardText.setText("Heard: listening. Speak clearly for 8 seconds...");
        spectrogramStatusText.setText("Waiting for analyzed audio chunk");
        spectrogramImage.setImageDrawable(null);
        micLevelText.setText("Mic level: listening...");
        appendLog("Session: " + sessionId);
        streamer.start();
        updateButtons(true);
        setStatus("Recording. Keep the call/audio on speakerphone.");
    }

    private void stopStreaming() {
        if (streamer != null) {
            streamer.stop();
        }
        micLevelText.setText("Mic level: stopped");
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
            startStreaming();
        } else {
            Toast.makeText(this, "Microphone permission is required.", Toast.LENGTH_LONG).show();
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

        runOnUiThread(() -> {
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
        connectionText.setText("Connected. Last response in "
                + json.optDouble("processing_time_ms", 0.0) + " ms");

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
        this.heardText.setText("Heard: " + heardDisplay);

        JSONObject audio = raw != null ? raw.optJSONObject("audio") : null;
        if (audio != null) {
            out.append("Deepfake score: ").append(audio.optString("deepfake_score", "null")).append("\n");
            out.append("Audio signal: ").append(audio.optString("audio_signal_strength", "unknown")).append("\n");
            out.append("Used in fusion: ").append(audio.optBoolean("used_in_fusion", false)).append("\n");
            String fusionGate = audio.optString("fusion_gate", "");
            if (!fusionGate.isEmpty()) {
                out.append("Fusion gate: ").append(fusionGate).append("\n");
            }
        }

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
        int bars = Math.max(0, Math.min(10, (int) Math.ceil(percent / 10.0)));
        StringBuilder meter = new StringBuilder();
        for (int i = 0; i < 10; i++) {
            meter.append(i < bars ? '|' : '.');
        }
        micLevelText.setText("Mic level: " + percent + "%  " + meter);
    }

    private boolean validateServerUrl(String serverUrl) {
        if (serverUrl.isEmpty()) {
            connectionText.setText("Enter server URL first.");
            return false;
        }
        if (!serverUrl.startsWith("http://") && !serverUrl.startsWith("https://")) {
            connectionText.setText("Server URL must start with http:// or https://");
            return false;
        }
        if (isPhysicalPhone() && serverUrl.contains("10.0.2.2")) {
            showEmulatorUrlWarning();
            return false;
        }
        return true;
    }

    private void showEmulatorUrlWarning() {
        String message = "10.0.2.2 works only on emulator. On this Redmi phone, run ipconfig on your laptop and use Wi-Fi IPv4, for example http://192.168.1.7:8000.";
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

    private String loadServerUrl() {
        SharedPreferences prefs = getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        return prefs.getString(PREF_SERVER_URL, isPhysicalPhone() ? "" : EMULATOR_SERVER_URL);
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
        startButton.setAlpha(recording ? 0.45f : 1.0f);
        stopButton.setAlpha(recording ? 1.0f : 0.55f);
        testButton.setAlpha(recording ? 0.45f : 1.0f);
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

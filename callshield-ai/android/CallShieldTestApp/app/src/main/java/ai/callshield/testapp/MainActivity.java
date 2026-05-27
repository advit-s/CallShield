package ai.callshield.testapp;

import android.app.Activity;
import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Bundle;
import android.text.InputType;
import android.text.method.ScrollingMovementMethod;
import android.view.Gravity;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONObject;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

public final class MainActivity extends Activity {
    private static final String PREFS = "callshield_test_app";
    private static final String PREF_SERVER_URL = "server_url";
    private static final String DEFAULT_SERVER_URL = "http://10.0.2.2:8000";
    private static final String DEFAULT_TRANSCRIPT =
            "Send Rs 25000 immediately via UPI. Do not tell anyone.";

    private final ExecutorService networkExecutor = Executors.newSingleThreadExecutor();
    private final CallShieldTestApiClient apiClient = new CallShieldTestApiClient();
    private final AtomicBoolean requestInFlight = new AtomicBoolean(false);

    private EditText serverUrlInput;
    private EditText transcriptInput;
    private TextView statusText;
    private TextView resultText;
    private TextView logText;
    private Button healthButton;
    private Button modelStatusButton;
    private Button analyzeButton;
    private Button scoreButton;
    private Button clearButton;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(buildUi());
        setStatus("Ready. Start the CallShield backend, then tap a test button.");
    }

    @Override
    protected void onDestroy() {
        networkExecutor.shutdownNow();
        super.onDestroy();
    }

    private View buildUi() {
        int padding = dp(18);
        ScrollView scrollView = new ScrollView(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(padding, padding, padding, padding);
        root.setBackgroundColor(Color.rgb(248, 250, 252));
        scrollView.addView(root);

        TextView title = new TextView(this);
        title.setText("CallShield Test App");
        title.setTextSize(26);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setTextColor(Color.rgb(15, 23, 42));
        root.addView(title);

        TextView badge = new TextView(this);
        badge.setText("Testing Only - API smoke tester, no microphone capture");
        badge.setTextSize(13);
        badge.setTypeface(Typeface.DEFAULT_BOLD);
        badge.setTextColor(Color.WHITE);
        badge.setBackgroundColor(Color.rgb(37, 99, 235));
        badge.setGravity(Gravity.CENTER);
        badge.setPadding(dp(10), dp(8), dp(10), dp(8));
        LinearLayout.LayoutParams badgeParams = matchWrap();
        badgeParams.setMargins(0, dp(10), 0, dp(14));
        root.addView(badge, badgeParams);

        root.addView(label("Backend URL"));
        serverUrlInput = new EditText(this);
        serverUrlInput.setSingleLine(true);
        serverUrlInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        serverUrlInput.setImeOptions(EditorInfo.IME_ACTION_DONE);
        serverUrlInput.setText(loadServerUrl());
        serverUrlInput.setHint("http://10.0.2.2:8000");
        root.addView(serverUrlInput, matchWrap());

        root.addView(label("Transcript"));
        transcriptInput = new EditText(this);
        transcriptInput.setMinLines(4);
        transcriptInput.setGravity(Gravity.TOP | Gravity.START);
        transcriptInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        transcriptInput.setText(DEFAULT_TRANSCRIPT);
        root.addView(transcriptInput, matchWrap());

        LinearLayout firstRow = buttonRow();
        healthButton = actionButton("GET /health", () -> runRequest("Health", () ->
                apiClient.health(currentServerUrl())));
        modelStatusButton = actionButton("GET /model-status", () -> runRequest("Model Status", () ->
                apiClient.modelStatus(currentServerUrl())));
        firstRow.addView(healthButton, weightWrap(1));
        firstRow.addView(modelStatusButton, weightWrap(1));
        root.addView(firstRow);

        LinearLayout secondRow = buttonRow();
        analyzeButton = actionButton("Analyze Transcript", () -> runRequest("Analyze Transcript", () ->
                apiClient.analyzeTranscript(currentServerUrl(), nextCallId("android-test-transcript"), transcriptText())));
        scoreButton = actionButton("Score Call", () -> runRequest("Score Call", () ->
                apiClient.scoreCall(currentServerUrl(), nextCallId("android-test-score"), transcriptText())));
        secondRow.addView(analyzeButton, weightWrap(1));
        secondRow.addView(scoreButton, weightWrap(1));
        root.addView(secondRow);

        clearButton = actionButton("Clear Result", () -> {
            resultText.setText("No request run yet.");
            logText.setText("");
            setStatus("Cleared.");
        });
        root.addView(clearButton, matchWrap());

        root.addView(label("Status"));
        statusText = panel("");
        root.addView(statusText, matchWrap());

        root.addView(label("Result"));
        resultText = panel("No request run yet.");
        resultText.setMinLines(12);
        resultText.setMovementMethod(new ScrollingMovementMethod());
        root.addView(resultText, matchWrap());

        root.addView(label("Log"));
        logText = panel("");
        logText.setMinLines(6);
        logText.setMovementMethod(new ScrollingMovementMethod());
        root.addView(logText, matchWrap());

        TextView note = new TextView(this);
        note.setText("Use 10.0.2.2 for the Android emulator. Use your laptop LAN IP for a physical phone. This app sends text/API requests only.");
        note.setTextSize(13);
        note.setTextColor(Color.rgb(100, 116, 139));
        note.setPadding(0, dp(16), 0, 0);
        root.addView(note);

        return scrollView;
    }

    private Button actionButton(String text, Runnable action) {
        Button button = new Button(this);
        button.setText(text);
        button.setAllCaps(false);
        button.setOnClickListener(view -> action.run());
        return button;
    }

    private void runRequest(String label, RequestAction action) {
        saveServerUrl();
        if (!requestInFlight.compareAndSet(false, true)) {
            Toast.makeText(this, "Request already running.", Toast.LENGTH_SHORT).show();
            return;
        }
        setButtonsEnabled(false);
        setStatus(label + " running...");
        appendLog(timestamp() + " " + label + " started");

        networkExecutor.submit(() -> {
            try {
                JSONObject response = action.run();
                runOnUiThread(() -> {
                    resultText.setText(formatJson(response));
                    setStatus(label + " complete");
                    appendLog(timestamp() + " " + label + " OK");
                });
            } catch (Exception error) {
                runOnUiThread(() -> {
                    resultText.setText(error.getMessage());
                    setStatus(label + " failed");
                    appendLog(timestamp() + " " + label + " failed: " + error.getMessage());
                });
            } finally {
                requestInFlight.set(false);
                runOnUiThread(() -> setButtonsEnabled(true));
            }
        });
    }

    private String currentServerUrl() {
        return serverUrlInput.getText().toString().trim();
    }

    private String transcriptText() {
        return transcriptInput.getText().toString();
    }

    private String nextCallId(String prefix) {
        return prefix + "-" + System.currentTimeMillis();
    }

    private TextView label(String text) {
        TextView view = new TextView(this);
        view.setText(text);
        view.setTextSize(13);
        view.setTypeface(Typeface.DEFAULT_BOLD);
        view.setTextColor(Color.rgb(51, 65, 85));
        view.setPadding(0, dp(12), 0, dp(5));
        return view;
    }

    private TextView panel(String text) {
        TextView view = new TextView(this);
        view.setText(text);
        view.setTextSize(14);
        view.setTextColor(Color.rgb(15, 23, 42));
        view.setBackgroundColor(Color.WHITE);
        view.setPadding(dp(12), dp(10), dp(12), dp(10));
        return view;
    }

    private LinearLayout buttonRow() {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setPadding(0, dp(12), 0, 0);
        return row;
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

    private void setButtonsEnabled(boolean enabled) {
        healthButton.setEnabled(enabled);
        modelStatusButton.setEnabled(enabled);
        analyzeButton.setEnabled(enabled);
        scoreButton.setEnabled(enabled);
        clearButton.setEnabled(enabled);
    }

    private void setStatus(String message) {
        statusText.setText(message);
    }

    private void appendLog(String message) {
        String existing = logText.getText().toString();
        logText.setText(existing.isEmpty() ? message : existing + "\n" + message);
    }

    private String loadServerUrl() {
        SharedPreferences prefs = getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        return prefs.getString(PREF_SERVER_URL, DEFAULT_SERVER_URL);
    }

    private void saveServerUrl() {
        getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit()
                .putString(PREF_SERVER_URL, currentServerUrl())
                .apply();
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density);
    }

    private static String timestamp() {
        return new SimpleDateFormat("HH:mm:ss", Locale.US).format(new Date());
    }

    private static String formatJson(JSONObject json) {
        try {
            return json.toString(2);
        } catch (Exception error) {
            return json.toString();
        }
    }

    private interface RequestAction {
        JSONObject run() throws Exception;
    }
}

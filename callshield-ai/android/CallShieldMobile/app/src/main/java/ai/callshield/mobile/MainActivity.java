package ai.callshield.mobile;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.ContentResolver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.VectorDrawable;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.OpenableColumns;
import android.text.InputType;
import android.text.method.ScrollingMovementMethod;
import android.util.Base64;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.inputmethod.EditorInfo;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

public final class MainActivity extends Activity {

    // ── permissions & prefs ──────────────────────────────────────────
    private static final int REQ_AUDIO = 1001;
    private static final int REQ_CALL = 1002;
    private static final int REQ_PICK_RECORDING = 1003;
    private static final int MAX_IMPORT_BYTES = 10 * 1024 * 1024;
    private static final String PREFS = "callshield_mobile";
    private static final String K_URL = "server_url";
    private static final String K_SAVE = "last_session_summary";
    private static final String K_HISTORY = "call_history";
    private static final String EMU_URL = "http://10.0.2.2:8000";

    public static final String ACTION_OPEN_FROM_CALL_NOTIFICATION =
            "ai.callshield.mobile.action.OPEN_FROM_CALL_NOTIFICATION";
    public static final String ACTION_OPEN_LAST_REPORT =
            "ai.callshield.mobile.action.OPEN_LAST_REPORT";

    private static final int TAB_SCAN = 0, TAB_HIST = 1, TAB_SET = 2;

    // ── palette (calm dark slate) ────────────────────────────────────
    private static final String C_BG = "#05060A";
    private static final String C_BAR = "#0B0A1A";
    private static final String C_SURFACE = "#0F172A";
    private static final String C_SURF_ALT = "#111827";
    private static final String C_BORDER = "#1F2937";
    private static final String C_TEAL = "#14B8A6";
    private static final String C_CYAN = "#22D3EE";
    private static final String C_GREEN = "#22C55E";
    private static final String C_AMBER = "#F59E0B";
    private static final String C_RED = "#F87171";
    private static final String C_ORANGE = "#FB7185";
    private static final String C_MUTED = "#9CA3AF";
    private static final String C_LABEL = "#94A3B8";
    private static final String C_WHITE = "#FFFFFF";
    private static final String C_INDIGO = "#312E81";
    private static final String C_DISABLED = "#6B7280";
    private static final String C_NAV = "#1E293B";

    // ── threading & services ─────────────────────────────────────────
    private final ExecutorService net = Executors.newSingleThreadExecutor();
    private final CallShieldApiClient api = new CallShieldApiClient();
    private final SessionAlertAnalyzer analy = new SessionAlertAnalyzer();
    private final AtomicInteger cnt = new AtomicInteger(0);
    private final AtomicBoolean fly = new AtomicBoolean(false);
    private final AtomicBoolean stopP = new AtomicBoolean(false);
    private AudioChunkStreamer streamer;

    // ── state ────────────────────────────────────────────────────────
    private int tab = TAB_SCAN;
    private String sid, url;
    private long t0;
    private byte[] lastWav;
    private int lastIdx, quiet;
    private boolean warned, scanning, fromIncall, micPending;

    // ── UI refs (names preserved for test compatibility) ─────────────
    private TextView topStatus, riskKicker, riskLabel, riskScore, riskSum;
    private TextView aTtl, aSub, lTtl, lSub, iTtl, iSub;
    private TextView liveTimer, micLvl, logTxt, connTxt, statTxt, modeHelp;
    private Button scanBtn, endBtn, srvBtn, saveChunkBtn, clearHistBtn;
    private EditText urlIn, editTextSessions;
    private Switch modeSw;
    private TextView heardTxt, specTxt;
    private ImageView specImg;
    private LinearLayout historyContainer;
    private java.util.List<HistoryEntry> allHistoryEntries = new ArrayList<>();

    // ═══════════════════════════════════════════════════════════════════
    // lifecycle
    // ═══════════════════════════════════════════════════════════════════
    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        setContentView(root());

        streamer = new AudioChunkStreamer(new AudioChunkStreamer.Listener() {
            @Override public void onChunk(byte[] w) { sendChunk(w); }
            @Override public void onLevel(int p) { runOnUiThread(() -> micUi(p)); }
            @Override public void onStatus(String m) { runOnUiThread(() -> log(m)); }
            @Override public void onError(Exception e) { runOnUiThread(() -> log("err: " + e.getMessage())); }
        });

        if (CallShieldSettings.isRealCallModeEnabled(this)) askCall();
        handleNotif(getIntent());
    }

    @Override protected void onNewIntent(Intent i) {
        super.onNewIntent(i);
        setIntent(i);
        handleNotif(i);
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQ_PICK_RECORDING
                && resultCode == RESULT_OK
                && data != null
                && data.getData() != null) {
            analyzeRecordingUri(data.getData());
        }
    }

    @Override protected void onResume() {
        super.onResume();
        CallShieldRuntime.markActivityVisible(this);
    }

    @Override protected void onPause() {
        CallShieldRuntime.markActivityHidden(this);
        super.onPause();
    }

    @Override protected void onDestroy() {
        if (streamer != null) streamer.stop();
        CallShieldRuntime.clearActivity(this);
        net.shutdownNow();
        super.onDestroy();
    }

    public void handlePhoneCallEndedFromReceiver() {
        if (scanning && fromIncall) {
            setStatus("Call ended. Saving.");
            endScan();
            return;
        }
        if (!scanning && topStatus != null) topStatus.setText("Call ended");
    }

    public void handlePhoneCallStartedFromReceiver() {
        startMonitoringFromIncomingCall();
    }

    // ═══════════════════════════════════════════════════════════════════
    // root layout — vertical LinearLayout (bar / content / nav)
    // ═══════════════════════════════════════════════════════════════════
    private View root() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(parse(C_BG));

        // App bar at top
        root.addView(bar());

        // Content fills remaining space
        ScrollView sv = new ScrollView(this);
        sv.setFillViewport(true);
        sv.setBackgroundColor(parse(C_BG));
        sv.setId(View.generateViewId());
        contentHolder = sv;
        swap();
        root.addView(sv, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                0, 1f));

        // Bottom nav at bottom
        root.addView(bottomNav(t -> { tab = t; swap(); }));

        return root;
    }

    private ScrollView contentHolder;

    private void swap() {
        if (contentHolder == null) return;
        contentHolder.removeAllViews();
        View page = page(tab);
        contentHolder.addView(page, new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT));
    }

    // ═══════════════════════════════════════════════════════════════════
    // app bar
    // ═══════════════════════════════════════════════════════════════════
    private LinearLayout bar() {
        LinearLayout bar = col();
        bar.setBackgroundColor(parse(C_BAR));
        int side = dp(16);
        bar.setPadding(side, dp(10), side, dp(8));
        bar.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT));

        LinearLayout row = row();
        row.setGravity(Gravity.CENTER_VERTICAL);

        // Shield icon via drawable
        ImageView shield = new ImageView(this);
        int iconSz = dp(24);
        LinearLayout.LayoutParams shieldLp =
                new LinearLayout.LayoutParams(iconSz, iconSz);
        shield.setLayoutParams(shieldLp);
        shield.setImageResource(getResourceId("drawable", "ic_shield"));
        shield.setScaleType(ImageView.ScaleType.FIT_CENTER);
        row.addView(shield);

        TextView title = tv("CallShield");
        title.setTextSize(18);
        title.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        title.setTextColor(Color.WHITE);
        title.setPadding(dp(8), 0, 0, 0);
        row.addView(title);

        // Spacer
        LinearLayout spacer = new LinearLayout(this);
        spacer.setLayoutParams(new LinearLayout.LayoutParams(0, 0, 1f));
        row.addView(spacer);

        // Status pill
        TextView pill = tv(scanning ? "LIVE" : "READY");
        pill.setTextSize(9);
        pill.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        pill.setTextColor(Color.WHITE);
        pill.setBackground(pillBg(scanning ? C_RED : C_GREEN));
        pill.setPadding(dp(8), dp(3), dp(8), dp(3));
        pill.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT));
        row.addView(pill);

        bar.addView(row);
        return bar;
    }

    private GradientDrawable pillBg(String color) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(parse(color));
        d.setCornerRadius(dp(10));
        return d;
    }

    private int getResourceId(String type, String name) {
        return getResources().getIdentifier(name, type, getPackageName());
    }

    // ═══════════════════════════════════════════════════════════════════
    // bottom nav — indicator dot, clean equal-width tabs
    // ═══════════════════════════════════════════════════════════════════
    private LinearLayout bottomNav(OnTab listener) {
        LinearLayout nav = row();
        nav.setOrientation(LinearLayout.HORIZONTAL);
        nav.setBackgroundColor(parse(C_BAR));
        nav.setElevation(dp(4));
        nav.setPadding(dp(4), dp(4), dp(4), dp(6));

        addNavTab(nav, "Scan", "ic_scan", TAB_SCAN, listener);
        addNavTab(nav, "History", "ic_history", TAB_HIST, listener);
        addNavTab(nav, "Settings", "ic_settings", TAB_SET, listener);
        return nav;
    }

    private void addNavTab(LinearLayout parent, String label,
                           String iconRes, int id, OnTab listener) {
        boolean on = (tab == id);
        LinearLayout item = col();
        item.setGravity(Gravity.CENTER);
        item.setTag(id);
        item.setPadding(dp(6), dp(4), dp(6), dp(2));

        int iconSz = dp(22);
        ImageView ic = new ImageView(this);
        ic.setImageResource(getResourceId("drawable", iconRes));
        LinearLayout.LayoutParams icLp = new LinearLayout.LayoutParams(iconSz, iconSz);
        ic.setLayoutParams(icLp);
        ic.setScaleType(ImageView.ScaleType.FIT_CENTER);
        ic.setColorFilter(on ? parse(C_TEAL) : parse("#6B7280"),
                android.graphics.PorterDuff.Mode.SRC_IN);
        item.addView(ic);

        TextView lb = tv(label);
        lb.setTextSize(10);
        lb.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        lb.setTextColor(on ? parse(C_TEAL) : parse("#6B7280"));
        lb.setPadding(0, dp(2), 0, 0);
        item.addView(lb);

        // subtle dot indicator below label when selected
        if (on) {
            View dot = new View(this);
            dot.setBackground(pillBg(C_TEAL));
            dot.setLayoutParams(new LinearLayout.LayoutParams(dp(4), dp(4)));
            dot.setPadding(0, dp(3), 0, 0);
            item.addView(dot);
        }

        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        p.gravity = Gravity.CENTER;
        parent.addView(item, p);

        item.setOnClickListener(v -> listener.on((int) v.getTag()));
    }

    interface OnTab { void on(int id); }

    // ═══════════════════════════════════════════════════════════════════
    // page router
    // ═══════════════════════════════════════════════════════════════════
    private View page(int t) {
        if (t == TAB_SCAN) return scanPage();
        if (t == TAB_HIST) return histPage();
        return settingsPage();
    }

    // ═══════════════════════════════════════════════════════════════════
    // SCAN PAGE
    // ═══════════════════════════════════════════════════════════════════
    private View scanPage() {
        LinearLayout r = col();
        int pad = dp(16);
        r.setPadding(pad, dp(12), pad, dp(20));

        // ── section: detection status ──────────────────────────────
        r.addView(heading("CallShield AI"));
        topStatus = tv(scanning ? "Monitoring audio..." : "Session analyzed");
        topStatus.setBackground(roundBg(C_SURF_ALT, C_BORDER, 1, 12));
        topStatus.setPadding(dp(14), dp(14), dp(14), dp(14));
        topStatus.setTextSize(14);
        r.addView(topStatus, mg(10));

        // ── section: three-signal analysis ─────────────────────────
        r.addView(heading("Three Signal Risk Analysis"));
        SigBag sig = new SigBag();
        r.addView(sigCard("Audio Deepfake & Replay", "ic_mic", "OFF", C_MUTED, "Audio ignored by fusion gate", sig));
        r.addView(sigCard("Scam Language Detection", "ic_language", "IDLE", C_MUTED, "Urgency / pressure phrases", sig));
        r.addView(sigCard("Identity Verification", "ic_person", "LOW", C_GREEN, "Callback + safe-phrase check", sig));
        aTtl = sig.t1; aSub = sig.s1;
        lTtl = sig.t2; lSub = sig.s2;
        iTtl = sig.t3; iSub = sig.s3;

        // ── section: overall risk ──────────────────────────────────
        r.addView(heading("Final risk level"));
        LinearLayout rc = riskCard();
        r.addView(rc, mg(10));

        LinearLayout live = dashboardCard("Live analysis");
        live.addView(infoPanel("Connection",
                loadUrl().isEmpty() ? "Backend URL missing" : "Backend URL set"), mg(6));
        live.addView(infoPanel("Microphone",
                scanning ? "Mic level active" : "Mic: waiting"), mg(6));
        live.addView(infoPanel("Latest result",
                "Risk: waiting\nWarning: none\nScam type: unknown\nASR: waiting"), mg(6));
        r.addView(live, mg(10));

        // ── backend setup helper card ──────────────────────────────
        if (loadUrl().isEmpty()) {
            LinearLayout wc = col();
            wc.setPadding(dp(16), dp(12), dp(16), dp(12));
            wc.setBackground(roundBg(C_SURFACE, C_ORANGE, 1, 12));

            TextView title = tv("Backend URL required", C_ORANGE, 13);
            title.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
            wc.addView(title);

            TextView msgText = tv("Add your laptop/server URL before scanning.", C_MUTED, 12);
            msgText.setPadding(0, dp(4), 0, dp(8));
            wc.addView(msgText);

            Button openSetBtn = makeBtn("Open Settings", C_TEAL);
            openSetBtn.setOnClickListener(v -> {
                tab = TAB_SET;
                setContentView(root());
                if (urlIn != null) urlIn.requestFocus();
            });
            wc.addView(openSetBtn, matchWrapLp());

            r.addView(wc, mg(10));
        }

        // ── section: call controls ────────────────────────────────
        scanBtn = makeBtn("Start Scan", C_TEAL);
        scanBtn.setOnClickListener(v -> startScan(false));
        endBtn = makeBtn("End Scan", C_INDIGO);
        endBtn.setEnabled(false);
        setEndScanDisabled();
        endBtn.setOnClickListener(v -> endScan());

        LinearLayout br = row();
        br.addView(scanBtn, weightLp());
        br.addView(endBtn, weightLp());
        r.addView(br, mg(10));

        // Speaker Assist Button
        Button spkBtn = makeBtn("Speaker Assist", C_SURFACE);
        spkBtn.setTextColor(parse(C_TEAL));
        spkBtn.setOnClickListener(v -> {
            enableSpeakerphoneAssist(true);
            Toast.makeText(this, "Routes call audio to speaker when Android allows it.", Toast.LENGTH_LONG).show();
        });
        r.addView(spkBtn, mg(10));

        Button importBtn = makeBtn("Analyze Recording File", C_NAV);
        importBtn.setTextColor(parse(C_CYAN));
        importBtn.setOnClickListener(v -> pickRecordingFile());
        r.addView(importBtn, mg(10));

        // ── Last Scan Session Card ─────────────────────────────────
        String savedTxt = getSharedPreferences(PREFS, MODE_PRIVATE).getString(K_SAVE, "");
        if (!savedTxt.isEmpty()) {
            LinearLayout lsc = col();
            lsc.setPadding(dp(16), dp(12), dp(16), dp(12));
            lsc.setBackground(roundBg(C_SURFACE, C_BORDER, 1, 12));

            TextView title = tv("Last Scan Session", C_TEAL, 12);
            title.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
            lsc.addView(title);

            TextView desc = tv("View details and copy full report below.", C_MUTED, 12);
            desc.setPadding(0, dp(4), 0, dp(8));
            lsc.addView(desc);

            LinearLayout actionRow = row();

            Button viewBtn = makeBtn("View Summary", C_NAV);
            viewBtn.setTextColor(parse(C_CYAN));
            viewBtn.setTextSize(11);
            viewBtn.setOnClickListener(v -> showSaved());
            actionRow.addView(viewBtn, weightLp());

            Button copyBtn = makeBtn("Copy Summary", C_NAV);
            copyBtn.setTextColor(parse(C_CYAN));
            copyBtn.setTextSize(11);
            copyBtn.setOnClickListener(v -> {
                android.content.ClipboardManager clipboard = (android.content.ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
                android.content.ClipData clip = android.content.ClipData.newPlainText("CallShield Session Summary", savedTxt);
                if (clipboard != null) {
                    clipboard.setPrimaryClip(clip);
                    Toast.makeText(this, "Copied summary to clipboard", Toast.LENGTH_SHORT).show();
                }
            });
            actionRow.addView(copyBtn, weightLp());

            Button histBtn = makeBtn("Go to History", C_NAV);
            histBtn.setTextColor(parse(C_CYAN));
            histBtn.setTextSize(11);
            histBtn.setOnClickListener(v -> {
                tab = TAB_HIST;
                setContentView(root());
            });
            actionRow.addView(histBtn, weightLp());

            lsc.addView(actionRow);
            r.addView(lsc, mg(10));
        }

        // ── section: call evidence ────────────────────────────────
        r.addView(heading("Call Evidence"));

        r.addView(heading("Heard by CallShield"));
        heardTxt = tv("Transcript: waiting for speech…");
        heardTxt.setBackground(roundBg(C_SURF_ALT, C_BORDER, 1, 12));
        heardTxt.setPadding(dp(14), dp(14), dp(14), dp(14));
        heardTxt.setTextSize(13);
        r.addView(heardTxt, mg(6));

        r.addView(heading("Audio fingerprint"));
        specTxt = tv("Spectrogram: waiting");
        specTxt.setBackground(roundBg(C_SURF_ALT, C_BORDER, 1, 12));
        specTxt.setPadding(dp(14), dp(10), dp(14), dp(10));
        specTxt.setTextSize(12);
        specTxt.setTextColor(parse(C_LABEL));
        r.addView(specTxt, mg(4));

        specImg = new ImageView(this);
        specImg.setScaleType(ImageView.ScaleType.FIT_XY);
        specImg.setBackground(roundBg(C_SURF_ALT, C_BORDER, 1, 12));
        LinearLayout.LayoutParams il = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(120));
        r.addView(specImg, il);

        micLvl = tv("Mic: waiting");
        micLvl.setTextSize(12);
        micLvl.setTextColor(parse(C_MUTED));
        r.addView(micLvl, mg(10));

        r.addView(heading("Advanced / debug"));
        // Save Last Chunk Button
        saveChunkBtn = makeBtn("Save Last Chunk", C_SURFACE);
        saveChunkBtn.setEnabled(lastWav != null);
        if (lastWav == null) {
            saveChunkBtn.setBackground(roundBg(C_DISABLED, "transparent", 0, 12));
            saveChunkBtn.setTextColor(parse("#4B5563"));
        } else {
            saveChunkBtn.setBackground(roundBg(C_TEAL, "transparent", 0, 12));
            saveChunkBtn.setTextColor(Color.WHITE);
        }
        saveChunkBtn.setOnClickListener(v -> {
            if (lastWav != null) {
                java.io.File dir = getExternalFilesDir(null);
                if (dir != null) {
                    java.io.File file = new java.io.File(dir, "last_chunk_" + lastIdx + ".wav");
                    try (java.io.FileOutputStream fos = new java.io.FileOutputStream(file)) {
                        fos.write(lastWav);
                        Toast.makeText(this, "Saved chunk: " + file.getName() + " to external storage", Toast.LENGTH_LONG).show();
                    } catch (Exception e) {
                        Toast.makeText(this, "Failed to save: " + e.getMessage(), Toast.LENGTH_SHORT).show();
                    }
                }
            }
        });
        r.addView(saveChunkBtn, mg(10));

        return r;
    }

    private void setEndScanDisabled() {
        if (endBtn == null) return;
        endBtn.setEnabled(false);
        endBtn.setBackground(roundBg(C_DISABLED, "transparent", 0, 12));
        endBtn.setTextColor(parse("#4B5563"));
    }

    private void setEndScanEnabled() {
        if (endBtn == null) return;
        endBtn.setEnabled(true);
        endBtn.setBackground(roundBg(C_INDIGO, "transparent", 0, 12));
        endBtn.setTextColor(Color.WHITE);
    }

    // ── risk card ────────────────────────────────────────────────────
    private LinearLayout riskCard() {
        LinearLayout rc = col();
        rc.setPadding(dp(16), dp(16), dp(16), dp(14));
        rc.setBackground(roundBg(C_SURFACE, C_BORDER, 1, 12));

        riskKicker = tv("Final risk level");
        riskKicker.setTextSize(10);
        riskKicker.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        riskKicker.setTextColor(parse(C_TEAL));
        rc.addView(riskKicker);

        riskLabel = tv("SAFE");
        riskLabel.setTextSize(28);
        riskLabel.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        riskLabel.setTextColor(parse(C_GREEN));
        riskLabel.setPadding(0, dp(2), 0, 0);
        rc.addView(riskLabel);

        riskScore = tv("0/100 risk");
        riskScore.setTextSize(13);
        riskScore.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        riskScore.setTextColor(parse(C_CYAN));
        riskScore.setPadding(0, dp(2), 0, 0);
        rc.addView(riskScore);

        riskSum = tv("Listening for first chunk…");
        riskSum.setTextSize(13);
        riskSum.setTextColor(parse(C_MUTED));
        riskSum.setPadding(0, dp(4), 0, dp(8));
        rc.addView(riskSum);

        // thin risk bar
        View bar = new View(this);
        bar.setBackground(roundBg(C_BORDER, "transparent", 0, 2));
        LinearLayout.LayoutParams bp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(3));
        bp.setMargins(0, 0, 0, dp(8));
        bar.setLayoutParams(bp);
        rc.addView(bar);

        // Check summary rows
        rc.addView(chkRow("Audio: real human voice detected", true, C_GREEN));
        rc.addView(chkRow("Language: no scam pressure", true, C_GREEN));
        rc.addView(chkRow("Identity: no suspicious urgency", true, C_GREEN));

        return rc;
    }

    private View chkRow(String text, boolean ok, String color) {
        LinearLayout row = row();
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(0, dp(2), 0, dp(2));

        // use a small circle dot instead of checkmark for cleaner look
        View dot = new View(this);
        dot.setBackground(pillBg(color));
        LinearLayout.LayoutParams dlp = new LinearLayout.LayoutParams(dp(6), dp(6));
        dot.setLayoutParams(dlp);
        row.addView(dot);

        View spacer = new View(this);
        row.addView(spacer, new LinearLayout.LayoutParams(dp(8), 1));

        TextView t = tv(text, C_MUTED, 12);
        row.addView(t);
        return row;
    }

    // ── signal card ───────────────────────────────────────────────────
    private static class SigBag {
        TextView t1, s1, t2, s2, t3, s3;
    }

    private LinearLayout sigCard(String title, String iconRes,
                                 String status, String color,
                                 String subtitle, SigBag bag) {
        LinearLayout c = row();
        c.setGravity(Gravity.CENTER_VERTICAL);
        c.setPadding(dp(14), dp(12), dp(14), dp(12));
        c.setBackground(roundBg(C_SURFACE, C_BORDER, 1, 12));
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT);
        p.setMargins(0, 0, 0, dp(6));
        c.setLayoutParams(p);

        int iconSz = dp(30);
        ImageView ic = new ImageView(this);
        ic.setImageResource(getResourceId("drawable", iconRes));
        LinearLayout.LayoutParams icLp =
                new LinearLayout.LayoutParams(iconSz, iconSz);
        ic.setLayoutParams(icLp);
        ic.setScaleType(ImageView.ScaleType.FIT_CENTER);
        ic.setColorFilter(parse(color), android.graphics.PorterDuff.Mode.SRC_IN);
        c.addView(ic);

        LinearLayout cl = col();
        cl.setPadding(dp(12), 0, 0, 0);
        TextView tt = tv(title, C_LABEL, 11);
        tt.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        cl.addView(tt);
        TextView st = tv(subtitle);
        st.setTextSize(13);
        st.setTextColor(Color.WHITE);
        st.setPadding(0, dp(2), 0, 0);
        cl.addView(st);
        c.addView(cl, weightLp());

        TextView badge = tv(status, color, 10);
        badge.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        badge.setTextColor(Color.WHITE);
        badge.setBackground(pillBg(color));
        badge.setGravity(Gravity.CENTER);
        badge.setPadding(dp(10), dp(4), dp(10), dp(4));
        c.addView(badge);

        if (bag.t1 == null) { bag.t1 = badge; bag.s1 = st; }
        else if (bag.t2 == null) { bag.t2 = badge; bag.s2 = st; }
        else { bag.t3 = badge; bag.s3 = st; }
        return c;
    }

    // ═══════════════════════════════════════════════════════════════════
    // HISTORY PAGE — local persistence, no fake data
    // ═══════════════════════════════════════════════════════════════════
    private View histPage() {
        LinearLayout r = col();
        int pad = dp(16);
        r.setPadding(pad, dp(12), pad, dp(16));

        r.addView(heading("History"));

        editTextSessions = new EditText(this);
        editTextSessions.setSingleLine(true);
        editTextSessions.setHint("Search saved scans…");
        editTextSessions.setTextColor(Color.WHITE);
        editTextSessions.setHintTextColor(parse("#6B7280"));
        editTextSessions.setBackground(roundBg(C_SURFACE, C_BORDER, 1, 12));
        editTextSessions.setPadding(dp(14), dp(12), dp(14), dp(12));
        editTextSessions.setTextSize(14);
        editTextSessions.setMinHeight(dp(48));
        editTextSessions.addTextChangedListener(new android.text.TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int st, int c, int a) {}
            @Override public void onTextChanged(CharSequence s, int st, int b, int c) {
                filterHistory(s.toString());
            }
            @Override public void afterTextChanged(android.text.Editable e) {}
        });
        r.addView(editTextSessions, mg(10));

        clearHistBtn = makeBtn("Clear History", C_NAV);
        clearHistBtn.setTextColor(parse(C_RED));
        clearHistBtn.setOnClickListener(v -> {
            new AlertDialog.Builder(this)
                    .setTitle("Clear History")
                    .setMessage("Delete all saved scans?")
                    .setPositiveButton("Clear All", (d, w) -> {
                        getSharedPreferences(PREFS, MODE_PRIVATE).edit().remove(K_HISTORY).apply();
                        loadAndRenderHistory();
                    })
                    .setNegativeButton("Cancel", null)
                    .show();
        });
        r.addView(clearHistBtn, mg(10));

        historyContainer = new LinearLayout(this);
        historyContainer.setOrientation(LinearLayout.VERTICAL);
        r.addView(historyContainer);

        loadAndRenderHistory();
        return r;
    }

    private void loadAndRenderHistory() {
        allHistoryEntries = loadHistoryEntries();
        renderHistory(allHistoryEntries);
    }

    private void renderHistory(java.util.List<HistoryEntry> entries) {
        if (historyContainer == null) return;
        historyContainer.removeAllViews();
        if (entries.isEmpty()) {
            historyContainer.addView(emptyHistoryState());
            if (clearHistBtn != null) clearHistBtn.setVisibility(View.GONE);
            return;
        }
        if (clearHistBtn != null) clearHistBtn.setVisibility(View.VISIBLE);
        for (HistoryEntry e : entries) {
            historyContainer.addView(historyRow(e), mg(8));
        }
    }

    private void deleteHistoryEntry(String id) {
        SharedPreferences sp = getSharedPreferences(PREFS, MODE_PRIVATE);
        String raw = sp.getString(K_HISTORY, "[]");
        try {
            JSONArray arr = new JSONArray(raw);
            JSONArray updated = new JSONArray();
            for (int i = 0; i < arr.length(); i++) {
                JSONObject o = arr.getJSONObject(i);
                if (!id.equals(o.optString("id", ""))) {
                    updated.put(o);
                }
            }
            sp.edit().putString(K_HISTORY, updated.toString()).apply();
        } catch (JSONException ignored) {}
        loadAndRenderHistory();
    }

    private void showHistoryDetail(HistoryEntry e) {
        StringBuilder msg = new StringBuilder();
        msg.append("Session: ").append(e.id).append("\n");
        msg.append("Date: ").append(formatDate(e.timestampMillis)).append("\n");
        msg.append("Alert: ").append(e.alertTitle).append("\n");
        msg.append("Max risk: ").append((int) e.maxRisk).append("/100\n");
        msg.append("Avg risk: ").append((int) e.averageRisk).append("/100\n");
        msg.append("Chunks: ").append(e.chunkCount)
                .append(" (").append(e.suspiciousChunks).append(" suspicious)\n");
        msg.append("Scam type: ").append(e.topScamType).append("\n");
        if (!e.evidence.isEmpty()) msg.append("\nEvidence:\n").append(e.evidence).append("\n");
        msg.append("\nAction: ").append(e.recommendedAction);
        if (!e.savedScores.isEmpty()) msg.append("\n\nScores:\n").append(e.savedScores);

        new AlertDialog.Builder(this)
                .setTitle("CallShield: " + e.alertTitle)
                .setMessage(msg.toString())
                .setPositiveButton("Close", null)
                .setNeutralButton("Copy", (dialog, which) -> {
                    android.content.ClipboardManager clipboard = (android.content.ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
                    android.content.ClipData clip = android.content.ClipData.newPlainText("CallShield Session Detail", msg.toString());
                    if (clipboard != null) clipboard.setPrimaryClip(clip);
                    Toast.makeText(this, "Copied details to clipboard", Toast.LENGTH_SHORT).show();
                })
                .setNegativeButton("Delete", (dialog, which) -> {
                    new AlertDialog.Builder(this)
                            .setTitle("Delete Scan?")
                            .setMessage("Are you sure you want to delete this scan?")
                            .setPositiveButton("Delete", (d, w) -> deleteHistoryEntry(e.id))
                            .setNegativeButton("Cancel", null)
                            .show();
                })
                .show();
    }

    private LinearLayout historyRow(HistoryEntry e) {
        LinearLayout row = row();
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(14), dp(14), dp(14), dp(14));
        row.setBackground(roundBg(C_NAV, C_BORDER, 1, 14));
        row.setLayoutParams(mg(8));
        row.setOnClickListener(v -> showHistoryDetail(e));

        String riskColor = riskBadgeColor(e.maxRisk);
        String badgeLetter = e.alertTitle.isEmpty() ? "S" : e.alertTitle.substring(0, 1).toUpperCase();
        row.addView(badgeChar(badgeLetter, riskColor));

        LinearLayout c = col();
        c.setPadding(dp(10), 0, 0, 0);
        c.addView(tv("Scan Session", C_WHITE, 14));
        String dateStr = formatDate(e.timestampMillis);
        c.addView(tv(dateStr + " · " + e.chunkCount + " chunks", C_MUTED, 12));
        row.addView(c, weightLp());

        LinearLayout rgt = col();
        rgt.setGravity(Gravity.END);
        rgt.addView(tv((int) e.maxRisk + "/100", C_MUTED, 12));
        TextView badge = tv(e.alertTitle);
        badge.setTextSize(10);
        badge.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        badge.setTextColor(Color.WHITE);
        badge.setBackground(roundBg(riskColor + "30", riskColor, 1, 20));
        badge.setGravity(Gravity.CENTER);
        badge.setPadding(dp(8), dp(4), dp(8), dp(4));
        rgt.addView(badge);
        row.addView(rgt);
        return row;
    }

    private View emptyHistoryState() {
        LinearLayout c = col();
        c.setGravity(Gravity.CENTER);
        c.setPadding(dp(40), dp(60), dp(40), dp(60));

        // use history clock icon instead of square placeholder
        ImageView icon = new ImageView(this);
        int sz = dp(48);
        LinearLayout.LayoutParams ilp = new LinearLayout.LayoutParams(sz, sz);
        ilp.gravity = Gravity.CENTER;
        icon.setLayoutParams(ilp);
        icon.setImageResource(getResourceId("drawable", "ic_history"));
        icon.setColorFilter(parse("#374151"), android.graphics.PorterDuff.Mode.SRC_IN);
        icon.setScaleType(ImageView.ScaleType.FIT_CENTER);
        c.addView(icon);

        TextView t1 = tv("No saved scans yet");
        t1.setTextSize(15);
        t1.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        t1.setTextColor(Color.WHITE);
        t1.setPadding(0, dp(12), 0, dp(4));
        t1.setGravity(Gravity.CENTER);
        c.addView(t1);

        TextView t2 = tv("Completed scans will appear here.");
        t2.setTextSize(13);
        t2.setTextColor(parse(C_MUTED));
        t2.setGravity(Gravity.CENTER);
        c.addView(t2);

        TextView t3 = tv("Run your first scan on the Scan tab.");
        t3.setTextSize(12);
        t3.setTextColor(parse("#6B7280"));
        t3.setPadding(0, dp(4), 0, 0);
        t3.setGravity(Gravity.CENTER);
        c.addView(t3);

        return c;
    }

    private String riskBadgeColor(double risk) {
        if (risk >= 63) return C_RED;
        if (risk >= 40) return C_AMBER;
        return C_GREEN;
    }

    private String formatDate(long millis) {
        java.text.SimpleDateFormat sdf = new java.text.SimpleDateFormat("MMM dd, yyyy · HH:mm", Locale.US);
        return sdf.format(new java.util.Date(millis));
    }

    private void filterHistory(String query) {
        String q = query.toLowerCase().trim();
        java.util.List<HistoryEntry> filtered = new ArrayList<>();
        if (q.isEmpty()) {
            filtered.addAll(allHistoryEntries);
        } else {
            for (HistoryEntry e : allHistoryEntries) {
                if (e.alertTitle.toLowerCase().contains(q)
                        || e.topScamType.toLowerCase().contains(q)
                        || String.valueOf((int) e.maxRisk).contains(q)) {
                    filtered.add(e);
                }
            }
        }
        renderHistory(filtered);
    }

    // ═══════════════════════════════════════════════════════════════════
    // SETTINGS PAGE
    // ═══════════════════════════════════════════════════════════════════
    private View settingsPage() {
        LinearLayout r = col();
        int pad = dp(16);
        r.setPadding(pad, dp(12), pad, dp(16));

        r.addView(heading("Settings"));

        // Server card
        LinearLayout sc = settingsCard("Server");

        // URL input row
        LinearLayout urlRow = row();
        LinearLayout urlCol = col();
        urlCol.setPadding(0, 0, dp(12), 0);
        TextView urlLabel = tv("Backend URL", C_LABEL, 12);
        urlLabel.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        urlCol.addView(urlLabel);
        urlIn = urlEdit();
        urlIn.setHint(isEmulator() ? EMU_URL : "http://192.168.1.x:8000");
        urlCol.addView(urlIn);
        urlRow.addView(urlCol, weightLp());

        // Server status badge on the right
        LinearLayout statusBadge = col();
        statusBadge.setGravity(Gravity.CENTER_VERTICAL | Gravity.END);
        statTxt = tv("Not Tested", C_MUTED, 11);
        statTxt.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        statTxt.setBackground(roundBg(C_SURF_ALT, C_BORDER, 1, 8));
        statTxt.setPadding(dp(10), dp(6), dp(10), dp(6));
        statusBadge.addView(statTxt);
        urlRow.addView(statusBadge);
        sc.addView(urlRow);

        // Connection hint
        connTxt = tv(isEmulator()
                ? "Emulator: " + EMU_URL
                : "Use your laptop's Wi-Fi IPv4 and the port shown by the backend, e.g. http://192.168.1.7:8000",
                C_MUTED, 12);
        connTxt.setPadding(0, dp(6), 0, 0);
        sc.addView(connTxt);

        // Connection Quality Helper Row
        LinearLayout helperRow = row();
        helperRow.setPadding(0, dp(6), 0, dp(6));

        Button emuBtn = makeBtn("Use Emulator URL", C_SURF_ALT);
        emuBtn.setTextColor(parse(C_CYAN));
        emuBtn.setTextSize(11);
        emuBtn.setOnClickListener(v -> {
            if (urlIn != null) {
                urlIn.setText(EMU_URL);
                persist();
            }
        });
        emuBtn.setEnabled(isEmulator());
        if (!isEmulator()) {
            emuBtn.setBackground(roundBg(C_DISABLED, "transparent", 0, 12));
            emuBtn.setTextColor(parse("#4B5563"));
        }
        helperRow.addView(emuBtn, weightLp());

        Button pasteBtn = makeBtn("Paste URL", C_SURF_ALT);
        pasteBtn.setTextColor(parse(C_CYAN));
        pasteBtn.setTextSize(11);
        pasteBtn.setOnClickListener(v -> {
            android.content.ClipboardManager clipboard = (android.content.ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
            if (clipboard != null && clipboard.hasPrimaryClip()) {
                android.content.ClipData.Item item = clipboard.getPrimaryClip().getItemAt(0);
                String text = item.getText() != null ? item.getText().toString().trim() : "";
                if (text.startsWith("http://") || text.startsWith("https://")) {
                    if (urlIn != null) {
                        urlIn.setText(text);
                        persist();
                        Toast.makeText(this, "Pasted URL", Toast.LENGTH_SHORT).show();
                    }
                } else {
                    Toast.makeText(this, "Clipboard does not contain a valid http/https URL", Toast.LENGTH_LONG).show();
                }
            } else {
                Toast.makeText(this, "Clipboard is empty", Toast.LENGTH_SHORT).show();
            }
        });
        helperRow.addView(pasteBtn, weightLp());

        sc.addView(helperRow);

        // Test button
        srvBtn = makeBtn("Test Connection", C_TEAL);
        srvBtn.setOnClickListener(v -> testServer());
        sc.addView(srvBtn, mg(10));

        r.addView(sc);
        r.addView(hdiv(10));

        // Readiness Card
        r.addView(buildReadinessCard());
        r.addView(hdiv(10));

        // Monitoring card
        LinearLayout mc = settingsCard("Monitoring");
        LinearLayout mr = row();
        mr.setGravity(Gravity.CENTER_VERTICAL);
        mr.setMinimumHeight(dp(52));

        LinearLayout ml = col();
        ml.addView(label("Real Call Mode"));
        modeHelp = tv("Manual mode — tap Scan to start.", C_MUTED, 13);
        ml.addView(modeHelp);
        mr.addView(ml, weightLp());

        modeSw = new Switch(this);
        modeSw.setChecked(CallShieldSettings.isRealCallModeEnabled(this));
        modeSw.setOnCheckedChangeListener((v, on) -> {
            CallShieldSettings.setRealCallModeEnabled(MainActivity.this, on);
            if (modeHelp != null) modeHelp.setText(
                    on ? "Monitoring armed." : "Manual mode — tap Scan to start.");
            if (on) askCall();
        });
        mr.addView(modeSw);
        mc.addView(mr);
        r.addView(mc);
        r.addView(hdiv(10));

        // Debug card
        LinearLayout dc = settingsCard("Debug");
        logTxt = tv("");
        logTxt.setMinLines(4);
        logTxt.setMaxLines(8);
        logTxt.setBackground(roundBg(C_BAR, C_BORDER, 1, 8));
        logTxt.setPadding(dp(12), dp(10), dp(12), dp(10));
        logTxt.setMovementMethod(new ScrollingMovementMethod());
        logTxt.setTextSize(10);
        logTxt.setTextColor(parse(C_MUTED));
        dc.addView(logTxt);
        r.addView(dc);

        return r;
    }

    private LinearLayout buildReadinessCard() {
        LinearLayout card = settingsCard("App Readiness");

        final boolean micOk = checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED;
        final boolean phoneOk = checkSelfPermission(Manifest.permission.READ_PHONE_STATE) == PackageManager.PERMISSION_GRANTED;
        final boolean notifOk = (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU)
                || (checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED);
        final boolean urlOk = !loadUrl().isEmpty();

        card.addView(statusRow("Microphone permission", micOk, false));
        card.addView(statusRow("Phone state permission", phoneOk, false));
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            card.addView(statusRow("Notifications permission", notifOk, false));
        }
        card.addView(statusRow("Backend URL status", urlOk, true));

        Button checkBtn = makeBtn("Check Permissions", C_SURF_ALT);
        checkBtn.setTextColor(parse(C_CYAN));
        checkBtn.setTextSize(12);
        checkBtn.setOnClickListener(v -> {
            ArrayList<String> req = new ArrayList<>();
            if (!micOk) req.add(Manifest.permission.RECORD_AUDIO);
            if (!phoneOk) req.add(Manifest.permission.READ_PHONE_STATE);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU && !notifOk) {
                req.add(Manifest.permission.POST_NOTIFICATIONS);
            }
            if (!req.isEmpty()) {
                requestPermissions(req.toArray(new String[0]), REQ_CALL);
            } else {
                Toast.makeText(this, "All permissions are already granted!", Toast.LENGTH_SHORT).show();
            }
        });
        card.addView(checkBtn, mg(6));

        return card;
    }

    private LinearLayout statusRow(String labelText, boolean ok, boolean isUrl) {
        LinearLayout row = row();
        row.setPadding(0, dp(4), 0, dp(4));

        TextView lbl = tv(labelText, C_LABEL, 12);
        row.addView(lbl, weightLp());

        String val = ok ? (isUrl ? "Set" : "Granted") : "Missing";
        TextView status = tv(val, ok ? C_GREEN : C_RED, 12);
        status.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        row.addView(status);

        return row;
    }

    private LinearLayout settingsCard(String title) {
        LinearLayout c = col();
        c.setPadding(dp(16), dp(10), dp(16), dp(10));
        c.setBackground(roundBg(C_SURFACE, C_BORDER, 1, 12));
        c.addView(heading(title));
        return c;
    }

    private LinearLayout dashboardCard(String title) {
        LinearLayout c = col();
        c.setPadding(dp(16), dp(12), dp(16), dp(12));
        c.setBackground(roundBg(C_SURFACE, C_BORDER, 1, 12));
        if (title != null && !title.isEmpty()) {
            c.addView(heading(title));
        }
        return c;
    }

    private LinearLayout infoPanel(String title, String body) {
        return infoPanel(title, tv(body, "#D1D5DB", 12));
    }

    private LinearLayout infoPanel(String title, TextView body) {
        LinearLayout panel = col();
        panel.setPadding(dp(12), dp(10), dp(12), dp(10));
        panel.setBackground(roundBg(C_SURF_ALT, C_BORDER, 1, 10));
        TextView label = tv(title, C_LABEL, 11);
        label.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        panel.addView(label);
        body.setPadding(0, dp(5), 0, 0);
        panel.addView(body);
        return panel;
    }

    private EditText urlEdit() {
        EditText e = new EditText(this);
        e.setSingleLine(true);
        e.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        e.setImeOptions(EditorInfo.IME_ACTION_DONE);
        e.setText(loadUrl());
        e.setTextColor(Color.WHITE);
        e.setHintTextColor(parse("#6B7280"));
        e.setBackground(roundBg(C_BAR, C_BORDER, 1, 10));
        e.setPadding(dp(14), dp(12), dp(14), dp(12));
        e.setTextSize(14);
        e.setMinHeight(dp(46));
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT);
        p.setMargins(0, dp(4), 0, 0);
        e.setLayoutParams(p);
        return e;
    }

    // ═══════════════════════════════════════════════════════════════════
    // scan flow — logic preserved, UI calls updated
    // ═══════════════════════════════════════════════════════════════════
    private void startMonitoringFromIncomingCall() {
        if (scanning) return;
        tab = TAB_SCAN;
        if (contentHolder != null) swap();
        setStatus("Call active. Auto monitoring.");
        startScan(true);
    }

    private void startScan(boolean inc) {
        if (scanning) return;
        persist();
        url = normUrl();
        if (!okUrl(url)) return;

        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            micPending = inc;
            requestPermissions(
                    new String[]{Manifest.permission.RECORD_AUDIO}, REQ_AUDIO);
            return;
        }

        sid = "apoc-" + System.currentTimeMillis();
        t0 = System.currentTimeMillis();
        scanning = true;
        fromIncall = inc;
        lastWav = null;
        lastIdx = 0;
        quiet = 0;
        warned = false;
        cnt.set(0);
        fly.set(false);
        stopP.set(false);
        analy.reset();

        clearScanUi();
        log("Session " + sid);
        if (inc) {
            enableSpeakerphoneAssist(true);
        }
        streamer.start();
        flipBtns(true);
        setStatus(inc ? "Auto monitoring call. Keep speaker on." : "Recording. Keep speaker on.");
    }

    private void endScan() {
        if (streamer != null) streamer.stop();
        scanning = false;
        fromIncall = false;
        CallAudioCaptureAssist.AssistResult r = CallAudioCaptureAssist.release(this);
        if (modeHelp != null) modeHelp.setText(r.userMessage);
        log("speaker release: " + r.logMessage);
        if (micLvl != null) micLvl.setText("Mic: stopped");
        if (topStatus != null) topStatus.setText("Call stopped");
        if (riskScore != null) riskScore.setText("Final…");
        flipBtns(false);
        persist();
        stopP.set(true);
        if (fly.get()) setStatus("Waiting for final…");
        else finalSum();
    }

    private void pickRecordingFile() {
        Intent pick = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        pick.addCategory(Intent.CATEGORY_OPENABLE);
        pick.setType("audio/*");
        pick.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        startActivityForResult(pick, REQ_PICK_RECORDING);
    }

    private void analyzeRecordingUri(Uri uri) {
        persist();
        url = normUrl();
        if (!okUrl(url)) return;

        analy.reset();
        sid = "recording-" + System.currentTimeMillis();
        t0 = System.currentTimeMillis();
        setStatus("Analyzing saved recording...");
        if (topStatus != null) topStatus.setText("Saved recording selected");
        if (riskLabel != null) {
            riskLabel.setText("ANALYZING");
            riskLabel.setTextColor(parse(C_TEAL));
        }
        if (riskScore != null) riskScore.setText("File upload");
        if (riskSum != null) riskSum.setText("Reading selected call recording file.");
        log("recording import queued");

        net.submit(() -> {
            try {
                String name = recordingDisplayName(uri);
                String mime = recordingMimeType(uri);
                byte[] bytes = readRecordingBytes(uri);
                api.analyzeAudio(url, sid, bytes, name, mime);
                runOnUiThread(() -> {
                    showResp();
                    stopP.set(true);
                    finalSum();
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    setStatus("Recording analysis failed");
                    connErr(e, url);
                    Toast.makeText(this, "Recording analysis failed: " + shortErr(e), Toast.LENGTH_LONG).show();
                });
            }
        });
    }

    private String recordingMimeType(Uri uri) {
        String mime = getContentResolver().getType(uri);
        return mime == null || mime.trim().isEmpty() ? "audio/wav" : mime;
    }

    private String recordingDisplayName(Uri uri) {
        String name = null;
        try (Cursor cursor = getContentResolver().query(uri, null, null, null, null)) {
            if (cursor != null && cursor.moveToFirst()) {
                int idx = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                if (idx >= 0) name = cursor.getString(idx);
            }
        } catch (Exception ignored) {
            // Fall back to a safe name below.
        }
        if (name == null || name.trim().isEmpty()) {
            name = "call_recording" + extensionForMime(recordingMimeType(uri));
        }
        if (!name.contains(".")) {
            name = name + extensionForMime(recordingMimeType(uri));
        }
        return name;
    }

    private String extensionForMime(String mime) {
        if (mime == null) return ".wav";
        String m = mime.toLowerCase(Locale.US);
        if (m.contains("mpeg") || m.contains("mp3")) return ".mp3";
        if (m.contains("mp4") || m.contains("m4a")) return ".m4a";
        if (m.contains("ogg")) return ".ogg";
        if (m.contains("flac")) return ".flac";
        if (m.contains("webm")) return ".webm";
        if (m.contains("aac")) return ".aac";
        return ".wav";
    }

    private byte[] readRecordingBytes(Uri uri) throws Exception {
        ContentResolver resolver = getContentResolver();
        try (InputStream in = resolver.openInputStream(uri);
             ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            if (in == null) {
                throw new IllegalStateException("Could not open selected recording");
            }
            byte[] buf = new byte[8192];
            int read;
            int total = 0;
            while ((read = in.read(buf)) != -1) {
                total += read;
                if (total > MAX_IMPORT_BYTES) {
                    throw new IllegalStateException("Recording is larger than 10 MB");
                }
                out.write(buf, 0, read);
            }
            if (total == 0) {
                throw new IllegalStateException("Recording file is empty");
            }
            return out.toByteArray();
        }
    }

    private void clearScanUi() {
        lastWav = null;
        lastIdx = 0;
        if (saveChunkBtn != null) {
            saveChunkBtn.setEnabled(false);
            saveChunkBtn.setBackground(roundBg(C_DISABLED, "transparent", 0, 12));
            saveChunkBtn.setTextColor(parse("#4B5563"));
        }
        if (riskLabel != null) {
            riskLabel.setText("ANALYZING");
            riskLabel.setTextColor(parse(C_TEAL));
        }
        if (riskScore != null) riskScore.setText("0/100 risk");
        if (riskSum != null) riskSum.setText("Listening for first chunk…");
        if (aTtl != null) aTtl.setText("IDLE");
        if (aSub != null) aSub.setText("Waiting");
        if (lTtl != null) lTtl.setText("IDLE");
        if (lSub != null) lSub.setText("Waiting");
        if (iTtl != null) iTtl.setText("LOW");
        if (iSub != null) iSub.setText("Ready");
    }

    private void flipBtns(boolean on) {
        scanBtn.setEnabled(!on);
        scanBtn.setAlpha(on ? 0.5f : 1f);
        if (on) setEndScanEnabled();
        else setEndScanDisabled();
        if (srvBtn != null) srvBtn.setEnabled(!on);
    }

    private void sendChunk(byte[] w) {
        int idx = cnt.incrementAndGet();
        String cid = sid + "-ch-" + idx;
        lastWav = Arrays.copyOf(w, w.length);
        lastIdx = idx;

        runOnUiThread(() -> {
            flipBtns(scanning);
            setStatus("Analyzing ch-" + idx);
            log("ch-" + idx + " queued");
            if (saveChunkBtn != null) {
                saveChunkBtn.setEnabled(true);
                saveChunkBtn.setBackground(roundBg(C_TEAL, "transparent", 0, 12));
                saveChunkBtn.setTextColor(Color.WHITE);
            }
        });

        net.submit(() -> {
            try {
                api.analyzeAudio(url, cid, w);
                fly.set(true);
                runOnUiThread(this::showResp);
            } catch (Exception e) {
                fly.set(false);
                runOnUiThread(() -> {
                    setStatus("Upload failed");
                    connErr(e, url);
                    log("ch-" + idx + " fail " + shortErr(e));
                });
            } finally {
                if (stopP.get()) runOnUiThread(this::finalSum);
            }
        });
    }

    // ═══════════════════════════════════════════════════════════════════
    // response rendering — logic preserved, colors updated
    // ═══════════════════════════════════════════════════════════════════
    private void showResp() {
        updTimer();
        JSONObject r = api.lastResponse;
        if (r == null) return;

        if (connTxt != null)
            connTxt.setText("Okay, last: "
                    + r.optDouble("processing_time_ms", 0) + "ms");

        JSONObject raw = r.optJSONObject("raw_components");
        renderSpec(raw);

        String heard = heardFrom(raw);
        String asrSt = asrStatus(raw);
        String seen = heard.isEmpty()
                ? "[no speech / " + asrSt + "]"
                : heard;
        if (heardTxt != null) heardTxt.setText("Transcript: " + seen);

        double sc = r.optDouble("risk_score", 0);
        String band = r.optString("risk_band", "?");
        boolean audioReview = deepfakeScore(raw) >= 0.5 && sc < 40;
        String disp = audioReview ? "AUDIO REVIEW" : riskBand(sc, band);
        int col = audioReview ? parse(C_AMBER) : riskColor(sc, band);

        riskLabel.setText(disp);
        riskLabel.setTextColor(col);
        riskScore.setText(String.format(Locale.US, "%.1f/100 risk", sc));
        riskSum.setText(audioReview
                ? "Audio looked synthetic. Scam language was not required for this warning."
                : r.optString("why_flagged", "Analyzing voice, language and identity."));
        rememberAnalysisChunk(r, raw, heard);

        if (aTtl != null) aTtl.setText(audioReview ? "REVIEW" : riskBand(sc, band));
        if (aSub != null) {
            aSub.setText("Synthetic " + deepfakeScoreStr(raw));
            aSub.setTextColor(col);
        }
        if (iTtl != null) iTtl.setText("CALLER " + riskBand(sc, band));
        if (iSub != null) {
            boolean susp = sc >= 35;
            iSub.setText(susp ? "Suspicious pattern" : "No urgency");
            iSub.setTextColor(susp ? parse(C_ORANGE) : parse(C_CYAN));
        }
    }

    private void rememberAnalysisChunk(JSONObject r, JSONObject raw, String heard) {
        JSONObject audio = raw == null ? null : raw.optJSONObject("audio");
        analy.addChunk(
                r.optDouble("risk_score", 0),
                r.optString("risk_band", "unknown"),
                r.optString("warning_level", "none"),
                r.optString("scam_type", "unknown"),
                heard,
                deepfakeScore(raw),
                audio != null && audio.optBoolean("used_in_fusion", false)
        );
    }

    private void finalSum() {
        if (!stopP.compareAndSet(true, false)) return;
        SessionAlertAnalyzer.SessionSummary s = analy.summarize();
        save(s);
        saveHistoryEntry(s); // persist real scan result locally

        setStatus("Stopped. " + s.alertTitle);
        if (riskLabel != null) {
            riskLabel.setText(s.alertTitle.toUpperCase(Locale.US));
            riskLabel.setTextColor(s.maxRisk >= 60
                    ? parse(C_RED) : parse(C_AMBER));
        }
        if (riskScore != null)
            riskScore.setText((int) s.maxRisk + "/100 peak risk");
        if (riskSum != null)
            riskSum.setText("Analyzed " + s.chunkCount + " chunks, "
                    + s.suspiciousChunks + " suspicious.");

        // Re-render scan page to display/refresh the "Last Scan Session" card when visible.
        if (tab == TAB_SCAN && CallShieldRuntime.isActivityVisible()) {
            setContentView(root());
        }

        showFinalReport(s);
    }

    private void showFinalReport(SessionAlertAnalyzer.SessionSummary s) {
        if (!CallShieldRuntime.isActivityVisible()) {
            showReportNotification(s);
            return;
        }
        new AlertDialog.Builder(this)
                .setTitle("CallShield: " + s.alertTitle)
                .setMessage(s.toDialogMessage())
                .setNeutralButton("View Saved", (d, w) -> showSaved())
                .setPositiveButton("OK", null)
                .show();
    }

    private void showReportNotification(SessionAlertAnalyzer.SessionSummary s) {
        NotificationManager manager = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (manager == null) return;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            return;
        }
        String channelId = "callshield_reports";
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    channelId,
                    "CallShield reports",
                    NotificationManager.IMPORTANCE_HIGH
            );
            channel.setDescription("Final CallShield call reports after monitored calls end.");
            manager.createNotificationChannel(channel);
        }

        Intent open = new Intent(this, MainActivity.class);
        open.setAction(ACTION_OPEN_LAST_REPORT);
        open.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent pending = PendingIntent.getActivity(
                this,
                42,
                open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );
        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(this, channelId)
                : new Notification.Builder(this);
        builder.setSmallIcon(android.R.drawable.stat_sys_warning)
                .setContentTitle("CallShield report: " + s.alertTitle)
                .setContentText("Max risk " + (int) s.maxRisk + "/100. Tap to view the full report.")
                .setContentIntent(pending)
                .setAutoCancel(true)
                .setPriority(Notification.PRIORITY_HIGH);
        manager.notify(9042, builder.build());
    }

    // ═══════════════════════════════════════════════════════════════════
    // permissions & notifications
    // ═══════════════════════════════════════════════════════════════════
    @Override
    public void onRequestPermissionsResult(int code, String[] perms, int[] grants) {
        super.onRequestPermissionsResult(code, perms, grants);
        if (code == REQ_AUDIO && grants.length > 0
                && grants[0] == PackageManager.PERMISSION_GRANTED) {
            startScan(micPending);
        } else if (code == REQ_CALL) {
            if (CallShieldSettings.isRealCallModeEnabled(this))
                CallShieldArmedNotifier.showArmed(this);
        } else {
            Toast.makeText(this, "Mic permission required", Toast.LENGTH_LONG).show();
        }

        if (tab == TAB_SET) {
            setContentView(root());
        }
    }

    private void askCall() {
        java.util.ArrayList<String> need = new java.util.ArrayList<>();
        if (checkSelfPermission(Manifest.permission.READ_PHONE_STATE)
                != PackageManager.PERMISSION_GRANTED)
            need.add(Manifest.permission.READ_PHONE_STATE);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED)
            need.add(Manifest.permission.POST_NOTIFICATIONS);
        if (!need.isEmpty())
            requestPermissions(need.toArray(new String[0]), REQ_CALL);
        else CallShieldArmedNotifier.showArmed(this);
    }

    // ═══════════════════════════════════════════════════════════════════
    // server helpers
    // ═══════════════════════════════════════════════════════════════════
    private void testServer() {
        String u = normUrl();
        if (!okUrl(u)) return;
        persist();
        String endpoint = cleanUrlBase(u) + "/health";
        long started = System.nanoTime();
        if (statTxt != null) {
            statTxt.setText("Testing...");
            statTxt.setTextColor(parse(C_CYAN));
        }
        connTxt.setText("Testing " + endpoint + "...");
        srvBtn.setEnabled(false);
        net.submit(() -> {
            try {
                JSONObject h = api.healthCheck(u);
                long ms = (System.nanoTime() - started) / 1_000_000L;
                runOnUiThread(() -> {
                    connTxt.setText("Connected. Last response in " + ms + " ms. v"
                            + h.optString("version", "?")
                            + " (" + h.optString("status", "ok") + ")");
                    log("server OK");
                    statTxt.setText("Connected");
                    statTxt.setTextColor(parse(C_GREEN));
                });
            } catch (Exception e) {
                runOnUiThread(() -> connErr(e, u));
            } finally {
                runOnUiThread(() -> { if (srvBtn != null) srvBtn.setEnabled(true); });
            }
        });
    }

    private void handleNotif(Intent i) {
        if (i == null) return;
        if (ACTION_OPEN_LAST_REPORT.equals(i.getAction())) {
            tab = TAB_HIST;
            if (contentHolder != null) swap();
            showSaved();
            return;
        }
        if (!ACTION_OPEN_FROM_CALL_NOTIFICATION.equals(i.getAction())) return;
        log("notif opened");
        if (!CallShieldSettings.isRealCallModeEnabled(this)) {
            setStatus("Real call mode off — use Scan.");
            return;
        }
        startMonitoringFromIncomingCall();
    }

    private void enableSpeakerphoneAssist(boolean start) {
        CallAudioCaptureAssist.AssistResult r = CallAudioCaptureAssist.enable(this);
        if (modeHelp != null)
            modeHelp.setText((start ? "Speaker assist on. " : "") + r.userMessage);
        log("spk: " + r.logMessage);
    }

    // ═══════════════════════════════════════════════════════════════════
    // persistence
    // ═══════════════════════════════════════════════════════════════════
    private void save(SessionAlertAnalyzer.SessionSummary s) {
        getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                .putString(K_SAVE, s.toSavedSessionText()).apply();
    }

    private void showSaved() {
        String txt = getSharedPreferences(PREFS, MODE_PRIVATE)
                .getString(K_SAVE, "No saved results yet.");
        new AlertDialog.Builder(this)
                .setTitle("Saved Session")
                .setMessage(txt)
                .setPositiveButton("OK", null)
                .show();
    }

    private String normUrl() {
        return urlIn != null ? urlIn.getText().toString().trim() : loadUrl();
    }

    private String cleanUrlBase(String raw) {
        String clean = raw == null ? "" : raw.trim();
        while (clean.endsWith("/")) {
            clean = clean.substring(0, clean.length() - 1);
        }
        return clean;
    }

    private String loadUrl() {
        return getSharedPreferences(PREFS, MODE_PRIVATE)
                .getString(K_URL, "");
    }

    private void persist() {
        getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                .putString(K_URL, normUrl()).apply();
    }

    // ═══════════════════════════════════════════════════════════════════
    // device helpers
    // ═══════════════════════════════════════════════════════════════════
    private boolean isEmulator() {
        String fp = Build.FINGERPRINT == null ? "" : Build.FINGERPRINT;
        String md = Build.MODEL == null ? "" : Build.MODEL;
        return fp.contains("generic") || md.contains("emulator");
    }

    private void emuWarn() {
        if (urlIn != null)
            urlIn.setHint("Use laptop Wi-Fi IPv4 on physical device");
    }

    private boolean okUrl(String u) {
        if (u.isEmpty()) {
            if (topStatus != null) topStatus.setTextColor(parse(C_AMBER));
            if (connTxt != null) connTxt.setText("Enter a backend address to start scanning.");
            if (urlIn != null) urlIn.requestFocus();
            return false;
        }
        if (!(u.startsWith("http://") || u.startsWith("https://"))) {
            showBlk("Bad URL", "URL must start with http:// or https://");
            return false;
        }
        if (!isEmulator() && u.contains("10.0.2.2")) {
            emuWarn();
            showBlk("Bad URL", "10.0.2.2 only works inside the emulator. On a real phone, use your laptop Wi-Fi IPv4 and the correct port.");
            return false;
        }
        return true;
    }

    private void connErr(Exception e, String u) {
        String detail = shortErr(e);
        if (connTxt != null) {
            connTxt.setText("Failed: " + detail
                    + ". Check same Wi-Fi, backend running, correct port, and Windows Firewall.");
        }
        if (statTxt != null) {
            statTxt.setText("Failed");
            statTxt.setTextColor(parse(C_RED));
        }
        log("err: " + detail);
    }

    private void showBlk(String t, String m) {
        setStatus(t);
        if (connTxt != null) connTxt.setText(m);
        log("Blocked: " + m);
        Toast.makeText(this, m, Toast.LENGTH_LONG).show();
    }

    private void setStatus(String s) {
        if (topStatus != null) topStatus.setText(s);
    }

    private void log(String s) {
        if (logTxt == null) return;
        String cur = logTxt.getText().toString();
        String buf = cur.isEmpty() ? s : cur + "\n" + s;
        String[] ls = buf.split("\n");
        if (ls.length > 30) {
            StringBuilder b = new StringBuilder();
            for (int i = ls.length - 30; i < ls.length; i++) {
                if (b.length() > 0) b.append('\n');
                b.append(ls[i]);
            }
            buf = b.toString();
        }
        logTxt.setText(buf);
    }

    // ═══════════════════════════════════════════════════════════════════
    // spectrogram rendering — logic preserved
    // ═══════════════════════════════════════════════════════════════════
    private void renderSpec(JSONObject raw) {
        if (specImg == null || specTxt == null) return;
        if (raw == null) {
            specTxt.setText("Spectrogram: missing");
            specImg.setImageDrawable(null);
            return;
        }
        JSONObject s = raw.optJSONObject("spectrogram");
        if (s == null) { specTxt.setText("Spectrogram: missing"); specImg.setImageDrawable(null); return; }
        if (!s.optBoolean("available", false)) {
            specTxt.setText("Unavailable: " + trunc(s.optString("error", "?"), 60));
            specImg.setImageDrawable(null);
            return;
        }
        String b64 = s.optString("image_base64", "");
        if (b64.isEmpty()) {
            specTxt.setText("Spectrogram: empty");
            specImg.setImageDrawable(null);
            return;
        }
        try {
            byte[] data = Base64.decode(b64, Base64.DEFAULT);
            Bitmap bmp = BitmapFactory.decodeByteArray(data, 0, data.length);
            if (bmp == null) throw new IllegalArgumentException("decode failed");
            specImg.setImageBitmap(bmp);
            specTxt.setText("Log-mel " + s.optInt("n_mels", 0) + "x"
                    + s.optInt("frames", 0) + " @ "
                    + s.optDouble("duration_seconds", 0.0) + "s");
        } catch (Exception ex) {
            specTxt.setText("Spectrogram decode failed");
            specImg.setImageDrawable(null);
        }
    }

    private double deepfakeScore(JSONObject raw) {
        if (raw == null) return 0d;
        JSONObject audio = raw.optJSONObject("audio");
        if (audio == null) return 0d;
        Object v = audio.opt("deepfake_score");
        if (v instanceof Number) return ((Number) v).doubleValue();
        if (v instanceof String) {
            try { return Double.parseDouble(((String) v).trim()); }
            catch (Exception ignored) {}
        }
        return 0d;
    }

    private String deepfakeScoreStr(JSONObject raw) {
        if (raw == null) return "?";
        JSONObject audio = raw.optJSONObject("audio");
        if (audio == null) return "?";
        Object v = audio.opt("deepfake_score");
        return v == null ? "?" : String.valueOf(v);
    }

    private String heardFrom(JSONObject raw) {
        if (raw == null) return "";
        JSONObject asr = raw.optJSONObject("asr");
        if (asr != null) {
            String t = asr.optString("transcript", "").trim();
            if (!t.isEmpty()) return t;
        }
        return raw.optString("transcript", "").trim();
    }

    private String asrStatus(JSONObject raw) {
        if (raw == null) return "missing";
        JSONObject asr = raw.optJSONObject("asr");
        if (asr == null) return "missing";
        String st = asr.optString("status", "?");
        String err = asr.optString("error", "");
        if (err != null && !err.trim().isEmpty() && !"null".equalsIgnoreCase(err))
            return st + " [" + trunc(err, 60) + "]";
        return st;
    }

    private String riskBand(double r, String b) {
        if ("critical".equalsIgnoreCase(b) || r >= 80) return "CRITICAL";
        if ("high".equalsIgnoreCase(b) || r >= 63) return "HIGH";
        if ("suspicious".equalsIgnoreCase(b) || r >= 40) return "REVIEW";
        return "SAFE";
    }

    private int riskColor(double r, String b) {
        if ("critical".equalsIgnoreCase(b) || r >= 80) return parse(C_RED);
        if ("high".equalsIgnoreCase(b) || r >= 63) return parse(C_RED);
        if ("suspicious".equalsIgnoreCase(b) || r >= 40) return parse(C_AMBER);
        return parse(C_GREEN);
    }

    private void micUi(int pct) {
        updTimer();
        int bars = Math.max(0, Math.min(10, (int) Math.ceil(pct / 10.0)));
        StringBuilder m = new StringBuilder();
        for (int i = 0; i < 10; i++) m.append(i < bars ? '|' : '.');
        if (micLvl != null) micLvl.setText("Mic: " + pct + "% " + m);
    }

    private void updTimer() {
        if (t0 <= 0 || liveTimer == null) return;
        long sec = Math.max(0L, (System.currentTimeMillis() - t0) / 1000);
        liveTimer.setText(String.format(Locale.US, "%02d:%02d",
                sec / 60, sec % 60));
    }

    // ═══════════════════════════════════════════════════════════════════
    // layout helpers
    // ═══════════════════════════════════════════════════════════════════
    private int dp(int v) {
        return (int) (v * getResources().getDisplayMetrics().density);
    }

    private static int parse(String s) { return Color.parseColor(s); }

    private TextView tv(String t) { return tv(t, "#D1D5DB", 13); }

    private TextView tv(String t, String c, int sz) {
        TextView v = new TextView(this);
        v.setText(t);
        v.setTextSize(sz);
        v.setTextColor(parse(c));
        return v;
    }

    private TextView heading(String t) {
        TextView v = tv(t, "#E5E7EB", 11);
        v.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        v.setLetterSpacing(0.04f);
        v.setPadding(0, 0, 0, dp(8));
        return v;
    }

    private TextView label(String t) {
        TextView v = tv(t, C_LABEL, 13);
        v.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        return v;
    }

    private Button makeBtn(String t, String col) {
        Button b = new Button(this);
        b.setText(t);
        b.setAllCaps(false);
        b.setTextSize(14);
        b.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        b.setTextColor(Color.WHITE);
        b.setBackground(roundBg(col, "transparent", 0, 12));
        b.setMinHeight(dp(46));
        return b;
    }

    private LinearLayout col() {
        LinearLayout v = new LinearLayout(this);
        v.setOrientation(LinearLayout.VERTICAL);
        return v;
    }

    private LinearLayout row() {
        LinearLayout v = new LinearLayout(this);
        v.setOrientation(LinearLayout.HORIZONTAL);
        v.setGravity(Gravity.CENTER_VERTICAL);
        return v;
    }

    private static GradientDrawable roundBg(String fill, String stroke, int sw, int r) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(Color.parseColor(fill));
        d.setCornerRadius(dp_wrap(r));
        if (sw > 0 && !"transparent".equalsIgnoreCase(stroke))
            d.setStroke(dp_wrap(sw), Color.parseColor(stroke));
        return d;
    }

    private static int dp_wrap(int v) { return v; }

    private LinearLayout.LayoutParams weightLp() {
        return new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
    }

    private LinearLayout.LayoutParams fixedWidthLp(int widthDp) {
        return new LinearLayout.LayoutParams(dp(widthDp), ViewGroup.LayoutParams.WRAP_CONTENT);
    }

    private LinearLayout.LayoutParams matchWrapLp() {
        return new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
    }

    private LinearLayout.LayoutParams mg(int bottomDp) {
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT);
        p.setMargins(0, 0, 0, dp(bottomDp));
        return p;
    }

    private View hdiv(int h) {
        View v = new View(this);
        v.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(h)));
        return v;
    }

    private static String trunc(String v, int n) {
        return v == null || v.length() <= n
                ? v : v.substring(0, n - 3) + "...";
    }

    private static String shortErr(Exception e) {
        String m = e.getMessage();
        return (m == null || m.trim().isEmpty())
                ? e.getClass().getSimpleName()
                : (m.length() > 140 ? m.substring(0, 137) + "..." : m);
    }

    private TextView badgeChar(String c, String fill) {
        TextView v = tv(c, C_WHITE, 12);
        v.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        v.setGravity(Gravity.CENTER);
        v.setBackground(roundBg(fill, fill, 0, 16));
        v.setLayoutParams(new LinearLayout.LayoutParams(dp(32), dp(32)));
        return v;
    }

    public static final class HistoryEntry {
        public final String id;
        public final long timestampMillis;
        public final String alertTitle;
        public final double maxRisk;
        public final double averageRisk;
        public final int chunkCount;
        public final int suspiciousChunks;
        public final String topScamType;
        public final String evidence;
        public final String recommendedAction;
        public final String savedScores;

        public HistoryEntry(String id, long timestampMillis, String alertTitle, double maxRisk, double averageRisk,
                            int chunkCount, int suspiciousChunks, String topScamType, String evidence,
                            String recommendedAction, String savedScores) {
            this.id = id;
            this.timestampMillis = timestampMillis;
            this.alertTitle = alertTitle;
            this.maxRisk = maxRisk;
            this.averageRisk = averageRisk;
            this.chunkCount = chunkCount;
            this.suspiciousChunks = suspiciousChunks;
            this.topScamType = topScamType;
            this.evidence = evidence;
            this.recommendedAction = recommendedAction;
            this.savedScores = savedScores;
        }
    }

    private java.util.List<HistoryEntry> loadHistoryEntries() {
        java.util.List<HistoryEntry> list = new ArrayList<>();
        SharedPreferences sp = getSharedPreferences(PREFS, MODE_PRIVATE);
        String raw = sp.getString(K_HISTORY, "[]");
        try {
            JSONArray arr = new JSONArray(raw);
            for (int i = 0; i < arr.length(); i++) {
                JSONObject o = arr.getJSONObject(i);
                list.add(new HistoryEntry(
                        o.optString("id", ""),
                        o.optLong("timestampMillis", System.currentTimeMillis()),
                        o.optString("alertTitle", ""),
                        o.optDouble("maxRisk", 0.0),
                        o.optDouble("averageRisk", 0.0),
                        o.optInt("chunkCount", 0),
                        o.optInt("suspiciousChunks", 0),
                        o.optString("topScamType", ""),
                        o.optString("evidence", ""),
                        o.optString("recommendedAction", ""),
                        o.optString("savedScores", "")
                ));
            }
        } catch (JSONException ignored) {}
        Collections.sort(list, (a, b) -> Long.compare(b.timestampMillis, a.timestampMillis));
        return list;
    }

    private void saveHistoryEntry(SessionAlertAnalyzer.SessionSummary s) {
        SharedPreferences sp = getSharedPreferences(PREFS, MODE_PRIVATE);
        String raw = sp.getString(K_HISTORY, "[]");
        try {
            JSONArray arr = new JSONArray(raw);
            JSONObject o = new JSONObject();
            o.put("id", sid != null ? sid : "apoc-" + System.currentTimeMillis());
            o.put("timestampMillis", System.currentTimeMillis());
            o.put("alertTitle", s.alertTitle);
            o.put("maxRisk", s.maxRisk);
            o.put("averageRisk", s.averageRisk);
            o.put("chunkCount", s.chunkCount);
            o.put("suspiciousChunks", s.suspiciousChunks);
            o.put("topScamType", s.topScamType);
            o.put("evidence", s.evidence);
            o.put("recommendedAction", s.recommendedAction);
            o.put("savedScores", s.savedScores);
            arr.put(o);
            sp.edit().putString(K_HISTORY, arr.toString()).apply();
        } catch (JSONException ignored) {}
    }
}

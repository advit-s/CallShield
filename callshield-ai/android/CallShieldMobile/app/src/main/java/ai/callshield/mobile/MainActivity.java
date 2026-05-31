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
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.Bundle;
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
import android.widget.LinearLayout;
import android.widget.ImageView;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONObject;

import java.util.Arrays;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

public final class MainActivity extends Activity {

    // permissions
    private static final int REQ_AUDIO = 1001;
    private static final int REQ_CALL  = 1002;
    private static final String PREFS  = "callshield_mobile";
    private static final String K_URL  = "server_url";
    private static final String K_SAVE = "last_session_summary";
    private static final String EMU_URL = "http://10.0.2.2:8000";
    public static final String ACTION_OPEN_FROM_CALL_NOTIFICATION =
            "ai.callshield.mobile.action.OPEN_FROM_CALL_NOTIFICATION";

    private static final int TAB_SCAN = 0, TAB_HIST = 1, TAB_SET = 2;

    // palette
    private static final String C_BG      = "#05060A";
    private static final String C_NAV     = "#0B0A1A";
    private static final String C_SURFACE = "#0F172A";
    private static final String C_BORDER  = "#1F2937";
    private static final String C_TEAL    = "#14B8A6";
    private static final String C_CYAN    = "#22D3EE";
    private static final String C_GREEN   = "#22C55E";
    private static final String C_AMBER   = "#F59E0B";
    private static final String C_RED     = "#F87171";
private static final String C_ORANGE = "#FB7185";
    private static final String C_MUTED   = "#9CA3AF";
    private static final String C_LABEL   = "#94A3B8";
    private static final String C_PURPLE  = "#A855F7";
    private static final String C_WHITE   = "#FFFFFF";
    private static final String C_INDIGO  = "#312E81";

    // threading / services
    private final ExecutorService net = Executors.newSingleThreadExecutor();
    private final CallShieldApiClient api = new CallShieldApiClient();
    private final SessionAlertAnalyzer analy = new SessionAlertAnalyzer();
    private final AtomicInteger cnt = new AtomicInteger(0);
    private final AtomicBoolean fly = new AtomicBoolean(false);
    private final AtomicBoolean stopP = new AtomicBoolean(false);
    private AudioChunkStreamer streamer;

    // state
    private int tab = TAB_SCAN;
    private String sid, url;
    private long t0;
    private byte[] lastWav;
    private int lastIdx, quiet;
    private boolean warned, scanning, fromIncall, micPending;

    // UI refs
    private TextView topStatus, riskKicker, riskLabel, riskScore, riskSum;
    private TextView aTtl, aSub, lTtl, lSub, iTtl, iSub;
    private TextView liveTimer, micLvl, logTxt, connTxt, statTxt, modeHelp;
    private Button scanBtn, endBtn, srvBtn;
    private EditText urlIn;
    private Switch modeSw;
private TextView heardTxt, specTxt;
private ImageView specImg;

    // ─── lifecycle ─────────────────────────────────────────────────────
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

    // ─── root layout ───────────────────────────────────────────────────
    private View root() {
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(parse(C_BG));

        root.addView(bar(), new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT));

        FrameLayout content = new FrameLayout(this);
        ScrollView sv = new ScrollView(this);
        sv.setFillViewport(true);
        sv.setBackgroundColor(parse(C_BG));
        sv.addView(page(tab), new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));
        content.addView(sv, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));
        root.addView(content, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));

        root.addView(bottomNav(t -> { tab = t; swap(content); }),
                new FrameLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT,
                        Gravity.BOTTOM));
        return root;
    }

    private void swap(FrameLayout container) {
        container.removeAllViews();
        ScrollView sv = new ScrollView(this);
        sv.setFillViewport(true);
        sv.setBackgroundColor(parse(C_BG));
        sv.addView(page(tab), new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));
        container.addView(sv, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));
    }

    // ─── app bar ───────────────────────────────────────────────────────
    private LinearLayout bar() {
        LinearLayout bar = col();
        bar.setBackground(grad("#0C0820", "#312653"));
        bar.setPadding(dp(14), dp(18), dp(14), dp(8));
        bar.setLayoutParams(new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT));

        LinearLayout row = row();
        row.setGravity(Gravity.CENTER_VERTICAL);

        TextView logo = tv("CS");
        logo.setTextSize(13);
        logo.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        logo.setTextColor(parse("#E0F2FE"));
        logo.setBackground(roundBg("#172554", C_CYAN, 1, 16));
        logo.setPadding(dp(10), dp(8), dp(10), dp(8));
        row.addView(logo);

        TextView title = tv("CallShield");
        title.setTextSize(18);
        title.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        title.setTextColor(Color.WHITE);
        title.setPadding(dp(10), 0, 0, 0);
        row.addView(title);

        TextView pill = tv(scanning ? "LIVE" : "READY");
        pill.setTextSize(9);
        pill.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        pill.setTextColor(Color.WHITE);
        pill.setBackground(roundBg(scanning ? C_RED : C_GREEN,
                scanning ? C_RED : C_GREEN, 0, 20));
        pill.setPadding(dp(8), dp(4), dp(8), dp(4));
        row.addView(pill);

        bar.addView(row);
        return bar;
    }

    // ─── bottom nav ────────────────────────────────────────────────────
    private LinearLayout bottomNav(OnTab listener) {
        LinearLayout nav = row();
        nav.setOrientation(LinearLayout.HORIZONTAL);
        nav.setBackgroundColor(parse(C_NAV));
        nav.setElevation(dp(12));
        nav.setPadding(dp(6), dp(6), dp(6), dp(8));
        addTab(nav, "Scan",     "🔍", TAB_SCAN, listener);
        addTab(nav, "History",  "📋", TAB_HIST, listener);
        addTab(nav, "Settings", "⚙",   TAB_SET,  listener);
        return nav;
    }

    private void addTab(LinearLayout parent, String label, String icon,
                        int id, OnTab listener) {
        boolean on = (tab == id);
        LinearLayout item = col();
        item.setGravity(Gravity.CENTER);
        item.setBackground(roundBg(on ? "#1E1B4B" : C_NAV,
                on ? "#1E1B4B" : C_NAV, 0, 14));

        TextView ic = tv(icon);
        ic.setTextSize(on ? 20 : 18);
        item.addView(ic);

        TextView lb = tv(label);
        lb.setTextSize(9);
        lb.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        item.addView(lb);

        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT);
        p.setMargins(dp(4), 0, dp(4), 0);
        parent.addView(item, p);

        item.setTag(id);
        item.setOnClickListener(v -> listener.on((int) v.getTag()));
    }

    interface OnTab { void on(int id); }

    // ─── page router ───────────────────────────────────────────────────
    private View page(int t) {
        if (t == TAB_SCAN) return scanPage();
        if (t == TAB_HIST) return histPage();
        return settingsPage();
    }

    // ─── SCAN PAGE ──────────────────────────────────────────────────────
    private View scanPage() {
        LinearLayout r = col();
        r.setPadding(dp(14), dp(12), dp(14), dp(12));

        r.addView(secHead("DETECTION STATUS", C_TEAL));
        topStatus = tv(scanning ? "Listening..." : "Ready");
        topStatus.setBackground(roundBg("#111827", C_BORDER, 1, 10));
        topStatus.setPadding(dp(12), dp(12), dp(12), dp(12));
        r.addView(topStatus, mg(8));

        r.addView(secHead("THREE-SIGNAL ANALYSIS", C_PURPLE));
        SigBag sig = new SigBag();
        r.addView(sigRow("FRAGMENT AUDIO", "🔊", "IDLE", "#64748B",
                "Deepfake + replay detection", sig));
        r.addView(sigRow("SCAM LANGUAGE", "💬", "IDLE", "#64748B",
                "Scam keywords / urgency", sig));
        r.addView(sigRow("CALLER IDENTITY", "👤", "LOW", C_GREEN,
                "Callback + safe-phrase guidance", sig));
        aTtl = sig.t1; aSub = sig.s1;
        lTtl = sig.t2; lSub = sig.s2;
        iTtl = sig.t3; iSub = sig.s3;

        r.addView(secHead("OVERALL RISK SCORE", C_RED));
        LinearLayout rc = col();
        rc.setPadding(dp(16), dp(18), dp(16), dp(16));
        rc.setBackground(grad("#1A0F2E", "#2D1040"));

        riskKicker = tv("RISK SCORE");
        riskKicker.setTextSize(10);
        riskKicker.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        riskKicker.setLetterSpacing(0.1f);
        riskKicker.setTextColor(parse(C_RED));
        rc.addView(riskKicker);

        riskLabel = tv("SAFE");
        riskLabel.setTextSize(36);
        riskLabel.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        riskLabel.setTextColor(parse(C_GREEN));
        riskLabel.setPadding(0, dp(2), 0, 0);
        rc.addView(riskLabel);

        riskScore = tv("0/100 risk");
        riskScore.setTextSize(14);
        riskScore.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        riskScore.setTextColor(parse("#C4B5FD"));
        rc.addView(riskScore);

        riskSum = tv("Listening for first chunk...");
        riskSum.setTextSize(12);
        riskSum.setTextColor(parse("#D1D5DB"));
        rc.addView(riskSum);

        rc.addView(chk("Audio: real human voice detected", true, C_GREEN));
        rc.addView(chk("Language: no scam pressure",          true, C_GREEN));
        rc.addView(chk("Identity: no suspicious urgency",      true, C_GREEN));
        r.addView(rc, mg(8));

        r.addView(secHead("CALL CONTROLS", C_MUTED));
        scanBtn = makeBtn("🔍 START SCAN", C_TEAL);
        scanBtn.setOnClickListener(v -> startScan(false));
        endBtn  = makeBtn("■ END", C_INDIGO);
        endBtn.setEnabled(false);
        endBtn.setAlpha(0.5f);
        endBtn.setOnClickListener(v -> endScan());
        LinearLayout br = row();
        br.setPadding(0, 0, 0, dp(6));
        br.addView(scanBtn, lp(0, 1));
        br.addView(endBtn,  lp(0, 1));
        r.addView(br);

        r.addView(secHead("CALL EVIDENCE", C_MUTED));

        heardTxt = tv("Transcript: waiting for speech...");
        heardTxt.setBackground(roundBg("#111827", C_BORDER, 1, 10));
        heardTxt.setPadding(dp(12), dp(12), dp(12), dp(12));
        heardTxt.setTextSize(13);
        r.addView(heardTxt, mg(6));

        specTxt = tv("Spectrogram: waiting");
        specTxt.setBackground(roundBg("#111827", C_BORDER, 1, 10));
        specTxt.setPadding(dp(12), dp(10), dp(12), dp(10));
        specTxt.setTextSize(12);
        specTxt.setTextColor(parse(C_LABEL));
        r.addView(specTxt, mg(4));

        specImg = new ImageView(this);
        specImg.setScaleType(ImageView.ScaleType.FIT_XY);
        specImg.setBackground(roundBg("#111827", C_BORDER, 1, 10));
        LinearLayout.LayoutParams il = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(130));
        r.addView(specImg, il);

        micLvl = tv("Mic: waiting");
        micLvl.setTextSize(12);
        micLvl.setTextColor(parse(C_MUTED));
        r.addView(micLvl, mg(6));

        return r;
    }

    // ─── HISTORY PAGE ───────────────────────────────────────────────────
    private View histPage() {
        LinearLayout r = col();
        r.setPadding(dp(14), dp(14), dp(14), dp(14));
        r.addView(secHead("CALL HISTORY", C_MUTED));

        EditText q = new EditText(this);
        q.setSingleLine(true);
        q.setHint("Search by name / number...");
        q.setTextColor(Color.WHITE);
        q.setHintTextColor(parse("#6B7280"));
        q.setBackground(roundBg(C_SURFACE, C_BORDER, 1, 14));
        q.setPadding(dp(12), dp(10), dp(12), dp(10));
        q.setTextSize(13);
        r.addView(q, mg(6));

        LinearLayout filters = row();
        filters.setPadding(0, 0, 0, dp(4));
        filters.addView(fPill("All Calls", true));
        filters.addView(fPill("Spam",      false));
        filters.addView(fPill("Verified",  false));
        r.addView(filters, mg(4));
        r.addView(hdiv(8));

        r.addView(hRow("Unknown", "+1 (415) 555-0118", "2 min ago", C_RED,    "High Risk"));
        r.addView(hRow("Joe",     "+1 (212) 555-0188", "Oct 18",    C_GREEN,   "Safe"));
        r.addView(hRow("Unknown", "+91 98765-43210",   "Oct 17",    C_AMBER,   "Review"));
        r.addView(hRow("Amazon",  "+1 (888) 280-4331", "Oct 15",    C_GREEN,   "Safe"));
        r.addView(hRow("Bank",    "+1 (800) 555-0142", "Oct 14",    C_GREEN,   "Safe"));
        return r;
    }

    private LinearLayout hRow(String name, String num, String ts,
                              String badgeCol, String badgeTxt) {
        LinearLayout row = row();
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(14), dp(14), dp(14), dp(14));
        row.setBackground(roundBg(C_NAV, C_BORDER, 1, 14));
        row.setLayoutParams(mg(8));
        row.addView(badgeChar(name.substring(0, 1).toUpperCase(), badgeCol));

        LinearLayout c = col();
        c.setPadding(dp(10), 0, 0, 0);
        c.addView(tv(name, C_WHITE, 14));
        c.addView(tv(num, C_MUTED, 12));
        row.addView(c, lp(0, 1));

        LinearLayout rgt = col();
        rgt.setGravity(Gravity.END);
        rgt.addView(tv(ts, C_MUTED, 12));
        TextView badge = tv(badgeTxt);
        badge.setTextSize(10);
        badge.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        badge.setTextColor(Color.WHITE);
        badge.setBackground(roundBg(badgeCol + "30", badgeCol, 1, 20));
        badge.setGravity(Gravity.CENTER);
        badge.setPadding(dp(8), dp(4), dp(8), dp(4));
        rgt.addView(badge);
        row.addView(rgt);
        return row;
    }

    private TextView fPill(String lbl, boolean on) {
        TextView v = tv(lbl);
        v.setTextSize(11);
        v.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        v.setGravity(Gravity.CENTER);
        if (on) { v.setBackground(roundBg(C_CYAN, C_CYAN, 0, 20));
                  v.setTextColor(parse(C_BG)); }
        else    { v.setBackground(roundBg("#111827", C_BORDER, 1, 20));
                  v.setTextColor(parse(C_MUTED)); }
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT);
        p.setMargins(0, 0, dp(6), 0);
        v.setLayoutParams(p);
        return v;
    }

    // ─── SETTINGS PAGE ──────────────────────────────────────────────────
    private View settingsPage() {
        LinearLayout r = col();
        r.setPadding(dp(14), dp(14), dp(14), dp(14));
        r.addView(secHead("SETTINGS", C_MUTED));

        r.addView(profileRow());
        r.addView(setCard("SERVER"));
        r.addView(label("Backend URL"));
        urlIn = urlEdit();
        urlIn.setHint(isEmulator() ? EMU_URL : "http://192.168.1.x:8010");
        r.addView(urlIn, mg(4));

        connTxt = tv(isEmulator()
                ? "Emulator: " + EMU_URL
                : "Use laptop Wi-Fi IPv4, e.g. http://192.168.1.7:8010");
        connTxt.setTextColor(parse(C_MUTED));
        connTxt.setTextSize(12);
        r.addView(connTxt);

        srvBtn = makeBtn("Test Connection", C_TEAL);
        srvBtn.setOnClickListener(v -> testServer());
        r.addView(srvBtn, mg(6));

        statTxt = tv("Ready");
        statTxt.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        statTxt.setBackground(roundBg("#111827", C_BORDER, 1, 10));
        statTxt.setPadding(dp(12), dp(10), dp(12), dp(10));
        r.addView(statTxt, mg(8));

        r.addView(setCard("MONITORING"));
        LinearLayout mr = row();
        mr.setPadding(dp(8), dp(8), dp(8), dp(8));
        LinearLayout mc = col();
        mc.addView(label("Real Call Mode"));
        modeHelp = tv("Manual mode - tap Scan to start.");
        modeHelp.setTextColor(parse(C_MUTED));
        modeHelp.setTextSize(12);
        mc.addView(modeHelp);
        mr.addView(mc, lp(0, 1));

        modeSw = new Switch(this);
        modeSw.setChecked(CallShieldSettings.isRealCallModeEnabled(this));
        modeSw.setOnCheckedChangeListener((v, on) -> {
            CallShieldSettings.setRealCallModeEnabled(this, on);
            if (modeHelp != null) modeHelp.setText(on
                    ? "Monitoring armed." : "Manual mode - tap Scan to start.");
            if (on) askCall();
        });
        mr.addView(modeSw);
        r.addView(mr, mg(8));

        r.addView(setCard("DEBUG"));
        logTxt = tv("");
        logTxt.setMinLines(8);
        logTxt.setBackground(roundBg(C_NAV, C_BORDER, 1, 10));
        logTxt.setPadding(dp(12), dp(12), dp(12), dp(12));
        logTxt.setMovementMethod(new ScrollingMovementMethod());
        logTxt.setTextSize(10);
        logTxt.setTextColor(parse(C_MUTED));
        r.addView(logTxt);
        return r;
    }

    private LinearLayout profileRow() {
        LinearLayout r = row();
        r.setGravity(Gravity.CENTER_VERTICAL);
        r.setPadding(dp(14), dp(14), dp(14), dp(14));
        r.setBackground(roundBg(C_NAV, C_BORDER, 1, 16));
        r.setLayoutParams(mg(8));
        r.addView(badgeChar("Y", "#10B981"));
        LinearLayout c = col();
        c.setPadding(dp(10), 0, 0, 0);
        c.addView(tv("You", C_WHITE, 15));
        c.addView(tv("Android User", C_MUTED, 12));
        r.addView(c, lp(0, 1));
        return r;
    }

    private TextView label(String t) {
 TextView v = tv(t, C_LABEL, 11);
 v.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
 return v;
}

private LinearLayout setCard(String title) {
        LinearLayout c = col();
        c.setPadding(dp(14), dp(14), dp(14), dp(14));
        c.setBackground(roundBg(C_NAV, C_BORDER, 1, 16));
        c.addView(secHead(title, C_PURPLE));
        return c;
    }

    // ─── SCAN FLOW ──────────────────────────────────────────────────────
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
        streamer.start();
        flipBtns(true);
        setStatus("Recording. Keep speaker on.");
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
        if (riskScore != null) riskScore.setText("Final...");
        flipBtns(false);
        persist();
        stopP.set(true);
        if (fly.get()) setStatus("Waiting for final...");
        else finalSum();
    }

    private void clearScanUi() {
        if (riskLabel != null) {
            riskLabel.setText("ANALYZING");
            riskLabel.setTextColor(parse(C_TEAL));
        }
        if (riskScore != null) riskScore.setText("0/100 risk");
        if (riskSum != null) riskSum.setText("Listening for first chunk...");
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
        endBtn.setEnabled(on);
        endBtn.setAlpha(!on ? 0.5f : 1f);
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

    // ─── response rendering ─────────────────────────────────────────────
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
        String seen  = heard.isEmpty() ? "[no speech / " + asrSt + "]" : heard;
        if (heardTxt != null) heardTxt.setText("Transcript: " + seen);

        double sc = r.optDouble("risk_score", 0);
        String band = r.optString("risk_band", "?");
        String holdFlag = raw != null && raw.optJSONObject("audio") != null
                ? raw.optJSONObject("audio").optString("fusion_gate", "") : "";
        boolean hold = "held_for_text_corroboration".equalsIgnoreCase(holdFlag)
                && deepfakeScore(raw) >= 0.5;
        String disp = hold ? "REVIEW" : riskBand(sc, band);
        int col = hold ? parse(C_ORANGE) : riskColor(sc, band);

        riskLabel.setText(disp);
        riskLabel.setTextColor(col);
        riskScore.setText(String.format(Locale.US, "%.1f/100 risk", sc));
        riskSum.setText(r.optString("why_flagged",
                "Analyzing voice, language and identity."));

        if (aTtl != null) aTtl.setText(riskBand(sc, band));
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

    private void finalSum() {
        if (!stopP.compareAndSet(true, false)) return;
        SessionAlertAnalyzer.SessionSummary s = analy.summarize();
        save(s);

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

        new AlertDialog.Builder(this)
                .setTitle("CallShield: " + s.alertTitle)
                .setMessage(s.toDialogMessage())
                .setNeutralButton("View Saved", (d, w) -> showSaved())
                .setPositiveButton("OK", null)
                .show();
    }

    @Override
    public void onRequestPermissionsResult(int code, String[] perms,
                                           int[] grants) {
        super.onRequestPermissionsResult(code, perms, grants);
        if (code == REQ_AUDIO && grants.length > 0
                && grants[0] == PackageManager.PERMISSION_GRANTED) {
            startScan(micPending);
        } else if (code == REQ_CALL) {
            if (CallShieldSettings.isRealCallModeEnabled(this))
                CallShieldArmedNotifier.showArmed(this);
        } else {
            Toast.makeText(this, "Mic permission required",
                    Toast.LENGTH_LONG).show();
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

    // ─── server helpers ────────────────────────────────────────────────
    private void testServer() {
        String u = normUrl();
        if (!okUrl(u)) return;
        persist();
        connTxt.setText("Testing " + u + "...");
        srvBtn.setEnabled(false);
        net.submit(() -> {
            try {
                JSONObject h = api.healthCheck(u);
                runOnUiThread(() -> {
                    connTxt.setText("v" + h.optString("version", "?")
                            + " (" + h.optString("status", "ok") + ")");
                    log("server OK");
                    statTxt.setTextColor(parse(C_GREEN));
                });
            } catch (Exception e) {
                runOnUiThread(() -> connErr(e, u));
            } finally {
                runOnUiThread(() -> srvBtn.setEnabled(true));
            }
        });
    }

    private void handleNotif(Intent i) {
        if (i == null
                || !ACTION_OPEN_FROM_CALL_NOTIFICATION.equals(i.getAction()))
            return;
        log("notif opened");
        if (!CallShieldSettings.isRealCallModeEnabled(this)) {
            setStatus("Real call mode off - use Scan.");
            return;
        }
        setStatus("Incoming call. Tap Scan to monitor.");
    }

    private void enableSpeakerphoneAssist(boolean start) {
        CallAudioCaptureAssist.AssistResult r = CallAudioCaptureAssist.enable(this);
        if (modeHelp != null)
            modeHelp.setText((start ? "Speaker assist on. " : "") + r.userMessage);
        log("spk: " + r.logMessage);
    }

    // ─── persistence ───────────────────────────────────────────────────
    private void save(SessionAlertAnalyzer.SessionSummary s) {
        getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                .putString(K_SAVE, s.toSavedSessionText()).apply();
    }

    private void showSaved() {
        String txt = getSharedPreferences(PREFS, MODE_PRIVATE)
                .getString(K_SAVE, "No saved results yet.");
        new AlertDialog.Builder(this).setTitle("Saved Session").setMessage(txt)
                .setPositiveButton("OK", null).show();
    }

    private String normUrl() {
        return urlIn != null ? urlIn.getText().toString().trim() : loadUrl();
    }

    private String loadUrl() {
        return getSharedPreferences(PREFS, MODE_PRIVATE)
                .getString(K_URL, "");
    }

    private void persist() {
        getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                .putString(K_URL, normUrl()).apply();
    }

    // ─── device helpers ─────────────────────────────────────────────────
    private boolean isEmulator() {
        String fp = Build.FINGERPRINT == null ? "" : Build.FINGERPRINT;
        String md = Build.MODEL == null ? "" : Build.MODEL;
        return fp.contains("generic") || md.contains("emulator");
    }

    private void emuWarn() {
        if (urlIn != null)
            urlIn.setHint("Use laptop Wi-Fi on physical device");
    }

    private boolean okUrl(String u) {
        if (u.isEmpty()) {
            showBlk("URL required", "Enter address & tap Test Connection.");
            return false;
        }
        if (!u.startsWith("http://")) {
            showBlk("Bad URL", "Start with http://");
            return false;
        }
        if (!isEmulator() && u.contains("10.0.2.2")) {
            emuWarn();
            return false;
        }
        return true;
    }

    private void connErr(Exception e, String u) {
        if (connTxt != null)
            connTxt.setText("Cannot reach " + u + ". Same Wi-Fi? Firewall?");
        log("err: " + shortErr(e));
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

    // ─── response rendering ─────────────────────────────────────────────
    private void renderSpec(JSONObject raw) {
        if (specImg == null || specTxt == null) return;
        if (raw == null) {
            specTxt.setText("Spectrogram: missing");
            specImg.setImageDrawable(null);
            return;
        }
        JSONObject s = raw.optJSONObject("spectrogram");
        if (s == null) { specTxt.setText("Spectrogram: missing");
            specImg.setImageDrawable(null); return; }
        if (!s.optBoolean("available", false)) {
            specTxt.setText("Unavailable: " + trunc(s.optString("error", "?"), 60));
            specImg.setImageDrawable(null); return;
        }
        String b64 = s.optString("image_base64", "");
        if (b64.isEmpty()) {
            specTxt.setText("Spectrogram: empty b64");
            specImg.setImageDrawable(null); return;
        }
        try {
            byte[] data = Base64.decode(b64, Base64.DEFAULT);
            Bitmap bmp = BitmapFactory.decodeByteArray(data, 0, data.length);
            if (bmp == null) throw new IllegalArgumentException("decode failed");
            specImg.setImageBitmap(bmp);
            specTxt.setText("Log-mel " + s.optInt("n_mels", 0) + "×"
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
        if ("high".equalsIgnoreCase(b)    || r >= 63) return "HIGH";
        if ("suspicious".equalsIgnoreCase(b) || r >= 40) return "REVIEW";
        return "SAFE";
    }

    private int riskColor(double r, String b) {
        if ("critical".equalsIgnoreCase(b) || r >= 80) return parse(C_RED);
        if ("high".equalsIgnoreCase(b)    || r >= 63) return parse(C_RED);
        if ("suspicious".equalsIgnoreCase(b) || r >= 40) return parse(C_AMBER);
        return parse(C_GREEN);
    }

private void micUi(int pct) { updTimer(); int bars = Math.max(0, Math.min(10, (int) Math.ceil(pct / 10.0))); StringBuilder m = new StringBuilder(); for (int i = 0; i < 10; i++) m.append(i < bars ? '|' : '.'); if (micLvl != null) micLvl.setText("Mic: " + pct + "% " + m);}
    private void updTimer() {
        if (t0 <= 0) return;
        long sec = Math.max(0L, (System.currentTimeMillis() - t0) / 1000);
        liveTimer.setText(String.format(Locale.US, "%02d:%02d",
                sec / 60, sec % 60));
    }

    // ─── signal card helper ─────────────────────────────────────────────
    private static class SigBag {
        TextView t1, s1, t2, s2, t3, s3;
    }

    private LinearLayout sigRow(String title, String icon, String status,
                                String col, String subtitle, SigBag bag) {
        LinearLayout c = row();
        c.setGravity(Gravity.CENTER_VERTICAL);
        c.setPadding(dp(12), dp(12), dp(12), dp(12));
        c.setBackground(roundBg(C_SURFACE, C_BORDER, 1, 14));
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT);
        p.setMargins(0, 0, 0, dp(8));
        c.setLayoutParams(p);

        TextView ic = tv(icon);
        ic.setTextSize(18);
        ic.setBackground(roundBg(col + "30", col, 1, 10));
        ic.setPadding(dp(12), dp(10), dp(12), dp(10));
        c.addView(ic);

        LinearLayout cl = col();
        cl.setPadding(dp(10), 0, 0, 0);
        TextView tt = tv(title, C_LABEL, 9);
        tt.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        tt.setLetterSpacing(0.08f);
        cl.addView(tt);
        TextView st = tv(subtitle);
        st.setTextSize(13);
        st.setTextColor(Color.WHITE);
        st.setPadding(0, dp(2), 0, 0);
        cl.addView(st);
        c.addView(cl, lp(0, 1));

        TextView badge = tv(status, col, 10);
        badge.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        badge.setTextColor(Color.WHITE);
        badge.setBackground(roundBg(col + "30", col, 1, 20));
        badge.setGravity(Gravity.CENTER);
        badge.setPadding(dp(8), dp(4), dp(8), dp(4));
        c.addView(badge);

        if (bag.t1 == null)      { bag.t1 = tt; bag.s1 = st; }
        else if (bag.t2 == null) { bag.t2 = tt; bag.s2 = st; }
        else                     { bag.t3 = tt; bag.s3 = st; }
        return c;
    }

    private LinearLayout chk(String text, boolean ok, String c) {
        LinearLayout row = row();
        row.setPadding(0, dp(2), 0, dp(2));
        row.addView(tv(ok ? "OK" : "", c, 14));
        row.addView(tv(text, "#D1D5DB", 13), lp(0, 1));
        return row;
    }

    private Button makeBtn(String t, String col) {
        Button b = new Button(this);
        b.setText(t);
        b.setAllCaps(false);
        b.setTextSize(13);
        b.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        b.setTextColor(Color.WHITE);
        b.setBackground(roundBg(col, col, 0, 10));
        b.setMinHeight(dp(44));
        return b;
    }

    private EditText urlEdit() {
        EditText e = new EditText(this);
        e.setSingleLine(true);
        e.setInputType(InputType.TYPE_CLASS_TEXT
                | InputType.TYPE_TEXT_VARIATION_URI);
        e.setImeOptions(EditorInfo.IME_ACTION_DONE);
        e.setText(loadUrl());
        e.setTextColor(Color.WHITE);
        e.setHintTextColor(parse("#6B7280"));
        e.setBackground(roundBg(C_SURFACE, C_BORDER, 1, 10));
        e.setPadding(dp(12), dp(12), dp(12), dp(12));
        e.setTextSize(15);
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT);
        p.setMargins(0, 0, 0, dp(4));
        e.setLayoutParams(p);
        return e;
    }

    private TextView badgeChar(String c, String fill) {
        TextView v = new TextView(this);
        v.setText(c);
        v.setTextSize(15);
        v.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        v.setTextColor(Color.WHITE);
        v.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(
                dp(44), dp(44));
        GradientDrawable d = new GradientDrawable();
        d.setColor(parse(fill));
        d.setCornerRadius(dp(999));
        v.setBackground(d);
        v.setLayoutParams(p);
        return v;
    }

    // ─── layout helpers ─────────────────────────────────────────────────
    private int dp(int v) {
        return (int) (v * getResources().getDisplayMetrics().density);
    }

    private static int parse(String s) { return Color.parseColor(s); }

    private static GradientDrawable grad(String... colors) {
        GradientDrawable d = new GradientDrawable(
                GradientDrawable.Orientation.TOP_BOTTOM,
                new int[]{ Color.parseColor(colors[0]),
                           Color.parseColor(colors[1]) });
        d.setCornerRadius(0f);
        return d;
    }

    private static GradientDrawable roundBg(String fill, String stroke,
                                            int sw, int r) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(Color.parseColor(fill));
        d.setCornerRadius(dp_wrap(r));
        if (sw > 0) d.setStroke(dp_wrap(sw), Color.parseColor(stroke));
        return d;
    }

    private static int dp_wrap(int v) { return v; }

    private TextView tv(String t) { return tv(t, "#D1D5DB", 13); }

    private TextView tv(String t, String c, int sz) {
        TextView v = new TextView(this);
        v.setText(t);
        v.setTextSize(sz);
        v.setTextColor(parse(c));
        return v;
    }

    private TextView secHead(String t, String c) {
        TextView v = tv(t, c, 10);
        v.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        v.setLetterSpacing(0.12f);
        v.setPadding(0, 0, 0, dp(6));
        return v;
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

    private LinearLayout.LayoutParams lp(int w, float wt) {
        int w2 = w == 0 ? ViewGroup.LayoutParams.WRAP_CONTENT
              : w == 1 ? 0 : ViewGroup.LayoutParams.MATCH_PARENT;
        return new LinearLayout.LayoutParams(w2,
                ViewGroup.LayoutParams.WRAP_CONTENT, wt);
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
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(h));
        v.setLayoutParams(p);
        return v;
    }

    private static String trunc(String v, int n) {
        return v == null || v.length() <= n ? v
                : v.substring(0, n - 3) + "...";
    }

    private static String shortErr(Exception e) {
        String m = e.getMessage();
        return (m == null || m.trim().isEmpty())
                ? e.getClass().getSimpleName()
                : (m.length() > 140 ? m.substring(0, 137) + "..." : m);
    }
}

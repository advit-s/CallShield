package ai.callshield.mobile;

import android.content.Context;
import android.content.SharedPreferences;

final class CallShieldSettings {
    private static final String PREFS = "callshield_mobile";
    private static final String PREF_REAL_CALL_MODE = "real_call_mode";

    private CallShieldSettings() {
    }

    static boolean isRealCallModeEnabled(Context context) {
        return prefs(context).getBoolean(PREF_REAL_CALL_MODE, true);
    }

    static void setRealCallModeEnabled(Context context, boolean enabled) {
        prefs(context).edit().putBoolean(PREF_REAL_CALL_MODE, enabled).apply();
    }

    private static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }
}

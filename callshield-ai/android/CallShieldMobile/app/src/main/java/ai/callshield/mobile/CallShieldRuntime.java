package ai.callshield.mobile;

import java.lang.ref.WeakReference;

final class CallShieldRuntime {
    private static volatile boolean activityVisible;
    private static WeakReference<MainActivity> currentActivity = new WeakReference<>(null);

    private CallShieldRuntime() {
    }

    static void markActivityVisible(MainActivity activity) {
        activityVisible = true;
        currentActivity = new WeakReference<>(activity);
    }

    static void markActivityHidden(MainActivity activity) {
        activityVisible = false;
        MainActivity current = currentActivity.get();
        if (current == activity) {
            currentActivity = new WeakReference<>(null);
        }
    }

    static boolean isActivityVisible() {
        return activityVisible && currentActivity.get() != null;
    }

    static MainActivity currentActivity() {
        return currentActivity.get();
    }
}

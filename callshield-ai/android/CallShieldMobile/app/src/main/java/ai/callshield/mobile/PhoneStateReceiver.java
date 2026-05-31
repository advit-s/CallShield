package ai.callshield.mobile;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.telephony.TelephonyManager;

public final class PhoneStateReceiver extends BroadcastReceiver {
    private static final String CHANNEL_ID = "callshield_incoming_calls";
    private static final int NOTIFICATION_ID = 8042;

    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent == null || !TelephonyManager.ACTION_PHONE_STATE_CHANGED.equals(intent.getAction())) {
            return;
        }
        if (!CallShieldSettings.isRealCallModeEnabled(context)) {
            return;
        }

        String state = intent.getStringExtra(TelephonyManager.EXTRA_STATE);
        if (TelephonyManager.EXTRA_STATE_RINGING.equals(state)) {
            showIncomingCallNotification(context);
            return;
        }

        if (TelephonyManager.EXTRA_STATE_OFFHOOK.equals(state)) {
            startMonitoringFromIncomingCall(context);
            return;
        }

        if (TelephonyManager.EXTRA_STATE_IDLE.equals(state)) {
            MainActivity activity = CallShieldRuntime.currentActivity();
            if (activity != null) {
                activity.runOnUiThread(activity::handlePhoneCallEndedFromReceiver);
            } else {
                showIncomingCallNotification(context);
            }
        }
    }

    private static void startMonitoringFromIncomingCall(Context context) {
        MainActivity activity = CallShieldRuntime.currentActivity();
        if (activity != null) {
            activity.runOnUiThread(activity::handlePhoneCallStartedFromReceiver);
            return;
        }
        showIncomingCallNotification(context);
    }

    private static void showIncomingCallNotification(Context context) {
        NotificationManager manager = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        if (manager == null) {
            return;
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU
                && context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            return;
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID,
                    "Incoming call monitoring",
                    NotificationManager.IMPORTANCE_HIGH
            );
            channel.setDescription("Starts CallShield monitoring when Android allows it.");
            manager.createNotificationChannel(channel);
        }

        Intent launch = new Intent(context, MainActivity.class);
        launch.setAction(MainActivity.ACTION_OPEN_FROM_CALL_NOTIFICATION);
        launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);

        PendingIntent pendingIntent = PendingIntent.getActivity(
                context,
                0,
                launch,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(context, CHANNEL_ID)
                : new Notification.Builder(context);
        builder.setSmallIcon(android.R.drawable.stat_sys_warning)
                .setContentTitle("Incoming call detected")
                .setContentText("CallShield will auto-monitor when possible. Tap to open.")
                .setContentIntent(pendingIntent)
                .setAutoCancel(true)
                .setPriority(Notification.PRIORITY_HIGH)
                .setCategory(Notification.CATEGORY_CALL);

        manager.notify(NOTIFICATION_ID, builder.build());
    }
}

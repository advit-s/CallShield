package ai.callshield.mobile;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;

final class CallShieldArmedNotifier {
    static final int ARMED_NOTIFICATION_ID = 8041;
    private static final String CHANNEL_ID = "callshield_armed";

    private CallShieldArmedNotifier() {
    }

    static void showArmed(Context context) {
        NotificationManager manager = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        if (manager == null || !canPostNotifications(context)) {
            return;
        }
        ensureChannel(manager);

        Intent launch = new Intent(context, MainActivity.class);
        launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent pendingIntent = PendingIntent.getActivity(
                context,
                1,
                launch,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(context, CHANNEL_ID)
                : new Notification.Builder(context);

        Notification notification = builder
                .setSmallIcon(android.R.drawable.stat_sys_warning)
                .setContentTitle("CallShield armed")
                .setContentText("Real Call Mode is on. Incoming calls can trigger monitoring.")
                .setContentIntent(pendingIntent)
                .setOngoing(true)
                .setPriority(Notification.PRIORITY_LOW)
                .setCategory(Notification.CATEGORY_STATUS)
                .build();

        manager.notify(ARMED_NOTIFICATION_ID, notification);
    }

    static void cancel(Context context) {
        NotificationManager manager = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        if (manager != null) {
            manager.cancel(ARMED_NOTIFICATION_ID);
        }
    }

    private static boolean canPostNotifications(Context context) {
        return Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU
                || context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED;
    }

    private static void ensureChannel(NotificationManager manager) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            return;
        }
        NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID,
                "CallShield armed mode",
                NotificationManager.IMPORTANCE_LOW
        );
        channel.setDescription("Keeps CallShield visible while Real Call Mode is armed.");
        manager.createNotificationChannel(channel);
    }
}

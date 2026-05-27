package ai.callshield.mobile;

import android.content.Context;
import android.media.AudioDeviceInfo;
import android.media.AudioManager;
import android.os.Build;

final class CallAudioCaptureAssist {
    private CallAudioCaptureAssist() {
    }

    static AssistResult enable(Context context) {
        AudioManager audioManager = (AudioManager) context.getSystemService(Context.AUDIO_SERVICE);
        if (audioManager == null) {
            return new AssistResult(
                    false,
                    "Speakerphone capture assist unavailable: audio service missing.",
                    "audio service missing"
            );
        }

        boolean routed = false;
        String route = "legacy speakerphone";
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                for (AudioDeviceInfo device : audioManager.getAvailableCommunicationDevices()) {
                    if (device.getType() == AudioDeviceInfo.TYPE_BUILTIN_SPEAKER) {
                        routed = audioManager.setCommunicationDevice(device);
                        route = "communication device speaker";
                        break;
                    }
                }
            }

            if (audioManager.getMode() != AudioManager.MODE_IN_CALL) {
                audioManager.setMode(AudioManager.MODE_IN_COMMUNICATION);
            }
            audioManager.setSpeakerphoneOn(true);
            routed = true;
        } catch (RuntimeException error) {
            return new AssistResult(
                    false,
                    "Could not force speakerphone. Manually tap Speaker in the phone call UI.",
                    error.getClass().getSimpleName() + ": " + error.getMessage()
            );
        }

        return new AssistResult(
                routed,
                "Speakerphone capture assist is on. Put the call on speaker so CallShield can hear the scammer through the microphone.",
                route
        );
    }

    static AssistResult release(Context context) {
        AudioManager audioManager = (AudioManager) context.getSystemService(Context.AUDIO_SERVICE);
        if (audioManager == null) {
            return new AssistResult(false, "Speakerphone capture assist stopped.", "audio service missing");
        }
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                audioManager.clearCommunicationDevice();
            }
            audioManager.setSpeakerphoneOn(false);
            if (audioManager.getMode() == AudioManager.MODE_IN_COMMUNICATION) {
                audioManager.setMode(AudioManager.MODE_NORMAL);
            }
        } catch (RuntimeException error) {
            return new AssistResult(
                    false,
                    "Speakerphone capture assist stopped. Restore call audio manually if needed.",
                    error.getClass().getSimpleName() + ": " + error.getMessage()
            );
        }
        return new AssistResult(true, "Speakerphone capture assist stopped.", "released");
    }

    static final class AssistResult {
        final boolean routed;
        final String userMessage;
        final String logMessage;

        AssistResult(boolean routed, String userMessage, String logMessage) {
            this.routed = routed;
            this.userMessage = userMessage;
            this.logMessage = logMessage;
        }
    }
}

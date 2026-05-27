package ai.callshield.mobile;

import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;

final class AudioChunkStreamer {
    interface Listener {
        void onChunk(byte[] wavBytes);
        void onLevel(int percent);
        void onStatus(String message);
        void onError(Exception error);
    }

    private static final int SAMPLE_RATE = 16000;
    private static final int CHANNEL_CONFIG = AudioFormat.CHANNEL_IN_MONO;
    private static final int ENCODING = AudioFormat.ENCODING_PCM_16BIT;
    private static final int BYTES_PER_SAMPLE = 2;
    private static final int CHUNK_SECONDS = 8;

    private final Listener listener;
    private volatile boolean running;
    private Thread worker;
    private AudioRecord audioRecord;

    AudioChunkStreamer(Listener listener) {
        this.listener = listener;
    }

    boolean isRunning() {
        return running;
    }

    void start() {
        if (running) {
            return;
        }
        running = true;
        worker = new Thread(this::captureLoop, "callshield-audio-capture");
        worker.start();
    }

    void stop() {
        running = false;
        if (audioRecord != null) {
            try {
                audioRecord.stop();
            } catch (IllegalStateException ignored) {
                // Already stopped.
            }
            audioRecord.release();
            audioRecord = null;
        }
    }

    private void captureLoop() {
        int minBuffer = AudioRecord.getMinBufferSize(SAMPLE_RATE, CHANNEL_CONFIG, ENCODING);
        if (minBuffer <= 0) {
            listener.onError(new IllegalStateException("AudioRecord buffer size is unavailable"));
            running = false;
            return;
        }

        int bufferSize = Math.max(minBuffer * 2, SAMPLE_RATE * BYTES_PER_SAMPLE);
        audioRecord = buildRecorder(MediaRecorder.AudioSource.VOICE_COMMUNICATION, bufferSize);
        if (audioRecord == null || audioRecord.getState() != AudioRecord.STATE_INITIALIZED) {
            audioRecord = buildRecorder(MediaRecorder.AudioSource.VOICE_RECOGNITION, bufferSize);
        }
        if (audioRecord == null || audioRecord.getState() != AudioRecord.STATE_INITIALIZED) {
            audioRecord = buildRecorder(MediaRecorder.AudioSource.MIC, bufferSize);
        }
        if (audioRecord == null || audioRecord.getState() != AudioRecord.STATE_INITIALIZED) {
            audioRecord = buildRecorder(MediaRecorder.AudioSource.CAMCORDER, bufferSize);
        }
        if (audioRecord == null || audioRecord.getState() != AudioRecord.STATE_INITIALIZED) {
            listener.onError(new IllegalStateException("Could not initialize microphone recorder"));
            running = false;
            return;
        }

        byte[] buffer = new byte[bufferSize];
        int targetChunkBytes = SAMPLE_RATE * BYTES_PER_SAMPLE * CHUNK_SECONDS;
        ByteArrayOutputStream pcm = new ByteArrayOutputStream(targetChunkBytes);
        long lastLevelEmitMs = 0L;

        try {
            audioRecord.startRecording();
            listener.onStatus("Recording call-assist microphone chunks at 16 kHz");

            while (running) {
                int read = audioRecord.read(buffer, 0, buffer.length);
                if (read > 0) {
                    long nowMs = System.currentTimeMillis();
                    if (nowMs - lastLevelEmitMs > 250) {
                        listener.onLevel(audioLevelPercent(buffer, read));
                        lastLevelEmitMs = nowMs;
                    }
                    pcm.write(buffer, 0, read);
                    if (pcm.size() >= targetChunkBytes) {
                        listener.onChunk(wavFromPcm(pcm.toByteArray()));
                        pcm.reset();
                    }
                } else if (read < 0) {
                    throw new IOException("AudioRecord read failed: " + read);
                }
            }

            if (pcm.size() > SAMPLE_RATE * BYTES_PER_SAMPLE) {
                listener.onChunk(wavFromPcm(pcm.toByteArray()));
            }
        } catch (Exception error) {
            listener.onError(error);
        } finally {
            stop();
            listener.onStatus("Audio capture stopped");
        }
    }

    private static int audioLevelPercent(byte[] pcm, int length) {
        long sumSquares = 0L;
        int samples = 0;
        for (int i = 0; i + 1 < length; i += 2) {
            int low = pcm[i] & 0xFF;
            int high = pcm[i + 1];
            short sample = (short) ((high << 8) | low);
            sumSquares += (long) sample * sample;
            samples++;
        }
        if (samples == 0) {
            return 0;
        }
        double rms = Math.sqrt(sumSquares / (double) samples);
        int percent = (int) Math.round((rms / 32768.0) * 180.0);
        return Math.max(0, Math.min(100, percent));
    }

    private AudioRecord buildRecorder(int source, int bufferSize) {
        try {
            return new AudioRecord(source, SAMPLE_RATE, CHANNEL_CONFIG, ENCODING, bufferSize);
        } catch (SecurityException | IllegalArgumentException error) {
            listener.onError(error);
            return null;
        }
    }

    private static byte[] wavFromPcm(byte[] pcm) throws IOException {
        ByteArrayOutputStream wav = new ByteArrayOutputStream(44 + pcm.length);
        int byteRate = SAMPLE_RATE * BYTES_PER_SAMPLE;

        writeAscii(wav, "RIFF");
        writeInt(wav, 36 + pcm.length);
        writeAscii(wav, "WAVE");
        writeAscii(wav, "fmt ");
        writeInt(wav, 16);
        writeShort(wav, (short) 1);
        writeShort(wav, (short) 1);
        writeInt(wav, SAMPLE_RATE);
        writeInt(wav, byteRate);
        writeShort(wav, (short) BYTES_PER_SAMPLE);
        writeShort(wav, (short) 16);
        writeAscii(wav, "data");
        writeInt(wav, pcm.length);
        wav.write(pcm);
        return wav.toByteArray();
    }

    private static void writeAscii(ByteArrayOutputStream out, String value) throws IOException {
        out.write(value.getBytes("US-ASCII"));
    }

    private static void writeInt(ByteArrayOutputStream out, int value) throws IOException {
        out.write(ByteBuffer.allocate(4).order(ByteOrder.LITTLE_ENDIAN).putInt(value).array());
    }

    private static void writeShort(ByteArrayOutputStream out, short value) throws IOException {
        out.write(ByteBuffer.allocate(2).order(ByteOrder.LITTLE_ENDIAN).putShort(value).array());
    }
}

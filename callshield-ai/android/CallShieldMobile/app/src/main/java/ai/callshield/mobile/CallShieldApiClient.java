package ai.callshield.mobile;

import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;

final class CallShieldApiClient {
 private JSONObject lastResponse;
    JSONObject healthCheck(String baseUrl) throws Exception {
        URL url = new URL(cleanBase(baseUrl) + "/health");
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        connection.setConnectTimeout(5000);
        connection.setReadTimeout(10000);
        connection.setRequestMethod("GET");
        lastResponse = readJsonResponse(connection);
 return lastResponse;
    }

    JSONObject analyzeAudio(String baseUrl, String callId, byte[] wavBytes) throws Exception {
        String encodedCallId = URLEncoder.encode(callId, "UTF-8");
        URL url = new URL(cleanBase(baseUrl)
                + "/analyze-audio?call_id=" + encodedCallId
                + "&include_transcript=true");
        String boundary = "CallShieldBoundary" + System.currentTimeMillis();

        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        connection.setConnectTimeout(10000);
        connection.setReadTimeout(120000);
        connection.setDoOutput(true);
        connection.setRequestMethod("POST");
        connection.setRequestProperty("Content-Type", "multipart/form-data; boundary=" + boundary);

        try (DataOutputStream out = new DataOutputStream(connection.getOutputStream())) {
            writeLine(out, "--" + boundary);
            writeLine(out, "Content-Disposition: form-data; name=\"audio\"; filename=\"chunk.wav\"");
            writeLine(out, "Content-Type: audio/wav");
            writeLine(out, "");
            out.write(wavBytes);
            writeLine(out, "");
            writeLine(out, "--" + boundary + "--");
        }

        lastResponse = readJsonResponse(connection);
 return lastResponse;
    }

    private static String cleanBase(String baseUrl) {
        String cleanBase = baseUrl.trim();
        while (cleanBase.endsWith("/")) {
            cleanBase = cleanBase.substring(0, cleanBase.length() - 1);
        }
        return cleanBase;
    }

    private static JSONObject readJsonResponse(HttpURLConnection connection) throws Exception {
        int status = connection.getResponseCode();
        InputStream responseStream = status >= 200 && status < 300
                ? connection.getInputStream()
                : connection.getErrorStream();
        String body = readFully(responseStream);
        connection.disconnect();

        if (status < 200 || status >= 300) {
            throw new IllegalStateException("HTTP " + status + ": " + body);
        }
        return new JSONObject(body);
    }

    private static void writeLine(DataOutputStream out, String value) throws Exception {
        out.write(value.getBytes(StandardCharsets.UTF_8));
        out.writeBytes("\r\n");
    }

    private static String readFully(InputStream inputStream) throws Exception {
        if (inputStream == null) {
            return "";
        }
        try (BufferedInputStream in = new BufferedInputStream(inputStream);
             ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int read;
            while ((read = in.read(buffer)) != -1) {
                out.write(buffer, 0, read);
            }
            return out.toString("UTF-8");
        }
    }
}

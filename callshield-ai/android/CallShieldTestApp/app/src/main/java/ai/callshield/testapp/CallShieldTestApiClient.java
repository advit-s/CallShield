package ai.callshield.testapp;

import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.ByteArrayOutputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

final class CallShieldTestApiClient {
    JSONObject health(String baseUrl) throws Exception {
        return request(baseUrl, "/health", "GET", null);
    }

    JSONObject modelStatus(String baseUrl) throws Exception {
        return request(baseUrl, "/model-status", "GET", null);
    }

    JSONObject analyzeTranscript(String baseUrl, String callId, String transcript) throws Exception {
        JSONObject body = new JSONObject();
        body.put("call_id", callId);
        body.put("transcript", transcript);
        return request(baseUrl, "/analyze-transcript", "POST", body);
    }

    JSONObject scoreCall(String baseUrl, String callId, String transcript) throws Exception {
        JSONObject body = new JSONObject();
        body.put("call_id", callId);
        body.put("transcript", transcript);
        return request(baseUrl, "/score-call", "POST", body);
    }

    private JSONObject request(String baseUrl, String path, String method, JSONObject body) throws Exception {
        String cleanBase = cleanBaseUrl(baseUrl);
        HttpURLConnection connection = (HttpURLConnection) new URL(cleanBase + path).openConnection();
        connection.setConnectTimeout(10000);
        connection.setReadTimeout(120000);
        connection.setRequestMethod(method);
        connection.setRequestProperty("Accept", "application/json");

        if (body != null) {
            byte[] payload = body.toString().getBytes(StandardCharsets.UTF_8);
            connection.setDoOutput(true);
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            connection.setRequestProperty("Content-Length", String.valueOf(payload.length));
            try (OutputStream out = connection.getOutputStream()) {
                out.write(payload);
            }
        }

        int status = connection.getResponseCode();
        String response = readFully(status >= 200 && status < 300
                ? connection.getInputStream()
                : connection.getErrorStream());
        connection.disconnect();

        if (status < 200 || status >= 300) {
            throw new IllegalStateException("HTTP " + status + ": " + response);
        }
        return new JSONObject(response);
    }

    private static String cleanBaseUrl(String value) {
        String clean = value == null ? "" : value.trim();
        while (clean.endsWith("/")) {
            clean = clean.substring(0, clean.length() - 1);
        }
        if (clean.isEmpty()) {
            throw new IllegalArgumentException("Server URL is required.");
        }
        return clean;
    }

    private static String readFully(java.io.InputStream inputStream) throws Exception {
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

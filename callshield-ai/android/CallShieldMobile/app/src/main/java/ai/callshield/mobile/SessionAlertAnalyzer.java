package ai.callshield.mobile;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

public final class SessionAlertAnalyzer {
    private final List<ChunkScore> chunks = new ArrayList<>();

    public void reset() {
        chunks.clear();
    }

    public boolean hasChunks() {
        return !chunks.isEmpty();
    }

    public void addChunk(
            double riskScore,
            String riskBand,
            String warningLevel,
            String scamType,
            String transcript,
            double deepfakeScore,
            boolean deepfakeUsedInFusion
    ) {
        chunks.add(new ChunkScore(
                riskScore,
                safe(riskBand, "unknown"),
                safe(warningLevel, "none"),
                safe(scamType, "unknown"),
                safe(transcript, ""),
                deepfakeScore,
                deepfakeUsedInFusion
        ));
    }

    public SessionSummary summarize() {
        if (chunks.isEmpty()) {
            return new SessionSummary(
                    "NO ANALYSIS",
                    0,
                    0.0,
                    0.0,
                    0.0,
                    "unknown",
                    0,
                    0,
                    0,
                    "",
                    "No analyzed chunks were received before stopping.",
                    ""
            );
        }

        double totalRisk = 0.0;
        double maxRisk = 0.0;
        double maxDeepfakeScore = 0.0;
        int softWarnings = 0;
        int hardWarnings = 0;
        int suspiciousOrWorse = 0;
        int transcriptChunks = 0;
        Map<String, Integer> scamTypeCounts = new HashMap<>();
        StringBuilder evidence = new StringBuilder();
        StringBuilder savedScores = new StringBuilder();

        for (int i = 0; i < chunks.size(); i++) {
            ChunkScore chunk = chunks.get(i);
            totalRisk += chunk.riskScore;
            maxRisk = Math.max(maxRisk, chunk.riskScore);
            if (chunk.deepfakeUsedInFusion || !chunk.transcript.isEmpty()) {
                maxDeepfakeScore = Math.max(maxDeepfakeScore, chunk.deepfakeScore);
            }

            if ("soft".equalsIgnoreCase(chunk.warningLevel)) {
                softWarnings += 1;
            }
            if ("hard".equalsIgnoreCase(chunk.warningLevel)) {
                hardWarnings += 1;
            }
            if (isSuspiciousOrWorse(chunk.riskBand)) {
                suspiciousOrWorse += 1;
            }
            if (!chunk.scamType.isEmpty() && !"unknown".equalsIgnoreCase(chunk.scamType)) {
                scamTypeCounts.put(chunk.scamType, scamTypeCounts.getOrDefault(chunk.scamType, 0) + 1);
            }
            if (!chunk.transcript.isEmpty() && evidence.length() < 260) {
                transcriptChunks += 1;
                if (evidence.length() > 0) {
                    evidence.append("\n");
                }
                evidence.append("- ").append(truncate(chunk.transcript, 90));
            }

            savedScores
                    .append("chunk ").append(i + 1)
                    .append(": risk=").append(format1(chunk.riskScore))
                    .append(", band=").append(chunk.riskBand)
                    .append(", warning=").append(chunk.warningLevel)
                    .append(", scam=").append(chunk.scamType)
                    .append(", deepfake=").append(format3(chunk.deepfakeScore))
                    .append(", audio_used=").append(chunk.deepfakeUsedInFusion)
                    .append(", heard=\"").append(truncate(chunk.transcript, 120)).append("\"")
                    .append("\n");
        }

        double averageRisk = totalRisk / chunks.size();
        String topScamType = topScamType(scamTypeCounts);
        String alertTitle = chooseAlertTitle(maxRisk, averageRisk, hardWarnings, softWarnings, suspiciousOrWorse, maxDeepfakeScore, transcriptChunks);
        String action = chooseAction(alertTitle, topScamType, maxDeepfakeScore, suspiciousOrWorse);

        return new SessionSummary(
                alertTitle,
                chunks.size(),
                round1(maxRisk),
                round1(averageRisk),
                round3(maxDeepfakeScore),
                topScamType,
                softWarnings,
                hardWarnings,
                suspiciousOrWorse,
                evidence.toString(),
                action,
                savedScores.toString().trim()
        );
    }

    private static String chooseAlertTitle(
            double maxRisk,
            double averageRisk,
            int hardWarnings,
            int softWarnings,
            int suspiciousOrWorse,
            double maxDeepfakeScore,
            int transcriptChunks
    ) {
        if (maxRisk >= 65.0 || hardWarnings > 0) {
            return "HIGH RISK";
        }
        if (maxRisk >= 35.0 || averageRisk >= 25.0 || softWarnings > 0 || suspiciousOrWorse > 0) {
            return "REVIEW CALL";
        }
        if (transcriptChunks == 0 && maxRisk < 1.0 && softWarnings == 0 && hardWarnings == 0) {
            return "NO CALL AUDIO";
        }
        if (maxDeepfakeScore >= 0.5) {
            return "AUDIO REVIEW";
        }
        return "SAFE";
    }

    private static String chooseAction(
            String alertTitle,
            String topScamType,
            double maxDeepfakeScore,
            int suspiciousOrWorse
    ) {
        if ("HIGH RISK".equals(alertTitle)) {
            return "Do not send money, OTP, PIN, passwords, or documents. Verify the caller using another trusted channel.";
        }
        if ("REVIEW CALL".equals(alertTitle)) {
            return "Pause before acting. The conversation had suspicious signals"
                    + ("unknown".equals(topScamType) ? "." : " around " + topScamType + ".")
                    + " Verify independently.";
        }
        if ("AUDIO REVIEW".equals(alertTitle)) {
            return "Audio looked synthetic, but scam-language evidence was weak. Treat as a soft signal and verify before trusting the caller.";
        }
        if ("NO CALL AUDIO".equals(alertTitle)) {
            return "CallShield did not hear usable speech. Turn on Speaker, raise call volume, keep the phone near the speaker, and confirm the backend ASR model is loaded.";
        }
        if (suspiciousOrWorse > 0 || maxDeepfakeScore >= 0.5) {
            return "Low overall risk, but review the saved session details if something felt unusual.";
        }
        return "No strong scam signals were detected in the analyzed chunks.";
    }

    private static boolean isSuspiciousOrWorse(String band) {
        return "suspicious".equalsIgnoreCase(band)
                || "high".equalsIgnoreCase(band)
                || "critical".equalsIgnoreCase(band);
    }

    private static String topScamType(Map<String, Integer> counts) {
        String best = "unknown";
        int bestCount = 0;
        for (Map.Entry<String, Integer> entry : counts.entrySet()) {
            if (entry.getValue() > bestCount) {
                best = entry.getKey();
                bestCount = entry.getValue();
            }
        }
        return best;
    }

    private static String safe(String value, String fallback) {
        if (value == null || value.trim().isEmpty() || "null".equalsIgnoreCase(value.trim())) {
            return fallback;
        }
        return value.trim();
    }

    private static String truncate(String value, int maxLength) {
        if (value == null || value.length() <= maxLength) {
            return value == null ? "" : value;
        }
        return value.substring(0, Math.max(0, maxLength - 3)) + "...";
    }

    private static double round1(double value) {
        return Math.round(value * 10.0) / 10.0;
    }

    private static double round3(double value) {
        return Math.round(value * 1000.0) / 1000.0;
    }

    private static String format1(double value) {
        return String.format(Locale.US, "%.1f", value);
    }

    private static String format3(double value) {
        return String.format(Locale.US, "%.3f", value);
    }

    private static final class ChunkScore {
        final double riskScore;
        final String riskBand;
        final String warningLevel;
        final String scamType;
        final String transcript;
        final double deepfakeScore;
        final boolean deepfakeUsedInFusion;

        ChunkScore(
                double riskScore,
                String riskBand,
                String warningLevel,
                String scamType,
                String transcript,
                double deepfakeScore,
                boolean deepfakeUsedInFusion
        ) {
            this.riskScore = riskScore;
            this.riskBand = riskBand;
            this.warningLevel = warningLevel;
            this.scamType = scamType;
            this.transcript = transcript;
            this.deepfakeScore = deepfakeScore;
            this.deepfakeUsedInFusion = deepfakeUsedInFusion;
        }
    }

    public static final class SessionSummary {
        public final String alertTitle;
        public final int chunkCount;
        public final double maxRisk;
        public final double averageRisk;
        public final double maxDeepfakeScore;
        public final String topScamType;
        public final int softWarnings;
        public final int hardWarnings;
        public final int suspiciousChunks;
        public final String evidence;
        public final String recommendedAction;
        public final String savedScores;

        SessionSummary(
                String alertTitle,
                int chunkCount,
                double maxRisk,
                double averageRisk,
                double maxDeepfakeScore,
                String topScamType,
                int softWarnings,
                int hardWarnings,
                int suspiciousChunks,
                String evidence,
                String recommendedAction,
                String savedScores
        ) {
            this.alertTitle = alertTitle;
            this.chunkCount = chunkCount;
            this.maxRisk = maxRisk;
            this.averageRisk = averageRisk;
            this.maxDeepfakeScore = maxDeepfakeScore;
            this.topScamType = topScamType;
            this.softWarnings = softWarnings;
            this.hardWarnings = hardWarnings;
            this.suspiciousChunks = suspiciousChunks;
            this.evidence = evidence;
            this.recommendedAction = recommendedAction;
            this.savedScores = savedScores;
        }

        public String toDialogMessage() {
            StringBuilder message = new StringBuilder();
            message.append("Chunks analyzed: ").append(chunkCount).append("\n");
            message.append("Max risk: ").append(format1(maxRisk)).append("/100\n");
            message.append("Average risk: ").append(format1(averageRisk)).append("/100\n");
            message.append("Suspicious chunks: ").append(suspiciousChunks).append("\n");
            message.append("Warnings: soft=").append(softWarnings).append(", hard=").append(hardWarnings).append("\n");
            message.append("Top scam type: ").append(topScamType).append("\n");
            message.append("Max deepfake score: ").append(format3(maxDeepfakeScore)).append("\n\n");
            if (!evidence.isEmpty()) {
                message.append("Evidence heard:\n").append(evidence).append("\n\n");
            }
            message.append("Action:\n").append(recommendedAction);
            return message.toString();
        }

        public String toSavedSessionText() {
            return alertTitle + "\n\n" + toDialogMessage() + "\n\nAll chunk scores:\n" + savedScores;
        }
    }
}

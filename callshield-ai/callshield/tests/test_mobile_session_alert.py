"""Tests for Android session alert aggregation logic."""

import subprocess
import textwrap
import os
from pathlib import Path
import shutil


def _javac() -> str:
    java_home = os.environ.get("JAVA_HOME")
    candidates = []
    if java_home:
        candidates.append(Path(java_home) / "bin" / "javac.exe")
    candidates.append(Path("C:/Program Files/Android/Android Studio/jbr/bin/javac.exe"))
    found = shutil.which("javac")
    if found:
        candidates.append(Path(found))
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    raise AssertionError("javac not found")


def _java() -> str:
    java_home = os.environ.get("JAVA_HOME")
    candidates = []
    if java_home:
        candidates.append(Path(java_home) / "bin" / "java.exe")
    candidates.append(Path("C:/Program Files/Android/Android Studio/jbr/bin/java.exe"))
    found = shutil.which("java")
    if found:
        candidates.append(Path(found))
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    raise AssertionError("java not found")


def test_session_alert_analyzer_summarizes_high_risk_session(tmp_path):
    repo = Path(__file__).resolve().parents[2]
    source = (
        repo
        / "android"
        / "CallShieldMobile"
        / "app"
        / "src"
        / "main"
        / "java"
        / "ai"
        / "callshield"
        / "mobile"
        / "SessionAlertAnalyzer.java"
    )
    test_file = tmp_path / "SessionAlertAnalyzerSmokeTest.java"
    test_file.write_text(
        textwrap.dedent(
            """
            import ai.callshield.mobile.SessionAlertAnalyzer;

            public final class SessionAlertAnalyzerSmokeTest {
                public static void main(String[] args) {
                    SessionAlertAnalyzer analyzer = new SessionAlertAnalyzer();
                    analyzer.addChunk(12.0, "safe", "none", "unknown", "", 0.0, false);
                    analyzer.addChunk(72.5, "high", "hard", "upi_payment_request",
                            "Send money urgently", 0.91, true);
                    SessionAlertAnalyzer.SessionSummary summary = analyzer.summarize();

                    if (!"HIGH RISK".equals(summary.alertTitle)) {
                        throw new AssertionError(summary.alertTitle);
                    }
                    if (summary.chunkCount != 2 || summary.maxRisk < 72.0 || summary.maxDeepfakeScore < 0.9) {
                        throw new AssertionError(summary.toDialogMessage());
                    }
                    if (!summary.toDialogMessage().contains("upi_payment_request")) {
                        throw new AssertionError(summary.toDialogMessage());
                    }
                }
            }
            """
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            _javac(),
            "-d",
            str(tmp_path),
            str(source),
            str(test_file),
        ],
        check=True,
        cwd=repo,
    )
    subprocess.run(
        [_java(), "-cp", str(tmp_path), "SessionAlertAnalyzerSmokeTest"],
        check=True,
        cwd=repo,
    )

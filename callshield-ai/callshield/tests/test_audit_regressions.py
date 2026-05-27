"""Regression tests for audit-driven hardening fixes."""

import os
import json
import wave
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from callshield.api import server
from callshield.api.server import app
from callshield.engine.fusion import RiskFusionEngine, SignalScores
from callshield.engine.scam_nlp import ScamLanguageEngine, ScamType
from callshield.engine.deepfake import DeepFakeDetector
from callshield.sdk import CallShieldSDK
from callshield.engine.privacy import PrivacyLayer
from callshield.engine.audio_features import AudioFeatureExtractor


client = TestClient(app)


def _write_wav(path: Path, frames: bytes = b"\x00\x00" * 1600) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(frames)


def _json_contains(value, needle: str) -> bool:
    return needle in json.dumps(value, sort_keys=True)


def test_fusion_partial_custom_weights_use_current_defaults():
    engine = RiskFusionEngine(weights={"scam_language": 0.5})

    result = engine.score(SignalScores(deepfake=1.0))

    assert result.raw_components["weights"]["deepfake"] == RiskFusionEngine.DEFAULT_WEIGHTS["deepfake"]
    assert result.risk_score == 20.0
    result.raw_components["weights"]["deepfake"] = 0.99
    assert engine.weights["deepfake"] == RiskFusionEngine.DEFAULT_WEIGHTS["deepfake"]


def test_scam_nlp_matches_upi_with_punctuation_and_sentence_end():
    analysis = ScamLanguageEngine().analyze("Please pay via UPI?")

    assert analysis.category_scores["upi_payment_request"] > 0


def test_scam_nlp_financial_urgency_gets_suspicious_base():
    analysis = ScamLanguageEngine().analyze("Rs 5000 urgently")

    assert analysis.scam_score >= 0.25
    assert analysis.urgency_score > 0
    assert any("5000" in item for item in analysis.financial_keywords)


def test_remote_access_classified_separately_from_tech_support():
    analysis = ScamLanguageEngine().analyze("Please share screen on AnyDesk immediately")

    assert analysis.scam_type is ScamType.REMOTE_ACCESS_REQUEST
    assert "remote_access_request" in analysis.category_scores


def test_safe_result_has_neutral_why_flagged_even_with_weak_cues():
    result = CallShieldSDK().analyze_transcript(
        "The police station called, your lost wallet is ready for pickup."
    )

    assert result.risk_band == "safe"
    assert result.why_flagged == "No scam signals detected."


def test_hash_phone_uses_full_hmac_and_environment_pepper(monkeypatch):
    monkeypatch.setenv("CALLSHIELD_PHONE_PEPPER", "pepper-one")
    first = PrivacyLayer.hash_phone("+91 98765 43210")
    monkeypatch.setenv("CALLSHIELD_PHONE_PEPPER", "pepper-two")
    second = PrivacyLayer.hash_phone("+91 98765 43210")

    assert len(first) == 64
    assert len(second) == 64
    assert first != second


def test_delete_call_summary_requires_admin_key(monkeypatch):
    monkeypatch.setenv("CALLSHIELD_ADMIN_KEY", "audit-secret")
    client.post(
        "/analyze-transcript",
        json={"call_id": "audit-delete-guard", "transcript": "Normal call."},
    )

    unauthorized = client.delete("/call-summary/audit-delete-guard")
    authorized = client.delete(
        "/call-summary/audit-delete-guard",
        headers={"X-Admin-API-Key": "audit-secret"},
    )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200


def test_verify_speaker_does_not_claim_embedding_is_stored():
    response = client.post(
        "/verify-speaker",
        json={"speaker_id": "speaker-audit", "name": "Audit User", "consent_given": True},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "consent_recorded"
    assert response.json()["embedding_stored"] is False


def test_analyze_audio_does_not_leak_transcript_by_default(monkeypatch, tmp_path):
    class FakeASR:
        def transcribe(self, audio_path, language=None):
            return {"text": "SECRET OTP 123456", "language": "en", "segments": []}

    monkeypatch.setattr(server, "_get_asr", lambda: FakeASR())
    monkeypatch.setenv("CALLSHIELD_ADMIN_KEY", "audit-secret")
    monkeypatch.delenv("STORE_TRANSCRIPTS", raising=False)
    monkeypatch.setenv("INCLUDE_TRANSCRIPT_PREVIEW", "true")

    wav_path = tmp_path / "audio.wav"
    _write_wav(wav_path)

    with wav_path.open("rb") as audio:
        response = client.post(
            "/analyze-audio?call_id=audit-audio-privacy",
            files={"audio": ("audio.wav", audio, "audio/wav")},
        )

    assert response.status_code == 200
    response_json = response.json()
    assert not _json_contains(response_json, "SECRET OTP")

    summary = client.get(
        "/call-summary/audit-audio-privacy",
        headers={"X-Admin-API-Key": "audit-secret"},
    ).json()
    assert not _json_contains(summary, "SECRET OTP")


def test_analyze_audio_can_return_live_transcript_without_storing_it(monkeypatch, tmp_path):
    class FakeASR:
        def transcribe(self, audio_path, language=None):
            return {"text": "send money your child is with us", "language": "en", "segments": []}

    monkeypatch.setattr(server, "_get_asr", lambda: FakeASR())
    monkeypatch.setenv("CALLSHIELD_ADMIN_KEY", "audit-secret")
    monkeypatch.delenv("STORE_TRANSCRIPTS", raising=False)

    wav_path = tmp_path / "audio.wav"
    _write_wav(wav_path)

    with wav_path.open("rb") as audio:
        response = client.post(
            "/analyze-audio?call_id=audit-live-transcript&include_transcript=true",
            files={"audio": ("audio.wav", audio, "audio/wav")},
        )

    assert response.status_code == 200
    response_json = response.json()
    assert _json_contains(response_json, "send money your child is with us")

    summary = client.get(
        "/call-summary/audit-live-transcript",
        headers={"X-Admin-API-Key": "audit-secret"},
    ).json()
    assert not _json_contains(summary, "send money your child is with us")


def test_call_summary_requires_owner_or_admin_key(monkeypatch):
    monkeypatch.setenv("CALLSHIELD_ADMIN_KEY", "audit-secret")
    client.post(
        "/analyze-transcript",
        json={
            "call_id": "audit-summary-guard",
            "user_id": "owner-user",
            "transcript": "Normal call.",
        },
    )

    unauthorized = client.get("/call-summary/audit-summary-guard")
    wrong_owner = client.get("/call-summary/audit-summary-guard?user_id=other-user")
    owner = client.get("/call-summary/audit-summary-guard?user_id=owner-user")
    admin = client.get(
        "/call-summary/audit-summary-guard",
        headers={"X-Admin-API-Key": "audit-secret"},
    )

    assert unauthorized.status_code == 401
    assert wrong_owner.status_code == 403
    assert owner.status_code == 200
    assert admin.status_code == 200


def test_analyze_audio_rejects_non_audio_upload():
    response = client.post(
        "/analyze-audio?call_id=audit-bad-upload",
        files={"audio": ("note.txt", b"not audio", "text/plain")},
    )

    assert response.status_code == 415


def test_analyze_audio_rejects_octet_stream_non_audio_upload():
    response = client.post(
        "/analyze-audio?call_id=audit-bad-octet",
        files={"audio": ("note.txt", b"not audio", "application/octet-stream")},
    )

    assert response.status_code == 415


def test_analyze_audio_rejects_corrupt_wav_payload():
    response = client.post(
        "/analyze-audio?call_id=audit-corrupt-wav",
        files={"audio": ("broken.wav", b"not a wav", "audio/wav")},
    )

    assert response.status_code == 400


def test_deepfake_detector_ignores_no_speech_audio(monkeypatch, tmp_path):
    class FakeExtractor:
        sample_rate = 16000

        def load_audio(self, audio_path):
            return np.zeros(16000, dtype=np.float32)

    detector = object.__new__(DeepFakeDetector)
    detector.extractor = FakeExtractor()
    detector.checkpoint_path = tmp_path / "deepfake_mel_cnn.pt"
    detector.model = object()
    detector.model_status = "trained_model_loaded"
    detector.calibration_status = "calibrated"
    detector.operating_threshold = 0.1978759765625
    detector.soft_audio_threshold = 0.1978759765625
    detector.hard_audio_threshold = 0.5
    detector.target_fpr = 0.1
    detector.device = "cpu"

    result = detector.detect(str(tmp_path / "silent.wav"))

    assert result["deepfake_score"] is None
    assert result["audio_signal_strength"] == "no_speech"
    assert result["used_in_fusion"] is False


def test_audio_activity_rejects_low_level_background_noise():
    extractor = AudioFeatureExtractor()
    rng = np.random.default_rng(123)
    low_noise = rng.normal(0.0, 0.002, 16000).astype(np.float32)

    activity = extractor.audio_activity(low_noise)

    assert activity["speech_like"] is False
    assert extractor.has_speech(low_noise) is False


def test_audio_deepfake_signal_needs_text_corroboration(monkeypatch):
    sdk = CallShieldSDK()

    monkeypatch.setattr(
        sdk.deepfake_detector,
        "detect",
        lambda audio_path: {
            "deepfake_score": 1.0,
            "raw_deepfake_score": 1.0,
            "fusion_deepfake_score": 1.0,
            "audio_signal_strength": "strong",
            "used_in_fusion": True,
            "model_status": "trained_model_loaded",
        },
    )

    result = sdk.analyze_audio("dummy.wav", "hello hello hello hello hello")

    assert result.risk_score == 0.0
    assert result.audio_analysis["used_in_fusion"] is False
    assert result.audio_analysis["fusion_gate"] == "held_for_text_corroboration"


def test_kidnapping_extortion_phrase_triggers_family_emergency():
    analysis = ScamLanguageEngine().analyze("Send money now, your child is with us.")

    assert analysis.scam_score >= 0.75
    assert analysis.scam_type is ScamType.FAMILY_EMERGENCY


def test_hinglish_kidnapping_extortion_phrase_triggers_family_emergency():
    analysis = ScamLanguageEngine().analyze("Paise bhejo abhi, tumhara bachcha hamare paas hai.")

    assert analysis.scam_score >= 0.75
    assert analysis.scam_type is ScamType.FAMILY_EMERGENCY


def test_direct_payment_pressure_from_asr_triggers_upi_review():
    result = CallShieldSDK().analyze_transcript("Send me money please.")

    assert result.risk_score >= 31
    assert result.risk_band == "suspicious"
    assert result.warning_level == "soft"
    assert result.scam_type == ScamType.UPI_PAYMENT_REQUEST.value


def test_send_money_now_triggers_upi_review():
    result = CallShieldSDK().analyze_transcript("Please send money now.")

    assert result.risk_score >= 31
    assert result.risk_band == "suspicious"
    assert result.scam_type == ScamType.UPI_PAYMENT_REQUEST.value


def test_benign_college_fee_money_request_stays_safe():
    result = CallShieldSDK().analyze_transcript(
        "Dad, can you send me some money for my college fees? It is Rs 15000 this semester."
    )

    assert result.risk_band == "safe"


def test_asr_suppresses_repeated_non_target_language_hallucination():
    from callshield.engine.asr import ASRTranscriber

    assert ASRTranscriber._looks_like_silence_hallucination(
        "\u062d\u0644\u0648 \u062d\u0644\u0648 \u062d\u0644\u0648 \u062d\u0644\u0648 \u062d\u0644\u0648 \u062d\u0644\u0648",
        "ur",
    )


def test_asr_suppresses_common_whisper_outro_hallucination():
    from callshield.engine.asr import ASRTranscriber

    assert ASRTranscriber._looks_like_silence_hallucination(
        "\u3054\u8996\u8074\u3042\u308a\u304c\u3068\u3046\u3054\u3056\u3044\u307e\u3057\u305f",
        "ja",
    )

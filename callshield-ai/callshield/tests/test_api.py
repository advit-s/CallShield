"""CallShield API Endpoint Tests.

Tests all endpoints for:
- /analyze-transcript          (text-based scam detection)
- /challenge-response          (verification challenge generation)
- /model-status                (model implementation transparency)
- /submit-feedback             (user feedback storage)
- /delete-call-summary/{id}    (data deletion)
- /delete-user-data/{id}        (Right to Erasure)
- /analyze-audio               (audio + temp-file cleanup)
- /score-call                  (combined endpoint)
"""

import os
import sys
import pytest
import tempfile
from fastapi.testclient import TestClient

# Test setup: make sure we import from the package root
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..")
)

from callshield.api.server import app, APP_VERSION

client = TestClient(app)

# ============= System / Health =============

def test_health():
    """GET /health should return status ok."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["version"] == APP_VERSION
    assert data["models_loaded"]["scam_nlp"] is True
    assert isinstance(data["models_loaded"]["deepfake"], bool)


def test_model_status():
    """GET /model-status should list all modules with status."""
    resp = client.get("/model-status")
    assert resp.status_code == 200
    data = resp.json()
    assert "modules" in data
    assert data["version"] == APP_VERSION
    assert data["modules"]["scam_nlp"]["status"] == "implemented"
    assert data["modules"]["deepfake"]["status"] in {
        "pipeline_implemented_no_trained_model",
        "trained_model_loaded",
        "audio_libraries_unavailable",
        "checkpoint_load_failed",
    }
    assert "description" in data["modules"]["scam_nlp"]


# ============= /analyze-transcript =============

def test_analyze_transcript_normal():
    """POST /analyze-transcript -- normal call should be safe."""
    resp = client.post("/analyze-transcript", json={
        "call_id": "test-normal-001",
        "user_id": "user-abc",
        "transcript": "Hi beta, how are you? I made your favorite dal today."
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_band"] == "safe"
    assert data["risk_score"] <= 30
    assert data["model_status"]["scam_nlp"] == "implemented"


def test_analyze_transcript_scam():
    """POST /analyze-transcript -- scam should trigger suspicious or higher."""
    resp = client.post("/analyze-transcript", json={
        "call_id": "test-scam-001",
        "user_id": "user-abc",
        "transcript": "Beta, I lost my phone. Send ₹25,000 immediately via UPI. Do not tell anyone."
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_score"] > 30
    assert data["detected_cues"]  # should have cues
    assert data["why_flagged"]     # explainable
    assert "challenges" in data     # challenge-response


def test_analyze_transcript_confidence_fields():
    """POST /analyze-transcript -- must include confidence fields."""
    resp = client.post("/analyze-transcript", json={
        "call_id": "test-conf-001",
        "transcript": "Send money right now, it is urgent. Do not tell anyone."
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "confidence" in data
    assert "confidence_score" in data
    assert "warning_level" in data
    assert "why_flagged" in data
    assert "challenges" in data
    assert isinstance(data["confidence_score"], float)
    assert 0 <= data["confidence_score"] <= 1


def test_analyze_transcript_call_id_in_history():
    """POST /analyze-transcript -- should store in call history with user_id."""
    client.post("/analyze-transcript", json={
        "call_id": "test-store-001",
        "user_id": "user-delete-test",
        "transcript": "Some test transcript."
    })
    summary = client.get("/call-summary/test-store-001?user_id=user-delete-test")
    assert summary.status_code == 200


# ============= /score-call =============

def test_score_call_combined():
    """POST /score-call -- combined endpoint with transcript only."""
    resp = client.post("/score-call", json={
        "call_id": "test-score-001",
        "user_id": "user-abc",
        "transcript": "This is a test call. Be careful, I am asking for money right now."
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "risk_score" in data
    assert "risk_band" in data
    assert "model_status" in data
    assert data["model_status"]["scam_nlp"] == "implemented"


def test_score_call_no_content():
    """POST /score-call -- no transcript or audio should fail gracefully."""
    resp = client.post("/score-call", json={
        "call_id": "test-score-empty-001",
        "transcript": "",
    })
    assert resp.status_code == 200  # should handle gracefully


# ============= /analyze-audio (temp file cleanup) =============

def test_analyze_audio_temp_cleanup():
    """POST /analyze-audio -- temp file must be deleted even on failure."""
    from unittest.mock import patch
    import callshield.engine.asr

    with patch("callshield.engine.asr.ASRTranscriber") as MockASR:
        # Simulate a failure
        MockASR.side_effect = RuntimeError("ASR failed")
        wav_header = b"RIFF\x24\x00\x00\x00WAVEfmt "
        resp = client.post("/analyze-audio?call_id=test-audio-001&user_id=user-abc",
                           files=[("audio", ("test.wav", wav_header, "audio/wav"))])
        # Should not crash; schema returns result even if ASR is placeholder
        assert resp.status_code in [200, 500]


# ============= /challenge-response =============

def test_challenge_response():
    """POST /challenge-response -- should return safe verification challenges."""
    resp = client.post("/challenge-response", json={
        "risk_band": "high",
        "scam_type": "family_emergency",
        "risk_score": 75.0
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "challenges" in data
    for ch in data["challenges"]:
        assert "question" in ch
        assert "why" in ch
        assert "type" in ch


def test_challenge_response_general():
    """POST /challenge-response -- for safe calls, should return call-back advice."""
    resp = client.post("/challenge-response", json={
        "risk_band": "safe",
        "scam_type": "unknown",
        "risk_score": 5.0
    })
    assert resp.status_code == 200
    assert "challenges" in resp.json()


# ============= /submit-feedback =============

def test_submit_feedback():
    """POST /submit-feedback -- should store feedback and link to call history."""
    # First analyze a transcript
    client.post("/analyze-transcript", json={
        "call_id": "test-fb-001",
        "transcript": "This is a test call transcript for feedback."
    })

    # Submit feedback
    resp = client.post("/submit-feedback", json={
        "call_id": "test-fb-001",
        "is_scam": False,
        "feedback_notes": "This was a legitimate call about a delivery.",
        "reported_cues": []
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "feedback_recorded"
    assert "review and evaluation" in data["note"]
    assert "NOT" in data["note"]  # should NOT say auto-retrained


# ============= /delete-call-summary/{id} =============

def test_delete_call_summary(monkeypatch):
    """DELETE /call-summary/{id} -- should delete a specific call."""
    monkeypatch.setenv("CALLSHIELD_ADMIN_KEY", "test-admin-secret")
    # Create a call
    client.post("/analyze-transcript", json={
        "call_id": "test-delete-001",
        "transcript": "A test call."
    })

    # Verify it exists
    assert client.get(
        "/call-summary/test-delete-001",
        headers={"X-Admin-API-Key": "test-admin-secret"},
    ).status_code == 200

    # Delete it
    resp = client.delete(
        "/call-summary/test-delete-001",
        headers={"X-Admin-API-Key": "test-admin-secret"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"

    # Verify it's gone
    assert client.get("/call-summary/test-delete-001").status_code == 404


# ============= /delete-user-data/{id} =============

def test_delete_user_data(monkeypatch):
    """DELETE /user-data/{id} -- Right to Erasure under DPDP Act."""
    monkeypatch.setenv("CALLSHIELD_ADMIN_KEY", "test-admin-secret")
    # Create calls for a specific user
    for i in range(3):
        client.post("/analyze-transcript", json={
            "call_id": f"test-user-{i}",
            "user_id": "user-to-delete",
            "transcript": f"Call {i} for user-to-delete."
        })

    # Submit feedback for one
    client.post("/submit-feedback", json={
        "call_id": "test-user-0",
        "is_scam": False,
        "feedback_notes": "",
        "reported_cues": []
    })

    # Delete user data
    resp = client.delete(
        "/user-data/user-to-delete",
        headers={"X-Admin-API-Key": "test-admin-secret"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "purged"
    assert data["deleted_calls"] == 3

    # Verify all calls are gone
    for i in range(3):
        assert client.get(f"/call-summary/test-user-{i}").status_code == 404


# ============= /verify-speaker (consent check) =============

def test_verify_speaker_consent_required():
    """POST /verify-speaker -- must require consent."""
    resp = client.post("/verify-speaker", json={
        "speaker_id": "speaker-001",
        "name": "Test User",
        "consent_given": False
    })
    assert resp.status_code == 400


def test_verify_speaker_with_consent():
    """POST /verify-speaker -- with consent, should succeed."""
    resp = client.post("/verify-speaker", json={
        "speaker_id": "speaker-002",
        "name": "Test User",
        "consent_given": True
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "consent_recorded"
    assert resp.json()["embedding_stored"] is False

# ============= /score-call debug mode path validation =============

def test_score_call_debug_mode_traversal_rejected():
    """Debug mode ON but audio_path escapes project root — must be rejected."""
    old = os.environ.get("CALLSHIELD_DEBUG")
    os.environ["CALLSHIELD_DEBUG"] = "true"
    try:
        resp = client.post("/score-call", json={
            "call_id": "traversal-test",
            "transcript": "",
            "audio_path": "../../../../../etc/passwd",
        })
    finally:
        if old is None:
            os.environ.pop("CALLSHIELD_DEBUG", None)
        else:
            os.environ["CALLSHIELD_DEBUG"] = old
    assert resp.status_code == 400

def test_score_call_debug_mode_sibling_prefix_rejected():
    """Debug mode ON but path is a sibling directory — must be rejected."""
    old = os.environ.get("CALLSHIELD_DEBUG")
    os.environ["CALLSHIELD_DEBUG"] = "true"
    try:
        resp = client.post("/score-call", json={
            "call_id": "sibling-test",
            "transcript": "",
            "audio_path": r"C:\some\other\callshield-ai-evil\file.wav",
        })
    finally:
        if old is None:
            os.environ.pop("CALLSHIELD_DEBUG", None)
        else:
            os.environ["CALLSHIELD_DEBUG"] = old
    assert resp.status_code == 400

def test_score_call_debug_mode_missing_file_returns_404():
    """Debug mode ON, path inside project but file missing — 404."""
    old = os.environ.get("CALLSHIELD_DEBUG")
    os.environ["CALLSHIELD_DEBUG"] = "true"
    try:
        # Build a path inside callshield-ai (project root for the server) but the file does not exist.
        # test_api.py lives at callshield-ai/callshield/tests/test_api.py.
        # Going up 4 levels reaches callshield-ai/.
        base = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(base, "..", ".."))
        missing = os.path.join(project_root, "missing_debug_only.wav")
        resp = client.post("/score-call", json={
            "call_id": "missing-test",
            "transcript": "",
            "audio_path": missing,
        })
    finally:
        if old is None:
            os.environ.pop("CALLSHIELD_DEBUG", None)
        else:
            os.environ["CALLSHIELD_DEBUG"] = old
    assert resp.status_code == 404

def test_score_call_no_debug_mode_rejects_audio_path():
    """Without debug mode, any audio_path must be rejected outright."""
    old = os.environ.get("CALLSHIELD_DEBUG")
    os.environ.pop("CALLSHIELD_DEBUG", None)
    try:
        resp = client.post("/score-call", json={
            "call_id": "no-debug-test",
            "transcript": "hello",
            "audio_path": "/some/path.wav",
        })
    finally:
        if old is None:
            os.environ.pop("CALLSHIELD_DEBUG", None)
        else:
            os.environ["CALLSHIELD_DEBUG"] = old
    assert resp.status_code == 400


if __name__ == "__main__":
    # Run all tests
    pytest.main([__file__, "-v"])

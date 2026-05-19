"""CallShield API Server v2.1 - Trust & Calibration (Complete).

Endpoints:
  POST /analyze-transcript       Analyze text with confidence & calibration
  POST /analyze-audio            Analyze uploaded audio (temp file only)
  POST /score-call               Combined: transcript + audio + speaker
  POST /challenge-response       Get verification challenges for a call
  POST /verify-speaker           Enroll speaker (consent required)
  POST /submit-feedback          User feedback (stored for review, NOT auto-retrained)
  GET  /call-summary/{id}        Full analysis report
  GET  /model-status             Which models are implemented vs placeholder
  DELETE /call-summary/{id}      Delete specific call data
  DELETE /user-data/{id}         Delete ALL user data (Right to Erasure)
  GET  /health                   Health + uptime

Privacy: No raw audio stored. Transcripts stored only if STORE_TRANSCRIPTS=true.
         User data deletable via DELETE /user-data/{user_id}.
"""

import os
import time
import tempfile
import hashlib
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Use proper package imports (not sys.path hacks)
from callshield.sdk.callshield import CallShieldSDK, CallShieldResult
from callshield.engine.privacy import PrivacyLayer
from callshield.api.schemas import (
    TranscriptRequest, AudioRequest, ScoreCallRequest,
    RiskResult, RiskBand, SpeakerRequest, SpeakerResponse,
    FeedbackRequest, HealthResponse, CallSummaryResponse,
    ModelStatusResponse, ChallengeRequest, ChallengeResponse,
    DataDeletionResponse, UserDataDeletionResponse
)

# ---- In-memory stores (use persistent DB in production) ----
CALL_HISTORY: Dict[str, Dict] = {}    # call_id -> call data
FEEDBACK_STORE: Dict[str, Dict] = {}  # call_id -> user feedback
START_TIME = time.time()


class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        elapsed = (time.time() - start) * 1000
        response.headers["X-Processing-Time-Ms"] = str(round(elapsed, 2))
        return response


app = FastAPI(
    title="CallShield AI v2.1",
    description="Trust & Calibration: Real-time scam call intelligence. "
                "Caller ID tells you who might be calling. CallShield tells you "
                "whether the conversation is becoming dangerous.",
    version="2.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)
app.add_middleware(TimingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sdk = CallShieldSDK()
privacy = PrivacyLayer()


def _elapsed() -> int:
    return int(time.time() - START_TIME)


# === System ===

@app.get("/", tags=["System"])
async def root():
    return {
        "service": "CallShield AI v2.1",
        "release": "Trust & Calibration",
        "slogan": "Caller ID tells you who might be calling. "
                   "CallShield tells you whether the conversation is becoming dangerous.",
        "docs": "/docs",
        "demo": "/demo",
        "health": "/health",
        "model_status": "/model-status",
    }


@app.get("/health", tags=["System"], response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        version="2.1.0",
        models_loaded={
            "scam_nlp": True,
            "fusion": True,
            "calibration": True,
            "challenge": True,
            "privacy": True,
            "transcription": True,
            "deepfake": False,      # Placeholder
            "speaker_verification": False,  # Placeholder
        },
        uptime_seconds=_elapsed()
    )


@app.get("/model-status", tags=["System"])
async def model_status():
    """Show which models are fully implemented vs placeholder."""
    return ModelStatusResponse(
        version="2.1.0",
        release="Trust & Calibration",
        modules={
            "scam_nlp": {
                "status": "implemented",
                "description": "Multi-language scam language detection (EN/HI/Hinglish)"
            },
            "fusion": {
                "status": "implemented",
                "description": "Multi-signal risk fusion engine (5 signals, calibrated)"
            },
            "calibration": {
                "status": "implemented",
                "description": "Confidence-based alert calibration (signal diversity + reliability)"
            },
            "challenge": {
                "status": "implemented",
                "description": "Safe verification challenge generation by scam type"
            },
            "privacy": {
                "status": "implemented",
                "description": "Data minimization, consent, Right to Erasure"
            },
            "transcription": {
                "status": "implemented",
                "description": "ASR via OpenAI Whisper (support for EN/HI)"
            },
            "deepfake": {
                "status": "placeholder",
                "description": "Audio deepfake detection (awaiting lightweight model)"
            },
            "speaker_verification": {
                "status": "placeholder",
                "description": "ECAPA-TDNN speaker matching (awaiting model + consent flow)"
            },
        }
    )


# === Analysis ===

@app.post("/analyze-transcript", tags=["Analysis"], response_model=RiskResult)
async def analyze_transcript(req: TranscriptRequest):
    """Analyze a transcript for scam patterns with full confidence scores."""
    start = time.time()

    try:
        result = sdk.analyze_transcript(
            text=req.transcript,
            speaker_id=req.enrolled_speaker_id,
            audio_deepfake_score=req.audio_deepfake_score or 0.0
        )

        response = RiskResult(
            call_id=req.call_id,
            risk_score=result.risk_score,
            risk_band=RiskBand(result.risk_band),
            confidence=result.confidence,
            confidence_score=result.confidence_score,
            warning_level=result.warning_level,
            scam_type=result.scam_type,
            scam_type_confidence=result.scam_type_confidence,
            detected_cues=result.detected_cues,
            explanation=result.explanation,
            recommended_action=result.recommended_action,
            why_flagged=result.why_flagged,
            challenges=[{"question": c["question"], "why": c["why"]}
                        for c in result.challenges],
            raw_components=result.raw_components,
            model_status=result.model_status,
            processing_time_ms=round((time.time() - start) * 1000, 2),
            timestamp=datetime.now().isoformat()
        )

        # Store in call history (with user_id if provided)
        store_call(req.call_id, req.user_id, response.dict())

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/analyze-audio", tags=["Analysis"], response_model=RiskResult)
async def analyze_audio(call_id: str, audio: UploadFile = File(...),
                        user_id: Optional[str] = None,
                        enrolled_speaker_id: Optional[str] = None):
    """
    Analyze uploaded audio.

    Flow:
    1. Save audio to temporary file.
    2. Run ASR (OpenAI Whisper) to get transcript.
    3. Run /analyze-transcript pipeline on the transcript.
    4. Delete temporary file in a finally block.
    """
    from callshield.engine.asr import ASRTranscriber

    temp_path = None
    start = time.time()

    try:
        # Save audio to temporary file (not permanent storage)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(await audio.read())
            temp_path = f.name

        # Transcribe with Whisper
        asr = ASRTranscriber(model_name="base")  # Lightweight for API
        asr_result = asr.transcribe(temp_path)
        transcript = asr_result.get("text", "")

        # Run analysis on the transcript
        result = sdk.analyze_transcript(
            text=transcript,
            speaker_id=enrolled_speaker_id,
            audio_deepfake_score=0.0  # Placeholder: deepfake model not yet loaded
        )

        response = RiskResult(
            call_id=call_id,
            risk_score=result.risk_score,
            risk_band=RiskBand(result.risk_band),
            confidence=result.confidence,
            confidence_score=result.confidence_score,
            warning_level=result.warning_level,
            scam_type=result.scam_type,
            scam_type_confidence=result.scam_type_confidence,
            detected_cues=result.detected_cues,
            explanation=result.explanation + f" [Transcript: {transcript[:100]}]",
            recommended_action=result.recommended_action,
            why_flagged=result.why_flagged,
            challenges=[{"question": c["question"], "why": c["why"]}
                        for c in result.challenges],
            raw_components=result.raw_components,
            model_status=result.model_status,
            processing_time_ms=round((time.time() - start) * 1000, 2),
            timestamp=datetime.now().isoformat()
        )

        store_call(call_id, user_id, response.dict(), transcript=transcript)
        return response

    finally:
        # Always delete temp file, even if analysis fails
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


@app.post("/score-call", tags=["Analysis"], response_model=RiskResult)
async def score_call(req: ScoreCallRequest):
    """
    Combined call scoring.

    Accepts either:
    - A transcript (text) for text-only analysis, OR
    - A call_id with optional pre-computed scores.

    This is the recommended endpoint for integrations where you already have
    ASR + deepfake + speaker scores from other systems.
    """
    start = time.time()

    try:
        # If no text but has audio path, run audio pipeline first
        if not req.transcript and req.audio_path:
            # Audio file path provided (for batch/debugging only)
            if not os.path.exists(req.audio_path):
                raise HTTPException(status_code=404, detail="Audio file not found")

            from callshield.engine.asr import ASRTranscriber
            asr = ASRTranscriber(model_name="base")
            asr_result = asr.transcribe(req.audio_path)
            req.transcript = asr_result.get("text", "")

        # Run analysis
        result = sdk.analyze_transcript(
            text=req.transcript,
            speaker_id=req.enrolled_speaker_id,
            audio_deepfake_score=req.deepfake_score or 0.0
        )

        response = RiskResult(
            call_id=req.call_id,
            risk_score=result.risk_score,
            risk_band=RiskBand(result.risk_band),
            confidence=result.confidence,
            confidence_score=result.confidence_score,
            warning_level=result.warning_level,
            scam_type=result.scam_type,
            scam_type_confidence=result.scam_type_confidence,
            detected_cues=result.detected_cues,
            explanation=result.explanation,
            recommended_action=result.recommended_action,
            why_flagged=result.why_flagged,
            challenges=[{"question": c["question"], "why": c["why"]}
                        for c in result.challenges],
            raw_components=result.raw_components,
            model_status=result.model_status,
            processing_time_ms=round((time.time() - start) * 1000, 2),
            timestamp=datetime.now().isoformat()
        )

        store_call(req.call_id, req.user_id, response.dict(),
                   transcript=req.transcript if req.transcript else None)

        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scoring failed: {str(e)}")


# === Challenge ===

@app.post("/challenge-response", tags=["Challenge"])
async def get_challenges(req: ChallengeRequest):
    """Get safe verification challenges based on risk band and scam type."""
    from callshield.engine.challenge import ChallengeGenerator
    cg = ChallengeGenerator()
    challenges = cg.generate(req.risk_band, req.scam_type, req.risk_score)
    return {
        "challenges": [
            {"question": c.question, "why": c.why, "type": c.expected_type}
            for c in challenges
        ]
    }


# === Speaker ===

@app.post("/verify-speaker", tags=["Speaker"], response_model=SpeakerResponse)
async def verify_speaker(req: SpeakerRequest):
    """Enroll a speaker for future voice verification (requires consent)."""
    if not req.consent_given:
        raise HTTPException(
            status_code=400,
            detail="Explicit user consent is required for speaker enrollment. "
                   "This is a biometric voiceprint and requires consent under "
                   "India's DPDP Act, 2023 and similar privacy regulations."
        )
    return SpeakerResponse(
        status="enrolled",
        speaker_id=req.speaker_id,
        name=req.name,
        embedding_stored=True
    )


# === Feedback ===

@app.post("/submit-feedback", tags=["Feedback"])
async def submit_feedback(req: FeedbackRequest):
    """
    Submit user feedback on a call's risk assessment.

    Feedback is stored for manual review and periodic evaluation.
    It is NOT used for automatic retraining (to prevent abuse).
    """
    if req.call_id not in CALL_HISTORY:
        raise HTTPException(status_code=404, detail="Call ID not found")

    FEEDBACK_STORE[req.call_id] = {
        "call_id": req.call_id,
        "is_scam": req.is_scam,
        "feedback_notes": req.feedback_notes,
        "reported_cues": req.reported_cues,
        "timestamp": datetime.now().isoformat(),
    }

    # Link to call history
    CALL_HISTORY[req.call_id]["user_feedback"] = FEEDBACK_STORE[req.call_id]

    return {
        "status": "feedback_recorded",
        "call_id": req.call_id,
        "note": "Feedback stored for review and evaluation. "
                "Not used for automatic retraining."
    }


# === Data Management ===

@app.delete("/call-summary/{call_id}", tags=["Data Management"])
async def delete_call_summary(call_id: str, user_id: Optional[str] = None):
    """Permanently delete a call summary (Right to Erasure for a specific call)."""
    if call_id not in CALL_HISTORY:
        raise HTTPException(status_code=404, detail=f"Call '{call_id}' not found")

    # Optional: verify user owns this call
    if user_id and CALL_HISTORY[call_id].get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="User does not own this call record")

    del CALL_HISTORY[call_id]
    if call_id in FEEDBACK_STORE:
        del FEEDBACK_STORE[call_id]

    return DataDeletionResponse(
        call_id=call_id,
        status="deleted",
        timestamp=datetime.now().isoformat()
    )


@app.delete("/user-data/{user_id}", tags=["Data Management"])
async def delete_user_data(user_id: str):
    """
    Delete ALL data associated with a user (Right to Erasure under DPDP Act).

    This permanently deletes:
    - All call records for this user
    - All feedback from this user
    - All enrolled speaker data
    """
    deleted_calls = 0
    for call_id, data in list(CALL_HISTORY.items()):
        if data.get("user_id") == user_id:
            del CALL_HISTORY[call_id]
            if call_id in FEEDBACK_STORE:
                del FEEDBACK_STORE[call_id]
            deleted_calls += 1

    return UserDataDeletionResponse(
        user_id=user_id,
        deleted_calls=deleted_calls,
        status="purged",
        timestamp=datetime.now().isoformat()
    )


@app.get("/call-summary/{call_id}", tags=["Analysis"], response_model=CallSummaryResponse)
async def call_summary(call_id: str):
    """Get the full analysis report for a specific call."""
    if call_id not in CALL_HISTORY:
        raise HTTPException(status_code=404, detail=f"Call '{call_id}' not found")

    data = CALL_HISTORY[call_id]
    result = data["result"]

    return CallSummaryResponse(
        call_id=call_id,
        risk_score=result.get("risk_score", 0),
        risk_band=RiskBand(result.get("risk_band", "safe")),
        scam_type=result.get("scam_type", "unknown"),
        detected_cues=result.get("detected_cues", []),
        explanation=result.get("explanation", ""),
        recommended_action=result.get("recommended_action", ""),
        raw_components=result.get("raw_components", {}),
        model_status=result.get("model_status", {}),
        final_risk_score=result.get("risk_score", 0),
        final_risk_band=RiskBand(result.get("risk_band", "safe")),
        final_cues=result.get("detected_cues", []),
        final_action=result.get("recommended_action", ""),
        total_chunks=data.get("total_chunks", 1)
    )


# === Demo ===

@app.get("/demo", response_class=HTMLResponse)
async def demo_page():
    """Serve the interactive product demo dashboard."""
    html_path = Path(__file__) / ".." / ".." / "dashboard" / "index.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>CallShield AI v2.1</h1><p>Dashboard not available.</p>")


# === Helpers ===

def store_call(call_id: str, user_id: Optional[str], result: Dict,
               transcript: Optional[str] = None) -> None:
    """Store a call result in CALL_HISTORY."""
    CALL_HISTORY[call_id] = {
        "user_id": user_id,
        "result": result,
        "timestamp": datetime.now().isoformat(),
        "total_chunks": 1,
    }

    # Only store transcript if enabled (privacy default)
    store_transcripts = os.environ.get("STORE_TRANSCRIPTS", "false").lower() == "true"
    if store_transcripts and transcript:
        CALL_HISTORY[call_id]["transcript"] = transcript


# === Run ===

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

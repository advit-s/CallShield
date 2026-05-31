"""CallShield API Server v2.4.0 - Mobile ASR and Scam NLP Hardening.

Endpoints:
POST /analyze-transcript Analyze text with confidence & calibration
POST /analyze-audio Analyze uploaded audio (temp file only)
POST /score-call Combined: transcript + audio + speaker
POST /challenge-response Get verification challenges for a call
POST /verify-speaker Enroll speaker (consent required)
POST /submit-feedback User feedback (stored for review, NOT auto-retrained)
GET /call-summary/{id} Full analysis report
GET /model-status Which models are trained, implemented, or pending
DELETE /call-summary/{id} Delete specific call data
DELETE /user-data/{id} Delete ALL user data (Right to Erasure)
GET /health Health + uptime

Privacy: No raw audio stored. Transcripts stored only if STORE_TRANSCRIPTS=true.
User data deletable via DELETE /user-data/{user_id}.
"""

import os
import time
import tempfile
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

from fastapi import FastAPI, HTTPException, UploadFile, File, Request, status, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Use proper package imports (not sys.path hacks)
from callshield.sdk import CallShieldSDK, CallShieldResult
from callshield.engine.privacy import PrivacyLayer
from callshield.engine.db import CallShieldDatabase
from callshield.engine.asr import (
    DEFAULT_HF_ASR_MODEL,
    default_hf_asr_root,
    resolve_hf_asr_model,
)
from callshield.api.schemas import (
    TranscriptRequest, AudioRequest, ScoreCallRequest,
    RiskResult, RiskBand, SpeakerRequest, SpeakerResponse,
    FeedbackRequest, HealthResponse, CallSummaryResponse,
    ModelStatusResponse, ChallengeRequest, ChallengeResponse,
    DataDeletionResponse, UserDataDeletionResponse
)

# Initialize database persistence layer
db = CallShieldDatabase()

# ---- In-memory stores (use persistent DB in production) ----
CALL_HISTORY: Dict[str, Dict] = {}  # call_id -> call data
FEEDBACK_STORE: Dict[str, Dict] = {}  # call_id -> user feedback
START_TIME = time.time()
APP_VERSION = "2.4.0"
APP_TITLE = "CallShield AI v2.4.0"
APP_RELEASE = "Mobile ASR and Scam NLP Hardening"
DEBUG_MODE = os.environ.get("CALLSHIELD_DEBUG", "false").lower() == "true"
MAX_AUDIO_UPLOAD_BYTES = int(os.environ.get("CALLSHIELD_MAX_AUDIO_UPLOAD_BYTES", str(10 * 1024 * 1024)))
ALLOWED_AUDIO_CONTENT_TYPES = {
    "audio/wav", "audio/wave", "audio/x-wav",
    "audio/mpeg", "audio/mp3", "audio/mp4",
    "audio/ogg", "audio/flac", "audio/webm",
}
ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".webm", ".aac"}
OCTET_STREAM_CONTENT_TYPE = "application/octet-stream"


def _cors_origins() -> List[str]:
    raw = os.environ.get(
        "CALLSHIELD_CORS_ORIGINS",
        "http://localhost:8000,http://127.0.0.1:8000,http://localhost:8010,http://127.0.0.1:8010",
    )
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return origins or ["http://localhost:8000"]


class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        elapsed = (time.time() - start) * 1000
        response.headers["X-Processing-Time-Ms"] = str(round(elapsed, 2))
        return response


app = FastAPI(
    title=APP_TITLE,
    description=f"{APP_RELEASE}: Real-time scam call intelligence. "
    "Caller ID tells you who might be calling. CallShield tells you "
    "whether the conversation is becoming dangerous.",
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)
app.add_middleware(TimingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=os.environ.get("CALLSHIELD_CORS_CREDENTIALS", "false").lower() == "true",
    allow_methods=["*"],
    allow_headers=["*"],
)

sdk = CallShieldSDK()
privacy = PrivacyLayer()


def _elapsed() -> int:
    return int(time.time() - START_TIME)


_ASR_INSTANCE = None


def _env_true(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).lower() in {"1", "true", "yes", "on"}


def _store_transcripts_enabled() -> bool:
    return _env_true("STORE_TRANSCRIPTS")


def _admin_key_matches(x_admin_api_key: Optional[str]) -> bool:
    if os.environ.get("CALLSHIELD_DEMO_MODE", "false").lower() == "true":
        return True
    expected = os.environ.get("CALLSHIELD_ADMIN_KEY")
    return bool(expected and x_admin_api_key == expected)


def _asr_runtime_config() -> Dict[str, Any]:
    """Resolve the ASR backend; prefer the local Hindi/Hinglish snapshot when present."""
    requested_model = os.environ.get("CALLSHIELD_HF_ASR_MODEL", DEFAULT_HF_ASR_MODEL)
    local_dir = os.environ.get("CALLSHIELD_HF_ASR_LOCAL_DIR")
    local_model = resolve_hf_asr_model(
        model_name=requested_model,
        local_dir=local_dir,
        local_root=default_hf_asr_root(),
        prefer_local=_env_true("CALLSHIELD_HF_ASR_PREFER_LOCAL", "true"),
    )

    backend = os.environ.get("CALLSHIELD_ASR_BACKEND")
    if not backend:
        backend = "huggingface" if Path(local_model).exists() else "openai_whisper"

    if backend == "huggingface":
        return {
            "backend": backend,
            "model_name": local_model,
            "local_files_only": _env_true("CALLSHIELD_ASR_OFFLINE") or Path(local_model).exists(),
        }

    return {
        "backend": backend,
        "model_name": os.environ.get("CALLSHIELD_WHISPER_MODEL", "base"),
        "local_files_only": False,
    }


def _get_asr():
    """Lazy-load Whisper once instead of reloading it for every upload."""
    global _ASR_INSTANCE
    if _ASR_INSTANCE is None:
        from callshield.engine.asr import ASRTranscriber
        config = _asr_runtime_config()
        _ASR_INSTANCE = ASRTranscriber(
            model_name=config["model_name"],
            backend=config["backend"],
            local_files_only=config["local_files_only"],
        )
    return _ASR_INSTANCE


def _validate_audio_upload(audio: UploadFile) -> str:
    suffix = Path(audio.filename or "").suffix.lower()
    content_type = (audio.content_type or "").lower()
    if suffix not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported audio upload type. Use wav, mp3, m4a, ogg, flac, webm, or aac.",
        )
    if content_type and content_type not in ALLOWED_AUDIO_CONTENT_TYPES and content_type != OCTET_STREAM_CONTENT_TYPE:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported audio upload content type.",
        )
    return suffix


def _spectrogram_preview(audio_path: str) -> Dict[str, Any]:
    """Build a transient log-mel spectrogram preview for live mobile debugging."""
    try:
        from callshield.engine.audio_features import AudioFeatureExtractor
        extractor = AudioFeatureExtractor()
        waveform = extractor.load_audio(audio_path)
        return extractor.spectrogram_preview(waveform)
    except Exception as exc:
        return {
            "available": False,
            "error": str(exc),
        }


async def _read_audio_upload(audio: UploadFile) -> bytes:
    payload = await audio.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Audio upload is empty")
    if len(payload) > MAX_AUDIO_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Audio upload exceeds size limit")
    return payload


def _validate_audio_payload(suffix: str, payload: bytes) -> None:
    """Reject obviously mislabeled audio before ASR/deepfake libraries touch it."""
    checks = {
        ".wav": lambda p: len(p) >= 12 and p[:4] == b"RIFF" and p[8:12] == b"WAVE",
        ".flac": lambda p: p.startswith(b"fLaC"),
        ".ogg": lambda p: p.startswith(b"OggS"),
        ".webm": lambda p: p.startswith(b"\x1a\x45\xdf\xa3"),
        ".mp3": lambda p: p.startswith(b"ID3") or (len(p) >= 2 and p[0] == 0xFF and (p[1] & 0xE0) == 0xE0),
    }
    checker = checks.get(suffix)
    if checker and not checker(payload):
        raise HTTPException(status_code=400, detail="Invalid audio payload for declared file type")


def require_admin_key(x_admin_api_key: Optional[str] = Header(None, alias="X-Admin-API-Key")) -> None:
    """Require an admin key for destructive demo-memory data deletion endpoints."""
    if not _admin_key_matches(x_admin_api_key):
        raise HTTPException(status_code=401, detail="Admin API key required")


# === System ===

@app.get("/", tags=["System"])
async def root():
    return {
        "service": APP_TITLE,
        "release": APP_RELEASE,
        "slogan": "Caller ID tells you who might be calling. "
        "CallShield tells you whether the conversation is becoming dangerous.",
        "docs": "/docs",
        "demo": "/demo",
        "health": "/health",
        "model_status": "/model-status",
    }


@app.get("/health", tags=["System"], response_model=HealthResponse)
async def health():
    status = sdk.get_model_status()
    return HealthResponse(
        status="ok",
        version=APP_VERSION,
        models_loaded={
            "scam_nlp": True,
            "fusion": True,
            "calibration": True,
            "challenge": True,
            "privacy": True,
            "transcription": status["asr"] == "available",
            "deepfake": status["deepfake"] == "trained_model_loaded",
            "speaker_verification": False,
        },
        uptime_seconds=_elapsed()
    )


@app.get("/model-status", tags=["System"])
async def model_status():
    """Show which modules are trained, implemented, or pending."""
    status = sdk.get_model_status()
    asr_config = _asr_runtime_config()
    return ModelStatusResponse(
        version=APP_VERSION,
        release=APP_RELEASE,
        modules={
            "scam_nlp": {
                "status": status["scam_nlp"],
                "description": "Multi-language scam language detection (EN/HI/Hinglish)",
            },
            "fusion": {
                "status": status["fusion"],
                "description": "Multi-signal risk fusion engine (5 signals, calibrated)",
            },
            "calibration": {
                "status": status["calibration"],
                "description": "Confidence-based alert calibration (signal diversity + reliability)",
            },
            "challenge": {
                "status": status["challenge"],
                "description": "Safe verification challenge generation by scam type",
            },
            "privacy": {
                "status": status["privacy"],
                "description": "Data minimization, consent, Right to Erasure",
            },
            "asr": {
                "status": status["asr"],
                "description": "ASR via OpenAI Whisper or offline Hugging Face snapshot",
                "backend": asr_config["backend"],
                "model": asr_config["model_name"],
                "offline": str(asr_config["local_files_only"]).lower(),
            },
            "deepfake": {
                "status": status["deepfake"],
                "description": "Log-mel CNN with calibrated fusion threshold",
                "calibration_status": sdk.deepfake_detector.calibration_status,
                "operating_threshold": str(round(sdk.deepfake_detector.operating_threshold, 4)),
                "soft_audio_threshold": str(round(sdk.deepfake_detector.soft_audio_threshold, 4)),
                "hard_audio_threshold": str(round(sdk.deepfake_detector.hard_audio_threshold, 4)),
                "target_fpr": str(sdk.deepfake_detector.target_fpr),
            },
            "speaker_verification": {
                "status": status["speaker_verification"],
                "description": "ECAPA-TDNN speaker matching (awaiting model + consent flow)",
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
            challenges=[{"question": c["question"], "why": c["why"]} for c in result.challenges],
            raw_components=result.raw_components,
            model_status=result.model_status,
            processing_time_ms=round((time.time() - start) * 1000, 2),
            timestamp=datetime.now().isoformat()
        )

        # Store in call history (with user_id if provided)
        store_call(req.call_id, req.user_id, response.model_dump())

        return response

    except Exception:
        raise HTTPException(status_code=500, detail="Analysis failed")


@app.post("/analyze-audio", tags=["Analysis"], response_model=RiskResult)
async def analyze_audio(
    call_id: str,
    audio: UploadFile = File(...),
    user_id: Optional[str] = None,
    enrolled_speaker_id: Optional[str] = None,
    include_transcript: bool = False,
):
    """
    Analyze uploaded audio.

    Flow:
    1. Save audio to temporary file.
    2. Run ASR (OpenAI Whisper) to get transcript.
    3. Run /analyze-transcript pipeline on the transcript.
    4. Delete temporary file in a finally block.
    """
    temp_path = None
    start = time.time()

    try:
        suffix = _validate_audio_upload(audio)
        payload = await _read_audio_upload(audio)
        _validate_audio_payload(suffix, payload)

        # Save audio to temporary file (not permanent storage)
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(payload)
            temp_path = f.name

        # Transcribe with Whisper
        asr_result = _get_asr().transcribe(temp_path)
        spectrogram = _spectrogram_preview(temp_path)
        transcript = asr_result.get("text", "")
        return_live_transcript = include_transcript or _store_transcripts_enabled()
        asr_debug = {
            "language": asr_result.get("language"),
            "status": asr_result.get("status", "unknown"),
            "error": asr_result.get("error"),
            "confidence": asr_result.get("confidence", 0.0),
            "activity": asr_result.get("activity"),
            "segment_count": len(asr_result.get("segments", [])),
            "heard_speech": bool(transcript.strip()),
        }
        if return_live_transcript:
            asr_debug["transcript"] = transcript

        # Run analysis on the audio and transcript
        result = sdk.analyze_audio(
            audio_path=temp_path,
            transcript=transcript,
            speaker_id=enrolled_speaker_id
        )
        raw_components = {
            **result.raw_components,
            "audio": result.audio_analysis,
            "asr": asr_debug,
            "spectrogram": spectrogram,
        }
        if return_live_transcript:
            raw_components["transcript"] = transcript

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
            explanation=(
                result.explanation + f" [Transcript: {transcript[:100]}]"
                if _env_true("INCLUDE_TRANSCRIPT_PREVIEW") and _store_transcripts_enabled() and transcript
                else result.explanation
            ),
            recommended_action=result.recommended_action,
            why_flagged=result.why_flagged,
            challenges=[{"question": c["question"], "why": c["why"]} for c in result.challenges],
            raw_components=raw_components,
            model_status=result.model_status,
            processing_time_ms=round((time.time() - start) * 1000, 2),
            timestamp=datetime.now().isoformat()
        )

        response_dump = response.model_dump()
        if not _store_transcripts_enabled():
            response_dump = _without_transcript_fields(response_dump)
        store_call(call_id, user_id, response_dump, transcript=transcript)
        return response

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Audio analysis failed")

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
        debug_mode = os.environ.get("CALLSHIELD_DEBUG", "false").lower() == "true"
        if req.audio_path and not debug_mode:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="audio_path is available only when CALLSHIELD_DEBUG=true. Use /analyze-audio for uploaded audio."
            )

        resolved_path = None

        # If no text but has audio path, run audio pipeline first in local debug mode.
        if not req.transcript and req.audio_path:
            resolved_path = Path(req.audio_path).resolve()
            project_root = PROJECT_ROOT.resolve()
            # Path containment check: reject traversal, sibling-prefix paths, symlinks
            try:
                resolved_path.relative_to(project_root)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Access denied: audio_path must be within the project workspace."
                )
            if not resolved_path.exists():
                raise HTTPException(status_code=404, detail="Audio file not found")

            asr_result = _get_asr().transcribe(str(resolved_path))
            req.transcript = asr_result.get("text", "")

        # Run analysis
        result = sdk.analyze_transcript(
            text=req.transcript or "",
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
            challenges=[{"question": c["question"], "why": c["why"]} for c in result.challenges],
            raw_components=result.raw_components,
            model_status=result.model_status,
            processing_time_ms=round((time.time() - start) * 1000, 2),
            timestamp=datetime.now().isoformat()
        )

        store_call(req.call_id, req.user_id, response.model_dump(), transcript=req.transcript if req.transcript else None)

        return response

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Scoring failed")


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
    db.store_speaker(req.speaker_id, req.name, req.consent_given, user_id=req.user_id)
    return SpeakerResponse(
        status="consent_recorded",
        speaker_id=req.speaker_id,
        name=req.name,
        embedding_stored=False
    )


# === Feedback ===

@app.post("/submit-feedback", tags=["Feedback"])
async def submit_feedback(req: FeedbackRequest):
    """
    Submit user feedback on a call's risk assessment.

    Feedback is stored for manual review and periodic evaluation.
    It is NOT used for automatic retraining (to prevent abuse).
    """
    call_record = db.get_call(req.call_id)
    if not call_record:
        raise HTTPException(status_code=404, detail="Call ID not found")

    db.store_feedback(
        call_id=req.call_id,
        is_scam=req.is_scam,
        notes=req.feedback_notes,
        reported_cues=req.reported_cues or []
    )

    # Sync back to in-memory dictionary for backward compatibility
    feedback_data = {
        "call_id": req.call_id,
        "is_scam": req.is_scam,
        "feedback_notes": req.feedback_notes,
        "reported_cues": req.reported_cues,
        "timestamp": datetime.now().isoformat(),
    }
    FEEDBACK_STORE[req.call_id] = feedback_data
    if req.call_id in CALL_HISTORY:
        CALL_HISTORY[req.call_id]["user_feedback"] = FEEDBACK_STORE[req.call_id]

    return {
        "status": "feedback_recorded",
        "call_id": req.call_id,
        "note": "Feedback stored for review and evaluation. "
        "NOT used for automatic retraining."
    }


# === Data Management ===

@app.delete("/call-summary/{call_id}", tags=["Data Management"])
async def delete_call_summary(
    call_id: str,
    user_id: Optional[str] = None,
    _: None = Depends(require_admin_key),
):
    """Permanently delete a call summary (Right to Erasure for a specific call)."""
    data = db.get_call(call_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Call '{call_id}' not found")

    # Optional: verify user owns this call
    if user_id and data.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="User does not own this call record")

    db.delete_call(call_id)

    # Sync back to in-memory
    if call_id in CALL_HISTORY:
        del CALL_HISTORY[call_id]
    if call_id in FEEDBACK_STORE:
        del FEEDBACK_STORE[call_id]

    return DataDeletionResponse(
        call_id=call_id,
        status="deleted",
        timestamp=datetime.now().isoformat()
    )


@app.delete("/user-data/{user_id}", tags=["Data Management"])
async def delete_user_data(user_id: str, _: None = Depends(require_admin_key)):
    """
    Delete ALL data associated with a user (Right to Erasure under DPDP Act).

    This permanently deletes:
    - All call records for this user
    - All feedback from this user
    - All enrolled speaker data
    """
    delete_report = db.delete_user_data(user_id)

    # Sync back to in-memory
    for call_id, data in list(CALL_HISTORY.items()):
        if data.get("user_id") == user_id:
            del CALL_HISTORY[call_id]
    if call_id in FEEDBACK_STORE:
        del FEEDBACK_STORE[call_id]

    return UserDataDeletionResponse(
        user_id=user_id,
        deleted_calls=delete_report["deleted_calls"],
        deleted_speakers=delete_report["deleted_speakers"],
        deleted_feedback=delete_report["deleted_feedback"],
        status="purged",
        timestamp=datetime.now().isoformat()
    )


@app.get("/call-summary/{call_id}", tags=["Analysis"], response_model=CallSummaryResponse)
async def call_summary(
    call_id: str,
    user_id: Optional[str] = None,
    x_admin_api_key: Optional[str] = Header(None, alias="X-Admin-API-Key"),
):
    """Get the full analysis report for a specific call."""
    data = db.get_call(call_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Call '{call_id}' not found")

    stored_user_id = data.get("user_id")
    if not _admin_key_matches(x_admin_api_key):
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID or admin API key required")
        if stored_user_id != user_id:
            raise HTTPException(status_code=403, detail="User does not own this call record")

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
    html_path = Path(__file__).resolve().parents[1] / "dashboard" / "index.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse(content=f"<h1>{APP_TITLE}</h1><p>Dashboard not available.</p>")


# === Helpers ===

def store_call(call_id: str, user_id: Optional[str], result: Dict, transcript: Optional[str] = None) -> None:
    """Store a call result in database and CALL_HISTORY."""
    # Only store transcript if enabled (privacy default)
    store_transcripts = os.environ.get("STORE_TRANSCRIPTS", "false").lower() == "true"

    # Store to SQLite database
    db.store_call(
        call_id=call_id,
        user_id=user_id,
        result=result,
        transcript=transcript if store_transcripts else None
    )

    # Sync back to in-memory CALL_HISTORY for backward compatibility
    CALL_HISTORY[call_id] = {
        "user_id": user_id,
        "result": result,
        "timestamp": datetime.now().isoformat(),
        "total_chunks": 1,
    }
    if store_transcripts and transcript:
        CALL_HISTORY[call_id]["transcript"] = transcript


def _without_transcript_fields(result: Dict[str, Any]) -> Dict[str, Any]:
    """Remove raw transcript fields before storing privacy-default call summaries."""
    sanitized = dict(result)
    raw_components = dict(sanitized.get("raw_components") or {})
    raw_components.pop("transcript", None)
    asr = raw_components.get("asr")
    if isinstance(asr, dict):
        safe_asr = dict(asr)
        safe_asr.pop("transcript", None)
        raw_components["asr"] = safe_asr
    sanitized["raw_components"] = raw_components
    return sanitized


# === Run ===

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

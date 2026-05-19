"""CallShield AI - Real-time deepfake call detection API."""

import os
import time
import base64
import asyncio
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

import numpy as np
import torch
import torchaudio
import soundfile as sf

import numpy as np
import torch
import torchaudio
import soundfile as sf

from .config import get_config
from .schemas import RiskBand, CallRequest
from audio.vad import AudioPreprocessor
from audio.deepfake_infer import DeepFakeDetector
from audio.speaker_verify import SpeakerVerifier
from nlp.asr import ASRTranscriber
from nlp.keyword_rules import ScamLanguageDetector
from fusion.risk import RiskFusionEngine, SignalScores

app = FastAPI(title="CallShield AI", version="1.0.0")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Initialize components ----
config = get_config()
pnb = AudioPreprocessor(target_sr=config.TARGET_SR)

# Lazy-loaded components
deepfake_detector = None
speaker_verifier = None
transcriber = None
scam_detector = None
fusion_engine = None


def get_deepfake():
    global deepfake_detector
    if deepfake_detector is None:
        deepfake_detector = DeepFakeDetector()
    return deepfake_detector


def get_speaker():
    global speaker_verifier
    if speaker_verifier is None:
        speaker_verifier = SpeakerVerifier()
    return speaker_verifier


def get_transcriber():
    global transcriber
    if transcriber is None:
        transcriber = ASRTranscriber(model_name=config.WHISPER_MODEL)
    return transcriber


def get_scam_detector():
    global scam_detector
    if scam_detector is None:
        scam_detector = ScamLanguageDetector()
    return scam_detector


def get_fusion():
    global fusion_engine
    if fusion_engine is None:
        fusion_engine = RiskFusionEngine()
    return fusion_engine


# ---- Authentication token for enrolled speakers ----
ENROLLED_SPEAKERS: Dict[str, str] = {}  # speaker_id -> name


@app.get("/")
async def root():
    return {"message": "CallShield AI API", "version": config.APP_VERSION}


@app.get("/health")
async def health():
    return {"status": "ok", "models_loaded": all([deepfake_detector is not None])}


@app.post("/enroll-speaker")
async def enroll_speaker(speaker_id: str, name: str, audio: UploadFile = File(...)):
    """Enroll a speaker's voice for future verification."""
    try:
        temp_path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp_path.write(await audio.read())
        temp_path.close()

        audio_array, sr = pnb.load_audio(temp_path.name)
        audio_tensor = pnb.preprocess(audio_array)

        verifier = get_speaker()
        verifier.enroll_speaker(speaker_id, audio_tensor)
        ENROLLED_SPEAKERS[speaker_id] = name

        os.unlink(temp_path.name)
        return {"status": "enrolled", "speaker_id": speaker_id, "name": name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Enrollment failed: {str(e)}")


@app.post("/score-call")
async def score_call(call_id: str, enrolled_speaker_id: Optional[str] = None,
                    audio_path: Optional[str] = None,
                    language_hint: Optional[str] = "auto"):
    """Score a call for scam risk."""
    start_time = time.time()
    try:
        if audio_path and os.path.exists(audio_path):
            audio_array, sr = pnb.load_audio(audio_path)
        else:
            return {"error": "No audio provided or file not found"}

        audio_tensor = pnb.preprocess(audio_array)

        # 1. Deepfake detection
        df_detector = get_deepfake()
        deepfake_score = df_detector.score(audio_tensor, sr=16000)

        # 2. Speech-to-text
        transcriber = get_transcriber()
        # Save temp for ASR
        temp_path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        sf.write(temp_path.name, audio_array, 16000)
        asr_result = transcriber.transcribe(temp_path.name, language_hint)
        transcript = asr_result.get("text", "")
        detected_language = asr_result.get("language")
        os.unlink(temp_path.name)

        # 3. Scam language detection
        scam_det = get_scam_detector()
        scam_result = scam_det.score_text(transcript)
        scam_score = scam_result["scam_score"]
        matched_cues = scam_result["matched_cues"]

        # 4. Speaker verification
        verifier = get_speaker()
        identity_mismatch = 0.0
        if enrolled_speaker_id:
            identity_mismatch = verifier.get_identity_mismatch(enrolled_speaker_id, audio_tensor)

        # 5. Risk fusion
        fusion = get_fusion()
        scores = SignalScores(
            deepfake=deepfake_score,
            scam_language=scam_score,
            identity_mismatch=identity_mismatch,
            verification_failed=False,
            rule_bonus=min(len(matched_cues) * 0.05, 0.2)
        )
        result = fusion.fuse(scores)

        return {
            "call_id": call_id,
            "risk_score": result["risk_score"],
            "risk_band": result["risk_band"].value,
            "audio_deepfake_score": deepfake_score,
            "scam_language_score": scam_score,
            "identity_mismatch_score": identity_mismatch,
            "top_cues": matched_cues[:3] or result["top_cues"],
            "recommended_action": result["recommendation"],
            "transcript": transcript,
            "language_detected": detected_language,
            "processing_time_ms": round((time.time() - start_time) * 1000, 1)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Call scoring failed: {str(e)}")


# ---- WebSocket for real-time streaming ----

@app.websocket("/ws/analyze")
async def websocket_analyze(websocket: WebSocket):
    await websocket.accept()
    call_data = {"chunks": [], "transcript": "", "risk_history": []}
    prev_drift = 0

    try:
        while True:
            data = await websocket.receive_json()
            call_id = data.get("call_id")
            chunk_id = data.get("chunk_id")
            audio_b64 = data.get("audio_data")
            enrolled_id = data.get("enrolled_speaker_id")

            if not audio_b64:
                continue

            try:
                # Decode audio
                audio_bytes = base64.b64decode(audio_b64)
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    temp_path = f.name
                    f.write(audio_bytes)

                audio_array, sr = pnb.load_audio(temp_path)
                audio_tensor = pnb.preprocess(audio_array)
                os.unlink(temp_path)

                # Analyze this chunk
                df_detector = get_deepfake()
                deepfake_score = df_detector.score(audio_tensor, sr=16000)

                # Transcribe chunk
                tr = get_transcriber()
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    temp2 = f.name
                sf.write(temp2, audio_array, 16000)
                asr = tr.transcribe(temp2)
                os.unlink(temp2)
                chunk_text = asr.get("text", "")
                call_data["transcript"] += " " + chunk_text

                # Scam detection
                sc = get_scam_detector()
                scam_r = sc.score_text(chunk_text)

                # Identity
                im = 0.0
                if enrolled_id:
                    sv = get_speaker()
                    im = sv.get_identity_mismatch(enrolled_id, audio_tensor)

                # Fusion
                fusion = get_fusion()
                scores = SignalScores(
                    deepfake=deepfake_score,
                    scam_language=scam_r["scam_score"],
                    identity_mismatch=im,
                    verification_failed=False,
                    rule_bonus=min(len(scam_r["matched_cues"]) * 0.05, 0.2)
                )
                result = fusion.fuse(scores)

                # Send update
                await websocket.send_json({
                    "call_id": call_id,
                    "chunk_id": chunk_id,
                    "risk_score": result["risk_score"],
                    "risk_band": result["risk_band"].value,
                    "chunk_transcript": chunk_text,
                    "top_cues": scam_r["matched_cues"][:3],
                    "deepfake_score": deepfake_score,
                    "scam_score": scam_r["scam_score"],
                    "identity_mismatch": im
                })

            except Exception as e:
                await websocket.send_json({"error": str(e)})

    except WebSocketDisconnect:
        pass


def get_frontend_html() -> str:
    """Read and return the demo frontend HTML."""
    project_dir = Path(__file__).parent.parent
    html_path = project_dir / "frontend" / "index.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    return "<h1>CallShield AI</h1><p>Demo UI not found. Build the frontend first.</p>"


# Serve the frontend
@app.get("/demo", response_class=HTMLResponse)
async def demo_page():
    return get_frontend_html()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.HOST, port=config.PORT)

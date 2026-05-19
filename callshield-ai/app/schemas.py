from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class RiskBand(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CallRequest(BaseModel):
    call_id: str = Field(..., description="Unique call identifier")
    audio_path: Optional[str] = None
    enrolled_speaker_id: Optional[str] = None
    language_hint: Optional[str] = "auto"


class RiskResponse(BaseModel):
    call_id: str
    risk_score: float = Field(..., ge=0, le=100, description="Overall risk score 0-100")
    risk_band: RiskBand
    audio_deepfake_score: float = Field(..., ge=0, le=1)
    scam_language_score: float = Field(..., ge=0, le=1)
    identity_mismatch_score: float = Field(..., ge=0, le=1)
    verification_failure: bool = False
    top_cues: List[str] = []
    recommended_action: str
    transcript: Optional[str] = None
    language_detected: Optional[str] = None
    timestamp: float


class StreamChunk(BaseModel):
    call_id: str
    chunk_id: str
    audio_data: str  # base64-encoded audio chunk
    enrolled_speaker_id: Optional[str] = None

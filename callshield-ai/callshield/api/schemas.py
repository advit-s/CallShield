"""CallShield API Schemas (Pydantic models)."""

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any
from enum import Enum


class RiskBand(str, Enum):
    SAFE = "safe"
    SUSPICIOUS = "suspicious"
    HIGH = "high"
    CRITICAL = "critical"


class ScamType(str, Enum):
    FAMILY_EMERGENCY = "family_emergency"
    BANK_KYC_FRAUD = "bank_kyc_fraud"
    POLICE_LEGAL_THREAT = "police_legal_threat"
    TECH_SUPPORT_SCAM = "tech_support_scam"
    JOB_INVESTMENT_SCAM = "job_investment_scam"
    OTP_PIN_REQUEST = "otp_pin_request"
    UPI_PAYMENT_REQUEST = "upi_payment_request"
    REMOTE_ACCESS_REQUEST = "remote_access_request"
    SECRECY_PRESSURE = "secrecy_pressure"
    ALTERNATE_NUMBER_CLAIM = "alternate_number_claim"
    UNKNOWN = "unknown"


class TranscriptRequest(BaseModel):
    """POST /analyze-transcript request."""
    call_id: str = Field(..., description="Unique call identifier")
    user_id: Optional[str] = Field(None, description="User identifier for data management and Right to Erasure")
    transcript: str = Field(..., description="Call transcript text")
    language_hint: Optional[str] = Field("auto", description="Language hint: 'en', 'hi', 'hinglish' or 'auto'")
    enrolled_speaker_id: Optional[str] = Field(None, description="Optional enrolled speaker ID")
    audio_deepfake_score: Optional[float] = Field(0.0, ge=0, le=1, description="Pre-computed deepfake score (0-1)")


class AudioRequest(BaseModel):
    """POST /analyze-audio request."""
    call_id: str = Field(..., description="Unique call identifier")
    user_id: Optional[str] = Field(None, description="User identifier for data management")
    enrolled_speaker_id: Optional[str] = Field(None, description="Optional enrolled speaker ID")
    language_hint: Optional[str] = Field("auto", description="Language hint")


class ScoreCallRequest(BaseModel):
    """POST /score-call request."""
    call_id: str = Field(..., description="Unique call identifier")
    user_id: Optional[str] = Field(None, description="User identifier for data management")
    transcript: Optional[str] = Field(None, description="Call transcript (if already transcribed)")
    audio_path: Optional[str] = Field(None, description="Path to audio file (for batch/debugging)")
    deepfake_score: Optional[float] = Field(None, ge=0, le=1, description="Pre-computed deepfake score (0-1)")
    enrolled_speaker_id: Optional[str] = Field(None, description="Optional enrolled speaker ID")


class FeedbackRequest(BaseModel):
    """POST /submit-feedback request."""
    call_id: str = Field(..., description="Call identifier")
    is_scam: bool = Field(..., description="User's assessment: was this actually a scam?")
    feedback_notes: Optional[str] = Field(None, description="Optional user notes")
    reported_cues: Optional[List[str]] = Field([], description="User-reported scam cues")


class RiskResult(BaseModel):
    """Call analysis response with confidence and calibration."""
    model_config = ConfigDict(protected_namespaces=())

    call_id: str
    risk_score: float = Field(..., description="Risk score 0-100")
    risk_band: RiskBand
    # Confidence calibration
    confidence: str = Field("very_low", description="Confidence level: very_low, low, medium, high, very_high")
    confidence_score: float = Field(0.0, description="Confidence as a score (0-1)")
    warning_level: str = Field("none", description="none, soft, hard, critical")
    # Scam type
    scam_type: str = Field(..., description="Detected scam type or 'unknown'")
    scam_type_confidence: float = Field(..., description="Confidence in scam type (0-1)")
    # Explainability
    detected_cues: List[str] = Field(default_factory=list, description="Detected scam cues")
    explanation: str = Field(..., description="Human-readable explanation")
    recommended_action: str = Field(..., description="User-facing recommended action")
    why_flagged: str = Field("", description="User-facing: why this call was flagged")
    # Challenge-response
    challenges: List[Dict] = Field(default_factory=list, description="Safe verification challenges")
    # Raw components
    raw_components: Dict[str, Any] = Field(default_factory=dict, description="Raw signal scores")
    model_status: Dict[str, str] = Field(default_factory=dict, description="Which models ran")
    processing_time_ms: float = Field(..., description="API processing time in ms")
    timestamp: str


class SpeakerRequest(BaseModel):
    """POST /verify-speaker request."""
    speaker_id: str
    name: str
    consent_given: bool = Field(False, description="User explicitly consented to voice enrollment")


class SpeakerResponse(BaseModel):
    """POST /verify-speaker response."""
    status: str
    speaker_id: str
    name: str
    embedding_stored: bool


class CallSummaryResponse(BaseModel):
    """GET /call-summary/{call_id} response."""
    model_config = ConfigDict(protected_namespaces=())

    call_id: str
    risk_score: float
    risk_band: RiskBand
    scam_type: str
    detected_cues: List[str]
    explanation: str
    recommended_action: str
    raw_components: Dict[str, Any]
    model_status: Dict[str, str]
    final_risk_score: float
    final_risk_band: RiskBand
    final_cues: List[str]
    final_action: str
    total_chunks: int = 1


class HealthResponse(BaseModel):
    """GET /health response."""
    status: str
    version: str
    models_loaded: Dict[str, bool]
    uptime_seconds: int


class ModelStatusResponse(BaseModel):
    """GET /model-status response."""
    version: str
    release: str
    modules: Dict[str, Dict[str, str]]


class ChallengeRequest(BaseModel):
    """POST /challenge-response request."""
    risk_band: str
    scam_type: str = "unknown"
    risk_score: float = 0.0


class ChallengeResponse(BaseModel):
    """POST /challenge-response response."""
    question: str
    why: str
    type: str


class DataDeletionResponse(BaseModel):
    """DELETE /call-summary/:id response."""
    call_id: str
    status: str
    timestamp: str = ""


class UserDataDeletionResponse(BaseModel):
    """DELETE /user-data/:id response."""
    user_id: str
    deleted_calls: int
    status: str
    timestamp: str = ""


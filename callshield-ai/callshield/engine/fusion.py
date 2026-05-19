"""CallShield Risk Fusion Engine.

Product-grade risk scoring combining:
- 35% scam_language_score
- 25% deepfake_score
- 20% identity_mismatch_score
- 10% urgency_score
- 10% verification_failure_score
+ rule_bonus

Risk bands: safe (0-30), suspicious (31-60), high (61-80), critical (81-100).
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class RiskBand(str, Enum):
    SAFE = "safe"
    SUSPICIOUS = "suspicious"
    HIGH = "high"
    CRITICAL = "critical"

    @classmethod
    def from_score(cls, score: float) -> "RiskBand":
        if score >= 81:
            return cls.CRITICAL
        elif score >= 61:
            return cls.HIGH
        elif score >= 31:
            return cls.SUSPICIOUS
        else:
            return cls.SAFE


@dataclass
class SignalScores:
    """Individual signal scores for the fusion engine."""
    scam_language: float = 0.0
    deepfake: float = 0.0
    identity_mismatch: float = 0.0
    urgency: float = 0.0
    verification_failed: bool = False
    rule_bonus: float = 0.0

    def __post_init__(self):
        # Clamp all values to [0, 1]
        for attr in ["scam_language", "deepfake", "identity_mismatch", "urgency", "rule_bonus"]:
            val = getattr(self, attr)
            if val < 0:
                val = 0.0
            elif val > 1.0:
                val = 1.0
            setattr(self, attr, val)


@dataclass
class RiskResult:
    """Structured risk assessment result."""
    risk_score: float = 0.0
    risk_band: RiskBand = RiskBand.SAFE
    scam_type: str = "unknown"
    scam_type_confidence: float = 0.0
    detected_cues: List[str] = field(default_factory=list)
    explanation: str = ""
    recommended_action: str = ""
    raw_components: Dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class RiskFusionEngine:
    """Product-grade risk fusion engine.

    Weights (priority order):
    - Scam language: highest (35%) — intent matters more than voice
    - Deepfake: 25% — secondary confirmation
    - Identity mismatch: 20% — trusted profile deviation
    - Urgency: 10% — behavioral signal
    - Verification failure: 10% — challenge-response failure
    - Rule bonus: additive for multiple red flags
    """

    DEFAULT_WEIGHTS = {
        "scam_language": 0.35,
        "deepfake": 0.25,
        "identity_mismatch": 0.20,
        "urgency": 0.10,
        "verification_failure": 0.10,
    }

    BAND_LABELS = {
        RiskBand.SAFE: {
            "label": "SAFE",
            "explanation": "No scam signals detected. The call appears normal.",
            "action": "Continue the call normally. No action needed."
        },
        RiskBand.SUSPICIOUS: {
            "label": "SUSPICIOUS",
            "explanation": "Some unusual patterns detected in the conversation.",
            "action": "Be cautious. Consider asking a verification question. Do not share personal or financial information."
        },
        RiskBand.HIGH: {
            "label": "HIGH RISK",
            "explanation": "Likely scam call detected. Multiple red flags present.",
            "action": "Do not send money or share OTP/PIN/password. Hang up and verify independently."
        },
        RiskBand.CRITICAL: {
            "label": "CRITICAL SCAM",
            "explanation": "High-confidence scam detected. Urgent action needed.",
            "action": "HANG UP IMMEDIATELY. Do not share any information. Call back using a known number. Report this call."
        }
    }

    def __init__(self, weights: Optional[Dict[str, float]] = None,
                 enable_history: bool = True):
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        self.enable_history = enable_history
        self.history: List[Dict] = [] if enable_history else None  # type: ignore

    def score(self, signals: SignalScores, scam_type: str = "unknown",
              scam_type_confidence: float = 0.0,
              detected_cues: Optional[List[str]] = None) -> RiskResult:
        """Compute final risk score from signal scores."""
        # Base weighted score
        verify_penalty = 1.0 if signals.verification_failed else 0.0

        raw = (
            self.weights.get("scam_language", 0.35) * signals.scam_language +
            self.weights.get("deepfake", 0.25) * signals.deepfake +
            self.weights.get("identity_mismatch", 0.20) * signals.identity_mismatch +
            self.weights.get("urgency", 0.10) * signals.urgency +
            self.weights.get("verification_failure", 0.10) * verify_penalty +
            signals.rule_bonus
        )

        risk = max(0.0, min(raw, 1.0))
        risk_100 = risk * 100.0

        band = RiskBand.from_score(risk_100)
        band_info = self.BAND_LABELS[band]

        explanation = self._build_explanation(signals, band, band_info["explanation"])
        action = self._build_recommendation(signals, band, band_info["action"])
        cues = detected_cues or self._derive_cues(signals)

        result = RiskResult(
            risk_score=round(risk_100, 1),
            risk_band=band,
            scam_type=scam_type,
            scam_type_confidence=scam_type_confidence,
            detected_cues=cues,
            explanation=explanation,
            recommended_action=action,
            raw_components={
                "scam_language": round(signals.scam_language, 3),
                "deepfake": round(signals.deepfake, 3),
                "identity_mismatch": round(signals.identity_mismatch, 3),
                "urgency": round(signals.urgency, 3),
                "verification_failed": signals.verification_failed,
                "rule_bonus": round(signals.rule_bonus, 3),
                "weights": self.weights,
            }
        )

        if self.enable_history:
            self.history.append({
                "timestamp": datetime.now().isoformat(),
                "risk_score": result.risk_score,
                "risk_band": band.value,
                "signals": {
                    "scam_language": signals.scam_language,
                    "deepfake": signals.deepfake,
                    "identity_mismatch": signals.identity_mismatch,
                    "urgency": signals.urgency,
                    "verification_failed": signals.verification_failed,
                }
            })

        return result

    def _build_explanation(self, signals: SignalScores, band: RiskBand,
                           base_explanation: str) -> str:
        """Build human-readable explanation of what's happening."""
        parts = [base_explanation]
        reasons = []

        if signals.scam_language > 0.5:
            reasons.append("scam language")
        if signals.deepfake > 0.5:
            reasons.append("synthetic voice")
        if signals.identity_mismatch > 0.5:
            reasons.append("voice identity mismatch")
        if signals.urgency > 0.5:
            reasons.append("excessive urgency")
        if signals.verification_failed:
            reasons.append("verification challenge failed")

        if reasons and band != RiskBand.SAFE:
            parts.append(f"Triggered by: {', '.join(reasons)}.")

        return " ".join(parts)

    def _build_recommendation(self, signals: SignalScores, band: RiskBand,
                              base_action: str) -> str:
        """Build actionable recommendation."""
        return base_action

    def _derive_cues(self, signals: SignalScores) -> List[str]:
        """Derive top cues from signal scores."""
        cues = []
        if signals.scam_language > 0.5:
            cues.append("Suspicious scam language detected")
        if signals.deepfake > 0.5:
            cues.append("Synthetic voice detected")
        if signals.identity_mismatch > 0.5:
            cues.append("Voice doesn't match trusted profile")
        if signals.urgency > 0.5:
            cues.append("Excessive urgency/pressure")
        if signals.verification_failed:
            cues.append("Failed verification challenge")
        if signals.rule_bonus > 0.15:
            cues.append("Multiple red flags detected")
        return cues or ["No scam signals detected"]

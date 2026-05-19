from typing import Dict, List, Optional
import time
from dataclasses import dataclass
from enum import Enum


class RiskBand(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class SignalScores:
    deepfake: float = 0.0  # probability
    scam_language: float = 0.0  # probability
    identity_mismatch: float = 0.0  # probability
    verification_failed: bool = False
    rule_bonus: float = 0.0


class RiskFusionEngine:
    """Fusion engine combining three signals into a unified risk score."""

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        default_weights = {
            "deepfake": 0.40,
            "scam_language": 0.30,
            "identity_mismatch": 0.20,
            "verification": 0.10
        }
        self.weights = weights or default_weights
        self.history = []  # For tracking score changes

    def fuse(self, scores: SignalScores,
             min_threshold: float = 35.0,
             max_threshold: float = 65.0) -> Dict:
        """Combine signal scores into a unified risk score."""
        verify_penalty = 1.0 if scores.verification_failed else 0.0

        raw = (
            self.weights.get("deepfake", 0.40) * scores.deepfake +
            self.weights.get("scam_language", 0.30) * scores.scam_language +
            self.weights.get("identity_mismatch", 0.20) * scores.identity_mismatch +
            self.weights.get("verification", 0.10) * verify_penalty +
            scores.rule_bonus
        )

        risk = max(0.0, min(raw, 1.0))
        risk_100 = risk * 100

        if risk_100 >= max_threshold:
            band = RiskBand.HIGH
        elif risk_100 >= min_threshold:
            band = RiskBand.MEDIUM
        else:
            band = RiskBand.LOW

        self.history.append({
            "timestamp": time.time(),
            "risk": risk,
            "scores": scores
        })

        # Build top cues based on signals firing
        top_cues = []
        if scores.deepfake > 0.6:
            top_cues.append("AI-generated voice detected")
        if scores.scam_language > 0.5:
            top_cues.append("Suspicious scam language")
        if scores.identity_mismatch > 0.5:
            top_cues.append("Voice doesn't match enrolled profile")
        if scores.verification_failed:
            top_cues.append("Failed identity verification prompt")

        return {
            "risk_score": round(risk_100, 1),
            "risk_band": band,
            "raw_components": {
                "deepfake": round(scores.deepfake, 3),
                "scam_language": round(scores.scam_language, 3),
                "identity_mismatch": round(scores.identity_mismatch, 3),
                "verification_failed": scores.verification_failed,
                "rule_bonus": round(scores.rule_bonus, 3)
            },
            "top_cues": top_cues or ["No high-risk signals detected"],
            "recommendation": self._recommendation(band, scores)
        }

    def _recommendation(self, band: RiskBand, scores: SignalScores) -> str:
        """Generate human-readable recommendation."""
        if band == RiskBand.LOW:
            return "This call appears safe. Continue normally."
        elif band == RiskBand.MEDIUM:
            return "Warning: Unusual patterns detected. Proceed with caution. Recommended: Ask a verification question."
        else:
            reasons = []
            if scores.deepfake > 0.5:
                reasons.append("synthetic voice")
            if scores.scam_language > 0.5:
                reasons.append("scam language")
            if scores.identity_mismatch > 0.5:
                reasons.append("identity mismatch")
            reason_str = ", ".join(reasons) if reasons else "multiple red flags"
            return f"HIGH RISK ({reason_str}). Hang up and call back their known number. Do not transfer money or share personal details."

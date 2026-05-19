"""CallShield Python SDK v2.1 (Trust & Calibration).

B2B-ready SDK with confidence levels, two-tier warnings,
and challenge-response verification.

Usage:
    from callshield.sdk import CallShieldSDK
    sdk = CallShieldSDK()
    result = sdk.analyze_transcript("Mera phone dead hai, abhi ₹25,000 bhejo")
    print(f"Risk: {result.risk_score}/100 ({result.risk_band})")
"""

from typing import Optional, Dict, List
from dataclasses import dataclass, field

from callshield.engine.scam_nlp import ScamLanguageEngine
from callshield.engine.fusion import RiskFusionEngine, SignalScores
from callshield.engine.calibration import CalibrationEngine
from callshield.engine.challenge import ChallengeGenerator
from callshield.engine.privacy import PrivacyLayer


@dataclass
class CallShieldResult:
    """SDK result object with v2.1 confidence and calibration."""
    risk_score: float = 0.0
    risk_band: str = "safe"
    confidence: str = "very_low"
    confidence_score: float = 0.0
    warning_level: str = "none"
    scam_type: str = "unknown"
    scam_type_confidence: float = 0.0
    detected_cues: List[str] = field(default_factory=list)
    explanation: str = ""
    recommended_action: str = ""
    why_flagged: str = ""
    model_status: Dict[str, str] = field(default_factory=dict)
    raw_components: Dict = field(default_factory=dict)
    challenges: List[Dict] = field(default_factory=list)


class CallShieldSDK:
    """v2.1 SDK - Trust & Calibration Release."""

    MODEL_STATUS = {
        "scam_nlp": "implemented",
        "fusion": "implemented",
        "calibration": "implemented",
        "challenge": "implemented",
        "privacy": "implemented",
        "asr": "implemented",
        "deepfake": "placeholder",
        "speaker_verification": "placeholder",
    }

    def __init__(self, custom_weights: Optional[Dict[str, float]] = None):
        self.scam_engine = ScamLanguageEngine()
        self.fusion = RiskFusionEngine(weights=custom_weights)
        self.calibration = CalibrationEngine()
        self.challenge = ChallengeGenerator()
        self.privacy = PrivacyLayer()

    def analyze_transcript(self, text: str,
                           speaker_id: Optional[str] = None,
                           audio_deepfake_score: float = 0.0,
                           identity_mismatch: float = 0.0) -> CallShieldResult:
        """Analyze a transcript with full calibration and challenge-response."""
        # 1. Analyze scam language
        analysis = self.scam_engine.analyze(text)

        # 2. Build signal scores
        signals = SignalScores(
            scam_language=analysis.scam_score,
            deepfake=audio_deepfake_score,
            identity_mismatch=identity_mismatch,
            urgency=analysis.urgency_score,
            verification_failed=False,
            rule_bonus=min(len(analysis.detected_cues) * 0.03, 0.15)
        )

        # 3. Risk fusion
        result = self.fusion.score(
            signals,
            scam_type=analysis.scam_type.value,
            scam_type_confidence=analysis.scam_type_confidence,
            detected_cues=analysis.detected_cues
        )

        # 4. Calibration
        scam_analysis_dict = {
            "category_scores": analysis.category_scores,
            "matched_patterns": analysis.matched_patterns,
            "urgency_score": analysis.urgency_score,
        }
        calibrated = self.calibration.calibrate(
            risk_score=result["risk_score"],
            band=result["risk_band"].value,
            scam_analysis=scam_analysis_dict,
            detected_cues=result["top_cues"]
        )

        # 5. Generate challenges
        challenges = self.challenge.generate(
            calibrated.risk_band,
            analysis.scam_type.value,
            result["risk_score"]
        )

        # 6. Build "why this was flagged"
        why = self._explain_why(analysis, calibrated)

        return CallShieldResult(
            risk_score=result["risk_score"],
            risk_band=calibrated.risk_band,
            confidence=calibrated.confidence_level.value,
            confidence_score=calibrated.confidence_score,
            warning_level=calibrated.warning_level.value,
            scam_type=result["scam_type"],
            scam_type_confidence=result["scam_type_confidence"],
            detected_cues=result["top_cues"],
            explanation=calibrated.explanation,
            recommended_action=calibrated.action,
            why_flagged=why,
            model_status=self.MODEL_STATUS,
            raw_components=result["raw_components"],
            challenges=[{"question": c.question, "why": c.why, "type": c.expected_type}
                        for c in challenges]
        )

    def _explain_why(self, analysis, calibrated) -> str:
        """Build user-facing 'why this was flagged' explanation."""
        cues = analysis.detected_cues[:3]
        if not cues:
            return "No scam signals detected."

        lines = []
        for cue in cues:
            if "family_emergency" in cue:
                lines.append("Caller mentions an emergency while calling from a new number.")
            elif "alternate_number" in cue:
                lines.append("Caller claims to be calling from an alternate or new phone.")
            elif "secrecy" in cue:
                lines.append("Caller urges you to keep the call secret.")
            elif "upi" in cue or "payment" in cue:
                lines.append("Caller is asking for money transfer via UPI or similar.")
            elif "otp" in cue or "pin" in cue or "cvv" in cue:
                lines.append("Caller requests sensitive payment credentials.")
            elif "urgency" in cue:
                lines.append("Caller creates a sense of urgency to pressure you.")
            elif "bank" in cue:
                lines.append("Caller claims to be from a bank and asks for details.")
            elif "police" in cue or "arrest" in cue:
                lines.append("Caller uses police or legal threats to create fear.")

        if not lines:
            lines.append("Multiple suspicious cues detected in the conversation.")

        if calibrated.signal_diversity >= 2:
            lines.append(f"Multiple independent risk factors ({calibrated.signal_diversity} signals).")

        return " ".join(lines)

    def quick_check(self, text: str) -> bool:
        return self.analyze_transcript(text).risk_score >= 31

    def get_history(self) -> List[Dict]:
        return self.fusion.history or []

    def hash_phone(self, phone: str) -> str:
        return self.privacy.hash_phone(phone)

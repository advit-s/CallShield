"""CallShield Python SDK v2.4.0 (Mobile ASR and Scam NLP Hardening).

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
from callshield.engine.deepfake import DeepFakeDetector


@dataclass
class CallShieldResult:
    """SDK result object with confidence and calibration."""
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
    audio_analysis: Dict = field(default_factory=dict)


class CallShieldSDK:
    """v2.4.0 SDK - Mobile ASR and Scam NLP Hardening."""

    def __init__(self, 
                 custom_weights: Optional[Dict[str, float]] = None,
                 deepfake_model_path: Optional[str] = None):
        self.scam_engine = ScamLanguageEngine()
        self.fusion = RiskFusionEngine(weights=custom_weights)
        self.calibration = CalibrationEngine()
        self.challenge = ChallengeGenerator()
        self.privacy = PrivacyLayer()
        self.deepfake_detector = DeepFakeDetector(model_path=deepfake_model_path)
        self.asr_available = self._is_asr_available()

    def _is_asr_available(self) -> bool:
        """Return whether at least one optional ASR backend is importable."""
        try:
            from callshield.engine.asr import pipeline, whisper
        except Exception:
            return False
        return whisper is not None or pipeline is not None

    def get_model_status(self) -> Dict[str, str]:
        """Return live module status without overstating untrained models."""
        return {
            "scam_nlp": "implemented",
            "fusion": "implemented",
            "calibration": "implemented",
            "challenge": "implemented",
            "privacy": "implemented",
            "asr": "available" if self.asr_available else "unavailable",
            "deepfake": self.deepfake_detector.model_status,
            "speaker_verification": "placeholder",
        }

    def analyze_audio(self, audio_path: str, transcript: str, 
                      speaker_id: Optional[str] = None) -> CallShieldResult:
        """Perform combined audio and text analysis."""
        # 1. Run deepfake detection
        audio_result = self.deepfake_detector.detect(audio_path)
        text_analysis = self.scam_engine.analyze(transcript or "")
        audio_can_support_fusion = (
            bool((transcript or "").strip())
            and (
                text_analysis.scam_score >= 0.20
                or text_analysis.urgency_score > 0.0
                or bool(text_analysis.detected_cues)
            )
        )
        deepfake_score = (
            audio_result.get("fusion_deepfake_score", audio_result.get("deepfake_score"))
            if (
                audio_can_support_fusion
                and audio_result.get("used_in_fusion")
                and audio_result.get("deepfake_score") is not None
            )
            else 0.0
        )
        if audio_result.get("used_in_fusion") and not audio_can_support_fusion:
            audio_result = {
                **audio_result,
                "fusion_deepfake_score": 0.0,
                "used_in_fusion": False,
                "fusion_gate": "held_for_text_corroboration",
                "note": (
                    "Deepfake evidence shown but not fused because transcript "
                    "has no scam-like language or urgency."
                ),
            }
        
        # 2. Run standard analysis with audio signal
        result = self.analyze_transcript(
            text=transcript,
            speaker_id=speaker_id,
            audio_deepfake_score=deepfake_score
        )
        
        # 3. Inject audio analysis details
        result.audio_analysis = audio_result
        if (
            audio_result.get("used_in_fusion")
            and audio_result.get("audio_signal_strength") == "strong"
            and result.risk_band != "safe"
        ):
            result.why_flagged += " Possible synthetic or cloned voice detected."
            
        return result

    def analyze_transcript(self, text: str,
                           speaker_id: Optional[str] = None,
                           audio_deepfake_score: float = 0.0,
                           identity_mismatch: float = 0.0) -> CallShieldResult:
        """Analyze a transcript with full calibration and challenge-response."""
        # 1. Analyze scam language
        analysis = self.scam_engine.analyze(text)

        # 2. Build signal scores
        # More aggressive rule bonus for strong scam indicators.
        bonus = min(len(analysis.detected_cues) * 0.05, 0.25)
        if analysis.scam_score > 0.8:
            bonus += 0.15  # Extra boost for high-confidence language matches
            
        signals = SignalScores(
            scam_language=analysis.scam_score,
            deepfake=audio_deepfake_score,
            identity_mismatch=identity_mismatch,
            urgency=analysis.urgency_score,
            verification_failed=False,
            rule_bonus=min(bonus, 0.4)
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
            risk_score=result.risk_score,
            band=result.risk_band.value,
            scam_analysis=scam_analysis_dict,
            detected_cues=result.detected_cues
        )

        # 5. Generate challenges
        challenges = self.challenge.generate(
            calibrated.risk_band,
            analysis.scam_type.value,
            result.risk_score
        )

        # 6. Build "why this was flagged"
        why = self._explain_why(analysis, calibrated)

        return CallShieldResult(
            risk_score=result.risk_score,
            risk_band=calibrated.risk_band,
            confidence=calibrated.confidence_level.value,
            confidence_score=calibrated.confidence_score,
            warning_level=calibrated.warning_level.value,
            scam_type=result.scam_type,
            scam_type_confidence=result.scam_type_confidence,
            detected_cues=result.detected_cues,
            explanation=calibrated.explanation,
            recommended_action=calibrated.action,
            why_flagged=why,
            model_status=self.get_model_status(),
            raw_components=result.raw_components,
            challenges=[
                {"question": c.question, "why": c.why, "type": c.expected_type}
                for c in challenges
            ]
        )

    def _explain_why(self, analysis, calibrated) -> str:
        """Build user-facing 'why this was flagged' explanation."""
        if calibrated.risk_band == "safe":
            return "No scam signals detected."

        cues = analysis.detected_cues[:3]
        if not cues:
            return "No scam signals detected."

        lines = []
        seen = set()
        for cue in cues:
            if "family_emergency" in cue:
                reason = "Caller mentions an emergency while calling from a new number."
            elif "alternate_number" in cue:
                reason = "Caller claims to be calling from an alternate or new phone."
            elif "secrecy" in cue:
                reason = "Caller urges you to keep the call secret."
            elif "upi" in cue or "payment" in cue:
                reason = "Caller is asking for money transfer via UPI or similar."
            elif "otp" in cue or "pin" in cue or "cvv" in cue:
                reason = "Caller requests sensitive payment credentials."
            elif "urgency" in cue:
                reason = "Caller creates a sense of urgency to pressure you."
            elif "bank" in cue:
                reason = "Caller claims to be from a bank and asks for details."
            elif "police" in cue or "arrest" in cue:
                reason = "Caller uses police or legal threats to create fear."
            elif "remote_access" in cue:
                reason = "Caller asks for remote access or screen sharing."
            else:
                reason = None

            if reason and reason not in seen:
                lines.append(reason)
                seen.add(reason)

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

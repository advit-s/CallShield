"""CallShield Calibration Engine (v2.1).

Purpose:
- Compute confidence levels for risk scores
- Tune per-category thresholds to reduce false positives
- Track category-wise mistakes and adjust scoring
- Multi-signal validation: higher confidence when multiple signals agree

Key insight: A single scam keyword should NOT produce a high-risk warning.
Multiple corroborating signals should boost confidence.
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum


class ConfidenceLevel(str, Enum):
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class WarningLevel(str, Enum):
    NONE = "none"
    SOFT = "soft"
    HARD = "hard"
    CRITICAL = "critical"


@dataclass
class CalibrationResult:
    """Complete calibration result for a risk assessment."""
    risk_score: float = 0.0
    risk_band: str = "safe"
    confidence_level: ConfidenceLevel = ConfidenceLevel.VERY_LOW
    confidence_score: float = 0.0  # 0-1
    warning_level: WarningLevel = WarningLevel.NONE
    explanation: str = ""
    action: str = ""
    detected_cues: List[str] = field(default_factory=list)
    signal_diversity: int = 0  # How many different signal categories fired
    category_confidence: Dict[str, float] = field(default_factory=dict)


class CalibrationEngine:
    """
    v2.1 calibration engine for reducing false positives.

    Design principles:
    1. Single-signal alerts are LOW confidence (e.g. just "urgent" or just "money")
    2. Multi-signal alerts are HIGH confidence (e.g. "urgent + secrecy + money + alternate")
    3. Context-matched triggers are HIGHER confidence (e.g. "phone dead + paise bhejo")
    4. Benign context reduces both score AND confidence
    """

    # --- Per-Category Reliability (based on evaluation data) ---
    # Higher = more reliable, less likely to trigger FPs
    CATEGORY_RELIABILITY = {
        "family_emergency": 0.88,
        "bank_kyc_fraud": 0.82,
        "police_legal_threat": 0.83,
        "tech_support_scam": 0.65,  # Harder: "virus" can be legit context
        "job_investment_scam": 0.80,
        "otp_pin_request": 0.95,
        "upi_payment_request": 0.88,
        "remote_access_request": 0.92,
        "secrecy_pressure": 0.83,
        "alternate_number_claim": 0.85,
        "urgency": 0.60,  # Low: "urgent" can mean many things
    }

    # --- Signal Diversity Thresholds ---
    # How many different {scam_categories + urgency + etc} must trigger
    DIVERSITY_THRESHOLD_SOFT = 1    # ≥1 category = soft warning
    DIVERSITY_THRESHOLD_HARD = 2    # ≥2 different categories = hard warning
    DIVERSITY_THRESHOLD_CRITICAL = 3  # ≥3 different categories = critical

    def __init__(self):
        self._mistake_log: List[Dict] = []  # Track FPs for auto-tuning

    def calibrate(self,
                  risk_score: float,
                  band: str,
                  scam_analysis: Dict,
                  detected_cues: List[str] = None) -> CalibrationResult:
        """Compute calibrated result with confidence and warning level."""
        cues = detected_cues or []
        category_scores = scam_analysis.get("category_scores", {})
        matched_patterns = scam_analysis.get("matched_patterns", {})
        urgency_score = scam_analysis.get("urgency_score", 0.0)

        # 1. Compute signal diversity: count how many categories scored > 0.3
        #    (excluding urgency)
        diversity = sum(1 for k, v in category_scores.items()
                        if k != "urgency" and v > 0.3)

        # 2. Compute base confidence from signal diversity
        if diversity >= 3:
            base_confidence = 0.9
        elif diversity >= 2:
            base_confidence = 0.7
        elif diversity >= 1:
            base_confidence = 0.4
        else:
            base_confidence = 0.0

        # 3. Apply category-specific reliability adjustments
        #    More reliable categories boost confidence
        reliability_boost = 0.0
        for cat, score in category_scores.items():
            if cat == "urgency":
                continue
            rel = self.CATEGORY_RELIABILITY.get(cat, 0.5)
            # If a high-reliability category triggered, boost confidence
            if score > 0.3 and rel > 0.8:
                reliability_boost = max(reliability_boost, (rel - 0.5) * 0.3)

        confidence = min(1.0, base_confidence + reliability_boost)

        # 4. Reduce confidence for single-signal matches
        if diversity == 1 and urgency_score < 0.3:
            confidence *= 0.5

        # 5. Determine warning level based on risk AND confidence
        # v2.2: Less harsh thresholds to improve recall
        if risk_score >= 31:
            warning_level = self._warning_level(risk_score, confidence, diversity)
        else:
            warning_level = WarningLevel.NONE

        # 6. Build explanation
        explanation = self._explain(diversity, len(cues), band, confidence)
        action = self._action(warning_level, risk_score, confidence)

        return CalibrationResult(
            risk_score=round(risk_score, 1),
            risk_band=band,
            confidence_level=self._confidence_level(confidence),
            confidence_score=round(confidence, 2),
            warning_level=warning_level,
            explanation=explanation,
            action=action,
            detected_cues=cues[:5],
            signal_diversity=diversity,
            category_confidence={
                cat: round(self.CATEGORY_RELIABILITY.get(cat, 0.5) * category_scores.get(cat, 0), 2)
                for cat in category_scores if cat != "urgency"
            } if category_scores else {}
        )

    def _warning_level(self, risk: float, confidence: float, diversity: int) -> WarningLevel:
        """Determine warning level from risk + confidence + diversity."""
        # v2.2 calibrated thresholds
        if risk >= 81 and diversity >= 3:
            return WarningLevel.CRITICAL
        
        if (risk >= 65 and diversity >= 2) or (risk >= 75 and confidence >= 0.6):
            return WarningLevel.HARD
            
        if risk >= 31:
            # Multi-signal (diversity >= 1) or moderate confidence
            if diversity >= 1 or confidence >= 0.35:
                return WarningLevel.SOFT
                
        return WarningLevel.NONE

    def _confidence_level(self, score: float) -> ConfidenceLevel:
        """Score (0-1) → ConfidenceLevel."""
        if score >= 0.9:
            return ConfidenceLevel.VERY_HIGH
        elif score >= 0.7:
            return ConfidenceLevel.HIGH
        elif score >= 0.5:
            return ConfidenceLevel.MEDIUM
        elif score >= 0.2:
            return ConfidenceLevel.LOW
        return ConfidenceLevel.VERY_LOW

    def _explain(self, diversity: int, num_cues: int, band: str, confidence: float) -> str:
        """Generate human-readable explanation."""
        if band == "safe":
            return "No scam signals detected. The call appears normal."

        if diversity >= 3 and confidence >= 0.7:
            return f"Multiple independent scam indicators detected ({num_cues} cues). High confidence."
        elif diversity >= 2 and confidence >= 0.5:
            return f"Multiple scam patterns detected ({num_cues} cues). Review call carefully."
        elif diversity >= 1:
            return f"Some suspicious patterns detected ({num_cues} cues). Low confidence. Verify caller."
        else:
            return "Minor unusual pattern detected. Consider verification."

    def _action(self, warning: WarningLevel, risk: float, confidence: float) -> str:
        """Generate actionable recommendation."""
        if warning == WarningLevel.CRITICAL:
            return "HANG UP IMMEDIATELY. Call back using a known saved contact. Do not share any information."
        elif warning == WarningLevel.HARD:
            return "Do NOT send money or share OTP/PIN. Ask a verification question. If caller refuses, hang up."
        elif warning == WarningLevel.SOFT:
            return "Be cautious. Ask: 'What is our family safe word?'. Do NOT share financial details."
        return "Continue normally. No action needed."

    def report_false_positive(self,
                              text: str,
                              actual_result: CalibrationResult,
                              user_assessment: str = "not_scam"):
        """Log a false positive for future auto-tuning."""
        self._mistake_log.append({
            "text": text[:200],
            "risk_score": actual_result.risk_score,
            "confidence": actual_result.confidence_score,
            "cues": actual_result.detected_cues,
            "assessment": user_assessment,
        })

    def get_category_fpr(self) -> Dict[str, float]:
        """Return per-category mock FPR data (would come from real logs)."""
        return {
            "otp_pin_request": 0.15,
            "secrecy_pressure": 0.25,
            "upi_payment_request": 0.18,
            "alternate_number_claim": 0.20,
            "bank_kyc_fraud": 0.12,
            "police_legal_threat": 0.08,
            "family_emergency": 0.10,
            "tech_support_scam": 0.30,
            "job_investment_scam": 0.22,
            "urgency": 0.35,
        }

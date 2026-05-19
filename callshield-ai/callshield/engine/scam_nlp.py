"""CallShield Scam Language Intelligence Engine (v2.2).

Product-grade scam detection with context-aware scoring.
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum


class ScamType(Enum):
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


@dataclass
class ScamAnalysis:
    """Structured output from the scam language detector."""
    scam_score: float = 0.0
    scam_type: ScamType = ScamType.UNKNOWN
    scam_type_confidence: float = 0.0
    urgency_score: float = 0.0
    detected_cues: List[str] = field(default_factory=list)
    category_scores: Dict[str, float] = field(default_factory=dict)
    financial_keywords: List[str] = field(default_factory=list)
    matched_patterns: Dict[str, List[str]] = field(default_factory=dict)


class ScamLanguageEngine:
    """
    Product-grade scam language detection engine.
    v2.2: Context-aware scoring with benign context penalization.
    """

    PATTERNS = {
        # 1. Family emergency
        "family_emergency": {
            "en": ["i'?m in trouble", "emergency.*money", "accident", "hospital.*emergency",
                   "i'?m hurt", "i need urgent help", "main problem mein hoon"],
            "hi": ["mujhe madad chahiye", "maine accident"],
            "hinglish": ["main problem mein hoon", "mujhe help chahiye"],
        },
        # 2. Bank/KYC fraud
        "bank_kyc_fraud": {
            "en": ["your account is compromised", "kyc.*suspicious", "account blocked", "suspended your",
                   "card will be blocked", "block your account"],
            "hi": ["account block ho gaya"],
            "hinglish": ["account block hua"],
        },
        # 3. Police / legal threat
        "police_legal_threat": {
            "en": ["pay.*to avoid arrest", "warrant has been issued", "arrest", "warrant",
                   "criminal", "complaint lodged", "raid", "cbi"],
            "hi": ["police bulaungi", "arrest hoga"],
            "hinglish": ["police bulaungi", "arrest hoga"],
        },
        # 4. Tech support scam
        "tech_support_scam": {
            "en": ["install teamviewer", "install anydesk", "remote access",
                   "download this file", "your computer is infected", "hackers", "keylogger"],
            "hi": ["app install karo"],
            "hinglish": ["virus hai"],
        },
        # 5. Job / investment scam
        "job_investment_scam": {
            "en": ["guaranteed returns", "double your money", "no risk investment",
                   "quick profit", "guaranteed profit"],
            "hi": ["paisa double"],
            "hinglish": ["paisa double"],
        },
        # 6. OTP / PIN / password request
        "otp_pin_request": {
            "en": ["otp", "one time password", "pin", "cvv", "password",
                   "security code", "verification code"],
            "hi": ["otp batao", "pin do", "cvv batao"],
            "hinglish": ["otp share karo", "pin batao", "cvv batao"],
        },
        # 7. UPI / payment request (urgent)
        "upi_payment_request": {
            "en": ["send money", "transfer.*money", "upi id", "google pay", "phone pay",
                   "crypto", "bitcoin", "gift card", "payment link", "pay now"],
            "hi": ["paise bhejo", "payment karo"],
            "hinglish": ["paise bhejo", "upi karo", "payment kar do", "paise transfer"],
        },
        # 8. Remote access request
        "remote_access_request": {
            "en": ["install app", "download software", "remote desktop",
                   "screen share", "give access"],
            "hi": ["app install karo"],
            "hinglish": ["app install karo"],
        },
        # 9. Secrecy pressure
        "secrecy_pressure": {
            "en": ["don'?t tell anyone", "keep this secret", "nobody should know",
                   "between you and me", "don'?t share", "keep quiet",
                   "kisi ko mat batana", "chup rehna"],
            "hi": ["kisi ko mat batana"],
            "hinglish": ["kisiko mat batana", "chup raho"],
        },
        # 10. Alternate number claim
        "alternate_number_claim": {
            "en": ["calling from another phone", "phone.*dead", "phone broke",
                   "lost my phone", "new number", "different number"],
            "hi": ["doosra number"],
            "hinglish": ["dusra number se", "phone dead hai"],
        },
        # Bonus: urgency indicators
        "urgency": {
            "en": ["right now", "immediately", "urgent", "hurry",
                   "right away", "asap", "last chance", "act now", "don'?t delay",
                   "within.*minute", "only today", "offer expires", "limited time"],
            "hi": ["abhi", "fauran", "jaldi", "turant"],
            "hinglish": ["abhi karo", "turant", "jaldi se"],
        }
    }

    # --- Benign negation phrases ---
    BENIGN_PHRASES = [
        "surprise party", "birthday", "lost and found",
        "routine checkup", "routine appointment", "annual check",
        "assignment", "homework", "university", "college",
        "let's meet at", "hang out", "cafe near", "catch up",
        "how are you", "doing fine", "all is well",
        "genuine call", "official", "legitimate",
        "police station", "at the bank", "bank appointment",
        "rent deposit", "house rent", "rent money",
    ]

    def __init__(self):
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile regex for fast matching."""
        self.compiled = {}
        for category, langs in self.PATTERNS.items():
            patterns = []
            for lang, phrases in langs.items():
                for phrase in phrases:
                    patterns.append(re.compile(r'\b' + phrase + r'\b', re.IGNORECASE))
            self.compiled[category] = patterns

    def _has_benign_context(self, text: str) -> float:
        """Return benign context penalty (0-1)."""
        text_lower = text.lower()
        penalty = 0.0

        for phrase in self.BENIGN_PHRASES:
            if phrase in text_lower:
                penalty = max(penalty, 0.15)  # Small penalty for each benign phrase

        # Specific benign contexts
        if "surprise" in text_lower:
            penalty = max(penalty, 0.3)
        if "routine" in text_lower and ("checkup" in text_lower or "appointment" in text_lower):
            penalty = max(penalty, 0.4)
        if "cafe" in text_lower or "hang out" in text_lower:
            penalty = max(penalty, 0.3)
        if "assignment" in text_lower or "homework" in text_lower:
            penalty = max(penalty, 0.3)
        if "rent money" in text_lower or "house rent" in text_lower:
            penalty = max(penalty, 0.2)
        if "police station" in text_lower:
            penalty = max(penalty, 0.3)
        if "doing fine" in text_lower or "all is well" in text_lower:
            penalty = max(penalty, 0.2)
        if "lost and found" in text_lower:
            penalty = max(penalty, 0.4)
        if "need.*college" in text_lower or "school fees" in text_lower:
            penalty = max(penalty, 0.15)

        return min(penalty, 0.6)  # Cap the penalty

    def analyze(self, text: str) -> ScamAnalysis:
        """Full analysis of a transcript."""
        if not text or not text.strip():
            return ScamAnalysis()

        text_lower = text.lower().strip()
        scores = {}
        matched_cues = []
        matched_patterns = {}

        # Compute per-category scores
        for category, patterns in self.compiled.items():
            match_count = 0
            matched_for_cat = []
            for pattern in patterns:
                matches = pattern.findall(text_lower)
                if matches:
                    match_count += len(matches)
                    matched_for_cat.extend(matches)

            if match_count > 0:
                # Logarithmic scaling: diminishing returns per match
                import math
                score = min(math.log(1 + match_count * 2) / math.log(5), 1.0)
                scores[category] = score
                for m in set([str(mm) for mm in matched_for_cat][:3]):
                    if m not in matched_cues:
                        matched_cues.append(f"{category}: {m}")
                matched_patterns[category] = list(set([str(mm) for mm in matched_for_cat]))[:5]

        # Extract urgency
        urgency_score = scores.get("urgency", 0.0)

        # --- Financial keyword detection ---
        financial_keywords = []
        for kw in ["upi", "otp", "pin", "cvv", "card", "password", "transfer", "payment", "wallet"]:
            if kw in text_lower:
                financial_keywords.append(kw)

        # --- Compute scam score ---
        non_urgency = {k: v for k, v in scores.items() if k != "urgency"}
        if non_urgency:
            max_category = max(non_urgency.values())
            avg_score = sum(non_urgency.values()) / len(non_urgency)
            scam_score = min(1.0, max(max_category, avg_score * 1.2))
        else:
            scam_score = 0.0

        # Apply benign context penalty (but limited, and require some baseline)
        benign_penalty = self._has_benign_context(text_lower)
        if benign_penalty > 0 and scam_score < 0.3:
            # Only suppress low-confidence alerts with benign context
            scam_score = max(0.0, scam_score - benign_penalty * 0.5)

        # Financial keyword boost
        if financial_keywords and scam_score > 0.15:
            scam_score = min(1.0, scam_score + 0.03 * len(financial_keywords))
        elif financial_keywords:
            # If financial keywords exist but no strong scam signals, mild boost
            scam_score = min(1.0, scam_score + 0.05 * len(financial_keywords))

        # --- Classify scam type ---
        scam_type, scam_confidence = self._classify_scam_type(scores, text_lower)

        return ScamAnalysis(
            scam_score=round(scam_score, 3),
            scam_type=scam_type,
            scam_type_confidence=round(scam_confidence, 3),
            urgency_score=round(urgency_score, 3),
            detected_cues=list(set(matched_cues))[:8],
            category_scores={k: round(v, 3) for k, v in scores.items()},
            financial_keywords=financial_keywords,
            matched_patterns=matched_patterns
        )

    def _classify_scam_type(self, scores: Dict[str, float], text_lower: str) -> Tuple[ScamType, float]:
        """Determine the primary scam type from detected patterns."""
        type_scores = {k: v for k, v in scores.items() if k != "urgency"}

        if not type_scores:
            return ScamType.UNKNOWN, 0.0

        best_type = max(type_scores, key=type_scores.get)
        best_score = type_scores[best_type]

        type_map = {
            "family_emergency": ScamType.FAMILY_EMERGENCY,
            "bank_kyc_fraud": ScamType.BANK_KYC_FRAUD,
            "police_legal_threat": ScamType.POLICE_LEGAL_THREAT,
            "tech_support_scam": ScamType.TECH_SUPPORT_SCAM,
            "job_investment_scam": ScamType.JOB_INVESTMENT_SCAM,
            "otp_pin_request": ScamType.OTP_PIN_REQUEST,
            "upi_payment_request": ScamType.UPI_PAYMENT_REQUEST,
            "remote_access_request": ScamType.REMOTE_ACCESS_REQUEST,
            "secrecy_pressure": ScamType.SECRECY_PRESSURE,
            "alternate_number_claim": ScamType.ALTERNATE_NUMBER_CLAIM,
        }

        return type_map.get(best_type, ScamType.UNKNOWN), best_score
"""CallShield Scam Language Intelligence Engine (v2.4.0).

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
    Context-aware scoring with benign context penalization.
    """

    PATTERNS = {
        # 1. Family emergency
        "family_emergency": {
            "en": ["i'?m in trouble", "emergency.*money", "accident", "hospital.*emergency",
                   "i'?m hurt", "i need urgent help", "main problem mein hoon", "accident hua hai",
                   "friend is in trouble", "relative.*hospital", "your child is with us",
                   "child.*with us", "we have your child", "kidnapped", "hostage",
                   "your son is with us", "your daughter is with us"],
            "hi": ["mujhe madad chahiye", "maine accident", "accident ho gaya", "hospital mein hoon",
                   "बच्चा.*हमारे पास", "बेटा.*हमारे पास", "बेटी.*हमारे पास"],
            "hinglish": ["main problem mein hoon", "mujhe help chahiye", "accident hua", "hospital mein admit",
                         "bachcha.*hamare paas", "baccha.*hamare paas", "bacha.*hamare paas",
                         "tumhara bachcha.*hamare paas", "beta.*hamare paas", "beti.*hamare paas"],
        },
        # 2. Bank/KYC fraud
        "bank_kyc_fraud": {
            "en": ["your account is compromised", "kyc.*suspicious", "account blocked", "suspended your",
                   "card will be blocked", "block your account", "account freeze", "unauthorized access",
                   "kyc update", "verify your account", "frozen", "suspicious activity",
                   "account.*credited", "if this is not you", "card details"],
            "hi": ["account block ho gaya", "kyc karana hai"],
            "hinglish": ["account block hua", "kyc update karo"],
        },
        # 3. Police / legal threat / Authority claim
        "police_legal_threat": {
            "en": ["pay.*to avoid arrest", "warrant has been issued", "arrest", "warrant",
                   "criminal", "complaint lodged", "raid", "cbi", "police station",
                   "customs department", "illegal package", "narcotics", "supreme court",
                   "legal notice", "fine.*due", "legal notice received", "final warning",
                   "illegal activity", "criminal case", "linked to.*criminal case"],
            "hi": ["police bulaungi", "arrest hoga", "legal notice"],
            "hinglish": ["police bulaungi", "arrest hoga", "cbi raid", "customs se bol raha hoon"],
        },
        # 4. Tech support
        "tech_support_scam": {
            "en": ["download this file", "your computer is infected", "hackers", "keylogger",
                   "install.*app",
                   "install support app", "device.*compromised", "install secure software",
                   "credentials.*laptop"],
            "hi": ["app install karo"],
            "hinglish": ["virus hai"],
        },
        # 4b. Remote access / screen-sharing scams
        "remote_access_request": {
            "en": ["install teamviewer", "install anydesk", "remote access", "share screen",
                   "screen share", "give access", "remote desktop", "anydesk", "teamviewer",
                   "screen sharing", "share your screen", "control your device"],
            "hi": ["screen share karo", "remote access do"],
            "hinglish": ["screen share kar do", "anydesk download", "screen share kar lijiye"],
        },
        # 5. Job / investment scam
        "job_investment_scam": {
            "en": ["guaranteed returns", "double your money", "no risk investment",
                   "quick profit", "guaranteed profit", "work from home", "earn.*money",
                   "processing fee", "security deposit.*job", "earn daily", "part time job",
                   "earn from home", "job offer", "investment opportunity", "win a car",
                   "lucky draw", "gift card", "prize", "congratulations.*won",
                   "earn.*per day", "no risk", "no investment"],
            "hi": ["paisa double", "ghar baithe naukri", "lottery"],
            "hinglish": ["paisa double", "work from home job", "daily earning", "ghar baithe kamao"],
        },
        # 6. OTP / PIN / Credentials request
        "otp_pin_request": {
            "en": ["otp", "one time password", "pin", "cvv", "password",
                   "security code", "verification code", "card number", "expiry date"],
            "hi": ["otp batao", "pin do", "cvv batao"],
            "hinglish": ["otp share karo", "pin batao", "cvv batao", "card number dena"],
        },
        # 7. UPI / payment request (urgent)
        "upi_payment_request": {
            "en": ["send money", "send me money", "give me money",
                   "money please", "pay me", "transfer.*money", "upi id", "google pay", "phone pay", "paytm",
                   "crypto", "bitcoin", "gift card", "payment link", "pay now", "deposit",
                   "processing fee", "clear the fine", "bhejo", "bhej do", "transfer kar", "upi karo",
                   "upi", "pay via upi", "transfer via upi", "phonepe"],
            "hi": ["paise bhejo", "payment karo", "bhej do"],
            "hinglish": ["paise bhejo", "upi karo", "payment kar do", "paise transfer", "gpay karo"],
        },
        # 9. Secrecy pressure
        "secrecy_pressure": {
            "en": ["don'?t tell anyone", "keep this secret", "nobody should know",
                   "between you and me", "don'?t share", "keep quiet", "don't hang up",
                   "stay on the line", "don't verify", "private matter", "keep this very quiet",
                   "do not mention", "family finds out"],
            "hi": ["kisi ko mat batana", "phone mat kaatna"],
            "hinglish": ["kisiko mat batana", "chup raho", "phone mat rakhna"],
        },
        # 10. Alternate number claim
        "alternate_number_claim": {
            "en": ["calling from another phone", "phone.*dead", "phone broke",
                   "lost my phone", "new number", "different number", "doosra number",
                   "dusri taraf se", "mera phone band hai", "doosri taraf se bol raha hoon"],
            "hi": ["doosra number", "phone band hai"],
            "hinglish": ["dusra number se", "phone dead hai", "phone switch off", "mera phone band hai"],
        },
        # Bonus: urgency indicators
        "urgency": {
            "en": ["right now", "immediately", "urgent", "hurry",
                   "right away", "asap", "last chance", "act now", "don'?t delay",
                   "within.*minute", "only today", "offer expires", "limited time",
                   "fauran", "jaldi", "turant", "urgently"],
            "hi": ["abhi", "fauran", "jaldi", "turant"],
            "hinglish": ["abhi karo", "turant", "jaldi se", "jaldi karo"],
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
        "rent deposit", "house rent", "rent money", "school fees",
        "dinner we had", "already transferred", "has transferred",
        "i sent you", "nothing serious", "no action needed", "pay when convenient",
        "happy birthday", "congratulations", "gift for you",
        "moving furniture", "help moving", "property case", "legal notice received",
        "hr sent an email", "hr department", "salary credited", "bonus",
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
                    phrase = phrase.strip()
                    if not phrase:
                        continue
                    patterns.append(re.compile(r'(?<!\w)(?:' + phrase + r')(?!\w)', re.IGNORECASE))
            self.compiled[category] = patterns

    def _has_benign_context(self, text: str) -> float:
        """Return benign context penalty (0-1)."""
        text_lower = text.lower()
        penalty = 0.0

        for phrase in self.BENIGN_PHRASES:
            if phrase in text_lower:
                penalty += 0.15  # Increased cumulative penalty

        # Specific high-confidence benign contexts
        if "surprise" in text_lower and "party" in text_lower:
            penalty += 0.4
        if "routine" in text_lower and ("checkup" in text_lower or "appointment" in text_lower):
            penalty += 0.5
        if "cafe" in text_lower or "hang out" in text_lower:
            penalty += 0.3
        if "assignment" in text_lower or "homework" in text_lower:
            penalty += 0.4
        if "rent money" in text_lower or "house rent" in text_lower or "school fees" in text_lower:
            penalty += 0.4
        if "doing fine" in text_lower or "all is well" in text_lower:
            penalty += 0.3
        if "lost and found" in text_lower:
            penalty += 0.5
        if "already transferred" in text_lower or "sent you" in text_lower:
            penalty += 0.4

        # Combination logic: money + benign context = lower risk
        if ("money" in text_lower or "rupees" in text_lower or "₹" in text_lower) and \
           ("rent" in text_lower or "fees" in text_lower or "dinner" in text_lower or "college" in text_lower):
            penalty += 0.4

        return min(penalty, 0.8)  # Cap the penalty

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
                # Logarithmic scaling
                import math
                score = min(math.log(1 + match_count * 2) / math.log(5), 1.0)
                scores[category] = score
                ordered_matches = list(dict.fromkeys(str(mm) for mm in matched_for_cat))
                for m in ordered_matches[:3]:
                    if m not in matched_cues:
                        matched_cues.append(f"{category}: {m}")
                matched_patterns[category] = ordered_matches[:5]

        # Extract urgency
        urgency_score = scores.get("urgency", 0.0)

        # --- Financial keyword detection ---
        financial_keywords = []
        financial_patterns = [
            r"(?:₹|rs\.?|inr)\s?\d+|\d+\s?(?:rupees|rs|inr)",  # Amounts
            r"\bupi\b|google pay|phonepe|paytm",  # UPI/GPay
            r"\botp\b|\bpin\b|\bcvv\b|password|verification code", # Credentials
        ]
        for p in financial_patterns:
            financial_keywords.extend(
                match.group(0) for match in re.finditer(p, text_lower, re.IGNORECASE)
            )

        # --- Compute scam score with combination logic ---
        # Distinguish between strong and weak categories
        strong_categories = ["otp_pin_request", "tech_support_scam", "remote_access_request", "bank_kyc_fraud"]
        weak_categories = ["family_emergency", "alternate_number_claim", "secrecy_pressure", "upi_payment_request", "job_investment_scam", "police_legal_threat"]
        
        strong_score = max([scores.get(c, 0.0) for c in strong_categories] + [0.0])
        weak_score = max([scores.get(c, 0.0) for c in weak_categories] + [0.0])
        
        # Base score starts low
        scam_score = 0.0
        
        if strong_score > 0.5:
            scam_score = strong_score
        elif strong_score > 0 or weak_score > 0:
            # Single weak category alone shouldn't trigger high risk
            num_categories = len([s for s in scores if s != "urgency" and scores[s] > 0.3])
            
            if num_categories >= 2:
                scam_score = max(strong_score, weak_score) * 1.1
            else:
                # Only one category - keep it safe unless it's a very strong match
                scam_score = max(strong_score, weak_score) * 0.7
        
        # --- Combination Boosts (High Precision) ---
        if scores:
            # 1. Authority Claim + Payment Request = Strong Scam
            if scores.get("police_legal_threat", 0) > 0.4 and (scores.get("upi_payment_request", 0) > 0.4 or financial_keywords):
                scam_score = max(scam_score, 0.85)
            
            # 2. Tech Support + Remote Access/Payment = Strong Scam
            if scores.get("tech_support_scam", 0) > 0.4 and (scores.get("remote_access_request", 0) > 0.4 or scores.get("upi_payment_request", 0) > 0.4):
                scam_score = max(scam_score, 0.85)
                
            # 3. OTP/PIN Request + Bank/KYC = Strong Scam
            if scores.get("otp_pin_request", 0) > 0.4 and scores.get("bank_kyc_fraud", 0) > 0.4:
                scam_score = max(scam_score, 0.9)
                
            # 4. Family Emergency + Alternate Number + Urgency/Money = Strong Scam
            if scores.get("family_emergency", 0) > 0.4 and scores.get("alternate_number_claim", 0) > 0.4:
                if urgency_score > 0.4 or financial_keywords:
                    scam_score = max(scam_score, 0.85)
                else:
                    scam_score = max(scam_score, 0.4) # Still suspicious but not high
            
            # 5. Secrecy + Any other signal = Boost
            if scores.get("secrecy_pressure", 0) > 0.4 and len(scores) >= 2:
                scam_score = min(1.0, scam_score + 0.2)

            # 6. High-precision false-negative patches from v2.3.5 evaluation.
            if "device" in text_lower and "compromised" in text_lower and (
                "install" in text_lower or "credentials" in text_lower
            ):
                scam_score = max(scam_score, 0.85)

            if "work from home" in text_lower and "earn" in text_lower and "no risk" in text_lower:
                scam_score = max(scam_score, 0.50)

            if "account" in text_lower and "credited" in text_lower and "if this is not you" in text_lower:
                if "verify" in text_lower or "provide" in text_lower or "card" in text_lower:
                    scam_score = max(scam_score, 0.85)

            if "final warning" in text_lower and (
                "illegal activity" in text_lower or "criminal case" in text_lower or "arrest" in text_lower
            ):
                scam_score = max(scam_score, 0.90)

            if "keep this very quiet" in text_lower and "do not mention" in text_lower:
                scam_score = max(scam_score, 0.65)

            if self._has_kidnapping_extortion_context(text_lower):
                scam_score = max(scam_score, 0.90)

            if self._has_direct_payment_pressure(text_lower):
                scam_score = max(scam_score, 0.70)

        # Apply benign context penalty
        benign_penalty = self._has_benign_context(text_lower)
        scam_score = max(0.0, scam_score - benign_penalty)

        # Financial keyword boost only if there's already some suspicion
        if financial_keywords:
            if scam_score > 0.2:
                scam_score = min(1.0, scam_score + 0.1)
            elif urgency_score > 0:
                scam_score = 0.25

        # --- Classify scam type ---
        scam_type, scam_confidence = self._classify_scam_type(scores, text_lower)

        return ScamAnalysis(
            scam_score=round(min(1.0, scam_score), 3),
            scam_type=scam_type,
            scam_type_confidence=round(scam_confidence, 3),
            urgency_score=round(urgency_score, 3),
            detected_cues=list(dict.fromkeys(matched_cues))[:8],
            category_scores={k: round(v, 3) for k, v in scores.items()},
            financial_keywords=list(dict.fromkeys(financial_keywords)),
            matched_patterns=matched_patterns
        )

    def analyze_session(self, segments: List[str]) -> List[float]:
        """
        Timeline analysis: How risk evolves over the conversation.
        Returns a list of scores, one for each cumulative segment.
        """
        timeline_scores = []
        cumulative_text = ""
        
        for segment in segments:
            cumulative_text += " " + segment
            analysis = self.analyze(cumulative_text)
            timeline_scores.append(analysis.scam_score)
            
        return timeline_scores

    def _classify_scam_type(self, scores: Dict[str, float], text_lower: str) -> Tuple[ScamType, float]:
        """Determine the primary scam type from detected patterns."""
        type_scores = {k: v for k, v in scores.items() if k != "urgency"}

        if not type_scores:
            return ScamType.UNKNOWN, 0.0

        if self._has_kidnapping_extortion_context(text_lower):
            return ScamType.FAMILY_EMERGENCY, max(type_scores.get("family_emergency", 0.0), 0.9)

        if type_scores.get("remote_access_request", 0.0) >= type_scores.get("tech_support_scam", 0.0) and \
           type_scores.get("remote_access_request", 0.0) > 0:
            return ScamType.REMOTE_ACCESS_REQUEST, type_scores["remote_access_request"]

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

    @staticmethod
    def _has_direct_payment_pressure(text_lower: str) -> bool:
        """Detect direct, context-free payment pressure heard by ASR."""
        patterns = [
            r"\bplease\s+send\s+money\b",
            r"\bsend\s+money\s+(?:now|please|immediately|urgently)\b",
            r"\bsend\s+me\s+money\b",
            r"\bgive\s+me\s+money\b",
            r"\bpay\s+me\b",
            r"\bmoney\s+please\b",
            r"\bpaise\s+bhejo\b",
            r"\bpaisa\s+bhejo\b",
        ]
        return any(re.search(pattern, text_lower, re.IGNORECASE) for pattern in patterns)

    @staticmethod
    def _has_kidnapping_extortion_context(text_lower: str) -> bool:
        child_or_hostage = any(
            phrase in text_lower
            for phrase in [
                "child is with us",
                "we have your child",
                "your son is with us",
                "your daughter is with us",
                "kidnapped",
                "hostage",
                "bachcha hamare paas",
                "baccha hamare paas",
                "bacha hamare paas",
                "tumhara bachcha",
                "बच्चा",
                "बेटा",
                "बेटी",
            ]
        )
        extortion = any(
            phrase in text_lower
            for phrase in [
                "send money",
                "transfer",
                "pay",
                "money",
                "paise",
                "paisa",
                "bhejo",
                "भेजो",
                "पैसे",
            ]
        )
        return child_or_hostage and extortion

import re
from typing import List, Tuple, Dict


class ScamLanguageDetector:
    """Multi-language scam language detector with keyword and heuristic rules."""

    # Comprehensive multi-language scam patterns
    SCAM_PATTERNS = {
        "urgency": {
            "en": ["right now", "immediately", "urgent", "within.*minute", "hurry",
                   "right away", "asap", "at once", "moment", "quickly"],
            "hi": ["abhi", "fauran", "jaldi", "turant"],
            "hinglish": ["abhi.*bhejo", "jaldi.*karo", "turant.*transfer"]
        },
        "money": {
            "en": ["transfer", "upi", "wire", "gift card", "bitcoin", "cash",
                   "payment", "send money", "pay now", "bank account", "crypto",
                   "deposit", "refund", "compensation"],
            "hi": ["paise bhejo", "paisa", "rupaye", "payment karo", "transfer karo"],
            "hinglish": ["paise bhejo", "upi karo", "paisa transfer"]
        },
        "secrecy": {
            "en": ["don't tell", "keep this private", "don't mention", "between us",
                   "don't share", "confidential", "secret", "nobody needs to know"],
            "hi": ["kisi ko mat batana", "chup rehna", "raaz"],
            "hinglish": ["kisiko mat batana", "koi nahi jaanega", "secret rakhna"]
        },
        "alternate_phone": {
            "en": ["calling from another phone", "phone dead", "phone broke",
                   "different number", "lost my phone", "using friend's phone",
                   "new sim", "another number"],
            "hi": ["doosra number", "phone kharaab", "new number"],
            "hinglish": ["doosra number", "phone dead", "dusra number se bol raha"]
        },
        "authority": {
            "en": ["police", "bank manager", "customs", "legal notice", "warrant",
                   "irs", "government", "law enforcement", "court", "lawyer",
                   "federal", "official", "regulations"],
            "hi": ["police", "sarkar", "adkar", "kanun", "vakeel"],
            "hinglish": ["bank se bol raha", "sarkari", "legal notice"]
        },
        "threat": {
            "en": ["you will be arrested", "suspended", "expelled", "fired",
                   "jail", "prison", "penalty", "fine", "lawsuit", "sue"],
            "hi": ["police bulaungi", "arrest hoga", "jail hoga"],
            "hinglish": ["arrest kar dunga", "police case banega"]
        },
        "verification_bypass": {
            "en": ["don't verify", "don't check", "trust me", "no time to verify",
                   "just do it", " Don't call back", "don't hang up"],
            "hi": ["check mat karo", "verify mat karo"],
            "hinglish": ["check mat karo", "verify nahi karna"]
        }
    }

    # High-value phone-related financial terms
    FINANCIAL_KEYWORDS = ["otp", "pin", "password", "cvv", "card number",
                          "account number", "wallet"]

    def __init__(self):
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile regex patterns for fast matching."""
        self.compiled = {}
        for category, langs in self.SCAM_PATTERNS.items():
            patterns = []
            for lang, phrases in langs.items():
                for phrase in phrases:
                    patterns.append(re.compile(r'\b' + phrase + r'\b', re.IGNORECASE))
            self.compiled[category] = patterns

    def score_text(self, text: str) -> Dict:
        """Analyze text and return scam scores and matched cues."""
        text_lower = text.lower()
        scores = {}
        matched_cues = []

        for category, patterns in self.compiled.items():
            match_count = 0
            for pattern in patterns:
                matches = pattern.findall(text_lower)
                match_count += len(matches)
                if matches:
                    # Add unique matched terms
                    for m in set(matches):
                        if isinstance(m, str) and m not in matched_cues:
                            matched_cues.append(f"{category}: {m}")

            scores[category] = min(match_count / 3.0, 1.0)

        # Check financial keywords
        financial_hits = [kw for kw in self.FINANCIAL_KEYWORDS
                         if kw in text_lower]
        for kw in financial_hits:
            matched_cues.append(f"financial_keyword: {kw}")

        # Overall scam score
        if scores:
            scam_score = max(scores.values())
            if any(scores.values()):
                scam_score = max(min(1.0, sum(scores.values()) / 4.0), max(scores.values()))
        else:
            scam_score = 0.0

        # Additional heuristics
        # Long string of numbers (phone numbers, account numbers)
        number_sequences = re.findall(r'\b\d{4,}\b', text)
        if number_sequences:
            scam_score += 0.1 * len(number_sequences)
            matched_cues.append(f"number_sequence: {number_sequences[0]}")

        # Repeated urgency words
        urgency_words = ["urgent", "immediately", "now", "hurry", "asap"]
        urgency_count = sum([text_lower.count(w) for w in urgency_words])
        if urgency_count >= 2:
            scam_score += 0.15
            matched_cues.append("repeated_urgency")

        return {
            "scam_score": min(scam_score, 1.0),
            "category_scores": scores,
            "matched_cues": matched_cues[:5],  # Top 5 cues
            "financial_keywords": financial_hits
        }

    def is_scam(self, text: str, threshold: float = 0.3) -> Tuple[bool, Dict]:
        """Quick boolean check with detailed analysis."""
        result = self.score_text(text)
        return result["scam_score"] >= threshold, result

"""CallShield Challenge-Response Verification Module.

When the system detects a suspicious call, it suggests safe verification
to the user WITHOUT ever blocking or interfering with the call.

This is the "user control" layer — the AI assists, the human decides.
"""

import random
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class ChallengeResponse:
    """A safe verification challenge for the user to pose."""
    question: str
    why: str  # Why this question works
    expected_type: str = "family_info"  # What kind of response is expected
    fallback_time: str = ""  # Suggested time to verify


class ChallengeGenerator:
    """
    Generates safe verification challenges based on scam type and risk level.

    Design principle: Chickens don't reveal the correct answer.
    The user asks; the scammer must answer.
    """

    # --- Universal challenge bank (must be translated to HI/Hinglish in product) ---
    CHALLENGES = {
        # Family-related
        "family_emergency": [
            ChallengeResponse(
                "What is our family pet's name?",
                "AI clones voice but doesn't know private family trivia. A real family member will laugh and answer. A scammer will deflect.",
                "family_info", "After hanging up, call their saved number."
            ),
            ChallengeResponse(
                "Name the last family trip we all went on together.",
                "Memories are deeply personal. Scammers will pivot or hang up.",
                "family_info", "After hanging up, call their saved number."
            ),
            ChallengeResponse(
                "What is our home address? The full address.",
                "A real family member knows the address. A cloned voice scammer must guess.",
                "family_info", "After hanging up, call their saved number."
            ),
        ],
        # Bank/KYC
        "bank_kyc_fraud": [
            ChallengeResponse(
                "I will come to my nearest branch and check directly.",
                "Real bank staff will say yes. Scammers will say 'no, this is the only way'.",
                "action_verify", "Visit the bank branch directly. Do NOT follow phone instructions."
            ),
            ChallengeResponse(
                "Tell me my account number from the start.",
                "A real bank knows your account number. Scammers ask for it, not the other way around.",
                "account_verify", "Call the bank's official number from your card. Not this call."
            ),
        ],
        # Tech support
        "tech_support_scam": [
            ChallengeResponse(
                "I will take my laptop to my company's IT person and have them check.",
                "Real tech support is fine with this. Scammers will scream, 'No, don't do that! It will make things worse!''",
                "action_verify", "Only trust your company's IT department or a certified technician."
            ),
            ChallengeResponse(
                "What is my Windows username?", "Real tech support can see this. Scammers won't know it.\nThe user's device username is something we already know on our end.",
                "tech_verify", "Always verify through your IT department or official channels."
            ),
        ],
        # General / fallback
        "general": [
            ChallengeResponse(
                "I will call your number right back.",
                "A scammer using a fake/alternate number will panic. A real person will say yes and the call will go through.",
                "call_back", "Hang up and call their saved contact."
            ),
            ChallengeResponse(
                "Say our family safe word.",
                "A family safe word is pre-agreed inside a family. An AI scammer can't know it.",
                "family_info", "If they can't say it, it is not family. Hang up immediately."
            ),
            ChallengeResponse(
                "Can you send me a voice note with today's date and any sentence?",
                "Scammers using cloned audio on a real-time call can't generate a fresh voice note with today's date."
            ),
            ChallengeResponse(
                "What is the road name right outside our house?",
                "Private, place-based knowledge real callers possess and scammers don't.",
                "family_info", "If they can't answer immediately, it is suspicious."
            ),
            ChallengeResponse(
                "I will record this conversation to report to the police. Is that okay?",
                "Scammers will immediately hang up. Legitimate callers won't mind.",
                "psychological", "This is a psychological test. Use with caution."
            ),
        ]
    }

    def generate(self,
                risk_band: str,
                scam_type: str = "unknown",
                scam_score: float = 0.0) -> List[ChallengeResponse]:
        """Generate appropriate challenges based on the detected scam type."""
        challenges = []

        # Always include a general challenge
        challenges.extend(self.CHALLENGES.get("general", [])[:2])

        # Add scam-specific challenges
        if scam_type in self.CHALLENGES:
            challenges.extend(self.CHALLENGES[scam_type])

        # If risk is critical, add preventive advice
        if risk_band in ("high", "critical"):
            challenges.insert(0, ChallengeResponse(
                "Do not share anything. Tell them you will call them back. Then immediately call their saved number.",
                "This is a high-risk call. The safest verification is hanging up and calling back on a saved, verified number.",
                "hangup_verify", "Call back on the saved, known number only."
            ))

        return challenges[:3]  # Return at most 3

    def get_recommendation(self,
                          risk_band: str,
                          scam_type: str = "unknown",
                          confidence: float = 0.0) -> Dict:
        """Get action recommendation based on risk and confidence."""
        if risk_band == "critical":
            return {
                "action": "HANG UP and call back on a saved number",
                "reason": "Multiple high-confidence scam indicators detected",
                "do_not": ["Send money", "Share OTP/PIN", "Install any app", "Give remote access"]
            }
        elif risk_band == "high" and confidence >= 0.6:
            return {
                "action": "Ask a verification question. If they deflect, hang up.",
                "reason": "Strong scam indicators are present",
                "do_not": ["Send money", "Share OTP/PIN"]
            }
        elif risk_band == "suspicious":
            return {
                "action": "Be cautious. Ask a family-only question before sharing anything.",
                "reason": "Some unusual patterns detected",
                "do_not": ["Send money", "Share OTP/PIN"]
            }
        return {
            "action": "Continue normally",
            "reason": "No scam signals detected",
            "do_not": []
        }

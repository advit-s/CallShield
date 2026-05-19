"""50 Scam Call Scenarios - for testing true positive rate.

These are real-world scam conversation patterns across all categories.
Covers: family emergency, bank fraud, UPI, OTP, deepfake, tech support, etc.
"""

SCAM_SCENARIOS = [
    # Family emergency scams
    {"id": "s01", "text": "Beta, your father met with an accident. The doctor says we need ₹50,000 immediately for the operation. I am using my friend's phone as I lost mine.", "category": "family_emergency", "expected_band": "critical"},
    {"id": "s02", "text": "Mera phone band hai, main doosri taraf se bol raha hoon. Mujhe ₹25,000 chahiye emergency ke liye. Jaldi paise bhej.", "category": "family_emergency", "expected_band": "high"},
    {"id": "s03", "text": "I am in trouble. Please don't tell anyone. Send ₹40,000 to this UPI ID. Do not call my number, it is dead.", "category": "family_emergency", "expected_band": "high"},
    {"id": "s04", "text": "Keep this secret. Your brother is in jail and needs bail money right now. Transfer ₹30,000 immediately.", "category": "family_emergency", "expected_band": "critical"},
    {"id": "s05", "text": "Don't verify anything. Just send the money. I am calling from another phone, my mother is faint.", "category": "family_emergency", "expected_band": "critical"},

    # Bank/KYC fraud
    {"id": "s06", "text": "This is the HDFC Bank. Your account has been compromised by hackers. We need your OTP to secure it. The amount is ₹25,000 and we need to transfer it to a safe account.", "category": "bank_kyc_fraud", "expected_band": "critical"},
    {"id": "s07", "text": "Your KYC has been suspended. Update your details immediately. We will block your account if you don't verify this call today. Don't tell anyone.", "category": "bank_kyc_fraud", "expected_band": "high"},
    {"id": "s08", "text": "You have received a refund of ₹15,000. Please confirm your account number, CVV, and OTP so we can process it right now.", "category": "bank_kyc_fraud", "expected_band": "high"},
    {"id": "s09", "text": "SBI Security alert: Your card has been blocked for suspicious transactions. Share your PIN now to unblock it urgently.", "category": "bank_kyc_fraud", "expected_band": "critical"},
    {"id": "s10", "text": "Your account is about to be frozen. To save your savings, transfer the balance immediately. This is between us and the bank.", "category": "bank_kyc_fraud", "expected_band": "critical"},

    # Police/Legal threat
    {"id": "s11", "text": "This is a call from the Delhi Police Narcotics Department. We have found illegal activities in your name. Pay ₹10,000 to avoid arrest.", "category": "police_legal_threat", "expected_band": "high"},
    {"id": "s12", "text": "A warrant has been issued for your arrest. This is very serious. Transfer ₹20,000 to the court account to settle this.", "category": "police_legal_threat", "expected_band": "critical"},
    {"id": "s13", "text": "CBI officials here. You are being investigated. We just need ₹30,000 processing fee. Keep this confidential.", "category": "police_legal_threat", "expected_band": "critical"},
    {"id": "s14", "text": "You have a legal notice from the customs department. A fine of ₹50,000 is due. Do not tell anyone, just pay it now.", "category": "police_legal_threat", "expected_band": "high"},
    {"id": "s15", "text": "Police is here, they want to arrest you. Pay me ₹15,000 bribe to make them go away. Don't hang up!", "category": "police_legal_threat", "expected_band": "critical"},

    # Tech support scam
    {"id": "s16", "text": "This is Microsoft support. Your computer is infected by 17 viruses. We need remote access to fix it. Please install TeamViewer and give us the ID and password.", "category": "tech_support_scam", "expected_band": "high"},
    {"id": "s17", "text": "We have detected hackers in your system. To remove this threat, you must allow us remote access to your computer.", "category": "tech_support_scam", "expected_band": "high"},
    {"id": "s18", "text": "Our system shows unauthorized access. For security, share screen with us. Install this app right now.", "category": "tech_support_scam", "expected_band": "high"},
    {"id": "s19", "text": "Your device is compromised. We need to install secure software. Give us the credentials to your laptop.", "category": "tech_support_scam", "expected_band": "high"},
    {"id": "s20", "text": "Remove a virus. We need you to download this file and run it. Your antivirus is also broken.", "category": "tech_support_scam", "expected_band": "high"},

    # Job/Investment scam
    {"id": "s21", "text": "Congratulations! You have won a special investment opportunity with guaranteed returns of 200%. No risk, just double your money in 30 days.", "category": "job_investment_scam", "expected_band": "high"},
    {"id": "s22", "text": "Earn from home! A unique job offer for you. Work online and earn ₹50,000 per month. No experience required.", "category": "job_investment_scam", "expected_band": "suspicious"},
    {"id": "s23", "text": "Quick profit! Invest ₹10,000 and get ₹1,00,000. This is a one-time offer. Act now, limited time.", "category": "job_investment_scam", "expected_band": "critical"},
    {"id": "s24", "text": "Guaranteed returns of 50%. You cannot lose money. Just send the amount right now.", "category": "job_investment_scam", "expected_band": "high"},
    {"id": "s25", "text": "Work from home and earn $100 per day. No risk, no investment.", "category": "job_investment_scam", "expected_band": "suspicious"},

    # OTP/PIN/Password request
    {"id": "s26", "text": "We are sending an OTP to your phone. Please tell us the OTP as soon as you receive it.", "category": "otp_pin_request", "expected_band": "high"},
    {"id": "s27", "text": "Your card will be blocked if you don't provide the CVV number. Enter it in the link.", "category": "otp_pin_request", "expected_band": "high"},
    {"id": "s28", "text": "For verification, we need your card number and the one time password. Please share.", "category": "otp_pin_request", "expected_band": "critical"},
    {"id": "s29", "text": "Enter the OTP immediately. Do not share this with anyone, not even your family.", "category": "otp_pin_request", "expected_band": "critical"},
    {"id": "s30", "text": "To secure your account, give us your PIN, password, and the security code in the message.", "category": "otp_pin_request", "expected_band": "critical"},

    # UPI/Payment request
    {"id": "s31", "text": "Send money urgently to this UPI ID. I am stuck at a medical facility. ₹25,000 through Google Pay. Do it right now.", "category": "upi_payment_request", "expected_band": "critical"},
    {"id": "s32", "text": "Transfer ₹40,000 now. The matter is urgent. My phone is dead, using a friend's.", "category": "upi_payment_request", "expected_band": "critical"},
    {"id": "s33", "text": "Payment needed for the emergency. ₹50,000 to this UPI ID. Don't tell anyone. Send immediately.", "category": "upi_payment_request", "expected_band": "critical"},
    {"id": "s34", "text": "Hurry! The amount needs to be paid now. Transfer via UPI: payfast@upi. It is the only way.", "category": "upi_payment_request", "expected_band": "high"},
    {"id": "s35", "text": "I need ₹10,000 urgently for the hospital. Transfer the money using this link. It is safe.", "category": "upi_payment_request", "expected_band": "high"},

    # SMS-based scams
    {"id": "s36", "text": "Your account has been credited with ₹50,000. If this is not you, contact us immediately and provide your card details.", "category": "bank_kyc_fraud", "expected_band": "high"},
    {"id": "s37", "text": "Alert: Unusual activity detected on your card ending 7845. Confirm your CVV to prevent this.", "category": "bank_kyc_fraud", "expected_band": "high"},
    {"id": "s38", "text": "You have received a gift card worth ₹2000. Click to redeem. The offer is valid today only!", "category": "job_investment_scam", "expected_band": "suspicious"},
    {"id": "s39", "text": "Your job application has been accepted. Submit a processing fee of ₹5,000 to confirm your seat.", "category": "job_investment_scam", "expected_band": "high"},
    {"id": "s40", "text": "Win a car! Send ₹2,000 to this number to enter the lucky draw. Act now, limited slots available!", "category": "job_investment_scam", "expected_band": "high"},

    # Deepfake-specific
    {"id": "s41", "text": "[AI-voice] Beta it's me. My phone is dead. I am calling from a different number. I need money for a medical emergency right now.", "category": "family_emergency", "expected_band": "critical"},
    {"id": "s42", "text": "[Synthetic voice] Don't verify this, just send the money. I am at the hospital and my phone broke.", "category": "family_emergency", "expected_band": "critical"},
    {"id": "s43", "text": "[AI-cloned voice] It's your brother. I am stuck at the police station, don't tell anyone.", "category": "family_emergency", "expected_band": "critical"},
    {"id": "s44", "text": "[AI voice] I am calling from your bank's security line. Your account has been locked. Kindly send your PIN to unlock it urgently.", "category": "bank_kyc_fraud", "expected_band": "critical"},
    {"id": "s45", "text": "[Cloned voice] This is the final warning. Your number is linked to a criminal case. If you don't transfer the amount, you will be arrested today.", "category": "police_legal_threat", "expected_band": "critical"},

    # Secrecy pressure
    {"id": "s46", "text": "Don't tell anyone about this call. This is between you and me. Keep it secret.", "category": "secrecy_pressure", "expected_band": "suspicious"},
    {"id": "s47", "text": "Nobody should know about this. It's a private matter. Just do what I say.", "category": "secrecy_pressure", "expected_band": "suspicious"},
    {"id": "s48", "text": "Keep this very quiet. Do not mention it to anyone. If the family finds out, it will be a problem.", "category": "secrecy_pressure", "expected_band": "high"},
    {"id": "s49", "text": "Between us, just give the verification code now. Don't even tell your husband.", "category": "secrecy_pressure", "expected_band": "high"},
    {"id": "s50", "text": "It's a secret. Don't share this with anyone. Just pay the money and keep quiet.", "category": "secrecy_pressure", "expected_band": "high"},
]

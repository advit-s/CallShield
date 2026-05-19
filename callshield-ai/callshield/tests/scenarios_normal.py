"""50 Normal Call Scenarios - for testing false positive rate.

These are real-world benign conversation patterns that should NOT trigger scam alerts.
Covers: family calls, friend conversations, work calls, doctor appointments,
service appointments, casual chats, romantic conversations, etc.
"""

NORMAL_SCENARIOS = [
    # Family calls
    {"id": "n01", "text": "Hi beta, how is your day going? Did you eat lunch?", "expected_band": "safe"},
    {"id": "n02", "text": "Hello, papa. I'm doing well, thanks. Just reached the office.", "expected_band": "safe"},
    {"id": "n03", "text": "Beta, we are coming tomorrow. What time you are free?", "expected_band": "safe"},
    {"id": "n04", "text":"Your aunt met with an accident but she is fine now, don't worry. She just had a minor fall.", "expected_band": "safe"},
    {"id": "n05", "text": "Dad, can you send me some money for my college fees? It is ₹15,000 this semester.", "expected_band": "safe"},  # Legitimate money request

    # Friend conversations
    {"id": "n06", "text": "Hey bro, long time no see. Wanna hang out this weekend?", "expected_band": "safe"},
    {"id": "n07", "text": "I'm using a new number now, lost my phone last week. Let's catch up soon!", "expected_band": "safe"},  # Honest alternate number
    {"id": "n08", "text": "Hey, my phone battery died, calling from a friend's phone. Can you pick me up?", "expected_band": "safe"},  # Honest emergency
    {"id": "n09", "text": "I got a new job! They are offering a good salary and work from home.", "expected_band": "safe"},  # Genuine job discussion
    {"id": "n10", "text": "Let's meet at the cafe near your house. I found a nice investment opportunity there.", "expected_band": "safe"},  # Genuine investment discussion

    # Work calls
    {"id": "n11", "text": "Good morning, this is Raj from the IT department. Can you check your email for the meeting link?", "expected_band": "safe"},
    {"id": "n12", "text": "Your salary for this month has been credited to your account. Please check.", "expected_band": "safe"},
    {"id": "n13", "text": "The boss wants everyone in the office by 10 tomorrow. Make sure you are not late.", "expected_band": "safe"},
    {"id": "n14", "text": "We need to complete this project by Friday. Any blockers from your side?", "expected_band": "safe"},
    {"id": "n15", "text": "HR sent an email about the new KYC update. Please check.", "expected_band": "safe"},  # Legitimate KYC

    # Service calls
    {"id": "n16", "text": "Hello, this is Airtel. Your postpaid bill of ₹499 is due. Pay when convenient.", "expected_band": "safe"},
    {"id": "n17", "text": "Your Flipkart order has been delivered. Rate your experience.", "expected_band": "safe"},
    {"id": "n18", "text": "This is Apollo Hospital. Your appointment with Dr. Sharma tomorrow at 3pm is confirmed.", "expected_band": "safe"},
    {"id": "n19", "text": "Your vehicle insurance is expiring next month. Would you like to renew?", "expected_band": "safe"},
    {"id": "n20", "text": "We deposited your refund to your bank account. It may take 5-7 business days.", "expected_band": "safe"},

    # Casual conversations
    {"id": "n21", "text": "Hey, I'm calling from a different number. Lost my old phone. Do you have the notes from class?", "expected_band": "safe"},
    {"id": "n22", "text": "Can you help me with this assignment? I'm stuck on question 3 and need some guidance.", "expected_band": "safe"},
    {"id": "n23", "text": "Let's go to the movie tonight. I saw the trailer and it looks amazing!", "expected_band": "safe"},
    {"id": "n24", "text": "Remember the safe word for the game today? It's 'blue mango'. Just kidding!", "expected_band": "safe"},  # Playful
    {"id": "n25", "text": "My mom asked me to call you. She wants to know if you are coming for dinner on Sunday.", "expected_band": "safe"},

    # Urgent but benign
    {"id": "n26", "text": "Hurry! The sale ends in 30 minutes. Can you grab the laptop for me?", "expected_band": "safe"},  # Shopping urgency, benign
    {"id": "n27", "text": "Come quickly, the train is arriving in 5 minutes!", "expected_band": "safe"},
    {"id": "n28", "text": "We need to submit the assignment right now. It closes in 10 minutes!", "expected_band": "safe"},
    {"id": "n29", "text": "Act fast, tickets are selling out! But no pressure. Just let me know.", "expected_band": "safe"},
    {"id": "n30", "text": "The doctor says we should come immediately for the follow-up. Nothing serious.", "expected_band": "safe"},

    # Financial but legitimate
    {"id": "n31", "text": "I sent you the UPI request for ₹500. It's for the dinner we had.", "expected_band": "safe"},
    {"id": "n32", "text": "Your brother has transferred the rent money. It's already in your account.", "expected_band": "safe"},
    {"id": "n33", "text": "The landlord called, the deposit is ready. You can pick it up on Monday.", "expected_band": "safe"},
    {"id": "n34", "text": "I refunded the amount. You should receive it in 2-3 days.", "expected_band": "safe"},
    {"id": "n35", "text": "The salary was credited late this month. Sorry for the inconvenience.", "expected_band": "safe"},

    # Sensitive but legitimate
    {"id": "n36", "text": "Keep this between us, it's a surprise party for Priya. Don't tell anyone!", "expected_band": "safe"},  # Fun secret
    {"id": "n37", "text": "Between you and me, the new boss is really nice.", "expected_band": "safe"},
    {"id": "n38", "text": "My phone died, I'm borrowing my colleague's phone to call you.", "expected_band": "safe"},
    {"id": "n39", "text": "I lost my phone. Can I have your number again? Lost all contacts.", "expected_band": "safe"},
    {"id": "n40", "text": "I am not at home yet, there is heavy traffic but I'll reach soon.", "expected_band": "safe"},

    # Legitimate official
    {"id": "n41", "text": "This is the police station at Carter Road. Your lost wallet has been found.", "expected_band": "safe"},
    {"id": "n42", "text": "The court appointment has been rescheduled to next Monday.", "expected_band": "safe"},
    {"id": "n43", "text": "Hello from the bank, your account is active and secure. No action needed.", "expected_band": "safe"},
    {"id": "n44", "text": "Customs clearance is complete. You can collect your shipment tomorrow.", "expected_band": "safe"},
    {"id": "n45", "text": "Legal notice received for the property case. Please reply in 10 days. This is genuine.", "expected_band": "safe"},

    # Mixed/Edge cases
    {"id": "n46", "text": "I need to pay the school fees urgently. Can you help? I'll pay you back tomorrow.", "expected_band": "safe"},  # Edge: urgency + money
    {"id": "n47", "text": "A friend is in trouble. He called from a new number and needs help moving furniture.", "expected_band": "safe"},  # Edge: trouble + new number, benign
    {"id": "n48", "text": "The mechanic says we need to fix the car immediately, it's leaking.", "expected_band": "safe"},  # Urgency, maintenance
    {"id": "n49", "text": "I am calling from hospital, but I'm fine, just a routine checkup.", "expected_band": "safe"},  # Edge: hospital but benign
    {"id": "n50", "text": "Don't tell anyone yet, but we are going to have a baby! It's a secret until next week.", "expected_band": "safe"},  # Edge: secrecy but joyful
]

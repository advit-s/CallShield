# Scam Pattern Extraction Report
*Generated on 2026-05-31 16:11*

## Dataset Coverage
- **indian_scam**: `ultra_premium_scam_dataset.csv` — 120 rows ✅
- **sms_multilingual**: `data-augmented.csv` — 5572 rows ✅
- **otp_spam**: `SMS_OTP_10000_samples.csv` — 10000 rows ✅

## 1. Indian Multilingual Scam Messages — New Phrases
Scam (60 rows) vs Legit (60 rows) comparison.

### Language: Hindi (19 unique phrases)
- `आपका बैंक खाता सत्यापन लंबित है`
- `आपका KYC पूरा नहीं है`
- `Aapka parcel customs me atka hai`
- `₹35 pay karke release kare immediately`
- `कृपया तुरंत अपडेट करें jaldi kare`
- `तुरंत अपडेट करें jaldi kare`
- `कृपया तुरंत अपडेट करें abhi kare`
- `Aapka ATM card block ho gaya hai`
- `You are selected for instant loan approval`
- `तुरंत अपडेट करें abhi kare`
- ... and 9 more

### Language: Hinglish (18 unique phrases)
- `You are selected for instant loan approval`
- `Aapka parcel customs me atka hai`
- `Aapka ATM card block ho gaya hai`
- `click to proceed please act now`
- `details update kare abhi kare`
- `आपका बैंक खाता सत्यापन लंबित है`
- `click to proceed`
- `₹35 pay karke release kare please act now`
- `₹35 pay karke release kare abhi kare`
- `कृपया तुरंत अपडेट करें immediately`
- ... and 8 more

### Language: English (22 unique phrases)
- `Aapka ATM card block ho gaya hai`
- `आपका KYC पूरा नहीं है`
- `You are selected for instant loan approval`
- `आपका बैंक खाता सत्यापन लंबित है`
- `Aapka parcel customs me atka hai`
- `details update kare jaldi kare`
- `click to proceed immediately`
- `तुरंत अपडेट करें please act now`
- `₹35 pay karke release kare immediately`
- `details update kare immediately`
- ... and 12 more


## 2. Multilingual SMS Spam — New English & Hinglish Patterns
English spam: 50 extracted phrases

### Top English SMS scam patterns
- `Valid 12hrs only`
- `We are trying to contact U`
- `2 claim is easy`
- `Claim 3030`
- `Send STOP FRND to 62468`
- `Latest Motorola`
- `Your 4* Costa Del Sol Holiday or £5000 await collection`
- `Your 2003 Account Statement for shows 800 un-redeemed S`
- `FREE for 1st week`
- `Call 09050090044 Now toClaim`
- `Only 10p per minute`
- `play java games`
- `noline rentl`
- `Thanks for your ringtone order`
- `T's&C's www`

### Hinglish/Devanagari spam: 0 phrases


## 3. OTP Dataset — `sms-otp-spam-dataset`
Classified by template; this dataset is **not SMS scam content** — it's
OTP delivery records labeled valid/expired/failed. Useful for teaching the
engine to recognize OTP delivery context, NOT to learn scam patterns from.

### Top OTP templates (masked)
- `{CODE} is your OTP to log in.` — 1838 occurrences
- `Use {CODE} to verify your account.` — 1831 occurrences
- `Security code: {CODE}. Do not share.` — 1807 occurrences
- `Your verification code is {CODE}.` — 1783 occurrences
- `Enter {CODE} to complete your login.` — 1741 occurrences
- `Urgent: Your bank account is compromised. Call {CODE} now.` — 231 occurrences
- `Get a loan approved instantly. Reply with {CODE}.` — 208 occurrences
- `Win a new iPhone by entering code {CODE} here!` — 201 occurrences
- `Your account will be locked. Enter {CODE} at our fake portal.` — 194 occurrences
- `Congratulations! You've won a free gift. Claim now using code {CODE}.` — 166 occurrences

### Intent classification
#### Likely Scam
- `{CODE} is your OTP to log in.`
- `Use {CODE} to verify your account.`
- `Security code: {CODE}. Do not share.`
- `Your verification code is {CODE}.`
- `Enter {CODE} to complete your login.`

#### Likely Legit

## 4. Proposed BENIGN_PHRASES Additions
From the 60 legit-labeled Indian scam messages:

- `Your order has been shipped and will arrive tomorrow please act now`
- `Your payment of ₹899 has been received jaldi kare`
- `Your parcel has been delivered successfully immediately`
- `Your train ticket has been booked successfully please act now`
- `Thank you for your purchase`
- `Your order has been shipped and will arrive tomorrow jaldi kare`
- `Your payment of ₹899 has been received please act now`
- `Your parcel has been delivered successfully immediately`
- `Your train ticket has been booked successfully`
- `Thank you for your purchase jaldi kare`

## 5. Existing Coverage Check
These categories are already covered by inline patterns in `scam_nlp.py`:
- OTP/PIN request (`otp`, `pin`, `cvv`, `one time password`)
- UPI/Payment (`upi`, `paise bhejo`, `gpay karo`, `send money`)
- Family emergency (`accident`, `hospital mein`, `kidnapped`)
- Bank/KYC (`account block`, `kyc update`, `account frozen`)
- Police/Legal (`arrest hoga`, `cbi raid`, `legal notice`)
- Tech support (`virus hai`, `screen share kar do`)
- Job/investment (`work from home`, `daily earning`, `paisa double`)
- Secrecy (`kisiko mat batana`, `chup raho`)
- Alternate number (`dusra number se`, `phone band hai`)

### Gaps identified (high-value additions):

| Gap | Rationale |
|-----|-----------|
| E-commerce fraud signals | Indian dataset has domain=`ecommerce` with scam patterns (fake delivery, order scams) — none in current engine |
| Telecom/utility scams | Domain=`telecom` + domain=`utilities` scam samples — no matching patterns |
| Government impersonation | Domain=`government` scam samples (tax, pension, scheme scams) — not covered |
| Finance-specific fraud | Domain=`finance` + `banking` scam variations — current patterns cover basic KYC but not loan/insurance scams |
| Hinglish verb-object combos | Dataset reveals common Hinglish scam constructions not yet in regex list |

---
*Next step: review `data/extracted_scam_patterns.json`, then manually merge
selected new phrases into `callshield/engine/scam_nlp.py` under `ScamLanguageEngine.PATTERNS`.*
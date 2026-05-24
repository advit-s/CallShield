# CallShield AI Codebase Audit Report (v2.3.5)

## 1. Executive Summary
This report presents a comprehensive technical, security, and product readiness audit of the **CallShield AI** codebase (v2.3.5). The system is designed to provide real-time scam-call intelligence by combining Scam NLP detection, audio deepfake detection, risk fusion, confidence calibration, and interactive challenge-responses.

Overall, the codebase represents a solid architecture with high-quality test coverage (21/21 pytests passing, and full scenario tests yielding 99.0% accuracy on simulated datasets). However, several **critical bugs**, **security/privacy vulnerabilities**, and **logic discrepancies** were identified during this audit. Specifically, the Scam NLP engine has regex boundary constraints that cause missed scam phrases, the Risk Fusion engine exhibits weights fallback discrepancies, the FastAPI server exposes credentials dynamically while using illegal CORS wildcards, and phone number hashing utilizes a static salt.

Once the recommended v2.3.5 bug-fix roadmap is executed, the codebase will be fully prepared for high-profile presentations, academic/mentor reviews, and initial product demos.

---

## 2. What Works Well
- **High-Quality Test Coverage:** The unit and scenario test suites run successfully (21/21 pytests pass in under 4 seconds). The NLP evaluation script (`main.py test`) verifies 100 scenario permutations, providing a strong baseline for regression testing.
- **Structured Risk Logic:** The division of labor between `scam_nlp.py` (intent), `deepfake.py` (audio authenticity), `fusion.py` (risk combining), and `calibration.py` (decision smoothing) is architecturally clean and follows modular design principles.
- **ASR and Model Safety Fallbacks:** If machine learning libraries (`torch`, `librosa`) or checkpoints are missing, the system gracefully handles the degradation, returning `null` values for deepfake scores rather than crashing.
- **Privacy Controls (Data Deletion & Consent):** Consent checks are implemented for speaker enrollment (`/verify-speaker`), and full Right to Erasure endpoints exist (`DELETE /user-data/{user_id}`) to comply with regulations such as India's DPDP Act, 2023.
- **Interactive UI Dashboard:** The HTML dashboard served at `/demo` is visually impressive, highly responsive, and combines simulated playback with real API form testing.

---

## 3. Critical Bugs

### Bug 3.1: Scam NLP Trailing Space Word Boundary Mismatch
- **Severity:** Critical
- **File Path:** [scam_nlp.py](file:///C:/Users/advit/OneDrive/Desktop/CallShield/callshield-ai/callshield/engine/scam_nlp.py#L105-L106) and [scam_nlp.py:L158-L167](file:///C:/Users/advit/OneDrive/Desktop/CallShield/callshield-ai/callshield/engine/scam_nlp.py#L158-L167)
- **What is wrong:** The patterns dictionary contains phrases with trailing spaces and colons (e.g., `"upi "`, `"upi:"`, and `"upi karo"`). When the engine compiles these patterns on line 166, it wraps them with word boundaries: `r'\b' + phrase + r'\b'`.
  - For `"upi "`, this becomes `r'\bupi \b'`. A word boundary `\b` following a space character requires the subsequent character in the input string to be a word character (alphanumeric or underscore). If the word "UPI" ends a sentence or is followed by punctuation (e.g. `"Send via UPI?"`), the pattern fails to match.
  - For `"upi:"`, this becomes `r'\bupi:\b'`. Because `:` is a non-word character, `:\b` requires a word character immediately following the colon, causing a match failure in normal sentences.
- **Why it matters:** It leads to false negatives where critical financial scams using UPI go undetected because of punctuation or sentence endings.
- **Exact recommended fix:** Replace the naive boundary wrapping with boundary lookarounds `(?<!\w)` and `(?!\w)` which handle trailing spaces and punctuation safely, and clean up the pattern list to remove redundant colons and spaces.
  ```python
  # Modify callshield/engine/scam_nlp.py Line 158-167
  def _compile_patterns(self):
      """Compile regex for fast matching."""
      self.compiled = {}
      for category, langs in self.PATTERNS.items():
          patterns = []
          for lang, phrases in langs.items():
              for phrase in phrases:
                  # Use lookarounds instead of \b to safely handle spaces and punctuation
                  pattern_str = r'(?<!\w)' + re.escape(phrase) + r'(?!\w)'
                  patterns.append(re.compile(pattern_str, re.IGNORECASE))
          self.compiled[category] = patterns
  ```

### Bug 3.2: Financial Boost Lockout
- **Severity:** Critical
- **File Path:** [scam_nlp.py:L322-L323](file:///C:/Users/advit/OneDrive/Desktop/CallShield/callshield-ai/callshield/engine/scam_nlp.py#L322-L323)
- **What is wrong:** The financial keyword boost is only applied if `scam_score > 0.2`:
  ```python
  if financial_keywords and scam_score > 0.2:
      scam_score = min(1.0, scam_score + 0.1)
  ```
  If a call contains a direct amount demand (e.g. `"₹25,000"`) and payment channels (e.g. `"UPI"`), but does not trigger any of the categorical NLP patterns (resulting in a base `scam_score = 0.0`), the boost is bypassed completely.
- **Why it matters:** Triggers false negatives. Scams that bypass the category checks but clearly mention payment/amounts remain flagged as `0.0` risk (SAFE).
- **Exact recommended fix:** If financial keywords are present, apply a base level of suspicion if other urgency or minor keywords triggered, and apply the boost if the score is greater than zero:
  ```python
  # Modify callshield/engine/scam_nlp.py Line 321-324
  if financial_keywords:
      if scam_score > 0.0:
          scam_score = min(1.0, scam_score + 0.1)
      elif urgency_score > 0.0 or any(v > 0.0 for v in scores.values() if v != "urgency"):
          scam_score = 0.25  # Elevate to suspicious base
  ```

### Bug 3.3: Risk Fusion Weights & Fallback Discrepancy
- **Severity:** Critical
- **File Path:** [fusion.py:L85-L91](file:///C:/Users/advit/OneDrive/Desktop/CallShield/callshield-ai/callshield/engine/fusion.py#L85-L91) and [fusion.py:L130-L135](file:///C:/Users/advit/OneDrive/Desktop/CallShield/callshield-ai/callshield/engine/fusion.py#L130-L135)
- **What is wrong:** The class documentation claims the weights are 35% scam, 25% deepfake, 20% identity mismatch. However, the `DEFAULT_WEIGHTS` dictionary in `fusion.py` uses different weights:
  ```python
  DEFAULT_WEIGHTS = {
      "scam_language": 0.45,
      "deepfake": 0.20,
      "identity_mismatch": 0.15,
      "urgency": 0.10,
      "verification_failure": 0.10,
  }
  ```
  Furthermore, the `score()` method hardcodes fallbacks inside `.get()` calls to the old weights instead of referencing `DEFAULT_WEIGHTS`:
  ```python
  self.weights.get("scam_language", 0.35) * signals.scam_language + \
  self.weights.get("deepfake", 0.25) * signals.deepfake + \
  self.weights.get("identity_mismatch", 0.20) * signals.identity_mismatch
  ```
- **Why it matters:** If custom weights are passed to the class but lack certain keys, the engine silently mixes old and new weights, leading to inconsistent scores, broken calibrations, and mathematical imbalances.
- **Exact recommended fix:** Update the `.get()` fallbacks to refer directly to `DEFAULT_WEIGHTS`:
  ```python
  # Modify callshield/engine/fusion.py Line 130-134
  raw = (
      self.weights.get("scam_language", self.DEFAULT_WEIGHTS["scam_language"]) * signals.scam_language +
      self.weights.get("deepfake", self.DEFAULT_WEIGHTS["deepfake"]) * signals.deepfake +
      self.weights.get("identity_mismatch", self.DEFAULT_WEIGHTS["identity_mismatch"]) * signals.identity_mismatch +
      self.weights.get("urgency", self.DEFAULT_WEIGHTS["urgency"]) * signals.urgency +
      self.weights.get("verification_failure", self.DEFAULT_WEIGHTS["verification_failure"]) * verify_penalty +
      signals.rule_bonus
  )
  ```

---

## 4. High-Priority Fixes

### Fix 4.1: Illegal CORS Wildcard with Credentials
- **Severity:** High
- **File Path:** [server.py:L74-L79](file:///C:/Users/advit/OneDrive/Desktop/CallShield/callshield-ai/callshield/api/server.py#L74-L79)
- **What is wrong:** The server adds CORS middleware with `allow_origins=["*"]` and `allow_credentials=True`.
- **Why it matters:** Starlette/FastAPI will throw a runtime error during requests, and browsers block these requests. Under CORS specifications, `Access-Control-Allow-Origin` cannot be wildcarded (`*`) if `Access-Control-Allow-Credentials` is set to `true`.
- **Exact recommended fix:** Specify trusted origins, or read them from environment configuration.
  ```python
  # Modify callshield/api/server.py Line 73-79
  app.add_middleware(
      CORSMiddleware,
      allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )
  ```

### Fix 4.2: Weak Static Salt in Biometric/Phone Hashing
- **Severity:** High
- **File Path:** [privacy.py:L25-L26](file:///C:/Users/advit/OneDrive/Desktop/CallShield/callshield-ai/callshield/engine/privacy.py#L25-L26)
- **What is wrong:** `PrivacyLayer.hash_phone` uses a static hardcoded salt: `"callshield_salt_v1"`, and truncates the resulting SHA-256 hash to 32 characters (`[:32]`).
- **Why it matters:** Phone numbers have very low entropy (10-12 digits). A static, hardcoded salt allows precomputation/dictionary attacks. Truncation to 32 hex characters reduces security to 128 bits, unnecessarily increasing collision risk.
- **Exact recommended fix:** Load a secure pepper from environment variables and return the full SHA-256 string.
  ```python
  # Modify callshield/engine/privacy.py Line 19-26
  @staticmethod
  def hash_phone(phone: str) -> str:
      """Hash a phone number using SHA-256 with environment pepper."""
      normalized = ''.join(c for c in phone if c.isdigit())
      pepper = os.getenv("CALLSHIELD_PHONE_PEPPER", "callshield_secure_default_pepper_v1")
      return hashlib.sha256(f"{normalized}:{pepper}".encode()).hexdigest()
  ```

### Fix 4.3: Strict Root Word Boundaries
- **Severity:** High
- **File Path:** [scam_nlp.py:L128-L135](file:///C:/Users/advit/OneDrive/Desktop/CallShield/callshield-ai/callshield/engine/scam_nlp.py#L128-L135)
- **What is wrong:** The urgency check uses strict word boundary constraints for `"urgent"`, missing adverbs like `"urgently"`. Similarly, `"accident"` fails to match plural `"accidents"`.
- **Why it matters:** Scammers frequently use slightly modified terms (like `"urgently"` or `"accidents"`), which bypass the strict boundary check, reducing the urgency score.
- **Exact recommended fix:** Add the suffixes or variants directly to the patterns list or compile with suffix support:
  ```python
  # Modify callshield/engine/scam_nlp.py
  # Under "urgency", change "urgent" to "urgently?"
  # Under "family_emergency", change "accident" to "accidents?"
  ```

### Fix 4.4: Missing Authorization on Erasure Endpoints
- **Severity:** High
- **File Path:** [server.py:L430-L474](file:///C:/Users/advit/OneDrive/Desktop/CallShield/callshield-ai/callshield/api/server.py#L430-L474)
- **What is wrong:** The endpoints `DELETE /call-summary/{call_id}` and `DELETE /user-data/{user_id}` perform destructive data deletion without requiring authentication or authorization.
- **Why it matters:** Any malicious external client can call these endpoints and purge historical data or user voice verification records.
- **Exact recommended fix:** Protect these endpoints using an admin key dependency check.
  ```python
  # Add dependency in callshield/api/server.py
  from fastapi.security import APIKeyHeader
  from fastapi import Depends
  
  API_KEY_NAME = "X-Admin-API-Key"
  api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

  async def verify_admin_key(api_key: str = Depends(api_key_header)):
      admin_key = os.getenv("CALLSHIELD_ADMIN_KEY", "default_admin_secret_key")
      if api_key != admin_key:
          raise HTTPException(status_code=401, detail="Unauthorized")
  ```

---

## 5. Medium-Priority Improvements

### Improvement 5.1: Simulator Dashboard Weights Discrepancy
- **Severity:** Medium
- **File Path:** [index.html:L538](file:///C:/Users/advit/OneDrive/Desktop/CallShield/callshield-ai/callshield/dashboard/index.html#L538)
- **What is wrong:** The frontend simulator hardcodes risk scores using old weights:
  ```javascript
  const risk = 0.35*line.scam + 0.25*line.df + 0.20*line.id + 0.10*line.urgency;
  ```
- **Why it matters:** The dashboard simulator scores diverge from actual backend values generated by `/analyze-transcript` or `/analyze-audio`, confusing testers.
- **Exact recommended fix:** Update the formula to match the weights used in `fusion.py`:
  ```javascript
  const risk = 0.45*line.scam + 0.20*line.df + 0.15*line.id + 0.10*line.urgency;
  ```

### Improvement 5.2: Memory Allocation on Fallback CNN
- **Severity:** Medium
- **File Path:** [deepfake.py:L96-L101](file:///C:/Users/advit/OneDrive/Desktop/CallShield/callshield-ai/callshield/engine/deepfake.py#L96-L101)
- **What is wrong:** If the checkpoint path does not exist but PyTorch is available, the detector still instantiates a random initialized `DeepFakeCNN` model and puts it on the GPU.
- **Why it matters:** Wastes memory and compute resources on GPU/CPU for a model that cannot make valid predictions.
- **Exact recommended fix:** Skip instantiation if the checkpoint file does not exist:
  ```python
  if not self.checkpoint_path.exists():
      self.model_status = "pipeline_implemented_no_trained_model"
      return
  ```

### Improvement 5.3: Sanitizer Temporary File Deletion Reliability
- **Severity:** Medium
- **File Path:** [privacy.py:L65-L76](file:///C:/Users/advit/OneDrive/Desktop/CallShield/callshield-ai/callshield/engine/privacy.py#L65-L76)
- **What is wrong:** `AudioSanitizer` relies on Python's destructors (`__del__`) to clean up temporary directories.
- **Why it matters:** In Python, `__del__` is not guaranteed to execute immediately or at all. If the server exits abruptly, raw audio files remain in the temp directory, leaking biometric data.
- **Exact recommended fix:** Avoid using `__del__` for cleanup. Enforce standard context managers (`try...finally` block or context wrappers) inside API methods to ensure absolute deletion.

---

## 6. Low-Priority Cleanup
- **Stale/Unused Code:** The `archives/` directory contains legacy scripts which should be isolated or removed.
- **sys.path hacks:** Multiple training and evaluation scripts use `sys.path.insert(0, str(PROJECT_ROOT))` to resolve imports. Clean this up by recommending standard Python package execution (`python -m scripts.evaluate_deepfake`).
- **Pydantic version updates:** The codebase pins Pydantic v2.5.0. Modern servers should upgrade to `pydantic>=2.7.0` for performance.

---

## 7. Security & Privacy Review
- **Threat Modeling:** The primary vulnerability is the exposure of administrative endpoints (`DELETE`) without authorization. 
- **Phone Hashing:** The phone hashing is deterministic, which is useful for matching but needs to use a secure pepper (as detailed in Fix 4.2).
- **Transcript Logs:** Transcripts are stored in the memory dictionary `CALL_HISTORY` only if `STORE_TRANSCRIPTS=true`. By default, this is disabled, conforming to data minimization standards.
- **Biometric speaker verification:** The speaker enrollment requires explicit user consent, complying with GDPR and DPDP Act. However, there is no real speaker enrollment database implemented; it is a simulation wrapper.
- **Sensitive data logging:** No passwords, phone numbers, or raw transcripts are leaked to stdout.

---

## 8. ML/Deepfake Model Review
- **Spectrogram extraction:** Audio conversion to 16 kHz mono with 128-bin log-mel extraction is a standard, robust input preparation pipeline for deepfake classification.
- **Operating Thresholds:** The operating threshold profile is calibrated at two tiers:
  - `soft_threshold = 0.1978759765625` (10% Target FPR, optimized for high recall).
  - `hard_threshold = 0.50` (Balanced threshold).
  This is a good design choice to prevent audio noise from dominating risk fusion.
- **Calibration Status:** The status resolves to `trained_model_loaded` when `deepfake_mel_cnn.pt` is present, matching the manifest.

---

## 9. Scam NLP Review
- **Combination Logic:** The engine includes multi-signal boosts (e.g., Authority + Payment Request = 0.85). This is much better than simple keyword matching.
- **False Negative Analysis:** Missed phrases containing spaces and punctuation (like `upi:`) have been addressed in Bug 3.1.
- **Hinglish/Code-switching:** The vocabulary lists cover common Hinglish phrases (e.g. `"paise transfer"`, `"gpay karo"`), but lack common variations like `"phonepe"`, `"paytm karo"`. These should be added.

---

## 10. API Review
- **Endpoint Contracts:** The FastAPI endpoints correspond cleanly to schemas defined in `schemas.py`.
- **Validation:** `/score-call` successfully rejects local files (`audio_path`) unless `CALLSHIELD_DEBUG=true` is enabled, protecting the host system.
- **Error Responses:** Errors are caught and returned as clean JSON HTTPExceptions.

---

## 11. Dashboard Review
- **Simulator connectivity:** The dashboard serves as both a client-side scenario simulation (mocked) and an interface containing operational POST forms to test `/analyze-transcript` and `/analyze-audio`.
- **Visual styling:** Excellent dark-mode glassmorphic theme. Uses an SVG circular gauge to display the risk score dynamically.

---

## 12. Documentation Review
- **README instructions:** Set up and training commands match the actual code files.
- **Metrics documentation:** The README correctly isolates Scam NLP metrics (Accuracy 99.0%, FPR 2.0%) from deepfake audio metrics.
- **Overclaiming check:** The README has been hardened to include honest claims regarding VoIP network channel distortions.

---

## 13. Evaluation Honesty Review
- **The Telephony Generalization Gap:** The audio model has been trained on ASVspoof datasets (studio-quality audio). These results do **NOT** prove equivalent performance on real-world cellular/VoIP networks. Factors such as codec compression (AMR-WB, Opus), packet loss, and acoustic noise will degrade EER and accuracy.
- **Speaker Overlap:** Split verification scripts confirm that there is **zero** speaker leakage between train/val/test splits, proving split hygiene.

---

## 14. Recommended v2.3.5 Roadmap (Immediate Bug Fixes)
1. **Fix NLP regex compilation** using lookarounds instead of standard boundary symbols (`\b`).
2. **Resolve Risk Fusion fallback weights** in `fusion.py` to match class definitions.
3. **Correct CORS wildcard configurations** to support secure credentials in FastAPI.
4. **Implement Admin API Key validation** on the data deletion endpoints.
5. **Secure phone number hashing** using a random or environment-specified pepper.

---

## 15. Recommended v2.4 Product Demo Roadmap (Truecaller Fit)
1. **Deploy ECAPA-TDNN for Speaker Enrollment:** Implement true voice embedding matching on top of the current mock.
2. **Channel Augmentation Pipeline:** Train the deepfake CNN on audio augmented with cellular codecs and noise to close the generalization gap.
3. **Telecommunication SDK Integration:** Implement a VoIP helper package to demonstrate in-call intercept possibilities.

---

## 16. Exact Commands You Ran
```powershell
# 1. Verification of python compilation
.venv\Scripts\python.exe -m compileall -q .

# 2. Executing internal scenario evaluation
.venv\Scripts\python.exe main.py test

# 3. Executing unit tests
.venv\Scripts\pytest -q

# 4. Checking data splits for train/val/test leakage
.venv\Scripts\python.exe scripts/check_deepfake_split_leakage.py --data data/deepfake
```

---

## 17. Final Readiness Rating
* **For Hackathon/Portfolio Demo:** **A** (Highly interactive, comprehensive APIs, clean visualization).
* **For Research/Academic Review:** **B+** (Clean data splits, strict split hygiene, minor calibration issues).
* **For Production Deployment:** **C-** (Needs API authorization, secure hashing, and cellular channel model tuning before live customer traffic).

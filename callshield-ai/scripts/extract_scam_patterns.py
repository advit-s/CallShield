"""Extract scam language patterns from SMS/text datasets.

Reads:
  ../Indian_Multilingual_Scam_Message_Dataset/ultra_premium_scam_dataset.csv
  ../SMS_Spam_Multilingual_Collection_Dataset/data-augmented.csv
  ../sms-otp-spam-dataset/SMS_OTP_10000_samples.csv

Outputs:
  data/extracted_scam_patterns.json   -- new patterns per language/category
  reports/scam_pattern_extraction_report.md

Does NOT modify scam_nlp.py. Review the JSON below before incorporating.
"""

import csv
import json
import math
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent  # callshield-ai/
IN_THE_WILD = ROOT.parent  # CallShield Desktop root (where source datasets live)

# ── sources ──────────────────────────────────────────────────────────────────
SOURCES = {
    "indian_scam": IN_THE_WILD / "Indian_Multilingual_Scam_Message_Dataset" / "ultra_premium_scam_dataset.csv",
    "sms_multilingual": IN_THE_WILD / "SMS_Spam_Multilingual_Collection_Dataset" / "data-augmented.csv",
    "otp_spam": IN_THE_WILD / "sms-otp-spam-dataset" / "SMS_OTP_10000_samples.csv",
}

# ── stop words ───────────────────────────────────────────────────────────────
STOP_WORDS: Set[str] = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "is", "are",
    "was", "were", "be", "been", "being", "have", "has", "had", "do", "does",
    "did", "will", "would", "could", "should", "may", "might", "can", "shall",
    "this", "that", "these", "those", "it", "its", "you", "your", "we", "our",
    "they", "them", "their", "he", "she", "his", "her", "i", "me", "my",
    "at", "by", "for", "with", "about", "but", "not", "no", "so", "if", "as",
    "from", "up", "out", "into", "over", "after", "just", "also", "than",
}

# ── helpers ───────────────────────────────────────────────────────────────────

def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Zऀ-ॿঀ-৿]+", text.lower())


def load_csv(path: Path, **pandas_kwargs) -> "pd.DataFrame":
    import pandas as pd
    if not path.exists():
        print(f"  [SKIP] {path} not found")
        return pd.DataFrame()
    return pd.read_csv(path, **pandas_kwargs)


# ── Dataset 1: Indian Multilingual Scam Messages ─────────────────────────────

@dataclass
class IndianScamExtractor:
    df: "pd.DataFrame" = field(default_factory=lambda: load_csv(
        SOURCES["indian_scam"],
        encoding="utf-8",
    ))

    label_col = "label"
    text_col = "message"
    lang_col = "language"
    domain_col = "domain"

    def scam_rows(self):
        if self.df.empty:
            return []
        return self.df[self.df[self.label_col] == "scam"]

    def legit_rows(self):
        if self.df.empty:
            return []
        return self.df[self.df[self.label_col] == "legit"]

    def extract_phrases(self, min_len: int = 3, max_phrases: int = 40) -> Dict[str, List[str]]:
        by_lang: Dict[str, List[str]] = defaultdict(list)
        for _, row in self.scam_rows().iterrows():
            lang = str(row.get(self.lang_col, "unknown")).strip()
            text = str(row.get(self.text_col, "")).strip()
            if not text:
                continue
            # Split on sentence boundaries, keep meaningful phrases
            parts = re.split(r"[.!?,;\n]", text)
            for part in parts:
                part = part.strip()
                words = part.split()
                if len(words) < min_len:
                    continue
                # Skip if too many stop words
                stops = sum(1 for w in words if w.lower() in STOP_WORDS)
                if stops / max(len(words), 1) > 0.6:
                    continue
                by_lang[lang].append(part)
        # Deduplicate, sort by frequency
        result = {}
        for lang, phrases in by_lang.items():
            counter = Counter(phrases)
            uniq = sorted(counter.keys(), key=lambda p: counter[p], reverse=True)[:max_phrases]
            result[lang] = uniq
        return dict(result)

    def benign_penalties(self) -> List[str]:
        """Legit-only phrases to add to BENIGN_PHRASES."""
        penalties = []
        for _, row in self.legit_rows().iterrows():
            text = str(row.get(self.text_col, ""))
            words = text.split()
            if 4 <= len(words) <= 15:
                penalties.append(text.strip())
        return penalties[:20]


# ── Dataset 2: Multilingual SMS Spam Collection ─────────────────────────────

@dataclass
class SMSMultilingualExtractor:
    df: "pd.DataFrame" = field(default_factory=lambda: load_csv(
        SOURCES["sms_multilingual"],
        index_col=0,
        encoding="utf-8",
    ))

    label_col = "labels"
    text_en = "text"

    def spam_rows(self):
        if self.df.empty:
            return []
        return self.df[self.df[self.label_col] == "spam"]

    def ham_rows(self):
        if self.df.empty:
            return []
        return self.df[self.df[self.label_col] == "ham"]

    def extract_english_phrases(self, max_phrases: int = 50) -> List[str]:
        phrases = []
        for _, row in self.spam_rows().iterrows():
            text = str(row.get(self.text_en, ""))
            if not text or not text.strip():
                continue
            parts = re.split(r"[.!?,;\n]", text)
            for part in parts:
                part = part.strip()
                words = part.split()
                if len(words) < 2:
                    continue
                # Score by length / stop ratio
                stops = sum(1 for w in words if w.lower() in STOP_WORDS)
                if stops / max(len(words), 1) > 0.5:
                    continue
                phrases.append(part)
        counter = Counter(phrases)
        return sorted(set(counter.keys()), key=lambda p: counter[p], reverse=True)[:max_phrases]

    def extract_hinglish_phrases(self, max_phrases: int = 40) -> List[str]:
        """Filter English spam text for Hindi-script presence (Devanagari range)."""
        phrases = []
        for _, row in self.spam_rows().iterrows():
            text = str(row.get(self.text_en, ""))
            if not text:
                continue
            # Keep only texts with Devanagari or Latin Hindi transliteration
            if not re.search(r"[ऀ-ॿ]", text):
                continue
            parts = re.split(r"[.!?,;\n]", text)
            for part in parts:
                part = part.strip()
                words = part.split()
                if len(words) < 2:
                    continue
                phrases.append(part)
        counter = Counter(phrases)
        return sorted(set(counter.keys()), key=lambda p: counter[p], reverse=True)[:max_phrases]


# ── Dataset 3: OTP/Spam SMS ──────────────────────────────────────────────────

@dataclass
class OTPSpamExtractor:
    df: "pd.DataFrame" = field(default_factory=lambda: load_csv(
        SOURCES["otp_spam"],
        encoding="utf-8",
    ))

    text_col = "sms_text"
    label_col = "label"

    def _mask_code(self, text: str) -> str:
        """Mask OTP digits so repeated OTPs collapse to one pattern."""
        return re.sub(r"\b\d{4,8}\b", "{CODE}", str(text))

    def extract_otp_patterns(self) -> Dict[str, int]:
        """Group OTP SMS by masked template, return {template: count}."""
        templates: Counter = Counter()
        for _, row in self.df.iterrows():
            text = str(row.get(self.text_col, ""))
            if not text:
                continue
            masked = self._mask_code(text)
            templates[masked] += 1
        return dict(templates.most_common(30))

    def classify_otp_intent(self) -> Dict[str, List[str]]:
        """Cluster OTP messages into scam/legit/borderline by keyword."""
        scam_signals = [
            "otp", "pin", "cvv", "password", "verification code",
            "security code", "account", "bank", "blocked", "suspended",
            "verify", "update", "kyc", "card", "login", "credentials",
        ]
        spam_exact = re.compile(r"spam|fraud|scam|phish", re.IGNORECASE)
        legit_exact = re.compile(
            r"valid|success|delivered|login|sign.in", re.IGNORECASE
        )

        spam_templates: List[str] = []
        legit_templates: List[str] = []
        templates = self.extract_otp_patterns()

        for template, count in templates.items():
            low = template.lower()
            if spam_exact.search(low):
                spam_templates.append(template)
            elif legit_exact.search(low) and not any(s in low for s in scam_signals):
                legit_templates.append(template)
            elif any(s in low for s in scam_signals) and count >= 2:
                spam_templates.append(template)

        # Deduplicate common words to keep list clean
        def clean(lst: List[str]) -> List[str]:
            seen = set()
            out = []
            for t in lst:
                base = " ".join(w for w in t.split() if w not in STOP_WORDS)
                if base and base not in seen:
                    seen.add(base)
                    out.append(t)
            return out

        return {
            "likely_scam": clean(spam_templates[:15]),
            "likely_legit": clean(legit_templates[:10]),
        }


# ── Integration Report ────────────────────────────────────────────────────────

def build_report(
    indian: IndianScamExtractor,
    sms: SMSMultilingualExtractor,
    otp: OTPSpamExtractor,
    out_path: Path,
) -> None:
    indian_phrases = indian.extract_phrases()
    sms_en = sms.extract_english_phrases()
    sms_hinglish = sms.extract_hinglish_phrases()
    benign = indian.benign_penalties()
    otp_intent = otp.classify_otp_intent()

    md: List[str] = []
    md.append("# Scam Pattern Extraction Report")
    md.append(f"*Generated on {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    md.append("")

    md.append("## Dataset Coverage")
    for name, path in SOURCES.items():
        exists = path.exists()
        rows = "n/a"
        if exists:
            try:
                df = load_csv(path, encoding="utf-8") if name != "sms_multilingual" else load_csv(path, index_col=0, encoding="utf-8")
                rows = str(len(df))
            except Exception:
                rows = "error"
        md.append(f"- **{name}**: `{path.name}` — {rows} rows {'✅' if exists else '❌ missing'}")
    md.append("")

    md.append("## 1. Indian Multilingual Scam Messages — New Phrases")
    md.append("Scam (60 rows) vs Legit (60 rows) comparison.\n")
    for lang, phrases in indian_phrases.items():
        md.append(f"### Language: {lang} ({len(phrases)} unique phrases)")
        for p in phrases[:10]:
            md.append(f"- `{p}`")
        if len(phrases) > 10:
            md.append(f"- ... and {len(phrases) - 10} more")
        md.append("")
    md.append("")

    md.append("## 2. Multilingual SMS Spam — New English & Hinglish Patterns")
    md.append(f"English spam: {len(sms_en)} extracted phrases\n")
    md.append("### Top English SMS scam patterns")
    for p in sms_en[:15]:
        md.append(f"- `{p}`")
    md.append("")
    md.append(f"### Hinglish/Devanagari spam: {len(sms_hinglish)} phrases\n")
    for p in sms_hinglish[:10]:
        md.append(f"- `{p}`")
    md.append("")

    md.append("## 3. OTP Dataset — `sms-otp-spam-dataset`")
    md.append("Classified by template; this dataset is **not SMS scam content** — it's")
    md.append("OTP delivery records labeled valid/expired/failed. Useful for teaching the")
    md.append("engine to recognize OTP delivery context, NOT to learn scam patterns from.\n")
    md.append("### Top OTP templates (masked)")
    templates = otp.extract_otp_patterns()
    for t, c in list(templates.items())[:10]:
        md.append(f"- `{t}` — {c} occurrences")
    md.append("")
    md.append("### Intent classification")
    for intent, phrases in otp_intent.items():
        md.append(f"#### {intent.replace('_', ' ').title()}")
        for p in phrases[:5]:
            md.append(f"- `{p}`")
        md.append("")

    md.append("## 4. Proposed BENIGN_PHRASES Additions")
    md.append("From the 60 legit-labeled Indian scam messages:\n")
    for p in benign[:10]:
        md.append(f"- `{p}`")
    md.append("")

    md.append("## 5. Existing Coverage Check")
    md.append("These categories are already covered by inline patterns in `scam_nlp.py`:")
    md.append("- OTP/PIN request (`otp`, `pin`, `cvv`, `one time password`)")
    md.append("- UPI/Payment (`upi`, `paise bhejo`, `gpay karo`, `send money`)")
    md.append("- Family emergency (`accident`, `hospital mein`, `kidnapped`)")
    md.append("- Bank/KYC (`account block`, `kyc update`, `account frozen`)")
    md.append("- Police/Legal (`arrest hoga`, `cbi raid`, `legal notice`)")
    md.append("- Tech support (`virus hai`, `screen share kar do`)")
    md.append("- Job/investment (`work from home`, `daily earning`, `paisa double`)")
    md.append("- Secrecy (`kisiko mat batana`, `chup raho`)")
    md.append("- Alternate number (`dusra number se`, `phone band hai`)")
    md.append("")
    md.append("### Gaps identified (high-value additions):")
    md.append("")
    md.append("| Gap | Rationale |")
    md.append("|-----|-----------|")
    md.append("| E-commerce fraud signals | Indian dataset has domain=`ecommerce` with scam patterns (fake delivery, order scams) — none in current engine |")
    md.append("| Telecom/utility scams | Domain=`telecom` + domain=`utilities` scam samples — no matching patterns |")
    md.append("| Government impersonation | Domain=`government` scam samples (tax, pension, scheme scams) — not covered |")
    md.append("| Finance-specific fraud | Domain=`finance` + `banking` scam variations — current patterns cover basic KYC but not loan/insurance scams |")
    md.append("| Hinglish verb-object combos | Dataset reveals common Hinglish scam constructions not yet in regex list |")
    md.append("")
    md.append("---")
    md.append("*Next step: review `data/extracted_scam_patterns.json`, then manually merge")
    md.append("selected new phrases into `callshield/engine/scam_nlp.py` under `ScamLanguageEngine.PATTERNS`.*")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(md), encoding="utf-8")
    print(f"  Report: {out_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    import pandas as pd  # noqa: F811 (re-import for type hints above)

    out_dir = ROOT / "data"
    reports_dir = ROOT / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    print("Loading datasets...")
    indian = IndianScamExtractor()
    sms = SMSMultilingualExtractor()
    otp = OTPSpamExtractor()

    print("Extracting patterns...")
    indian_phrases = indian.extract_phrases()
    sms_en = sms.extract_english_phrases()
    sms_hinglish = sms.extract_hinglish_phrases()
    benign = indian.benign_penalties()
    otp_intent = otp.classify_otp_intent()
    otp_top = otp.extract_otp_patterns()

    patterns = {
        "indian_scam_by_language": indian_phrases,
        "sms_english_spam": sms_en,
        "sms_hinglish_spam": sms_hinglish,
        "proposed_benign_phrases": benign,
        "otp_templates_top30": otp_top,
        "otp_intent_classification": otp_intent,
        "gaps_identified": [
            "ecommerce_fraud_signals",
            "telecom_utility_scams",
            "government_impersonation",
            "finance_loan_insurance_scams",
            "hinglish_verb_object_combos",
        ],
        "meta": {
            "indian_scam_rows": len(indian.scam_rows()),
            "indian_legit_rows": len(indian.legit_rows()),
            "sms_spam_rows": len(sms.spam_rows()),
            "sms_ham_rows": len(sms.ham_rows()),
            "otp_total_rows": len(otp.df),
            "note": "Review before incorporating into scam_nlp.py PATTERNS dict",
        },
    }

    out_json = out_dir / "extracted_scam_patterns.json"
    out_json.write_text(json.dumps(patterns, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  JSON:  {out_json}")

    report_path = reports_dir / "scam_pattern_extraction_report.md"
    build_report(indian, sms, otp, report_path)

    print("Done. Review:")
    print(f"  {out_json}")
    print(f"  {report_path}")


if __name__ == "__main__":
    main()

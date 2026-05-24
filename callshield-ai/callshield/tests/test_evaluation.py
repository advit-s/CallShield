"""CallShield Evaluation Suite.

Runs 100 test scenarios (50 normal + 50 scam) and reports:
- Accuracy, Precision, Recall, F1 score
- False Positive Rate (FPR)
- Risk score distribution by band
- Per-category performance
"""

import sys
import os
from typing import Dict, List, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sdk.callshield import CallShieldSDK
from tests.scenarios_normal import NORMAL_SCENARIOS
from tests.scenarios_scam import SCAM_SCENARIOS


def evaluate_scenarios(verbose: bool = False) -> Dict:
    """Run the full evaluation."""
    sdk = CallShieldSDK()

    # Track results
    results = {
        "normal": {  # Benign scenarios
            "true_negatives": 0,
            "false_positives": 0,
            "soft_warnings": 0,
            "hard_warnings": 0,
            "scores": [],
            "by_band": {"safe": 0, "suspicious": 0, "high": 0, "critical": 0},
        },
        "scam": {  # Scam scenarios
            "true_positives": 0,
            "false_negatives": 0,
            "soft_warnings": 0,
            "hard_warnings": 0,
            "scores": [],
            "by_band": {"safe": 0, "suspicious": 0, "high": 0, "critical": 0},
            "by_category": {cat: {"tp": 0, "fn": 0, "soft": 0, "hard": 0} for cat in set(s["category"] for s in SCAM_SCENARIOS)},
        }
    }

    print(f"{'='*70}")
    print(f"  CallShield AI - Evaluation Report v2.3.5")
    print(f"  Testing {len(NORMAL_SCENARIOS)} normal + {len(SCAM_SCENARIOS)} scam scenarios")
    print(f"{'='*70}")
    print()

    # --- Evaluate normal scenarios (should be SAFE) ---
    print("[1/2] Testing NORMAL scenarios (should be safe)...")
    for sc in NORMAL_SCENARIOS:
        result = sdk.analyze_transcript(sc["text"])
        score = result.risk_score
        band = result.risk_band
        warning = result.warning_level

        results["normal"]["scores"].append(score)
        results["normal"]["by_band"][band] += 1
        
        if warning in ("soft", "hard", "critical"):
            results["normal"]["soft_warnings"] += 1
        if warning in ("hard", "critical"):
            results["normal"]["hard_warnings"] += 1

        # Threshold: safe = <=30 (no false positive if score <= 30)
        if band in ("suspicious", "high", "critical"):
            results["normal"]["false_positives"] += 1
            if verbose:
                print(f"  FP: {sc['id']} (score={score:.1f}, band={band}, warn={warning}) - {sc['text'][:60]}...")
        else:
            results["normal"]["true_negatives"] += 1

        print(f"  {sc['id']:4s}: score={score:5.1f}  band={band:10s}  warn={warning:8s}  {sc['text'][:50]}...")

    print()

    # --- Evaluate scam scenarios (should trigger alert) ---
    print("[2/2] Testing SCAM scenarios (should raise alert)...")
    for sc in SCAM_SCENARIOS:
        result = sdk.analyze_transcript(sc["text"])
        score = result.risk_score
        band = result.risk_band
        warning = result.warning_level
        cat = sc.get("category", "unknown")

        results["scam"]["scores"].append(score)
        results["scam"]["by_band"][band] += 1
        
        if warning in ("soft", "hard", "critical"):
            results["scam"]["soft_warnings"] += 1
            if cat in results["scam"]["by_category"]:
                results["scam"]["by_category"][cat]["soft"] += 1
        if warning in ("hard", "critical"):
            results["scam"]["hard_warnings"] += 1
            if cat in results["scam"]["by_category"]:
                results["scam"]["by_category"][cat]["hard"] += 1

        # Threshold: high or critical = TP; suspicious = weak TP; safe = FN
        if band in ("high", "critical"):
            results["scam"]["true_positives"] += 1
            if cat in results["scam"]["by_category"]:
                results["scam"]["by_category"][cat]["tp"] += 1
            cat_label = "TP"
        elif band == "suspicious":
            results["scam"]["true_positives"] += 1
            if cat in results["scam"]["by_category"]:
                results["scam"]["by_category"][cat]["tp"] += 1
            cat_label = "TP*"
        else:
            results["scam"]["false_negatives"] += 1
            if cat in results["scam"]["by_category"]:
                results["scam"]["by_category"][cat]["fn"] += 1
            cat_label = "FN"
            if verbose:
                print(f"  FN: {sc['id']} (score={score:.1f}, band={band}, warn={warning}, cat={cat}) - {sc['text'][:60]}...")

        print(f"  {sc['id']:4s} [{cat_label}]: score={score:5.1f}  band={band:10s}  warn={warning:8s}  {sc['text'][:50]}...")

    # --- Compute Metrics ---
    tp = results["scam"]["true_positives"]
    fn = results["scam"]["false_negatives"]
    tn = results["normal"]["true_negatives"]
    fp = results["normal"]["false_positives"]
    
    soft_recall = results["scam"]["soft_warnings"] / (tp + fn) if (tp + fn) > 0 else 0
    hard_recall = results["scam"]["hard_warnings"] / (tp + fn) if (tp + fn) > 0 else 0
    soft_fpr = results["normal"]["soft_warnings"] / (tn + fp) if (tn + fp) > 0 else 0
    hard_fpr = results["normal"]["hard_warnings"] / (tn + fp) if (tn + fp) > 0 else 0

    # Core metrics
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    accuracy = (tp + tn) / (tp + tn + fp + fn)
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0

    # Print report
    print(f"\n{'='*70}")
    print(f"  EVALUATION RESULTS (v2.3.5)")
    print(f"{'='*70}")
    print(f"\n  Raw Detection (Risk Band >= Suspicious):")
    print(f"    Recall:              {recall:.1%} (Target: 85%+)")
    print(f"    False Positive Rate: {fpr:.1%} (Target: <10%)")
    
    print(f"\n  Warning Performance (Calibrated):")
    print(f"    Soft Warning Recall: {soft_recall:.1%} (Target: 70%+)")
    print(f"    Soft Warning FPR:    {soft_fpr:.1%}")
    print(f"    Hard Warning Recall: {hard_recall:.1%}")
    print(f"    Hard Warning FPR:    {hard_fpr:.1%} (Target: <5%)")

    print(f"\n  Overall Metrics:")
    print(f"    Accuracy:            {accuracy:.1%}")
    print(f"    Precision:           {precision:.3f}")
    print(f"    F1 Score:            {f1:.3f}")

    print(f"\n  Category-wise Confusion Analysis:")
    for cat, stats in results["scam"]["by_category"].items():
        cat_total = stats["tp"] + stats["fn"]
        cat_recall = stats["tp"] / cat_total if cat_total > 0 else 0
        cat_soft = stats["soft"] / cat_total if cat_total > 0 else 0
        status = "✅" if cat_recall >= 0.8 else "⚠️"
        print(f"    {status} {cat:28s}: {stats['tp']:3d}/{cat_total:3d} (recall={cat_recall:4.1%}) | Soft={cat_soft:4.1%}")

    if fp > 0:
        print(f"\n  False Positive Root Cause Analysis (Top 3):")
        # Identify top categories causing FPs
        fp_cues = []
        for sc in NORMAL_SCENARIOS:
            res = sdk.analyze_transcript(sc["text"])
            if res.risk_band != "safe":
                fp_cues.extend(res.why_flagged.split(", "))
        
        from collections import Counter
        top_cues = Counter(fp_cues).most_common(3)
        for cue, count in top_cues:
            print(f"    - {cue:30s}: {count:2d} occurrences")

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_positive_rate": fpr,
        "soft_warning_recall": soft_recall,
        "hard_warning_fpr": hard_fpr,
        "avg_normal_score": sum(results["normal"]["scores"]) / len(results["normal"]["scores"]),
        "avg_scam_score": sum(results["scam"]["scores"]) / len(results["scam"]["scores"]),
    }


if __name__ == "__main__":
    evaluate_scenarios(verbose=True)

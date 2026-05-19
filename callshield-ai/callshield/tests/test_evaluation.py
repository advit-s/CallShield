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
            "scores": [],
            "by_band": {"safe": 0, "suspicious": 0, "high": 0, "critical": 0},
        },
        "scam": {  # Scam scenarios
            "true_positives": 0,
            "false_negatives": 0,
            "scores": [],
            "by_band": {"safe": 0, "suspicious": 0, "high": 0, "critical": 0},
            "by_category": {cat: {"tp": 0, "fn": 0} for cat in set(s["category"] for s in SCAM_SCENARIOS)},
        }
    }

    print(f"{'='*70}")
    print(f"  CallShield AI - Evaluation Report v2.0")
    print(f"  Testing {len(NORMAL_SCENARIOS)} normal + {len(SCAM_SCENARIOS)} scam scenarios")
    print(f"{'='*70}")
    print()

    # --- Evaluate normal scenarios (should be SAFE) ---
    print("[1/2] Testing NORMAL scenarios (should be safe)...")
    for sc in NORMAL_SCENARIOS:
        result = sdk.analyze_transcript(sc["text"])
        score = result.risk_score
        band = result.risk_band

        results["normal"]["scores"].append(score)
        results["normal"]["by_band"][band] += 1

        # Threshold: safe = <=30 (no false positive if score <= 30)
        # But let's use the bands themselves: safe=safe, suspicious>=31 = FP
        if band in ("suspicious", "high", "critical"):
            results["normal"]["false_positives"] += 1
            if verbose:
                print(f"  FP: {sc['id']} (score={score:.1f}, band={band}) - {sc['text'][:60]}...")
        else:
            results["normal"]["true_negatives"] += 1

        print(f"  {sc['id']:4s}: score={score:5.1f}  band={band:10s}  {sc['text'][:50]}...")

    print()

    # --- Evaluate scam scenarios (should trigger alert) ---
    print("[2/2] Testing SCAM scenarios (should raise alert)...")
    for sc in SCAM_SCENARIOS:
        result = sdk.analyze_transcript(sc["text"])
        score = result.risk_score
        band = result.risk_band
        cat = sc.get("category", "unknown")

        results["scam"]["scores"].append(score)
        results["scam"]["by_band"][band] += 1

        # Threshold: high or critical = TP; suspicious = weak TP; safe = FN
        if band in ("high", "critical"):
            results["scam"]["true_positives"] += 1
            if cat in results["scam"]["by_category"]:
                results["scam"]["by_category"][cat]["tp"] += 1
            cat_label = "TP"
        elif band == "suspicious":
            # Suspicious is caught but at lower confidence
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
                print(f"  FN: {sc['id']} (score={score:.1f}, band={band}, cat={cat}) - {sc['text'][:60]}...")

        print(f"  {sc['id']:4s} [{cat_label}]: score={score:5.1f}  band={band:10s}  {sc['text'][:50]}...")

    # --- Compute Metrics ---
    tp = results["scam"]["true_positives"]
    fn = results["scam"]["false_negatives"]
    tn = results["normal"]["true_negatives"]
    fp = results["normal"]["false_positives"]

    # Core metrics
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    accuracy = (tp + tn) / (tp + tn + fp + fn)
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0

    # Print report
    print(f"\n{'='*70}")
    print(f"  EVALUATION RESULTS")
    print(f"{'='*70}")
    print(f"\n  Normal Analysis:")
    print(f"    Total scenarios:     {len(NORMAL_SCENARIOS)}")
    print(f"    True Negatives:      {tn}")
    print(f"    False Positives:     {fp}")
    print(f"    FPR:                 {fpr:.3f} ({fpr*100:.1f}%)")
    avg_normal = sum(results["normal"]["scores"]) / len(results["normal"]["scores"])
    print(f"    Avg Risk Score:      {avg_normal:.1f}/100")
    print(f"    Band distribution:   safe={results['normal']['by_band']['safe']}, suspicious={results['normal']['by_band']['suspicious']}, high={results['normal']['by_band']['high']}, critical={results['normal']['by_band']['critical']}")

    print(f"\n  Scam Analysis:")
    print(f"    Total scenarios:     {len(SCAM_SCENARIOS)}")
    print(f"    True Positives:      {tp}")
    print(f"    False Negatives:     {fn}")
    avg_scam = sum(results["scam"]["scores"]) / len(results["scam"]["scores"])
    print(f"    Avg Risk Score:      {avg_scam:.1f}/100")
    print(f"    Band distribution:   safe={results['scam']['by_band']['safe']}, suspicious={results['scam']['by_band']['suspicious']}, high={results['scam']['by_band']['high']}, critical={results['scam']['by_band']['critical']}")

    print(f"\n  Overall Metrics:")
    print(f"    Accuracy:            {accuracy:.1%}")
    print(f"    Precision:           {precision:.3f}")
    print(f"    Recall:              {recall:.3f}")
    print(f"    F1 Score:            {f1:.3f}")
    print(f"    False Positive Rate: {fpr:.1%}")

    print(f"\n  Per-Category Scam Performance:")
    for cat, stats in results["scam"]["by_category"].items():
        cat_total = stats["tp"] + stats["fn"]
        cat_recall = stats["tp"] / cat_total if cat_total > 0 else 0
        print(f"    {cat:30s}: {stats['tp']:3d}/{cat_total:3d} detected (recall={cat_recall:.1%})")

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_positive_rate": fpr,
        "avg_normal_score": avg_normal,
        "avg_scam_score": avg_scam,
        "normal_results": results["normal"],
        "scam_results": results["scam"],
    }


if __name__ == "__main__":
    evaluate_scenarios(verbose=True)

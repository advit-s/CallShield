"""Write a deploy-time deepfake calibration file from evaluation reports."""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List


def load_report(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def target_fpr_threshold(report: Dict) -> Dict:
    return report["metrics"]["threshold_analysis"]["target_fpr"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create deepfake calibration JSON from evaluation reports.")
    parser.add_argument("--primary-report", type=Path, required=True, help="Report used for deploy operating threshold")
    parser.add_argument("--secondary-report", type=Path, action="append", default=[], help="Additional report to record")
    parser.add_argument("--out", type=Path, default=Path("models/deepfake_calibration.json"))
    parser.add_argument("--model", type=Path, default=Path("models/deepfake_mel_cnn.pt"))
    return parser.parse_args()


def compact_report(report: Dict) -> Dict:
    metrics = report["metrics"]
    return {
        "report": report.get("test_csv"),
        "files": report.get("files"),
        "roc_auc": metrics.get("roc_auc"),
        "eer": metrics.get("eer"),
        "eer_threshold": metrics.get("eer_threshold"),
        "default_threshold": {
            "threshold": metrics.get("threshold"),
            "fpr": metrics.get("false_positive_rate"),
            "recall": metrics.get("recall"),
            "f1": metrics.get("f1"),
        },
        "target_fpr": metrics.get("threshold_analysis", {}).get("target_fpr"),
        "best_f1": metrics.get("threshold_analysis", {}).get("best_f1"),
    }


def main() -> int:
    args = parse_args()
    primary = load_report(args.primary_report)
    target = target_fpr_threshold(primary)
    secondary_reports: List[Dict] = [load_report(path) for path in args.secondary_report]

    calibration = {
        "version": "2.3.5",
        "status": "calibrated",
        "created_at": datetime.now().isoformat(),
        "model_path": str(args.model),
        "operating_threshold": target["threshold"],
        "soft_audio_threshold": target["threshold"],
        "hard_audio_threshold": 0.5,
        "target_fpr": target["target"],
        "calibration_source": str(args.primary_report),
        "note": "Conservative calibrated threshold. Scores below this threshold are not used as a deepfake fusion signal.",
        "primary_report": compact_report(primary),
        "secondary_reports": [compact_report(report) for report in secondary_reports],
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        json.dump(calibration, f, indent=2)

    print(f"Wrote calibration: {args.out}")
    print(f"Operating threshold: {target['threshold']:.4f}")
    print(f"Target FPR: {target['target']:.3f}")
    print(f"Recall at target FPR: {target['recall']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

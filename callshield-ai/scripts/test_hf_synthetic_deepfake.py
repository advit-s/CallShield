"""Score Hugging Face synthetic speech with the CallShield deepfake detector."""

import argparse
import csv
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from callshield.engine.deepfake import DeepFakeDetector


def load_metadata(metadata_csv: Path = None, input_dir: Path = None) -> list[dict]:
    if metadata_csv:
        with metadata_csv.open("r", newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    if input_dir:
        return [
            {
                "audio_path": str(path),
                "label": 1,
                "source": "huggingface:unknown",
                "speaker_id": input_dir.name,
                "text": "",
            }
            for path in sorted(input_dir.glob("*.wav"))
        ]
    raise ValueError("Provide --metadata or --input-dir")


def summarize_results(rows: list[dict], soft_threshold: float, hard_threshold: float, min_detection_rate: float) -> dict:
    scored = [row for row in rows if row.get("deepfake_score") is not None]
    scores = [float(row["deepfake_score"]) for row in scored]
    soft_hits = [score for score in scores if score >= soft_threshold]
    hard_hits = [score for score in scores if score >= hard_threshold]
    total = len(rows)
    scored_count = len(scored)
    soft_rate = len(soft_hits) / max(scored_count, 1)
    hard_rate = len(hard_hits) / max(scored_count, 1)
    recommendation = (
        "retrain_or_add_augmented_synthetic_data"
        if soft_rate < min_detection_rate
        else "passes_current_synthetic_smoke_test"
    )
    return {
        "files": total,
        "scored_files": scored_count,
        "soft_threshold": soft_threshold,
        "hard_threshold": hard_threshold,
        "min_detection_rate": min_detection_rate,
        "soft_detection_rate": soft_rate,
        "hard_detection_rate": hard_rate,
        "average_score": statistics.mean(scores) if scores else None,
        "min_score": min(scores) if scores else None,
        "max_score": max(scores) if scores else None,
        "recommendation": recommendation,
    }


def score_rows(rows: list[dict], detector: DeepFakeDetector) -> list[dict]:
    scored_rows = []
    for index, row in enumerate(rows, start=1):
        audio_path = row["audio_path"]
        print(f"[{index}/{len(rows)}] Scoring {audio_path}")
        result = detector.detect(audio_path)
        score = result.get("deepfake_score")
        scored_rows.append(
            {
                **row,
                "deepfake_score": score,
                "audio_signal_strength": result.get("audio_signal_strength"),
                "calibrated_decision": result.get("calibrated_decision"),
                "used_in_fusion": result.get("used_in_fusion"),
                "confidence": result.get("confidence"),
                "model_status": result.get("model_status"),
                "error": result.get("error", ""),
            }
        )
    return scored_rows


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "audio_path",
        "label",
        "source",
        "speaker_id",
        "text",
        "deepfake_score",
        "audio_signal_strength",
        "calibrated_decision",
        "used_in_fusion",
        "confidence",
        "model_status",
        "error",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test HF synthetic speech against CallShield deepfake detector.")
    parser.add_argument("--metadata", default="samples/hf_synthetic/metadata.csv")
    parser.add_argument("--input-dir", default=None)
    parser.add_argument("--checkpoint", default="models/deepfake_mel_cnn.pt")
    parser.add_argument("--calibration", default=None)
    parser.add_argument("--out-json", default="reports/hf_synthetic_deepfake_test.json")
    parser.add_argument("--out-csv", default="reports/hf_synthetic_deepfake_test.csv")
    parser.add_argument("--min-detection-rate", type=float, default=0.70)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    metadata = Path(args.metadata) if args.metadata else None
    input_dir = Path(args.input_dir) if args.input_dir else None
    rows = load_metadata(metadata, input_dir)
    if not rows:
        print("No audio files found.")
        return 1

    detector = DeepFakeDetector(args.checkpoint, args.calibration)
    scored_rows = score_rows(rows, detector)
    summary = summarize_results(
        scored_rows,
        soft_threshold=float(detector.soft_audio_threshold),
        hard_threshold=float(detector.hard_audio_threshold),
        min_detection_rate=args.min_detection_rate,
    )
    report = {
        "created_at": datetime.now().isoformat(),
        "checkpoint": str(detector.checkpoint_path),
        "calibration": str(detector.calibration_path),
        "model_status": detector.model_status,
        "calibration_status": detector.calibration_status,
        "summary": summary,
        "rows": scored_rows,
    }

    out_json = Path(args.out_json)
    out_csv = Path(args.out_csv)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_csv(scored_rows, out_csv)

    print("\nSynthetic deepfake detector test")
    print(f"Files: {summary['files']}")
    print(f"Scored: {summary['scored_files']}")
    print(f"Average score: {summary['average_score']}")
    print(f"Soft detection rate: {summary['soft_detection_rate']:.1%}")
    print(f"Hard detection rate: {summary['hard_detection_rate']:.1%}")
    print(f"Recommendation: {summary['recommendation']}")
    print(f"Saved JSON: {out_json}")
    print(f"Saved CSV: {out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

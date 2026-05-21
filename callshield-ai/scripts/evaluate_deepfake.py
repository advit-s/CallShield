"""Evaluate a trained CallShield deepfake checkpoint on a test CSV."""

import argparse
import csv
import json
import math
import random
import sys
from contextlib import nullcontext
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, Dataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

    class _NoGrad:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

        def __call__(self, fn):
            return fn

    class _TorchShim:
        @staticmethod
        def no_grad():
            return _NoGrad()

    torch = _TorchShim()
    nn = None
    DataLoader = None

    class Dataset:
        pass

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from callshield.engine.audio_features import AudioFeatureExtractor
from callshield.engine.deepfake import DeepFakeCNN


def limit_rows(rows: List[Tuple[Path, int]], limit: int, seed: int = 42) -> List[Tuple[Path, int]]:
    if limit <= 0 or len(rows) <= limit:
        return rows
    real = [row for row in rows if row[1] == 0]
    fake = [row for row in rows if row[1] == 1]
    rng = random.Random(seed)
    rng.shuffle(real)
    rng.shuffle(fake)
    if real and fake:
        half = limit // 2
        selected = real[:half] + fake[:limit - half]
        if len(selected) < limit:
            selected.extend((real[half:] + fake[limit - half:])[:limit - len(selected)])
    else:
        selected = rows[:limit]
    rng.shuffle(selected)
    return selected[:limit]


class DeepfakeCSVDataset(Dataset):
    def __init__(self, csv_path: Path, limit: int = None):
        self.csv_path = csv_path
        self.extractor = AudioFeatureExtractor()
        self.rows = self._load_rows(csv_path)
        if limit is not None:
            self.rows = limit_rows(self.rows, limit)

    @staticmethod
    def _load_rows(csv_path: Path) -> List[Tuple[Path, int]]:
        rows: List[Tuple[Path, int]] = []
        with csv_path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                audio_path = Path(row["audio_path"])
                if not audio_path.is_absolute():
                    audio_path = (csv_path.parent / audio_path).resolve()
                rows.append((audio_path, int(row["label"])))
        return rows

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, idx: int):
        path, label = self.rows[idx]
        y = self.extractor.load_audio(path)
        y_proc = self.extractor.preprocess_audio(y)
        log_mel = self.extractor.extract_mel(y_proc)
        tensor = torch.from_numpy(log_mel).float().unsqueeze(0)
        return tensor, torch.tensor([label], dtype=torch.float32)


def threshold_candidates(scores: Sequence[float]) -> List[float]:
    return sorted(set([0.0, 0.5, 1.0, *scores]))


def metrics_at_threshold(labels: Sequence[int], scores: Sequence[float], threshold: float) -> Dict[str, float]:
    preds = [1 if score >= threshold else 0 for score in scores]
    tp = sum(1 for y, p in zip(labels, preds) if y == 1 and p == 1)
    tn = sum(1 for y, p in zip(labels, preds) if y == 0 and p == 0)
    fp = sum(1 for y, p in zip(labels, preds) if y == 0 and p == 1)
    fn = sum(1 for y, p in zip(labels, preds) if y == 1 and p == 0)
    accuracy = (tp + tn) / max(len(labels), 1)
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-12)
    false_positive_rate = fp / max(fp + tn, 1)
    false_negative_rate = fn / max(fn + tp, 1)
    return {
        "threshold": threshold,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_positive_rate": false_positive_rate,
        "false_negative_rate": false_negative_rate,
        "confusion_matrix": {
            "tp": tp,
            "tn": tn,
            "fp": fp,
            "fn": fn,
        },
        "true_positives": tp,
        "true_negatives": tn,
        "false_positives": fp,
        "false_negatives": fn,
    }


def compute_eer_point(labels: Sequence[int], scores: Sequence[float]) -> Dict[str, float]:
    thresholds = threshold_candidates(scores)
    if not thresholds:
        return {"threshold": float("nan"), "eer": float("nan")}
    best = {"gap": 1.0, "threshold": 0.5, "eer": 1.0}
    for threshold in thresholds:
        metrics = metrics_at_threshold(labels, scores, threshold)
        fpr = metrics["false_positive_rate"]
        fnr = metrics["false_negative_rate"]
        gap = abs(fpr - fnr)
        eer = (fpr + fnr) / 2
        if gap < best["gap"]:
            best = {"gap": gap, "threshold": threshold, "eer": eer}
    return {"threshold": best["threshold"], "eer": best["eer"]}


def best_f1_threshold(labels: Sequence[int], scores: Sequence[float]) -> Dict[str, float]:
    return max(
        (metrics_at_threshold(labels, scores, threshold) for threshold in threshold_candidates(scores)),
        key=lambda item: (item["f1"], item["accuracy"], -item["false_positive_rate"]),
    )


def threshold_for_target_fpr(labels: Sequence[int], scores: Sequence[float], target_fpr: float) -> Dict[str, float]:
    candidates = [metrics_at_threshold(labels, scores, threshold) for threshold in threshold_candidates(scores)]
    under_target = [item for item in candidates if item["false_positive_rate"] <= target_fpr]
    if not under_target:
        return min(candidates, key=lambda item: item["false_positive_rate"])
    return max(under_target, key=lambda item: (item["recall"], item["f1"], item["accuracy"]))


def compute_metrics(
    labels: Sequence[int],
    scores: Sequence[float],
    threshold: float = 0.5,
    target_fpr: float = 0.10,
) -> Dict[str, float]:
    metrics = metrics_at_threshold(labels, scores, threshold)
    eer_point = compute_eer_point(labels, scores)
    metrics["eer"] = eer_point["eer"]
    metrics["eer_threshold"] = eer_point["threshold"]
    metrics["threshold_analysis"] = {
        "operating_threshold": threshold,
        "best_f1": best_f1_threshold(labels, scores),
        "target_fpr": {
            "target": target_fpr,
            **threshold_for_target_fpr(labels, scores, target_fpr),
        },
        "eer": eer_point,
    }
    try:
        from sklearn.metrics import roc_auc_score

        metrics["roc_auc"] = float(roc_auc_score(labels, scores))
    except Exception:
        metrics["roc_auc"] = float("nan")
    return metrics


def resolve_device(requested: str) -> str:
    if requested == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but torch.cuda.is_available() is false. Install a CUDA PyTorch build.")
    return requested


def print_device_info(device: str) -> None:
    print(f"Evaluating on: {device}")
    if device == "cuda":
        idx = torch.cuda.current_device()
        props = torch.cuda.get_device_properties(idx)
        total_gb = props.total_memory / (1024 ** 3)
        print(f"CUDA device: {torch.cuda.get_device_name(idx)}")
        print(f"CUDA capability: {props.major}.{props.minor}")
        print(f"CUDA memory: {total_gb:.1f} GB")


@torch.no_grad()
def evaluate(model, loader, device: str, amp: bool, threshold: float, target_fpr: float) -> Dict[str, float]:
    model.eval()
    labels: List[int] = []
    scores: List[float] = []
    criterion = nn.BCEWithLogitsLoss()
    total_loss = 0.0

    for features, targets in loader:
        features = features.to(device, non_blocking=device == "cuda")
        targets = targets.to(device, non_blocking=device == "cuda")
        context = torch.cuda.amp.autocast() if amp else nullcontext()
        with context:
            logits = model.forward_logits(features)
            loss = criterion(logits, targets)
        total_loss += loss.item() * features.size(0)
        labels.extend(int(v) for v in targets.cpu().view(-1).tolist())
        scores.extend(float(v) for v in torch.sigmoid(logits).cpu().view(-1).tolist())

    metrics = compute_metrics(labels, scores, threshold=threshold, target_fpr=target_fpr)
    metrics["loss"] = total_loss / max(len(loader.dataset), 1)
    return metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate CallShield deepfake CNN checkpoint.")
    parser.add_argument("--checkpoint", type=Path, default=Path("models/deepfake_mel_cnn.pt"))
    parser.add_argument("--test", type=Path, default=Path("data/deepfake/test.csv"), help="Test CSV path")
    parser.add_argument("--out-json", type=Path, default=Path("reports/deepfake_eval_v2_3_3.json"), help="Path to save metrics JSON")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None, help="Maximum test rows for dry-run evaluation")
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto", help="Evaluation device")
    parser.add_argument("--amp", action="store_true", help="Use CUDA automatic mixed precision")
    parser.add_argument("--pin-memory", action="store_true", help="Pin DataLoader memory for CUDA evaluation")
    parser.add_argument("--threshold", type=float, default=0.5, help="Operating threshold for confusion matrix metrics")
    parser.add_argument("--target-fpr", type=float, default=0.10, help="Report a calibrated threshold at or below this FPR")
    return parser.parse_args()


def json_safe(value):
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    return value


def main() -> int:
    args = parse_args()
    if not TORCH_AVAILABLE:
        print("torch is required for evaluation. Install requirements.txt before evaluating a checkpoint.")
        return 1

    if not args.checkpoint.exists():
        print(f"Checkpoint not found: {args.checkpoint}")
        return 1
    if not args.test.exists():
        print(f"Test CSV not found: {args.test}")
        return 1

    try:
        device = resolve_device(args.device)
    except RuntimeError as e:
        print(str(e))
        return 1
    amp = args.amp and device == "cuda"
    pin_memory = args.pin_memory or device == "cuda"
    if args.amp and device != "cuda":
        print("AMP requested but CUDA is not active; AMP disabled.")

    print_device_info(device)
    model = DeepFakeCNN().to(device)
    checkpoint = torch.load(args.checkpoint, map_location=device)
    state_dict = checkpoint.get("model_state_dict", checkpoint) if isinstance(checkpoint, dict) else checkpoint
    model.load_state_dict(state_dict)

    dataset = DeepfakeCSVDataset(args.test, limit=args.limit)
    if len(dataset) == 0:
        print("Test CSV contains no rows.")
        return 1
    loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        pin_memory=pin_memory,
        persistent_workers=args.num_workers > 0,
    )
    metrics = evaluate(model, loader, device, amp, args.threshold, args.target_fpr)

    print(f"Files:     {len(dataset)}")
    print(f"Loss:      {metrics['loss']:.4f}")
    print(f"Threshold: {metrics['threshold']:.4f}")
    print(f"Accuracy:  {metrics['accuracy']:.3f}")
    print(f"Precision: {metrics['precision']:.3f}")
    print(f"Recall:    {metrics['recall']:.3f}")
    print(f"F1:        {metrics['f1']:.3f}")
    print(f"FPR:       {metrics['false_positive_rate']:.3f}")
    print(f"FNR:       {metrics['false_negative_rate']:.3f}")
    if math.isnan(metrics["roc_auc"]):
        print("ROC-AUC:   unavailable")
    else:
        print(f"ROC-AUC:   {metrics['roc_auc']:.3f}")
    print(f"EER:       {metrics['eer']:.3f} at threshold {metrics['eer_threshold']:.4f}")
    print("Confusion Matrix:")
    print(f"  TP: {metrics['true_positives']}  FP: {metrics['false_positives']}")
    print(f"  FN: {metrics['false_negatives']}  TN: {metrics['true_negatives']}")

    best_f1 = metrics["threshold_analysis"]["best_f1"]
    target = metrics["threshold_analysis"]["target_fpr"]
    print("Threshold Calibration:")
    print(
        f"  Best F1 threshold: {best_f1['threshold']:.4f} "
        f"F1={best_f1['f1']:.3f} FPR={best_f1['false_positive_rate']:.3f} "
        f"Recall={best_f1['recall']:.3f}"
    )
    print(
        f"  Target FPR <= {target['target']:.3f}: threshold {target['threshold']:.4f} "
        f"FPR={target['false_positive_rate']:.3f} Recall={target['recall']:.3f} "
        f"F1={target['f1']:.3f}"
    )

    report = {
        "version": "2.3.4",
        "report_type": "deepfake_audio_eval",
        "created_at": datetime.now().isoformat(),
        "checkpoint": str(args.checkpoint),
        "test_csv": str(args.test),
        "limit": args.limit,
        "device": device,
        "amp": amp,
        "files": len(dataset),
        "metrics": json_safe(metrics),
        "note": "Deepfake CNN metrics are separate from scam NLP conversation-risk metrics.",
    }
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    with args.out_json.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Saved JSON: {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

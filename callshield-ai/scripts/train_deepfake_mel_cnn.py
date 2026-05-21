"""Train the CallShield log-mel CNN deepfake detector."""

import argparse
import csv
import random
import sys
from contextlib import nullcontext
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
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
    optim = None
    DataLoader = None
    WeightedRandomSampler = None

    class Dataset:
        pass

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from callshield.engine.audio_features import AudioFeatureExtractor
from callshield.engine.deepfake import DeepFakeCNN


def limit_rows(rows: List[Tuple[Path, int]], limit: int, seed: int) -> List[Tuple[Path, int]]:
    """Return a small, class-balanced-ish subset for smoke tests."""
    if limit <= 0 or len(rows) <= limit:
        return rows

    rng = random.Random(seed)
    real = [row for row in rows if row[1] == 0]
    fake = [row for row in rows if row[1] == 1]
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
    """Dataset backed by audio_path,label CSV files."""

    def __init__(self, csv_path: Path, limit: int = None, seed: int = 42):
        self.csv_path = csv_path
        self.extractor = AudioFeatureExtractor()
        self.rows = self._load_rows(csv_path)
        if limit is not None:
            self.rows = limit_rows(self.rows, limit, seed)

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


def compute_metrics(labels: Sequence[int], scores: Sequence[float]) -> Dict[str, float]:
    preds = [1 if score >= 0.5 else 0 for score in scores]
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

    metrics = {
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

    try:
        from sklearn.metrics import roc_auc_score

        metrics["roc_auc"] = float(roc_auc_score(labels, scores))
    except Exception:
        metrics["roc_auc"] = float("nan")

    metrics["eer"] = compute_eer(labels, scores)
    return metrics


def class_counts(rows: Sequence[Tuple[Path, int]]) -> Dict[int, int]:
    counts = {0: 0, 1: 0}
    for _, label in rows:
        counts[label] = counts.get(label, 0) + 1
    return counts


def make_balanced_sampler(dataset: DeepfakeCSVDataset):
    counts = class_counts(dataset.rows)
    if counts.get(0, 0) == 0 or counts.get(1, 0) == 0:
        return None

    weights = [1.0 / counts[label] for _, label in dataset.rows]
    return WeightedRandomSampler(weights, num_samples=len(weights), replacement=True)


def resolve_device(requested: str) -> str:
    if requested == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but torch.cuda.is_available() is false. Install a CUDA PyTorch build.")
    return requested


def print_device_info(device: str) -> None:
    print(f"Training on: {device}")
    if device == "cuda":
        idx = torch.cuda.current_device()
        props = torch.cuda.get_device_properties(idx)
        total_gb = props.total_memory / (1024 ** 3)
        print(f"CUDA device: {torch.cuda.get_device_name(idx)}")
        print(f"CUDA capability: {props.major}.{props.minor}")
        print(f"CUDA memory: {total_gb:.1f} GB")


def compute_eer(labels: Sequence[int], scores: Sequence[float]) -> float:
    thresholds = sorted(set(scores))
    if not thresholds:
        return float("nan")

    best = (1.0, 1.0)
    for threshold in thresholds:
        preds = [1 if score >= threshold else 0 for score in scores]
        fp = sum(1 for y, p in zip(labels, preds) if y == 0 and p == 1)
        fn = sum(1 for y, p in zip(labels, preds) if y == 1 and p == 0)
        tn = sum(1 for y, p in zip(labels, preds) if y == 0 and p == 0)
        tp = sum(1 for y, p in zip(labels, preds) if y == 1 and p == 1)
        fpr = fp / max(fp + tn, 1)
        fnr = fn / max(fn + tp, 1)
        gap = abs(fpr - fnr)
        eer = (fpr + fnr) / 2
        if gap < best[0]:
            best = (gap, eer)
    return best[1]


def run_epoch(model, loader, criterion, optimizer, device: str, amp: bool, scaler) -> float:
    model.train()
    total_loss = 0.0
    for features, labels in loader:
        features = features.to(device, non_blocking=device == "cuda")
        labels = labels.to(device, non_blocking=device == "cuda")

        optimizer.zero_grad(set_to_none=True)
        context = torch.cuda.amp.autocast() if amp else nullcontext()
        with context:
            logits = model.forward_logits(features)
            loss = criterion(logits, labels)

        if amp:
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
        else:
            loss.backward()
            optimizer.step()

        total_loss += loss.item() * features.size(0)
    return total_loss / max(len(loader.dataset), 1)


@torch.no_grad()
def evaluate(model, loader, criterion, device: str, amp: bool) -> Tuple[float, Dict[str, float]]:
    model.eval()
    total_loss = 0.0
    labels: List[int] = []
    scores: List[float] = []

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

    return total_loss / max(len(loader.dataset), 1), compute_metrics(labels, scores)


def selection_score(metric_name: str, metrics: Dict[str, float], val_loss: float) -> Tuple[float, bool]:
    """Return score and whether larger is better."""
    if metric_name == "loss":
        return val_loss, False
    if metric_name == "eer":
        return metrics["eer"], False
    return metrics[metric_name], True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train CallShield deepfake CNN from train/val CSVs.")
    parser.add_argument("--data", type=Path, default=Path("data/deepfake"), help="Directory containing train.csv and val.csv")
    parser.add_argument("--train-csv", type=Path, default=None, help="Override train CSV path")
    parser.add_argument("--val-csv", type=Path, default=None, help="Override validation CSV path")
    parser.add_argument("--checkpoint", type=Path, default=Path("models/deepfake_mel_cnn.pt"), help="Output checkpoint path")
    parser.add_argument("--init-checkpoint", type=Path, default=None, help="Optional checkpoint to warm-start/fine-tune from")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--limit", type=int, default=None, help="Maximum rows per train/val CSV for dry-run smoke tests")
    parser.add_argument("--no-balanced-sampler", action="store_true", help="Disable weighted sampling for imbalanced training CSVs")
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto", help="Training device")
    parser.add_argument("--amp", action="store_true", help="Use CUDA automatic mixed precision")
    parser.add_argument("--pin-memory", action="store_true", help="Pin DataLoader memory for CUDA training")
    parser.add_argument(
        "--selection-metric",
        choices=["f1", "roc_auc", "eer", "loss"],
        default="roc_auc",
        help="Validation metric used to save the best checkpoint",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not TORCH_AVAILABLE:
        print("torch is required for training. Install requirements.txt before running the smoke test.")
        return 1

    random.seed(args.seed)
    torch.manual_seed(args.seed)

    train_csv = args.train_csv or args.data / "train.csv"
    val_csv = args.val_csv or args.data / "val.csv"
    if not train_csv.exists() or not val_csv.exists():
        print("Missing train.csv or val.csv. Run prepare and validate scripts first.")
        return 1

    train_dataset = DeepfakeCSVDataset(train_csv, limit=args.limit, seed=args.seed)
    val_dataset = DeepfakeCSVDataset(val_csv, limit=args.limit, seed=args.seed + 1)
    if len(train_dataset) == 0 or len(val_dataset) == 0:
        print("Training and validation CSVs must both contain at least one row.")
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

    model = DeepFakeCNN().to(device)
    if args.init_checkpoint is not None:
        if not args.init_checkpoint.exists():
            print(f"Init checkpoint not found: {args.init_checkpoint}")
            return 1
        checkpoint = torch.load(args.init_checkpoint, map_location=device)
        state_dict = checkpoint.get("model_state_dict", checkpoint) if isinstance(checkpoint, dict) else checkpoint
        model.load_state_dict(state_dict)
        print(f"Loaded init checkpoint: {args.init_checkpoint}")

    criterion = nn.BCEWithLogitsLoss()
    optimizer = optim.Adam(model.parameters(), lr=args.lr)
    scaler = torch.cuda.amp.GradScaler(enabled=amp)
    sampler = None if args.no_balanced_sampler else make_balanced_sampler(train_dataset)

    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=sampler is None,
        sampler=sampler,
        num_workers=args.num_workers,
        pin_memory=pin_memory,
        persistent_workers=args.num_workers > 0,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        pin_memory=pin_memory,
        persistent_workers=args.num_workers > 0,
    )

    best_score = None
    args.checkpoint.parent.mkdir(parents=True, exist_ok=True)

    print_device_info(device)
    print(f"Train files: {len(train_dataset)}")
    print(f"Val files:   {len(val_dataset)}")
    print(f"Train class counts: {class_counts(train_dataset.rows)}")
    print(f"Val class counts:   {class_counts(val_dataset.rows)}")
    print(f"Balanced sampler: {'on' if sampler is not None else 'off'}")
    print(f"AMP: {'on' if amp else 'off'}")
    print(f"Pin memory: {'on' if pin_memory else 'off'}")
    print(f"DataLoader workers: {args.num_workers}")
    print(f"Checkpoint selection metric: {args.selection_metric}")

    for epoch in range(1, args.epochs + 1):
        train_loss = run_epoch(model, train_loader, criterion, optimizer, device, amp, scaler)
        val_loss, metrics = evaluate(model, val_loader, criterion, device, amp)

        print(
            f"Epoch {epoch:03d}/{args.epochs} "
            f"train_loss={train_loss:.4f} val_loss={val_loss:.4f} "
            f"acc={metrics['accuracy']:.3f} precision={metrics['precision']:.3f} "
            f"recall={metrics['recall']:.3f} f1={metrics['f1']:.3f} "
            f"fpr={metrics['false_positive_rate']:.3f} fnr={metrics['false_negative_rate']:.3f} "
            f"roc_auc={metrics['roc_auc']:.3f} eer={metrics['eer']:.3f}"
        )

        current_score, larger_is_better = selection_score(args.selection_metric, metrics, val_loss)
        is_better = (
            best_score is None
            or (larger_is_better and current_score > best_score)
            or (not larger_is_better and current_score < best_score)
        )
        if is_better:
            best_score = current_score
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "model_name": "log_mel_cnn_v1",
                    "version": "2.3.4",
                    "epoch": epoch,
                    "selection_metric": args.selection_metric,
                    "selection_score": current_score,
                    "metrics": metrics,
                },
                args.checkpoint,
            )
            print(f"Saved checkpoint: {args.checkpoint}")

    if not args.checkpoint.exists():
        print(f"Checkpoint was not created: {args.checkpoint}")
        return 1

    print(f"Checkpoint ready: {args.checkpoint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

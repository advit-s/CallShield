"""Prepare ADD 2023 Track 1.2 audio into CallShield train/val/test CSVs.

Only Track 1.2 is used here because it has whole-utterance binary labels:
``fake`` and ``genuine``. ADD Track 2 is partially fake segment detection and
Track 3 is source/algorithm classification, so those need different modeling.
"""

import argparse
import csv
import random
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from callshield.engine.dataset_paths import portable_audio_path

CSV_FIELDS = ["audio_path", "label", "source", "speaker_id"]
LABEL_MAP = {
    "genuine": "0",
    "bonafide": "0",
    "bona-fide": "0",
    "real": "0",
    "fake": "1",
    "spoof": "1",
    "synthetic": "1",
}


def format_audio_path(audio_path: Path, portable_paths: bool, path_root: Optional[Path]) -> str:
    if portable_paths:
        return portable_audio_path(audio_path, path_root)
    return str(audio_path.resolve())


def read_track12_labels(
    split_dir: Path,
    portable_paths: bool = False,
    path_root: Optional[Path] = None,
) -> List[dict]:
    """Read ADD 2023 Track 1.2 label.txt rows from an extracted split folder."""
    label_path = split_dir / "label.txt"
    wav_dir = split_dir / "wav"
    if not label_path.exists():
        raise FileNotFoundError(f"Missing ADD 2023 label file: {label_path}")
    if not wav_dir.exists():
        raise FileNotFoundError(f"Missing ADD 2023 wav directory: {wav_dir}")

    rows = []
    with label_path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            parts = line.strip().split()
            if len(parts) < 2:
                continue
            filename, raw_label = parts[0], parts[1].lower()
            if raw_label not in LABEL_MAP:
                raise ValueError(f"Unknown ADD 2023 label {raw_label!r} at {label_path}:{line_no}")
            audio_path = wav_dir / filename
            if not audio_path.exists():
                raise FileNotFoundError(f"Missing ADD 2023 audio file: {audio_path}")
            rows.append(
                {
                    "audio_path": format_audio_path(audio_path, portable_paths, path_root),
                    "label": LABEL_MAP[raw_label],
                    "source": "add2023_track1_2",
                    "speaker_id": "unknown",
                }
            )
    return rows


def stratified_split(rows: List[dict], test_fraction: float, seed: int) -> Dict[str, List[dict]]:
    """Split rows into val/test while preserving class balance as much as possible."""
    if not 0.0 < test_fraction < 1.0:
        raise ValueError("--test-fraction must be between 0 and 1")

    rng = random.Random(seed)
    by_label: Dict[str, List[dict]] = {}
    for row in rows:
        by_label.setdefault(row["label"], []).append(row)

    val_rows = []
    test_rows = []
    for label_rows in by_label.values():
        label_rows = list(label_rows)
        rng.shuffle(label_rows)
        test_count = max(1, int(round(len(label_rows) * test_fraction))) if len(label_rows) > 1 else 0
        test_rows.extend(label_rows[:test_count])
        val_rows.extend(label_rows[test_count:])

    rng.shuffle(val_rows)
    rng.shuffle(test_rows)
    return {"val": val_rows, "test": test_rows}


def limit_rows(rows: List[dict], limit: Optional[int], seed: int, balanced: bool) -> List[dict]:
    if limit is None or limit <= 0 or len(rows) <= limit:
        return rows

    rng = random.Random(seed)
    rows = list(rows)
    if not balanced:
        rng.shuffle(rows)
        return rows[:limit]

    by_label: Dict[str, List[dict]] = {}
    for row in rows:
        by_label.setdefault(row["label"], []).append(row)
    for label_rows in by_label.values():
        rng.shuffle(label_rows)

    labels = sorted(by_label)
    per_label = max(1, limit // max(len(labels), 1))
    selected = []
    for label in labels:
        selected.extend(by_label[label][:per_label])
    leftovers = []
    for label in labels:
        leftovers.extend(by_label[label][per_label:])
    rng.shuffle(leftovers)
    selected.extend(leftovers[: max(0, limit - len(selected))])
    rng.shuffle(selected)
    return selected[:limit]


def prepare_track12(
    root: Path,
    test_fraction: float = 0.5,
    seed: int = 42,
    portable_paths: bool = False,
    path_root: Optional[Path] = None,
    limit: Optional[int] = None,
    balanced: bool = False,
) -> Dict[str, List[dict]]:
    """Prepare extracted ADD 2023 Track 1.2 train/dev folders for CallShield."""
    track_root = root / "Track1.2"
    if not track_root.exists():
        raise FileNotFoundError(f"Expected extracted ADD Track1.2 folder at: {track_root}")

    path_root = path_root if path_root is not None else root.parent
    train_rows = read_track12_labels(track_root / "train", portable_paths, path_root)
    dev_rows = read_track12_labels(track_root / "dev", portable_paths, path_root)
    dev_split = stratified_split(dev_rows, test_fraction=test_fraction, seed=seed)

    return {
        "train": limit_rows(train_rows, limit, seed, balanced),
        "val": limit_rows(dev_split["val"], limit, seed + 1, balanced),
        "test": limit_rows(dev_split["test"], limit, seed + 2, balanced),
    }


def write_csv(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def count_labels(rows: List[dict]) -> Dict[str, int]:
    return {
        "real": sum(1 for row in rows if row["label"] == "0"),
        "fake": sum(1 for row in rows if row["label"] == "1"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare ADD 2023 Track 1.2 CSVs for CallShield.")
    parser.add_argument("--root", type=Path, required=True, help="Extracted ADD 2023 root containing Track1.2/")
    parser.add_argument("--out", type=Path, default=Path("data/deepfake_add2023"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--test-fraction", type=float, default=0.5, help="Fraction of Track1.2 dev rows used for test")
    parser.add_argument("--limit", type=int, default=None, help="Maximum rows per split for smoke runs")
    parser.add_argument("--balanced", action="store_true", help="Balance classes when applying --limit")
    parser.add_argument("--portable-paths", action="store_true", help="Write paths relative to --path-root")
    parser.add_argument("--path-root", type=Path, default=None, help="Root used for portable paths")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows_by_split = prepare_track12(
        args.root,
        test_fraction=args.test_fraction,
        seed=args.seed,
        portable_paths=args.portable_paths,
        path_root=args.path_root,
        limit=args.limit,
        balanced=args.balanced,
    )
    for split, rows in rows_by_split.items():
        write_csv(args.out / f"{split}.csv", rows)
        counts = count_labels(rows)
        print(f"{split}: {len(rows)} files real={counts['real']} fake={counts['fake']}")
    print(f"Wrote ADD 2023 Track 1.2 CSVs to: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

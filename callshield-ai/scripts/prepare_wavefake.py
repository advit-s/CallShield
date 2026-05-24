"""Prepare WaveFake-style audio directories into CallShield CSVs."""

import argparse
import csv
import random
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from callshield.engine.dataset_paths import portable_audio_path

AUDIO_EXTENSIONS = {".wav", ".flac", ".mp3", ".ogg", ".m4a"}
CSV_FIELDS = ["audio_path", "label", "source", "speaker_id"]


def infer_label(path: Path) -> Optional[int]:
    parts = {part.lower() for part in path.parts}
    if parts & {"real", "bonafide", "bona_fide", "human", "genuine"}:
        return 0
    if parts & {"fake", "spoof", "synthetic", "generated"}:
        return 1
    return None


def format_audio_path(audio_path: Path, portable_paths: bool, path_root: Optional[Path]) -> str:
    if portable_paths:
        return portable_audio_path(audio_path, path_root)
    return str(audio_path.resolve())


def collect_rows(root: Path, portable_paths: bool = False, path_root: Optional[Path] = None) -> List[dict]:
    rows = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in AUDIO_EXTENSIONS:
            continue
        label = infer_label(path)
        if label is None:
            continue
        rows.append(
            {
                "audio_path": format_audio_path(path, portable_paths, path_root),
                "label": label,
                "source": "wavefake",
                "speaker_id": "unknown",
            }
        )
    return rows


def split_rows(rows: List[dict], seed: int) -> Dict[str, List[dict]]:
    rng = random.Random(seed)
    rng.shuffle(rows)
    n = len(rows)
    train_end = int(n * 0.8)
    val_end = train_end + int(n * 0.1)
    return {
        "train": rows[:train_end],
        "val": rows[train_end:val_end],
        "test": rows[val_end:],
    }


def limit_split_rows(
    rows_by_split: Dict[str, List[dict]],
    limit: int,
    seed: int,
    balanced: bool = False,
) -> Dict[str, List[dict]]:
    """Cap each output split for quick dataset dry runs."""
    if limit <= 0:
        return rows_by_split

    rng = random.Random(seed)
    limited = {}
    for split, rows in rows_by_split.items():
        rows = list(rows)
        if balanced:
            real = [row for row in rows if int(row["label"]) == 0]
            fake = [row for row in rows if int(row["label"]) == 1]
            rng.shuffle(real)
            rng.shuffle(fake)
            per_class = limit // 2
            selected = real[:per_class] + fake[:limit - per_class]
            if len(selected) < limit:
                leftovers = real[per_class:] + fake[limit - per_class:]
                rng.shuffle(leftovers)
                selected.extend(leftovers[:limit - len(selected)])
            rng.shuffle(selected)
            limited[split] = selected[:limit]
        else:
            rng.shuffle(rows)
            limited[split] = rows[:limit]
    return limited


def read_existing(path: Path) -> List[dict]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    deduped = {}
    for row in rows:
        deduped[row["audio_path"]] = row
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(deduped.values())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare WaveFake CSVs for CallShield deepfake training.")
    parser.add_argument("--root", type=Path, required=True, help="WaveFake dataset root")
    parser.add_argument("--out", type=Path, default=Path("data/deepfake"), help="Output CSV directory")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing CSVs instead of appending")
    parser.add_argument("--limit", type=int, default=None, help="Maximum new rows to add per split for dry runs")
    parser.add_argument("--balanced", action="store_true", help="Balance real/fake rows when applying --limit")
    parser.add_argument(
        "--portable-paths",
        action="store_true",
        help="Write audio paths relative to --path-root so CSVs can move across machines.",
    )
    parser.add_argument(
        "--path-root",
        type=Path,
        default=None,
        help="Root used when writing portable relative paths. Defaults to --root parent.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path_root = args.path_root if args.path_root is not None else args.root.parent
    rows_by_split = split_rows(
        collect_rows(args.root, portable_paths=args.portable_paths, path_root=path_root),
        args.seed,
    )
    if args.limit is not None:
        rows_by_split = limit_split_rows(rows_by_split, args.limit, args.seed, balanced=args.balanced)

    for split in ("train", "val", "test"):
        path = args.out / f"{split}.csv"
        rows = rows_by_split[split]
        if not args.overwrite:
            rows = read_existing(path) + rows
        write_csv(path, rows)
        print(f"{split}: {len(rows)} files")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

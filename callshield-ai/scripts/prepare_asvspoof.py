"""Prepare ASVspoof audio into CallShield train/val/test CSVs."""

import argparse
import csv
import random
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from callshield.engine.dataset_paths import portable_audio_path

AUDIO_EXTENSIONS = {".wav", ".flac", ".mp3", ".ogg", ".m4a"}
CSV_FIELDS = ["audio_path", "label", "source", "speaker_id"]
REAL_LABELS = {"bonafide", "bona_fide", "genuine", "real", "human"}
FAKE_LABELS = {"spoof", "fake", "synthetic"}


def find_audio_files(root: Path) -> Dict[str, Path]:
    return {
        path.stem: path.resolve()
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    }


def protocol_files(root: Path, extra_files: Optional[List[Path]] = None) -> List[Path]:
    candidates = []
    for path in root.rglob("*.txt"):
        filename = path.name.lower()
        if any(token in filename for token in ("protocol", "metadata", "key", "trial", "cm")):
            candidates.append(path)
    for path in extra_files or []:
        candidates.append(path)
    return sorted(candidates)


def split_for_protocol(path: Path) -> str:
    text = str(path).lower()
    if "train" in text:
        return "train"
    if "dev" in text or "val" in text:
        return "val"
    if "eval" in text or "test" in text:
        return "test"
    if "trial_metadata" in text and ("2021" in text or "df" in text):
        return "test"
    return "unsplit"


def label_from_token(token: str) -> int:
    value = token.strip().lower()
    if value in REAL_LABELS:
        return 0
    if value in FAKE_LABELS:
        return 1
    raise ValueError(f"Unknown ASVspoof label: {token}")


def label_from_parts(parts: List[str]) -> Optional[int]:
    for token in reversed(parts):
        value = token.strip().lower()
        if value in REAL_LABELS:
            return 0
        if value in FAKE_LABELS:
            return 1
    return None


def find_audio_for_parts(parts: List[str], audio_index: Dict[str, Path]) -> Tuple[Optional[str], Optional[Path]]:
    for token in parts:
        file_id = Path(token).stem
        audio_path = audio_index.get(file_id)
        if audio_path is not None:
            return file_id, audio_path
    return None, None


def source_name(root: Path) -> str:
    root_text = str(root).lower()
    if "2021" in root_text and "df" in root_text:
        return "asvspoof2021_df"
    if "2019" in root_text:
        return "asvspoof2019"
    return "asvspoof"


def parse_line(line: str) -> List[str]:
    return line.strip().replace(",", " ").replace("\t", " ").split()


def format_audio_path(audio_path: Path, portable_paths: bool, path_root: Optional[Path]) -> str:
    if portable_paths:
        return portable_audio_path(audio_path, path_root)
    return str(audio_path.resolve())


def parse_protocols(
    root: Path,
    key_files: Optional[List[Path]] = None,
    portable_paths: bool = False,
    path_root: Optional[Path] = None,
) -> Tuple[Dict[str, List[dict]], Dict[str, int]]:
    audio_index = find_audio_files(root)
    rows = {"train": [], "val": [], "test": [], "unsplit": []}
    diagnostics = {
        "audio_files": len(audio_index),
        "protocol_files": 0,
        "unlabeled_trials": 0,
        "labeled_rows": 0,
    }

    for protocol in protocol_files(root, key_files):
        if not protocol.exists():
            print(f"WARNING: key/protocol file not found: {protocol}")
            continue
        diagnostics["protocol_files"] += 1
        split = split_for_protocol(protocol)
        with protocol.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                parts = parse_line(line)
                if not parts:
                    continue
                label = label_from_parts(parts)
                file_id, audio_path = find_audio_for_parts(parts, audio_index)

                if label is None:
                    if audio_path is not None:
                        diagnostics["unlabeled_trials"] += 1
                    continue

                if audio_path is None:
                    continue

                rows[split].append(
                    {
                        "audio_path": format_audio_path(audio_path, portable_paths, path_root),
                        "label": label,
                        "source": source_name(root),
                        "speaker_id": parts[0] if parts[0] != file_id else "unknown",
                    }
                )
                diagnostics["labeled_rows"] += 1
    return rows, diagnostics


def infer_rows_from_dirs(root: Path, portable_paths: bool = False, path_root: Optional[Path] = None) -> List[dict]:
    rows = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in AUDIO_EXTENSIONS:
            continue
        parts = {part.lower() for part in path.parts}
        if parts & {"bonafide", "bona_fide", "real", "genuine", "human"}:
            label = 0
        elif parts & {"spoof", "fake", "synthetic"}:
            label = 1
        else:
            continue
        rows.append(
            {
                "audio_path": format_audio_path(path, portable_paths, path_root),
                "label": label,
                "source": source_name(root),
                "speaker_id": "unknown",
            }
        )
    return rows


def split_key_value(row: dict, split_key: str) -> str:
    if split_key == "speaker_id":
        value = str(row.get("speaker_id", "")).strip()
        if value and value != "unknown":
            return f"speaker:{value}"
        return f"file:{Path(str(row.get('audio_path', ''))).stem}"
    if split_key == "file_id":
        return f"file:{Path(str(row.get('audio_path', ''))).stem}"
    return f"row:{row.get('audio_path', '')}"


def split_rows(rows: List[dict], seed: int, split_key: str = "speaker_id") -> Dict[str, List[dict]]:
    rng = random.Random(seed)
    rows = list(rows)
    if split_key == "none":
        rng.shuffle(rows)
        n = len(rows)
        train_end = int(n * 0.8)
        val_end = train_end + int(n * 0.1)
        return {
            "train": rows[:train_end],
            "val": rows[train_end:val_end],
            "test": rows[val_end:],
        }

    groups: Dict[str, List[dict]] = {}
    for row in rows:
        groups.setdefault(split_key_value(row, split_key), []).append(row)

    grouped_rows = list(groups.values())
    rng.shuffle(grouped_rows)
    n = len(rows)
    targets = {"train": int(n * 0.8), "val": int(n * 0.1)}
    splits = {"train": [], "val": [], "test": []}
    for group in grouped_rows:
        if len(splits["train"]) < targets["train"]:
            split = "train"
        elif len(splits["val"]) < targets["val"]:
            split = "val"
        else:
            split = "test"
        splits[split].extend(group)
    for split_rows_ in splits.values():
        rng.shuffle(split_rows_)
    return splits


def combine_all_splits(rows_by_split: Dict[str, List[dict]]) -> List[dict]:
    combined: List[dict] = []
    for split in ("train", "val", "test", "unsplit"):
        combined.extend(rows_by_split.get(split, []))
    return combined


def ensure_non_empty_test(rows_by_split: Dict[str, List[dict]], seed: int, split_key: str) -> Dict[str, List[dict]]:
    """Create an internal test split when train/val exist but test is empty."""
    if rows_by_split.get("test"):
        return rows_by_split
    combined = rows_by_split.get("train", []) + rows_by_split.get("val", [])
    if not combined:
        return rows_by_split
    return split_rows(combined, seed, split_key=split_key)


def force_split_eval_metadata(rows_by_split: Dict[str, List[dict]], seed: int, split_key: str) -> Dict[str, List[dict]]:
    """Turn eval-only labeled metadata into train/val/test for domain adaptation."""
    return split_rows(combine_all_splits(rows_by_split), seed, split_key=split_key)


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


def write_csv(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare ASVspoof CSVs for CallShield deepfake training.")
    parser.add_argument("--root", type=Path, required=True, help="ASVspoof dataset root")
    parser.add_argument("--out", type=Path, default=Path("data/deepfake"), help="Output CSV directory")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--limit", type=int, default=None, help="Maximum rows to write per split for dry runs")
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
    parser.add_argument(
        "--split-key",
        choices=["speaker_id", "file_id", "none"],
        default="speaker_id",
        help="Grouping key used when creating synthetic train/val/test splits.",
    )
    parser.add_argument(
        "--split-all",
        action="store_true",
        help="Combine all labeled rows and create train/val/test using --split-key.",
    )
    parser.add_argument(
        "--ensure-test-split",
        action="store_true",
        help="If test.csv would be empty, re-split train+val into train/val/test.",
    )
    parser.add_argument(
        "--split-eval-metadata",
        action="store_true",
        help="For labeled eval-only metadata such as ASVspoof 2021 DF, split rows into train/val/test.",
    )
    parser.add_argument(
        "--key",
        type=Path,
        action="append",
        default=[],
        help="Optional ASVspoof key/metadata/protocol file with bonafide/spoof labels. Can be passed more than once.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path_root = args.path_root if args.path_root is not None else args.root.parent
    rows_by_split, diagnostics = parse_protocols(
        args.root,
        key_files=args.key,
        portable_paths=args.portable_paths,
        path_root=path_root,
    )
    if args.split_all:
        rows_by_split = split_rows(combine_all_splits(rows_by_split), args.seed, split_key=args.split_key)
    elif args.split_eval_metadata:
        rows_by_split = force_split_eval_metadata(rows_by_split, args.seed, split_key=args.split_key)
    elif any(rows_by_split[split] for split in ("train", "val", "test")):
        unsplit = rows_by_split.pop("unsplit", [])
        if unsplit:
            extra = split_rows(unsplit, args.seed, split_key=args.split_key)
            for split, rows in extra.items():
                rows_by_split[split].extend(rows)
    elif rows_by_split["unsplit"]:
        if source_name(args.root) == "asvspoof2021_df":
            rows_by_split = {"train": [], "val": [], "test": rows_by_split["unsplit"]}
        else:
            rows_by_split = split_rows(rows_by_split["unsplit"], args.seed, split_key=args.split_key)
    else:
        inferred = infer_rows_from_dirs(args.root, portable_paths=args.portable_paths, path_root=path_root)
        rows_by_split = split_rows(inferred, args.seed, split_key=args.split_key)

    if args.ensure_test_split:
        rows_by_split = ensure_non_empty_test(rows_by_split, args.seed, split_key=args.split_key)

    if args.limit is not None:
        rows_by_split = limit_split_rows(rows_by_split, args.limit, args.seed, balanced=args.balanced)

    for split in ("train", "val", "test"):
        write_csv(args.out / f"{split}.csv", rows_by_split.get(split, []))
        print(f"{split}: {len(rows_by_split.get(split, []))} files")

    if diagnostics["unlabeled_trials"] and diagnostics["labeled_rows"] == 0:
        print(
            "WARNING: Found audio and trial IDs, but no bonafide/spoof labels. "
            "ASVspoof 2021 DF eval downloads often include only a .trl.txt list; "
            "download/place the official key or trial_metadata file to compute metrics."
        )
        print(f"Unlabeled trials matched to audio: {diagnostics['unlabeled_trials']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

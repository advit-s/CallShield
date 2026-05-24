"""Validate CallShield deepfake train/val/test CSVs before training."""

import argparse
import csv
import sys
import wave
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from callshield.engine.dataset_paths import resolve_audio_path

try:
    import soundfile as sf
except ImportError:
    sf = None


def read_csv(path: Path) -> List[dict]:
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def audio_info(path: Path) -> Tuple[Optional[float], Optional[int]]:
    if sf is not None:
        try:
            info = sf.info(str(path))
            return float(info.frames) / float(info.samplerate), int(info.samplerate)
        except Exception:
            return None, None

    try:
        with wave.open(str(path), "rb") as f:
            return f.getnframes() / float(f.getframerate()), f.getframerate()
    except Exception:
        return None, None


def file_id_from_audio_path(path_text: str) -> str:
    return Path(path_text).stem


def validate_split(name: str, path: Path, dataset_root: Optional[Path] = None) -> Dict:
    result = {
        "name": name,
        "exists": path.exists(),
        "rows": 0,
        "real": 0,
        "fake": 0,
        "missing": 0,
        "bad_labels": 0,
        "unreadable": 0,
        "durations": [],
        "sample_rates": Counter(),
        "warnings": [],
        "file_ids": set(),
        "speakers": set(),
        "sources": set(),
    }
    if not path.exists():
        return result

    rows = read_csv(path)
    result["rows"] = len(rows)
    for row in rows:
        label = str(row.get("label", "")).strip()
        if label not in {"0", "1"}:
            result["bad_labels"] += 1
            continue
        if label == "0":
            result["real"] += 1
        else:
            result["fake"] += 1

        raw_audio_path = row.get("audio_path", "")
        result["file_ids"].add(file_id_from_audio_path(raw_audio_path))
        speaker_id = str(row.get("speaker_id", "")).strip()
        if speaker_id and speaker_id != "unknown":
            result["speakers"].add(speaker_id)
        source = str(row.get("source", "")).strip()
        if source:
            result["sources"].add(source)

        audio_path = resolve_audio_path(raw_audio_path, path, dataset_root)
        if not audio_path.exists():
            result["missing"] += 1
            continue

        duration, sample_rate = audio_info(audio_path)
        if duration is None or sample_rate is None:
            result["unreadable"] += 1
            continue
        result["durations"].append(duration)
        result["sample_rates"][sample_rate] += 1

    return result


def class_balance_warning(real: int, fake: int) -> Optional[str]:
    total = real + fake
    if total == 0:
        return "no valid labeled rows found"
    if real == 0:
        return "no real clips found; labels need class 0 examples"
    if fake == 0:
        return "no fake clips found; labels need class 1 examples"

    minority_ratio = min(real, fake) / total
    if minority_ratio < 0.2:
        return f"class imbalance warning; minority class is {minority_ratio:.1%} of labeled clips"
    if minority_ratio < 0.35:
        return f"class balance caution; minority class is {minority_ratio:.1%} of labeled clips"
    return None


def pairwise_overlap(results: List[Dict], key: str) -> List[Tuple[str, str, Set[str]]]:
    overlaps = []
    for i, left in enumerate(results):
        for right in results[i + 1:]:
            shared = left[key] & right[key]
            if shared:
                overlaps.append((left["name"], right["name"], shared))
    return overlaps


def print_overlap_report(results: List[Dict]) -> bool:
    print("Leakage checks:")
    duplicate_file_ids = pairwise_overlap(results, "file_ids")
    speaker_overlaps = pairwise_overlap(results, "speakers")
    source_overlaps = pairwise_overlap(results, "sources")

    if duplicate_file_ids:
        for left, right, shared in duplicate_file_ids:
            sample = ", ".join(sorted(shared)[:5])
            print(f"WARNING: duplicate file IDs across {left}/{right}: {len(shared)} ({sample})")
    else:
        print("Duplicate file IDs across splits: 0")

    if speaker_overlaps:
        for left, right, shared in speaker_overlaps:
            sample = ", ".join(sorted(shared)[:5])
            print(f"WARNING: speaker overlap across {left}/{right}: {len(shared)} ({sample})")
    else:
        print("Speaker overlap across splits: 0")

    if source_overlaps:
        for left, right, shared in source_overlaps:
            sample = ", ".join(sorted(shared)[:5])
            print(f"Source overlap across {left}/{right}: {len(shared)} ({sample})")
    else:
        print("Source overlap across splits: 0")

    return not duplicate_file_ids


def print_split(result: Dict) -> None:
    name = result["name"].capitalize()
    if not result["exists"]:
        print(f"{name}: missing CSV")
        return
    avg_duration = (
        sum(result["durations"]) / len(result["durations"])
        if result["durations"]
        else 0.0
    )
    rates = ", ".join(f"{rate} Hz: {count}" for rate, count in result["sample_rates"].most_common(3))
    labeled = result["real"] + result["fake"]
    real_pct = result["real"] / labeled if labeled else 0.0
    fake_pct = result["fake"] / labeled if labeled else 0.0
    balance_warning = class_balance_warning(result["real"], result["fake"])
    if balance_warning:
        result["warnings"].append(balance_warning)

    print(f"{name}: {result['rows']} files")
    print(f"Real: {result['real']} ({real_pct:.1%})")
    print(f"Fake: {result['fake']} ({fake_pct:.1%})")
    print(f"Class balance: real={real_pct:.1%}, fake={fake_pct:.1%}")
    print(f"Missing files: {result['missing']}")
    print(f"Bad labels: {result['bad_labels']}")
    print(f"Unreadable files: {result['unreadable']}")
    print(f"Average duration: {avg_duration:.2f} sec")
    print(f"Sample rates: {rates or 'none'}")
    for warning in result["warnings"]:
        print(f"WARNING: {warning}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate CallShield deepfake dataset CSVs.")
    parser.add_argument("--data", type=Path, default=Path("data/deepfake"), help="Directory containing train/val/test CSVs")
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=None,
        help="Optional root for relative audio_path values. Also supports CALLSHIELD_DATASET_ROOT.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results = [
        validate_split("train", args.data / "train.csv", args.dataset_root),
        validate_split("val", args.data / "val.csv", args.dataset_root),
        validate_split("test", args.data / "test.csv", args.dataset_root),
    ]

    ready = True
    for result in results:
        print_split(result)
        print()
        ready = ready and result["exists"]
        ready = ready and result["rows"] > 0
        ready = ready and result["missing"] == 0
        ready = ready and result["bad_labels"] == 0
        ready = ready and result["unreadable"] == 0
        ready = ready and result["real"] > 0
        ready = ready and result["fake"] > 0

    ready = ready and print_overlap_report(results)
    print(f"Ready for training: {'yes' if ready else 'no'}")
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())

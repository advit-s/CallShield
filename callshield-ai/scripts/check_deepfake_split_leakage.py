"""Check CallShield deepfake CSV splits for train/val/test leakage."""

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from callshield.engine.dataset_paths import resolve_audio_path


def read_rows(csv_path: Path, dataset_root: Optional[Path]) -> List[dict]:
    if not csv_path.exists():
        return []
    rows = []
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            resolved = resolve_audio_path(row.get("audio_path", ""), csv_path, dataset_root)
            rows.append({**row, "_resolved_path": str(resolved), "_stem": resolved.stem})
    return rows


def split_values(rows: List[dict], field: str, include_unknown: bool = False) -> Set[str]:
    values = set()
    for row in rows:
        value = str(row.get(field, "")).strip()
        if value and (include_unknown or value != "unknown"):
            values.add(value)
    return values


def file_hash(path: Path) -> Optional[str]:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_values(rows: List[dict]) -> Set[str]:
    hashes = set()
    for row in rows:
        digest = file_hash(Path(row["_resolved_path"]))
        if digest:
            hashes.add(digest)
    return hashes


def pairwise_overlap(values_by_split: Dict[str, Set[str]]) -> Dict[str, Dict[str, object]]:
    names = list(values_by_split)
    result = {}
    for index, left in enumerate(names):
        for right in names[index + 1:]:
            shared = values_by_split[left] & values_by_split[right]
            result[f"{left}_vs_{right}"] = {
                "count": len(shared),
                "examples": sorted(shared)[:10],
            }
    return result


def has_overlap(report: Dict[str, Dict[str, object]]) -> bool:
    return any(item["count"] > 0 for item in report.values())


def print_section(title: str, report: Dict[str, Dict[str, object]], fail_on_overlap: bool) -> bool:
    print(f"{title}:")
    found = has_overlap(report)
    for pair, item in report.items():
        status = "WARNING" if item["count"] else "OK"
        print(f"  {status}: {pair}: {item['count']}")
        if item["examples"]:
            print(f"    examples: {', '.join(item['examples'][:5])}")
    return found if fail_on_overlap else False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check deepfake dataset splits for leakage.")
    parser.add_argument("--data", type=Path, default=Path("data/deepfake"), help="Directory with train/val/test CSVs")
    parser.add_argument("--train", type=Path, default=None, help="Override train CSV")
    parser.add_argument("--val", type=Path, default=None, help="Override val CSV")
    parser.add_argument("--test", type=Path, default=None, help="Override test CSV")
    parser.add_argument("--dataset-root", type=Path, default=None, help="Root for relative audio paths")
    parser.add_argument("--hash-audio", action="store_true", help="Also compare SHA-256 hashes of readable audio files")
    parser.add_argument("--out-json", type=Path, default=None, help="Optional JSON report path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    csvs = {
        "train": args.train or args.data / "train.csv",
        "val": args.val or args.data / "val.csv",
        "test": args.test or args.data / "test.csv",
    }
    rows_by_split = {
        split: read_rows(csv_path, args.dataset_root)
        for split, csv_path in csvs.items()
    }

    path_report = pairwise_overlap({
        split: split_values(rows, "_resolved_path", include_unknown=True)
        for split, rows in rows_by_split.items()
    })
    stem_report = pairwise_overlap({
        split: split_values(rows, "_stem", include_unknown=True)
        for split, rows in rows_by_split.items()
    })
    speaker_report = pairwise_overlap({
        split: split_values(rows, "speaker_id")
        for split, rows in rows_by_split.items()
    })
    source_report = pairwise_overlap({
        split: split_values(rows, "source", include_unknown=True)
        for split, rows in rows_by_split.items()
    })

    leakage_found = False
    print("Rows:")
    for split, rows in rows_by_split.items():
        print(f"  {split}: {len(rows)}")
    leakage_found |= print_section("Duplicate resolved paths", path_report, True)
    leakage_found |= print_section("Duplicate file stems", stem_report, True)
    leakage_found |= print_section("Speaker overlap", speaker_report, True)
    print_section("Source overlap", source_report, False)

    hash_report = {}
    if args.hash_audio:
        print("Hashing audio files. This can take a while.")
        hash_report = pairwise_overlap({
            split: hash_values(rows)
            for split, rows in rows_by_split.items()
        })
        leakage_found |= print_section("Duplicate audio hashes", hash_report, True)

    report = {
        "version": "2.3.5",
        "rows": {split: len(rows) for split, rows in rows_by_split.items()},
        "duplicate_paths": path_report,
        "duplicate_file_stems": stem_report,
        "speaker_overlap": speaker_report,
        "source_overlap": source_report,
        "duplicate_audio_hashes": hash_report,
        "hash_audio": args.hash_audio,
        "leakage_found": leakage_found,
        "ready_for_final_reporting": not leakage_found,
    }

    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        with args.out_json.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"Saved JSON: {args.out_json}")

    print(f"Leakage found: {'yes' if leakage_found else 'no'}")
    return 1 if leakage_found else 0


if __name__ == "__main__":
    raise SystemExit(main())


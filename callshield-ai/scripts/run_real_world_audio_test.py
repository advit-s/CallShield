"""Run CallShield on real-world audio samples for pilot testing.

This script is intentionally privacy-conscious: it does not copy audio, and it
does not store transcript previews/full transcripts unless explicitly requested.
"""

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from callshield.sdk import CallShieldSDK

AUDIO_EXTENSIONS = {".wav", ".flac", ".mp3", ".ogg", ".m4a", ".aac", ".webm"}
SUSPICIOUS_BANDS = {"suspicious", "high", "critical"}


def parse_bool(value: Optional[str]) -> Optional[bool]:
    if value is None or str(value).strip() == "":
        return None
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "scam", "fake", "deepfake"}:
        return True
    if normalized in {"0", "false", "no", "n", "normal", "real", "bonafide"}:
        return False
    return None


def short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]


def audio_hash(path: Path) -> Optional[str]:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def iter_audio_files(args: argparse.Namespace) -> List[Path]:
    paths: List[Path] = []
    for item in args.audio or []:
        paths.append(Path(item))
    for directory in args.audio_dir or []:
        root = Path(directory)
        paths.extend(
            path
            for path in root.rglob("*")
            if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
        )
    return sorted({path.resolve() for path in paths})


def transcript_keys(path_text: str) -> Iterable[str]:
    path = Path(path_text)
    yield str(path)
    yield str(path.resolve()) if path.exists() else str(path)
    yield path.name
    yield path.stem


def load_transcript_rows(path: Optional[Path]) -> Dict[str, dict]:
    if path is None or not path.exists():
        return {}
    rows: Dict[str, dict] = {}
    with path.open("r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            audio_path = row.get("audio_path") or row.get("file") or row.get("filename") or ""
            for key in transcript_keys(audio_path):
                rows[key] = row
    return rows


def metadata_for_audio(audio_path: Path, metadata_rows: Dict[str, dict]) -> dict:
    for key in transcript_keys(str(audio_path)):
        if key in metadata_rows:
            return metadata_rows[key]
    return {}


def transcribe_audio(audio_path: Path, model_name: str, language: Optional[str]) -> str:
    from callshield.engine.asr import ASRTranscriber

    transcriber = ASRTranscriber(model_name=model_name)
    result = transcriber.transcribe(str(audio_path), language=language)
    return result.get("text", "")


def band_counts(rows: List[dict]) -> Dict[str, int]:
    return dict(Counter(row["risk_band"] for row in rows))


def signal_counts(rows: List[dict]) -> Dict[str, int]:
    return dict(Counter(row["audio_signal_strength"] for row in rows))


def binary_metrics(labels: List[bool], predictions: List[bool]) -> Dict[str, float]:
    tp = sum(1 for y, p in zip(labels, predictions) if y and p)
    tn = sum(1 for y, p in zip(labels, predictions) if not y and not p)
    fp = sum(1 for y, p in zip(labels, predictions) if not y and p)
    fn = sum(1 for y, p in zip(labels, predictions) if y and not p)
    total = max(len(labels), 1)
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-12)
    return {
        "samples": len(labels),
        "accuracy": (tp + tn) / total,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_positive_rate": fp / max(fp + tn, 1),
        "false_negative_rate": fn / max(fn + tp, 1),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
    }


def labeled_metrics(rows: List[dict]) -> Dict[str, dict]:
    scam_rows = [row for row in rows if row["label_is_scam"] is not None]
    deepfake_rows = [row for row in rows if row["label_is_deepfake"] is not None]
    metrics: Dict[str, dict] = {}
    if scam_rows:
        metrics["scam_language_or_fusion"] = binary_metrics(
            [bool(row["label_is_scam"]) for row in scam_rows],
            [row["risk_band"] in SUSPICIOUS_BANDS for row in scam_rows],
        )
    if deepfake_rows:
        labels = [bool(row["label_is_deepfake"]) for row in deepfake_rows]
        metrics["deepfake_soft_threshold"] = binary_metrics(
            labels,
            [row["audio_signal_strength"] in {"weak", "strong"} for row in deepfake_rows],
        )
        metrics["deepfake_hard_threshold"] = binary_metrics(
            labels,
            [row["audio_signal_strength"] == "strong" for row in deepfake_rows],
        )
    return metrics


def write_csv(path: Path, rows: List[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run CallShield on real-world audio samples.")
    parser.add_argument("--audio", action="append", default=[], help="Audio file path. Can be passed multiple times.")
    parser.add_argument("--audio-dir", action="append", default=[], help="Directory of audio files.")
    parser.add_argument("--transcript", default=None, help="Transcript to use when analyzing one audio file.")
    parser.add_argument("--transcripts-csv", type=Path, default=None, help="CSV with audio_path,transcript,is_scam,is_deepfake columns.")
    parser.add_argument("--asr", action="store_true", help="Run Whisper ASR when a transcript is not provided.")
    parser.add_argument("--whisper-model", default="base", help="Whisper model for --asr.")
    parser.add_argument("--language", default=None, help="Optional ASR language hint, e.g. en or hi.")
    parser.add_argument("--out-json", type=Path, default=Path("reports/real_world_pilot.json"))
    parser.add_argument("--out-csv", type=Path, default=None)
    parser.add_argument("--include-paths", action="store_true", help="Store full local audio paths in reports.")
    parser.add_argument("--include-transcript-preview", action="store_true", help="Store a 180-character transcript preview in reports.")
    parser.add_argument("--include-transcripts", action="store_true", help="Store full transcripts in reports.")
    parser.add_argument("--hash-audio", action="store_true", help="Store SHA-256 hashes of audio files for deduplication.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    audio_files = iter_audio_files(args)
    if not audio_files:
        print("No audio files found. Pass --audio or --audio-dir.")
        return 1
    if args.transcript and len(audio_files) != 1:
        print("--transcript can only be used with exactly one audio file.")
        return 1

    metadata_rows = load_transcript_rows(args.transcripts_csv)
    sdk = CallShieldSDK()
    results = []

    for index, audio_path in enumerate(audio_files, start=1):
        metadata = metadata_for_audio(audio_path, metadata_rows)
        transcript = args.transcript if args.transcript is not None else metadata.get("transcript", "")
        asr_used = False
        if not transcript and args.asr:
            transcript = transcribe_audio(audio_path, args.whisper_model, args.language)
            asr_used = True

        result = sdk.analyze_audio(str(audio_path), transcript or "")
        audio = result.audio_analysis or {}
        row = {
            "sample_id": short_hash(str(audio_path.resolve())),
            "audio_file": audio_path.name,
            "audio_path": str(audio_path) if args.include_paths else "",
            "audio_sha256": audio_hash(audio_path) if args.hash_audio else "",
            "asr_used": asr_used,
            "transcript_preview": (transcript or "")[:180] if args.include_transcript_preview else "",
            "transcript": transcript if args.include_transcripts else "",
            "label_is_scam": parse_bool(metadata.get("is_scam")),
            "label_is_deepfake": parse_bool(metadata.get("is_deepfake")),
            "risk_score": result.risk_score,
            "risk_band": result.risk_band,
            "warning_level": result.warning_level,
            "scam_type": result.scam_type,
            "why_flagged": result.why_flagged,
            "recommended_action": result.recommended_action,
            "deepfake_score": audio.get("deepfake_score"),
            "fusion_deepfake_score": audio.get("fusion_deepfake_score"),
            "audio_signal_strength": audio.get("audio_signal_strength", "unavailable"),
            "audio_confidence": audio.get("confidence", "unavailable"),
            "soft_audio_threshold": audio.get("soft_audio_threshold"),
            "hard_audio_threshold": audio.get("hard_audio_threshold"),
            "deepfake_model_status": audio.get("model_status"),
            "deepfake_calibration_status": audio.get("calibration_status"),
            "notes": metadata.get("notes", ""),
        }
        results.append(row)
        print(
            f"[{index}/{len(audio_files)}] {audio_path.name}: "
            f"risk={row['risk_score']} {row['risk_band']} "
            f"audio={row['deepfake_score']} {row['audio_signal_strength']}"
        )

    summary = {
        "version": "2.3.5",
        "report_type": "real_world_pilot",
        "created_at": datetime.now().isoformat(),
        "samples": len(results),
        "asr_enabled": args.asr,
        "band_counts": band_counts(results),
        "audio_signal_counts": signal_counts(results),
        "labeled_metrics": labeled_metrics(results),
        "privacy_note": "No raw audio is copied. Full paths and transcript previews/full transcripts are omitted unless explicitly requested.",
        "limitations": [
            "Small real-world pilot results are not production claims.",
            "Use consented audio only.",
            "Report noisy, compressed, Hindi/Hinglish, and phone-call samples separately.",
        ],
    }

    report = {"summary": summary, "samples": results}
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    with args.out_json.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Saved JSON: {args.out_json}")

    if args.out_csv:
        write_csv(args.out_csv, results)
        print(f"Saved CSV: {args.out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

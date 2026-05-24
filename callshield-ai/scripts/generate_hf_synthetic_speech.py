"""Generate generic Hugging Face synthetic speech for CallShield detector testing.

This script is for detector evaluation only. It does not clone, imitate, or
target a real person's voice.
"""

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_TEXTS = [
    "Hello, this is a generic synthetic voice generated for CallShield detector testing.",
    "Send money urgently, my phone is broken, do not tell anyone.",
    "Your account has been credited. If this was not you, verify your identity now.",
    "This is a safety test using artificial speech, not a real person.",
]


def safe_model_slug(model_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "__", model_id).strip("_")


def load_texts(path: Path = None) -> list[str]:
    if path is None:
        return DEFAULT_TEXTS
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if text and not text.startswith("#"):
            lines.append(text)
    return lines


def resolve_device(device: str) -> int:
    if device == "cpu":
        return -1
    if device == "cuda":
        return 0
    try:
        import torch

        return 0 if torch.cuda.is_available() else -1
    except Exception:
        return -1


def configure_hf_cache(cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(cache_dir))
    os.environ.setdefault("HF_HUB_CACHE", str(cache_dir / "hub"))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(cache_dir / "transformers"))
    return cache_dir


def console_text(text: str) -> str:
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding, errors="replace")


def write_wav(path: Path, audio, sampling_rate: int) -> None:
    import numpy as np
    import soundfile as sf

    samples = np.asarray(audio, dtype=np.float32).squeeze()
    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
    if peak > 1.0:
        samples = samples / peak
    sf.write(path, samples, sampling_rate)


def generate_speech(
    model_id: str,
    texts: list[str],
    out_dir: Path,
    device: str = "auto",
    local_files_only: bool = False,
    cache_dir: Path = None,
) -> list[dict]:
    configure_hf_cache(cache_dir or (ROOT / "models" / "hf_cache"))

    from transformers import pipeline

    out_dir.mkdir(parents=True, exist_ok=True)
    pipe_kwargs = {
        "model": model_id,
        "device": resolve_device(device),
    }
    if local_files_only:
        pipe_kwargs["model_kwargs"] = {"local_files_only": True}

    print("Safety: generating generic synthetic speech only; no voice cloning or impersonation.")
    print(f"Loading Hugging Face TTS model: {model_id}")
    generator = pipeline("text-to-audio", **pipe_kwargs)

    rows = []
    model_slug = safe_model_slug(model_id)
    for index, text in enumerate(texts, start=1):
        print(console_text(f"[{index}/{len(texts)}] Generating: {text}"))
        output = generator(text)
        wav_path = out_dir / f"{model_slug}_{index:03d}.wav"
        write_wav(wav_path, output["audio"], int(output["sampling_rate"]))
        rows.append(
            {
                "audio_path": str(wav_path),
                "label": 1,
                "source": f"huggingface:{model_id}",
                "speaker_id": model_slug,
                "text": text,
            }
        )
    return rows


def write_metadata(rows: list[dict], out_dir: Path, model_id: str) -> None:
    csv_path = out_dir / "metadata.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["audio_path", "label", "source", "speaker_id", "text"],
        )
        writer.writeheader()
        writer.writerows(rows)

    manifest = {
        "created_at": datetime.now().isoformat(),
        "model": model_id,
        "purpose": "generic synthetic speech detector evaluation",
        "safety_note": "No real voice cloning or impersonation was performed.",
        "files": len(rows),
        "metadata_csv": str(csv_path),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate generic HF synthetic speech test audio.")
    parser.add_argument("--model", default="facebook/mms-tts-eng", help="HF TTS model id or local folder.")
    parser.add_argument("--texts-file", default=None, help="Optional text file with one prompt per line.")
    parser.add_argument("--out-dir", default="samples/hf_synthetic", help="Output folder.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of prompts.")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--cache-dir", default="models/hf_cache", help="Project-local Hugging Face cache folder.")
    parser.add_argument("--local-files-only", action="store_true", help="Load model only from local HF cache/folder.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    texts = load_texts(Path(args.texts_file) if args.texts_file else None)
    if args.limit:
        texts = texts[: args.limit]
    if not texts:
        print("No texts to synthesize.")
        return 1
    out_dir = Path(args.out_dir)
    rows = generate_speech(
        model_id=args.model,
        texts=texts,
        out_dir=out_dir,
        device=args.device,
        local_files_only=args.local_files_only,
        cache_dir=Path(args.cache_dir),
    )
    write_metadata(rows, out_dir, args.model)
    print(f"\nGenerated {len(rows)} synthetic audio files in {out_dir}")
    print(f"Metadata: {out_dir / 'metadata.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Download a Hugging Face ASR model snapshot for offline CallShield use."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from callshield.engine.asr import (
    DEFAULT_HF_ASR_MODEL,
    default_hf_asr_root,
    hf_asr_model_slug,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download a Hugging Face ASR model to models/hf_asr for offline inference."
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_HF_ASR_MODEL,
        help="Hugging Face model id to download.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Exact output folder. Defaults to models/hf_asr/<safe-model-id>.",
    )
    parser.add_argument(
        "--revision",
        default=None,
        help="Optional Hugging Face revision, branch, or commit.",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Optional Hugging Face token for gated/private models.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("huggingface-hub is not installed. Run: python -m pip install huggingface-hub")
        return 1

    out_dir = Path(args.out) if args.out else default_hf_asr_root() / hf_asr_model_slug(args.model)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading Hugging Face ASR model: {args.model}")
    print(f"Local folder: {out_dir}")
    snapshot_download(
        repo_id=args.model,
        revision=args.revision,
        token=args.token,
        local_dir=str(out_dir),
        local_dir_use_symlinks=False,
    )

    manifest = {
        "model": args.model,
        "revision": args.revision,
        "local_dir": str(out_dir),
        "downloaded_at": datetime.now().isoformat(),
        "usage": {
            "CALLSHIELD_ASR_BACKEND": "huggingface",
            "CALLSHIELD_ASR_OFFLINE": "true",
            "CALLSHIELD_HF_ASR_LOCAL_DIR": str(out_dir),
        },
    }
    manifest_path = out_dir / "callshield_offline_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("\nOffline model is ready.")
    print("Start CallShield with:")
    print('$env:CALLSHIELD_ASR_BACKEND="huggingface"')
    print('$env:CALLSHIELD_ASR_OFFLINE="true"')
    print(f'$env:CALLSHIELD_HF_ASR_LOCAL_DIR="{out_dir}"')
    print(".\\.venv\\Scripts\\python.exe main.py server")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

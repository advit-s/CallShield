"""CallShield AI Model Verification and Retrieval Workflow.

Verifies local model checkpoint integrity against model_manifest.json
and performs local recovery from archives or downloads if needed.
"""

import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "models" / "model_manifest.json"


def compute_sha256(filepath: Path) -> str:
    """Compute the SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest().upper()


def main() -> int:
    print("=== CallShield Model Verification Workflow ===")
    if not MANIFEST_PATH.exists():
        print(f"[ERROR] Model manifest not found at: {MANIFEST_PATH}")
        return 1

    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as exc:
        print(f"[ERROR] Failed to parse model manifest: {exc}")
        return 1

    expected_file = manifest.get("deployed_checkpoint", "models/deepfake_mel_cnn.pt")
    expected_hash = manifest.get("deployed_checkpoint_sha256", "")
    target_path = ROOT / expected_file

    print(f"Target Checkpoint: {expected_file}")
    print(f"Expected SHA-256:  {expected_hash}")

    # Check local file
    if target_path.exists():
        print("Computing local checkpoint hash...")
        local_hash = compute_sha256(target_path)
        print(f"Local SHA-256:     {local_hash}")
        
        if local_hash == expected_hash:
            print("\n[SUCCESS] Checkpoint verified! Integrity check passed.")
            return 0
        else:
            print("\n[WARNING] Checkpoint hash mismatch! The local file may be corrupted or outdated.")
    else:
        print("\n[INFO] Checkpoint file is missing from models/ directory.")

    # Try local recovery from archives
    source_file = manifest.get("source_checkpoint", "models/archives/deepfake_mel_cnn_combined_2019_2021_add2023.pt")
    archive_path = ROOT / source_file
    
    if archive_path.exists():
        print(f"Attempting local recovery from archive: {source_file} ...")
        archive_hash = compute_sha256(archive_path)
        
        if archive_hash == expected_hash:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(archive_path, target_path)
            print("[SUCCESS] Checkpoint recovered successfully from archives and verified!")
            return 0
        else:
            print(f"[WARNING] Archive file {source_file} also has a hash mismatch.")
    
    print("\n[ERROR] Model checkpoint could not be recovered locally.")
    print("To manually install the model checkpoint, please obtain 'deepfake_mel_cnn.pt'")
    print("from CallShield's release downloads or Hugging Face dataset, and place it in:")
    print(f"  {target_path}")
    print(f"Verify that its SHA-256 matches: {expected_hash}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

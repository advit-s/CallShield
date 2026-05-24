"""Dataset path helpers for portable deepfake CSVs."""

import os
from pathlib import Path
from typing import Iterable, Optional

DATASET_ROOT_ENV = "CALLSHIELD_DATASET_ROOT"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _candidate_roots(dataset_root: Optional[Path] = None) -> Iterable[Path]:
    if dataset_root is not None:
        yield Path(dataset_root)

    env_value = os.environ.get(DATASET_ROOT_ENV, "")
    for item in env_value.split(os.pathsep):
        if item.strip():
            yield Path(item.strip())


def resolve_audio_path(
    audio_path: str,
    csv_path: Optional[Path] = None,
    dataset_root: Optional[Path] = None,
) -> Path:
    """Resolve an audio path from absolute, dataset-root-relative, or CSV-relative form."""
    path = Path(audio_path)
    if path.is_absolute():
        return path

    candidates = []
    for root in _candidate_roots(dataset_root):
        candidates.append((root / path).resolve())
    if csv_path is not None:
        candidates.append((Path(csv_path).parent / path).resolve())
    candidates.append((PROJECT_ROOT / path).resolve())

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0] if candidates else path.resolve()


def portable_audio_path(audio_path: Path, path_root: Optional[Path]) -> str:
    """Return a portable relative path when possible, otherwise the absolute path."""
    resolved = Path(audio_path).resolve()
    if path_root is None:
        return str(resolved)

    try:
        return str(resolved.relative_to(Path(path_root).resolve()))
    except ValueError:
        return str(resolved)


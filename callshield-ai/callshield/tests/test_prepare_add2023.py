"""Tests for ADD 2023 CSV preparation."""

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _load_prepare_add2023():
    script = ROOT / "scripts" / "prepare_add2023.py"
    spec = importlib.util.spec_from_file_location("prepare_add2023", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_prepare_add2023_track12_maps_labels_and_splits_dev(tmp_path):
    module = _load_prepare_add2023()
    root = tmp_path / "ADD2023"

    for split in ("train", "dev"):
        wav_dir = root / "Track1.2" / split / "wav"
        wav_dir.mkdir(parents=True)
        for idx in range(4):
            (wav_dir / f"ADD2023_T1.2_{split[0].upper()}_{idx:08d}.wav").write_bytes(b"RIFF....WAVE")

    (root / "Track1.2" / "train" / "label.txt").write_text(
        "\n".join(
            [
                "ADD2023_T1.2_T_00000000.wav fake",
                "ADD2023_T1.2_T_00000001.wav genuine",
                "ADD2023_T1.2_T_00000002.wav fake",
                "ADD2023_T1.2_T_00000003.wav genuine",
            ]
        ),
        encoding="utf-8",
    )
    (root / "Track1.2" / "dev" / "label.txt").write_text(
        "\n".join(
            [
                "ADD2023_T1.2_D_00000000.wav fake",
                "ADD2023_T1.2_D_00000001.wav genuine",
                "ADD2023_T1.2_D_00000002.wav fake",
                "ADD2023_T1.2_D_00000003.wav genuine",
            ]
        ),
        encoding="utf-8",
    )

    rows_by_split = module.prepare_track12(root, test_fraction=0.5, seed=7)

    assert len(rows_by_split["train"]) == 4
    assert len(rows_by_split["val"]) == 2
    assert len(rows_by_split["test"]) == 2
    assert {row["label"] for row in rows_by_split["train"]} == {"0", "1"}
    assert {row["source"] for row in rows_by_split["train"]} == {"add2023_track1_2"}

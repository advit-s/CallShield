"""Dataset path portability tests."""

from pathlib import Path

from callshield.engine.dataset_paths import DATASET_ROOT_ENV, resolve_audio_path


def test_resolve_audio_path_uses_dataset_root_env(tmp_path, monkeypatch):
    dataset_root = tmp_path / "datasets"
    audio_path = dataset_root / "ASVspoof_2019_LA" / "clip.flac"
    audio_path.parent.mkdir(parents=True)
    audio_path.write_bytes(b"audio")

    csv_path = tmp_path / "data" / "deepfake" / "train.csv"
    csv_path.parent.mkdir(parents=True)
    monkeypatch.setenv(DATASET_ROOT_ENV, str(dataset_root))

    resolved = resolve_audio_path("ASVspoof_2019_LA/clip.flac", csv_path)

    assert resolved == audio_path.resolve()


def test_resolve_audio_path_falls_back_to_csv_relative(tmp_path, monkeypatch):
    csv_path = tmp_path / "data" / "deepfake" / "train.csv"
    audio_path = csv_path.parent / "clip.flac"
    audio_path.parent.mkdir(parents=True)
    audio_path.write_bytes(b"audio")
    monkeypatch.delenv(DATASET_ROOT_ENV, raising=False)

    resolved = resolve_audio_path("clip.flac", csv_path)

    assert resolved == audio_path.resolve()


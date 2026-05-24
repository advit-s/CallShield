"""Tests for Hugging Face synthetic speech detector workflow helpers."""

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _load_script(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_synthetic_generator_safe_slug_and_default_texts():
    generator = _load_script("generate_hf_synthetic_speech.py")

    assert generator.safe_model_slug("facebook/mms-tts-eng") == "facebook__mms-tts-eng"
    assert generator.DEFAULT_TEXTS
    assert all("clone" not in text.lower() for text in generator.DEFAULT_TEXTS)


def test_synthetic_generator_configures_project_local_hf_cache(tmp_path, monkeypatch):
    generator = _load_script("generate_hf_synthetic_speech.py")
    monkeypatch.delenv("HF_HOME", raising=False)
    monkeypatch.delenv("HF_HUB_CACHE", raising=False)
    monkeypatch.delenv("TRANSFORMERS_CACHE", raising=False)

    cache_dir = generator.configure_hf_cache(tmp_path / "hf_cache")

    assert cache_dir.exists()
    assert "hf_cache" in generator.os.environ["HF_HOME"]
    assert generator.os.environ["HF_HUB_CACHE"].endswith("hub")
    assert generator.os.environ["TRANSFORMERS_CACHE"].endswith("transformers")


def test_synthetic_generator_console_text_is_windows_safe(monkeypatch):
    generator = _load_script("generate_hf_synthetic_speech.py")

    class FakeStdout:
        encoding = "cp1252"

    monkeypatch.setattr(generator.sys, "stdout", FakeStdout())

    assert "?" in generator.console_text("कृत्रिम आवाज")


def test_synthetic_detection_summary_recommends_retraining_when_scores_are_low():
    tester = _load_script("test_hf_synthetic_deepfake.py")
    rows = [
        {"deepfake_score": 0.10},
        {"deepfake_score": 0.12},
        {"deepfake_score": 0.15},
    ]

    summary = tester.summarize_results(
        rows,
        soft_threshold=0.2,
        hard_threshold=0.5,
        min_detection_rate=0.70,
    )

    assert summary["soft_detection_rate"] == 0.0
    assert summary["recommendation"] == "retrain_or_add_augmented_synthetic_data"


def test_synthetic_detection_summary_passes_when_scores_are_high():
    tester = _load_script("test_hf_synthetic_deepfake.py")
    rows = [
        {"deepfake_score": 0.8},
        {"deepfake_score": 0.9},
        {"deepfake_score": 0.95},
    ]

    summary = tester.summarize_results(
        rows,
        soft_threshold=0.2,
        hard_threshold=0.5,
        min_detection_rate=0.70,
    )

    assert summary["soft_detection_rate"] == 1.0
    assert summary["hard_detection_rate"] == 1.0
    assert summary["recommendation"] == "passes_current_synthetic_smoke_test"

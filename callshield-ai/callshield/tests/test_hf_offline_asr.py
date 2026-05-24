"""Offline Hugging Face ASR model loading tests."""

from pathlib import Path

from callshield.engine import asr as asr_module
from callshield.engine.asr import ASRTranscriber, resolve_hf_asr_model


def test_resolve_hf_asr_prefers_downloaded_local_snapshot(tmp_path):
    local_root = tmp_path / "models" / "hf_asr"
    local_model = local_root / "Org__Whisper-Test"
    local_model.mkdir(parents=True)
    (local_model / "config.json").write_text("{}", encoding="utf-8")

    resolved = resolve_hf_asr_model(
        model_name="Org/Whisper-Test",
        local_root=local_root,
        prefer_local=True,
    )

    assert resolved == str(local_model)


def test_hf_asr_pipeline_uses_local_files_only(monkeypatch, tmp_path):
    local_model = tmp_path / "hf_model"
    local_model.mkdir()
    (local_model / "config.json").write_text("{}", encoding="utf-8")
    calls = {}

    def fake_pipeline(task, **kwargs):
        calls["task"] = task
        calls.update(kwargs)
        return object()

    monkeypatch.setattr(asr_module, "pipeline", fake_pipeline)
    monkeypatch.setattr(asr_module, "torch", None)

    transcriber = ASRTranscriber(
        model_name=str(local_model),
        backend="huggingface",
        local_files_only=True,
    )

    assert transcriber.model is not None
    assert calls["task"] == "automatic-speech-recognition"
    assert calls["model"] == str(local_model)
    assert calls["model_kwargs"]["local_files_only"] is True

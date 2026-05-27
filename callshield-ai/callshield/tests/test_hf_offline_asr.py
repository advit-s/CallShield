"""Offline Hugging Face ASR model loading tests."""

from pathlib import Path

from callshield.api import server
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


def test_hf_asr_retries_with_slow_tokenizer_when_fast_tokenizer_fails(monkeypatch, tmp_path):
    local_model = tmp_path / "hf_model"
    local_model.mkdir()
    (local_model / "config.json").write_text("{}", encoding="utf-8")
    calls = {"pipeline": 0}

    class FakeTokenizer:
        pass

    class FakeFeatureExtractor:
        pass

    class FakeModel:
        pass

    def fake_pipeline(task, **kwargs):
        calls["pipeline"] += 1
        if calls["pipeline"] == 1:
            raise ValueError("data did not match any variant of untagged enum ModelWrapper")
        calls["retry_kwargs"] = kwargs
        return object()

    class FakeAutoTokenizer:
        @staticmethod
        def from_pretrained(model_name, **kwargs):
            calls["tokenizer_kwargs"] = kwargs
            return FakeTokenizer()

    class FakeAutoFeatureExtractor:
        @staticmethod
        def from_pretrained(model_name, **kwargs):
            calls["feature_extractor_kwargs"] = kwargs
            return FakeFeatureExtractor()

    class FakeAutoModel:
        @staticmethod
        def from_pretrained(model_name, **kwargs):
            calls["model_kwargs"] = kwargs
            return FakeModel()

    monkeypatch.setattr(asr_module, "pipeline", fake_pipeline)
    monkeypatch.setattr(asr_module, "AutoTokenizer", FakeAutoTokenizer)
    monkeypatch.setattr(asr_module, "AutoFeatureExtractor", FakeAutoFeatureExtractor)
    monkeypatch.setattr(asr_module, "AutoModelForSpeechSeq2Seq", FakeAutoModel)
    monkeypatch.setattr(asr_module, "torch", None)

    transcriber = ASRTranscriber(
        model_name=str(local_model),
        backend="huggingface",
        local_files_only=True,
    )

    assert transcriber.model is not None
    assert calls["pipeline"] == 2
    assert calls["tokenizer_kwargs"]["use_fast"] is False
    assert calls["tokenizer_kwargs"]["local_files_only"] is True
    assert calls["model_kwargs"]["local_files_only"] is True
    assert isinstance(calls["retry_kwargs"]["tokenizer"], FakeTokenizer)


def test_server_defaults_to_local_hindi_hinglish_asr_when_snapshot_exists(monkeypatch, tmp_path):
    local_model = tmp_path / "models" / "hf_asr" / "Oriserve__Whisper-Hindi2Hinglish-Swift"
    local_model.mkdir(parents=True)
    (local_model / "config.json").write_text("{}", encoding="utf-8")

    monkeypatch.delenv("CALLSHIELD_ASR_BACKEND", raising=False)
    monkeypatch.delenv("CALLSHIELD_ASR_OFFLINE", raising=False)
    monkeypatch.delenv("CALLSHIELD_HF_ASR_LOCAL_DIR", raising=False)
    monkeypatch.setattr(server, "default_hf_asr_root", lambda: tmp_path / "models" / "hf_asr")

    config = server._asr_runtime_config()

    assert config["backend"] == "huggingface"
    assert config["local_files_only"] is True
    assert config["model_name"] == str(local_model)

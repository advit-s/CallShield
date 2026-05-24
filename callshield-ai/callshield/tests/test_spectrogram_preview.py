"""Log-mel spectrogram preview tests."""

import base64
import wave
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from callshield.api import server
from callshield.api.server import app
from callshield.engine.audio_features import AudioFeatureExtractor


client = TestClient(app)


def _write_tone(path: Path, seconds: float = 1.0) -> None:
    sample_rate = 16000
    t = np.arange(int(sample_rate * seconds), dtype=np.float32) / sample_rate
    wave_data = (0.25 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    pcm = np.clip(wave_data * 32767, -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())


def test_audio_feature_extractor_returns_png_spectrogram_preview():
    extractor = AudioFeatureExtractor()
    sample_rate = extractor.sample_rate
    t = np.arange(sample_rate, dtype=np.float32) / sample_rate
    y = (0.25 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

    preview = extractor.spectrogram_preview(y)

    image_bytes = base64.b64decode(preview["image_base64"])
    assert preview["content_type"] == "image/png"
    assert preview["n_mels"] == extractor.n_mels
    assert preview["frames"] > 0
    assert image_bytes.startswith(b"\x89PNG\r\n\x1a\n")


def test_analyze_audio_response_includes_spectrogram_preview(monkeypatch, tmp_path):
    class FakeASR:
        def transcribe(self, audio_path, language=None):
            return {
                "text": "hello testing audio",
                "language": "en",
                "segments": [],
                "status": "ok",
                "error": None,
            }

    monkeypatch.setattr(server, "_get_asr", lambda: FakeASR())

    wav_path = tmp_path / "tone.wav"
    _write_tone(wav_path)

    with wav_path.open("rb") as audio:
        response = client.post(
            "/analyze-audio?call_id=spectrogram-preview",
            files={"audio": ("tone.wav", audio, "audio/wav")},
        )

    assert response.status_code == 200
    spectrogram = response.json()["raw_components"]["spectrogram"]
    assert spectrogram["content_type"] == "image/png"
    assert base64.b64decode(spectrogram["image_base64"]).startswith(b"\x89PNG\r\n\x1a\n")

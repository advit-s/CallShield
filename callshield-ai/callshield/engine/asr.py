try:
    import whisper
except ImportError:
    whisper = None

try:
    import torch
except ImportError:
    torch = None

try:
    from transformers import pipeline
except ImportError:
    pipeline = None

try:
    from transformers import AutoFeatureExtractor, AutoModelForSpeechSeq2Seq, AutoTokenizer
except ImportError:
    AutoFeatureExtractor = None
    AutoModelForSpeechSeq2Seq = None
    AutoTokenizer = None

import os
import warnings
from typing import Optional, Union
from pathlib import Path

from .audio_features import AudioFeatureExtractor

try:
    import numpy as np
except ImportError:
    np = None

try:
    import soundfile as sf
except ImportError:
    sf = None

try:
    import librosa
except ImportError:
    librosa = None


DEFAULT_HF_ASR_MODEL = "Oriserve/Whisper-Hindi2Hinglish-Swift"


def hf_asr_model_slug(model_name: str) -> str:
    """Create a Windows-safe local folder name for a Hugging Face model id."""
    return model_name.replace("\\", "__").replace("/", "__").replace(":", "_")


def default_hf_asr_root() -> Path:
    """Default checked-in project location for downloaded ASR model snapshots."""
    return Path(__file__).resolve().parents[2] / "models" / "hf_asr"


def _looks_like_hf_snapshot(path: Path) -> bool:
    return path.exists() and (
        (path / "config.json").exists()
        or (path / "preprocessor_config.json").exists()
        or (path / "model.safetensors").exists()
        or (path / "pytorch_model.bin").exists()
    )


def resolve_hf_asr_model(
    model_name: str = DEFAULT_HF_ASR_MODEL,
    local_dir: Optional[Union[str, Path]] = None,
    local_root: Optional[Union[str, Path]] = None,
    prefer_local: bool = True,
) -> str:
    """Resolve a Hugging Face ASR id to a local snapshot folder when available."""
    if local_dir:
        local_path = Path(local_dir).expanduser()
        if _looks_like_hf_snapshot(local_path):
            return str(local_path)

    model_path = Path(model_name).expanduser()
    if _looks_like_hf_snapshot(model_path):
        return str(model_path)

    if prefer_local:
        root = Path(local_root).expanduser() if local_root else default_hf_asr_root()
        candidate = root / hf_asr_model_slug(model_name)
        if _looks_like_hf_snapshot(candidate):
            return str(candidate)

    return model_name


class ASRTranscriber:
    """Whisper-based ASR with scam-relevant language support."""

    def __init__(
        self,
        model_name: str = "base",
        device: str = "cpu",
        backend: str = "openai_whisper",
        local_files_only: bool = False,
    ):
        self.model_name = model_name
        self.device = device
        self.backend = backend.lower()
        self.local_files_only = local_files_only
        self.model = None
        self.activity = AudioFeatureExtractor()
        self._load_model()

    def _load_model(self):
        if self.backend == "huggingface":
            if pipeline is None:
                warnings.warn("transformers not found. Hugging Face ASR will be unavailable.")
                return
            try:
                if self.local_files_only:
                    os.environ.setdefault("HF_HUB_OFFLINE", "1")
                device_id = 0 if torch is not None and torch.cuda.is_available() else -1
                kwargs = {
                    "model": self.model_name,
                    "device": device_id,
                }
                if self.local_files_only:
                    kwargs["model_kwargs"] = {"local_files_only": True}
                self.model = pipeline("automatic-speech-recognition", **kwargs)
                mode = "offline" if self.local_files_only else "online/cache"
                print(f"Loaded Hugging Face ASR model ({mode}): {self.model_name}")
            except Exception as e:
                if self._is_fast_tokenizer_parse_error(e):
                    self.model = self._load_hf_pipeline_with_slow_tokenizer(device_id)
                    if self.model is not None:
                        return
                warnings.warn(f"Could not load Hugging Face ASR model: {e}. Transcription will be limited.")
                self.model = None
            return

        if whisper is None:
            warnings.warn("Whisper library not found. Transcription will be unavailable.")
            return

        try:
            self.model = whisper.load_model(self.model_name)
            print(f"Loaded Whisper model: {self.model_name}")
        except Exception as e:
            warnings.warn(f"Could not load Whisper: {e}. Transcription will be limited.")
            self.model = None

    def _load_hf_pipeline_with_slow_tokenizer(self, device_id: int):
        """Retry Whisper ASR with the Python tokenizer when tokenizer.json is incompatible."""
        if (
            AutoTokenizer is None
            or AutoFeatureExtractor is None
            or AutoModelForSpeechSeq2Seq is None
        ):
            return None
        try:
            pretrained_kwargs = {"local_files_only": True} if self.local_files_only else {}
            tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                use_fast=False,
                **pretrained_kwargs,
            )
            feature_extractor = AutoFeatureExtractor.from_pretrained(
                self.model_name,
                **pretrained_kwargs,
            )
            model = AutoModelForSpeechSeq2Seq.from_pretrained(
                self.model_name,
                **pretrained_kwargs,
            )
            loaded = pipeline(
                "automatic-speech-recognition",
                model=model,
                tokenizer=tokenizer,
                feature_extractor=feature_extractor,
                device=device_id,
            )
            mode = "offline" if self.local_files_only else "online/cache"
            print(f"Loaded Hugging Face ASR model with slow tokenizer ({mode}): {self.model_name}")
            return loaded
        except Exception as retry_error:
            warnings.warn(
                f"Could not load Hugging Face ASR model with slow tokenizer: {retry_error}. "
                "Transcription will be limited."
            )
            return None

    @staticmethod
    def _is_fast_tokenizer_parse_error(error: Exception) -> bool:
        message = str(error)
        return "ModelWrapper" in message or "data did not match any variant" in message

    def transcribe(self, audio_path: Union[str, "torch.Tensor"], language: Optional[str] = None) -> dict:
        """Transcribe audio file or tensor. Returns dict with text, language, segments."""
        if self.model is None:
            return {
                "text": "",
                "language": None,
                "segments": [],
                "status": "unavailable",
                "error": "Whisper model is not loaded",
            }

        temp_path = None
        waveform = None
        try:
            if isinstance(audio_path, str):
                waveform = self._load_audio_array(audio_path)
                if waveform is not None:
                    activity = self.activity.audio_activity(waveform)
                    if not activity["speech_like"]:
                        return {
                            "text": "",
                            "language": None,
                            "segments": [],
                            "confidence": 0.0,
                            "status": "no_speech",
                            "error": None,
                            "activity": activity,
                        }
                    result = self._transcribe_waveform(waveform, language=language)
                else:
                    result = self._transcribe_path(audio_path, language=language)
            else:
                # If tensor, need to save temporarily
                import tempfile
                import soundfile as sf_local
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    temp_path = f.name
                    audio_np = audio_path.numpy() if torch is not None and isinstance(audio_path, torch.Tensor) else audio_path
                    if audio_np.ndim > 1:
                        audio_np = audio_np.squeeze()
                    sf_local.write(f.name, audio_np, 16000)
                    result = self._transcribe_path(f.name, language=language)

            text = result.get("text", "").strip()
            if waveform is not None:
                activity = self.activity.audio_activity(waveform)
            else:
                activity = None
            language = result.get("language")
            if self._looks_like_silence_hallucination(text, language):
                return {
                    "text": "",
                    "language": language,
                    "segments": result.get("segments", []),
                    "confidence": 0.0,
                    "status": "hallucination_suppressed",
                    "error": None,
                    "activity": activity,
                }
            return {
                "text": text,
                "language": language,
                "segments": result.get("segments", []),
                "confidence": result.get("confidence", 0.0),
                "status": "ok" if text else "no_speech",
                "error": None,
                "activity": activity,
            }
        except Exception as e:
            warnings.warn(f"Transcription failed: {e}")
            return {
                "text": "",
                "language": None,
                "segments": [],
                "status": "failed",
                "error": str(e),
                "activity": None,
            }
        finally:
            if temp_path:
                try:
                    Path(temp_path).unlink(missing_ok=True)
                except Exception:
                    pass

    def _load_audio_array(self, audio_path: str):
        """Load common WAV files directly to avoid ffmpeg dependency in Whisper path mode."""
        if sf is None or np is None:
            return None
        suffix = Path(audio_path).suffix.lower()
        if suffix not in {".wav", ".flac", ".ogg"}:
            return None

        try:
            audio, sample_rate = sf.read(audio_path, dtype="float32", always_2d=False)
            if getattr(audio, "ndim", 1) > 1:
                audio = audio.mean(axis=1)
            if sample_rate != 16000:
                if librosa is None:
                    return None
                audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=16000)
            return np.asarray(audio, dtype=np.float32)
        except Exception as e:
            warnings.warn(f"Direct audio load failed, falling back to Whisper loader: {e}")
            return None

    def _transcribe_waveform(self, waveform, language: Optional[str] = None) -> dict:
        if self.backend == "huggingface":
            output = self.model(waveform)
            return {
                "text": output.get("text", "") if isinstance(output, dict) else "",
                "language": language,
                "segments": [],
                "confidence": 0.0,
            }
        return self.model.transcribe(
            waveform,
            language=language,
            fp16=False,
            verbose=False
        )

    def _transcribe_path(self, audio_path: str, language: Optional[str] = None) -> dict:
        if self.backend == "huggingface":
            waveform = self._load_audio_array(audio_path)
            if waveform is None:
                output = self.model(audio_path)
            else:
                output = self.model(waveform)
            return {
                "text": output.get("text", "") if isinstance(output, dict) else "",
                "language": language,
                "segments": [],
                "confidence": 0.0,
            }
        return self.model.transcribe(
            audio_path,
            language=language,
            fp16=False,
            verbose=False
        )

    @staticmethod
    def _looks_like_silence_hallucination(text: str, language: Optional[str] = None) -> bool:
        if not text:
            return False
        normalized = text.strip().lower()
        hallucinations = [
            "\u3054\u8996\u8074\u3042\u308a\u304c\u3068\u3046\u3054\u3056\u3044\u307e\u3057\u305f",
            "\u3054\u6e05\u8074\u3042\u308a\u304c\u3068\u3046\u3054\u3056\u3044\u307e\u3057\u305f",
            "thank you for watching",
            "thanks for watching",
            "subtitle",
            "subtitles",
            "caption",
        ]
        if any(phrase in normalized for phrase in hallucinations):
            return True
        tokens = [token for token in normalized.replace(".", " ").replace(",", " ").split() if token]
        if len(tokens) >= 6 and len(set(tokens)) <= 2:
            return True
        allowed_languages = {"en", "hi"}
        if language and language not in allowed_languages:
            latin_or_devanagari = any("a" <= ch <= "z" for ch in normalized) or any("\u0900" <= ch <= "\u097f" for ch in text)
            if not latin_or_devanagari:
                return True
        return False

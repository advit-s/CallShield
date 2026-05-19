import numpy as np
import webrtcvad
import torch
import torchaudio
from typing import Tuple, Optional
import io


class VoiceActivityDetector:
    def __init__(self, aggressiveness: int = 2, frame_duration_ms: int = 30):
        self.vad = webrtcvad.Vad(aggressiveness)
        self.frame_duration_ms = frame_duration_ms
        self.sample_rate = 16000
        self.frame_size = int(self.sample_rate * frame_duration_ms / 1000)

    def has_speech(self, audio: np.ndarray, threshold_ratio: float = 0.3) -> bool:
        """Return True if proportion of voiced frames exceeds threshold."""
        audio_int16 = (audio * 32767).astype(np.int16)
        frames = []
        for i in range(0, len(audio_int16) - self.frame_size, self.frame_size):
            frame = audio_int16[i:i + self.frame_size]
            if len(frame) == self.frame_size:
                frames.append(self.vad.is_speech(frame.tobytes(), self.sample_rate))
        if not frames:
            return False
        return sum(frames) / len(frames) >= threshold_ratio

    def split_on_silence(self, audio: np.ndarray, min_chunk_s: float = 0.5,
                         silence_thresh: float = 0.02) -> list:
        """Split audio on silence, return list of (start_idx, end_idx) tuples."""
        silence = np.abs(audio) < silence_thresh
        chunks = []
        start = 0
        in_silence = False
        min_samples = int(min_chunk_s * self.sample_rate)
        for i, is_silent in enumerate(silence):
            if not in_silence and is_silent and (i - start) > min_samples:
                chunks.append((start, i))
                in_silence = True
            elif is_silent:
                in_silence = True
            elif in_silence and not is_silent:
                start = i
                in_silence = False
        if not in_silence and (len(audio) - start) > min_samples:
            chunks.append((start, len(audio)))
        return chunks


class AudioPreprocessor:
    def __init__(self, target_sr: int = 16000):
        self.target_sr = target_sr
        self.vad = VoiceActivityDetector()

    def load_audio(self, path: str) -> Tuple[np.ndarray, int]:
        """Load audio and resample to target sample rate."""
        wav, sr = torchaudio.load(path)
        if wav.shape[0] > 1:
            wav = wav.mean(dim=0, keepdim=True)
        if sr != self.target_sr:
            wav = torchaudio.functional.resample(wav, sr, self.target_sr)
        wav = wav / (wav.abs().max() + 1e-8)
        return wav.squeeze().numpy(), self.target_sr

    def preprocess(self, audio: np.ndarray) -> torch.Tensor:
        """Normalize and convert to torch tensor."""
        audio = audio / (np.abs(audio).max() + 1e-8)
        return torch.from_numpy(audio).float()

    def to_log_mel(self, audio: torch.Tensor, n_mels: int = 80,
                   n_fft: int = 512, hop_length: int = 160) -> torch.Tensor:
        mel_spec = torchaudio.transforms.MelSpectrogram(
            sample_rate=self.target_sr, n_fft=n_fft,
            hop_length=hop_length, n_mels=n_mels
        )(audio)
        return (mel_spec + 1e-6).log()

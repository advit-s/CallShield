#!/usr/bin/env python3
"""Generate synthetic demo audio for CallShield testing.

This script creates simple synthetic audio clips representing different
scenarios for the CallShield demo.
"""

import numpy as np
import soundfile as sf
import os


def generate_silence(duration: float, sr: int = 16000):
    """Generate silent audio."""
    return np.zeros(int(duration * sr))


def generate_tone(freq: float, duration: float, sr: int = 16000, amplitude: float = 0.3):
    """Generate a pure tone."""
    t = np.linspace(0, duration, int(duration * sr), False)
    return amplitude * np.sin(2 * np.pi * freq * t)


def apply_fade(audio: np.ndarray, fade_duration: float = 0.05, sr: int = 16000):
    """Apply fade in/out to audio."""
    fade_samples = int(fade_duration * sr)
    if len(audio) <= 2 * fade_samples:
        return audio
    audio = audio.copy()
    audio[:fade_samples] *= np.linspace(0, 1, fade_samples)
    audio[-fade_samples:] *= np.linspace(1, 0, fade_samples)
    return audio


def generate_synthetic_speech_like(duration: float, sr: int = 16000, is_deepfake: bool = False):
    """Generate synthetic speech-like audio.

    For demonstration, creates pulsed noise that mimics speech patterns.
    Deepfake has more consistent spectral structure, real has more natural variation.
    """
    total_samples = int(duration * sr)
    audio = np.zeros(total_samples)

    if is_deepfake:
        # More consistent, synthetic-sounding
        for i in range(0, total_samples, int(0.01 * sr)):
            chunk_size = int(0.005 * sr)
            if i + chunk_size < total_samples:
                # More regular, synthetic patterns
                freq = 150 + 80 * (np.sin(2 * np.pi * i / sr * 2) + 1) / 2
                audio[i:i + chunk_size] += generate_tone(freq, chunk_size / sr, amplitude=0.5)[:chunk_size]
    else:
        # More natural variation, less regular
        for i in range(0, total_samples, int(0.01 * sr)):
            chunk_size = int(0.005 * sr)
            if i + chunk_size < total_samples:
                freq = 100 + 150 * np.random.random()
                audio[i:i + chunk_size] += generate_tone(freq, chunk_size / sr, amplitude=0.4)[:chunk_size]

    # Add some noise for realism
    noise = np.random.normal(0, 0.01, total_samples)
    audio += noise
    return apply_fade(audio, sr=sr)


def generate_scenario_audio(scenario: str, output_path: str, sr: int = 16000):
    """Generate a demo audio file for a given scenario.

    Scenarios:
    - normal: Normal voice, low risk
    - scam_human: Human scammer, medium-high scam language, no deepfake
    - deepfake: AI-generated voice, high deepfake + scam language
    - replay: Replayed voice recording (partial deepfake signal)
    """
    if scenario == "normal":
        # Clean, short, normal-sounding
        audio = generate_synthetic_speech_like(3.0, sr=sr, is_deepfake=False)
    elif scenario == "scam_human":
        # Human-like with moderate consistency
        audio = generate_synthetic_speech_like(5.0, sr=sr, is_deepfake=False)
    elif scenario == "deepfake":
        # Synthetic, consistent patterns
        audio = generate_synthetic_speech_like(5.0, sr=sr, is_deepfake=True)
    elif scenario == "replay":
        # Mix of normal and replay artifacts
        audio = np.concatenate([
            generate_synthetic_speech_like(2.0, sr=sr, is_deepfake=False)[:int(2*sr)] * 0.8,
            generate_synthetic_speech_like(3.0, sr=sr, is_deepfake=True)[:int(3*sr)] * 0.7,
        ])
    else:
        audio = generate_synthetic_speech_like(3.0, sr=sr, is_deepfake=False)

    # Normalize
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = audio / max_val * 0.8

    sf.write(output_path, audio, sr)
    print(f"Generated: {output_path} (scenario: {scenario}, duration: {len(audio)/sr:.1f}s)")
    return output_path


def main():
    output_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'sample_calls')
    os.makedirs(output_dir, exist_ok=True)

    scenarios = {
        "normal_call.wav": "normal",
        "human_scam.wav": "scam_human",
        "deepfake_scam.wav": "deepfake",
        "replay_attack.wav": "replay",
    }

    for filename, scenario in scenarios.items():
        path = os.path.join(output_dir, filename)
        generate_scenario_audio(scenario, path)

    print(f"\nAll demo audio files generated in: {output_dir}")


if __name__ == "__main__":
    main()

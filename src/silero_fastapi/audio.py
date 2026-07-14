from __future__ import annotations

import io
import wave

import numpy as np


def audio_to_wav_bytes(audio: object, sample_rate: int) -> bytes:
    if hasattr(audio, "detach"):
        audio = audio.detach()
    if hasattr(audio, "cpu"):
        audio = audio.cpu()
    if hasattr(audio, "numpy"):
        audio = audio.numpy()
    samples = np.asarray(audio, dtype=np.float32).squeeze()
    if samples.ndim != 1:
        raise ValueError(f"Expected mono audio, received shape {samples.shape}")
    samples = np.nan_to_num(samples, nan=0.0, posinf=1.0, neginf=-1.0)
    pcm = (np.clip(samples, -1.0, 1.0) * 32767.0).astype("<i2")
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())
    return output.getvalue()


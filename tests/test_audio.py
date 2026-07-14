import io
import wave

import numpy as np

from silero_fastapi.audio import audio_to_wav_bytes


def test_audio_to_wav_bytes_writes_mono_pcm() -> None:
    payload = audio_to_wav_bytes(np.array([-1.2, -0.5, 0.0, 0.5, 1.2]), 48_000)
    with wave.open(io.BytesIO(payload), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == 48_000
        assert wav.getnframes() == 5


def test_audio_to_wav_bytes_rejects_multichannel_audio() -> None:
    audio = np.zeros((2, 4), dtype=np.float32)
    try:
        audio_to_wav_bytes(audio, 24_000)
    except ValueError as exc:
        assert "mono" in str(exc)
    else:
        raise AssertionError("Expected multichannel audio to be rejected")


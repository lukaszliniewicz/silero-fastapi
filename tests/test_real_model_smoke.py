import os
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from silero_fastapi.app import create_app
from silero_fastapi.catalog import get_model
from silero_fastapi.runtime import SileroRuntime
from silero_fastapi.service import ServiceContext
from silero_fastapi.settings import Settings
from silero_fastapi.store import ModelStore

pytestmark = pytest.mark.real_model


@pytest.mark.skipif(
    not os.environ.get("SILERO_REAL_MODEL_DIR"),
    reason="Set SILERO_REAL_MODEL_DIR to a populated service data directory",
)
def test_real_ukrainian_generation(tmp_path: Path) -> None:
    store = ModelStore(Path(os.environ["SILERO_REAL_MODEL_DIR"]))
    model = get_model("v5_cis_base_nostress")
    assert store.is_installed(model, verify=True)
    runtime = SileroRuntime(store, device="cpu", cpu_threads=4, cache_size=1)

    result = runtime.synthesize(
        model,
        text="Я люблю слухати цікаві книжки.",
        voice="ukr_igor",
        language="ukr",
        stress_mode="auto",
        sample_rate=48_000,
    )

    output = tmp_path / "ukrainian.wav"
    output.write_bytes(result.audio)
    with wave.open(str(output), "rb") as wav:
        assert wav.getframerate() == 48_000
        assert wav.getnframes() > 1_000
    assert result.stress_applied is True
    assert result.stress_engine == "silero-stress-accentor"


@pytest.mark.skipif(
    not os.environ.get("SILERO_REAL_MODEL_DIR"),
    reason="Set SILERO_REAL_MODEL_DIR to a populated service data directory",
)
def test_real_ukrainian_http_request() -> None:
    data_dir = Path(os.environ["SILERO_REAL_MODEL_DIR"])
    settings = Settings(data_dir=data_dir)
    context = ServiceContext(settings)
    app = create_app(settings, context=context)

    with TestClient(app) as client:
        response = client.post(
            "/v1/audio/speech",
            json={
                "model": "v5_cis_base_nostress",
                "input": "Я люблю українські аудіокниги.",
                "voice": "ukr_igor",
                "language": "ukr",
            },
        )
    context.close()

    assert response.status_code == 200
    assert response.content.startswith(b"RIFF")
    assert response.headers["x-silero-stress"] == "silero-stress-accentor"

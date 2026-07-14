from pathlib import Path

from fastapi.testclient import TestClient

from silero_fastapi.app import create_app
from silero_fastapi.catalog import get_model
from silero_fastapi.runtime import SynthesisResult
from silero_fastapi.service import ServiceContext
from silero_fastapi.settings import Settings
from silero_fastapi.store import ModelStore
from silero_fastapi.stress import StressResult


class FakeStress:
    available = True

    def process(self, text, **_kwargs):
        return StressResult(text=text, applied=False, engine="fake")


class FakeRuntime:
    available = True
    stress = FakeStress()

    def loaded_models(self):
        return ()

    def voices(self, spec, load_installed=True):
        return tuple(voice.id for voice in spec.voices)

    def unload(self, model_id=None):
        return None

    def synthesize(self, spec, *, text, voice, language, sample_rate, **_kwargs):
        return SynthesisResult(
            audio=b"RIFFfake-wave",
            model_id=spec.id,
            voice_id=voice,
            language=language,
            sample_rate=sample_rate,
            stress_text=text,
            stress_applied=False,
            stress_engine="fake",
            stress_warning="",
        )


def _client(tmp_path: Path, *, api_key: str = "") -> TestClient:
    settings = Settings(data_dir=tmp_path, api_key=api_key)
    context = ServiceContext(settings, store=ModelStore(tmp_path), runtime=FakeRuntime())
    return TestClient(create_app(settings, context=context))


def test_catalogue_and_voice_endpoints_are_machine_readable(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        models = client.get("/v1/models")
        voices = client.get(
            "/v1/audio/voices",
            params={"model": "v5_cis_ext", "language": "ukr"},
        )
    assert models.status_code == 200
    assert models.json()["data"][0]["id"] == "v5_cis_base_nostress"
    assert [voice["display_name"] for voice in voices.json()["data"]] == [
        "Kateryna",
        "Lada",
        "Mykyta",
        "Oleksa",
        "Tetiana",
    ]
    assert all(not voice["available"] for voice in voices.json()["data"])


def test_speech_is_stateless_and_returns_provenance_headers(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        response = client.post(
            "/v1/audio/speech",
            json={
                "model": "v5_cis_base_nostress",
                "input": "Тест",
                "voice": "ukr_igor",
                "language": "ukr",
            },
            headers={"X-Request-ID": "request-123"},
        )
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.headers["x-silero-model"] == "v5_cis_base_nostress"
    assert response.headers["x-silero-license"] == "MIT"
    assert response.headers["x-request-id"] == "request-123"


def test_noncommercial_download_is_not_gated_by_acknowledgement(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "silero_fastapi.service.ServiceContext.start_download",
        lambda self, spec: self.store.mark_queued(spec),
    )
    with _client(tmp_path) as client:
        response = client.post("/v1/models/v5_cis_ext/download", json={})
    assert response.status_code == 202
    assert response.json()["model"] == "v5_cis_ext"
    assert response.json()["state"] == "queued"


def test_api_key_protects_generation_but_not_health(tmp_path: Path) -> None:
    with _client(tmp_path, api_key="secret") as client:
        assert client.get("/health").status_code == 200
        denied = client.get("/v1/models")
        allowed = client.get("/v1/models", headers={"Authorization": "Bearer secret"})
    assert denied.status_code == 401
    assert allowed.status_code == 200


def test_unknown_model_uses_consistent_error_envelope(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        response = client.get("/v1/models/not-real")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "model_not_found"


def test_empty_value_error_still_has_an_actionable_message(tmp_path: Path) -> None:
    class FailingRuntime(FakeRuntime):
        def synthesize(self, *_args, **_kwargs):
            raise ValueError

    settings = Settings(data_dir=tmp_path)
    context = ServiceContext(
        settings,
        store=ModelStore(tmp_path),
        runtime=FailingRuntime(),
    )
    with TestClient(create_app(settings, context=context)) as client:
        response = client.post(
            "/v1/audio/speech",
            json={
                "model": "v5_cis_base_nostress",
                "input": "Valid text",
                "voice": "ukr_igor",
                "language": "ukr",
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["message"] == (
        "The synthesis request could not be processed."
    )


def test_catalogue_contains_expected_license_metadata() -> None:
    assert get_model("v5_cis_base_nostress").license.commercial_use_allowed
    assert not get_model("v5_cis_ext").license.commercial_use_allowed

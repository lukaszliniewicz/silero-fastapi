import sys
import types
from pathlib import Path

import numpy as np

from silero_fastapi.catalog import get_model
from silero_fastapi.runtime import SileroRuntime
from silero_fastapi.store import ModelStore
from silero_fastapi.stress import StressResult


class FakeModel:
    speakers = ["ukr_igor", "ukr_roman"]

    def __init__(self) -> None:
        self.kwargs = None

    def to(self, _device):
        return self

    def eval(self):
        return self

    def apply_tts(self, **kwargs):
        self.kwargs = kwargs
        return np.zeros(100, dtype=np.float32)


class FakeStress:
    available = True

    def process(self, text, **_kwargs):
        return StressResult(text=f"accented:{text}", applied=True, engine="fake")


def test_runtime_loads_pinned_package_and_generates_wav(tmp_path: Path, monkeypatch) -> None:
    model = FakeModel()

    class Importer:
        def __init__(self, _path):
            pass

        def load_pickle(self, package, name):
            assert (package, name) == ("tts_models", "model")
            return model

    fake_torch = types.SimpleNamespace(
        set_num_threads=lambda _threads: None,
        package=types.SimpleNamespace(PackageImporter=Importer),
        device=lambda value: value,
        cuda=types.SimpleNamespace(is_available=lambda: False, empty_cache=lambda: None),
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setattr("silero_fastapi.runtime.importlib.util.find_spec", lambda name: object())

    store = ModelStore(tmp_path)
    spec = get_model("v5_cis_base_nostress")
    monkeypatch.setattr(store, "is_installed", lambda _spec, verify=False: True)
    monkeypatch.setattr(store, "model_path", lambda _spec: tmp_path / "model.pt")
    runtime = SileroRuntime(store, stress=FakeStress())

    result = runtime.synthesize(
        spec,
        text="Я читаю книгу",
        voice="ukr_igor",
        language="ukr",
    )

    assert result.audio.startswith(b"RIFF")
    assert result.stress_applied is True
    assert model.kwargs["text"].startswith("accented:")
    assert model.kwargs["speaker"] == "ukr_igor"


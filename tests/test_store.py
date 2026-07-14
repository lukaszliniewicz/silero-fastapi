import hashlib
import io
from pathlib import Path

import pytest

from silero_fastapi.catalog import MIT_CIS, ModelSpec
from silero_fastapi.store import DownloadCancelled, ModelStore


class FakeResponse(io.BytesIO):
    status = 200

    def getcode(self) -> int:
        return self.status


def _spec(payload: bytes) -> ModelSpec:
    return ModelSpec(
        id="test-model",
        display_name="Test Model",
        pack="test",
        url="https://example.invalid/test.pt",
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
        license=MIT_CIS,
        languages=("en",),
    )


def test_download_verifies_and_promotes_atomically(tmp_path: Path, monkeypatch) -> None:
    payload = b"model-contents" * 100
    spec = _spec(payload)
    store = ModelStore(tmp_path)
    monkeypatch.setattr(
        "silero_fastapi.store.urllib.request.urlopen",
        lambda _request, timeout: FakeResponse(payload),
    )

    destination = store.download(spec)

    assert destination.read_bytes() == payload
    assert not store.partial_path(spec).exists()
    assert store.status(spec).state == "installed"
    assert store.is_installed(spec, verify=True)


def test_invalid_existing_file_is_not_reported_as_installed(tmp_path: Path) -> None:
    payload = b"expected"
    spec = _spec(payload)
    store = ModelStore(tmp_path)
    store.ensure()
    store.model_path(spec).write_bytes(b"bad")
    assert store.status(spec).state == "invalid"


def test_queued_download_can_be_canceled_without_losing_partial_file(tmp_path: Path) -> None:
    payload = b"expected"
    spec = _spec(payload)
    store = ModelStore(tmp_path)
    store.ensure()
    store.partial_path(spec).write_bytes(b"exp")
    store.mark_queued(spec)
    assert store.cancel(spec) is True

    with pytest.raises(DownloadCancelled):
        store.download(spec)

    assert store.status(spec).state == "canceled"
    assert store.partial_path(spec).read_bytes() == b"exp"

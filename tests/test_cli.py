from pathlib import Path

from silero_fastapi.catalog import MODEL_CATALOG
from silero_fastapi.cli import main
from silero_fastapi.store import ModelStore


def test_download_all_installs_every_catalogue_model(tmp_path: Path, monkeypatch) -> None:
    installed: list[str] = []

    def fake_download(self, spec, *, progress=None):
        installed.append(spec.id)
        return self.model_path(spec)

    monkeypatch.setattr(ModelStore, "download", fake_download)
    main(["--data-dir", str(tmp_path), "download-all"])

    assert installed == [model.id for model in MODEL_CATALOG]


def test_noncommercial_model_download_does_not_require_acknowledgement(
    tmp_path: Path, monkeypatch
) -> None:
    installed: list[str] = []

    def fake_download(self, spec, *, progress=None):
        installed.append(spec.id)
        return self.model_path(spec)

    monkeypatch.setattr(ModelStore, "download", fake_download)
    main(["--data-dir", str(tmp_path), "download", "v5_cis_ext"])

    assert installed == ["v5_cis_ext"]

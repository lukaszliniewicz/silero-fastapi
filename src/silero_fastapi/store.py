from __future__ import annotations

import hashlib
import os
import threading
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from .catalog import ModelSpec


class DownloadError(RuntimeError):
    pass


class DownloadCancelled(DownloadError):
    pass


@dataclass(frozen=True, slots=True)
class DownloadStatus:
    model_id: str
    state: str
    bytes_downloaded: int = 0
    total_bytes: int = 0
    message: str = ""

    @property
    def progress(self) -> float:
        if not self.total_bytes:
            return 0.0
        return min(1.0, self.bytes_downloaded / self.total_bytes)


class ModelStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.models_dir = self.root / "models"
        self._lock = threading.RLock()
        self._statuses: dict[str, DownloadStatus] = {}
        self._cancel_events: dict[str, threading.Event] = {}

    def ensure(self) -> None:
        self.models_dir.mkdir(parents=True, exist_ok=True)

    def model_path(self, spec: ModelSpec) -> Path:
        return self.models_dir / spec.filename

    def partial_path(self, spec: ModelSpec) -> Path:
        return self.models_dir / f"{spec.filename}.part"

    def is_installed(self, spec: ModelSpec, *, verify: bool = False) -> bool:
        path = self.model_path(spec)
        if not path.is_file() or path.stat().st_size != spec.size_bytes:
            return False
        return not verify or sha256_file(path) == spec.sha256

    def status(self, spec: ModelSpec) -> DownloadStatus:
        with self._lock:
            active = self._statuses.get(spec.id)
            if active is not None:
                return active
        path = self.model_path(spec)
        if self.is_installed(spec):
            return DownloadStatus(spec.id, "installed", spec.size_bytes, spec.size_bytes)
        partial = self.partial_path(spec)
        if partial.exists():
            return DownloadStatus(spec.id, "partial", partial.stat().st_size, spec.size_bytes)
        if path.exists():
            return DownloadStatus(
                spec.id,
                "invalid",
                path.stat().st_size,
                spec.size_bytes,
                "Installed file does not match the pinned size.",
            )
        return DownloadStatus(spec.id, "not_installed", 0, spec.size_bytes)

    def _set_status(self, status: DownloadStatus) -> None:
        with self._lock:
            self._statuses[status.model_id] = status

    def mark_queued(self, spec: ModelSpec) -> DownloadStatus:
        with self._lock:
            self._cancel_events[spec.id] = threading.Event()
        status = DownloadStatus(
            model_id=spec.id,
            state="queued",
            bytes_downloaded=(
                self.partial_path(spec).stat().st_size
                if self.partial_path(spec).exists()
                else 0
            ),
            total_bytes=spec.size_bytes,
        )
        self._set_status(status)
        return status

    def cancel(self, spec: ModelSpec) -> bool:
        with self._lock:
            event = self._cancel_events.get(spec.id)
            status = self._statuses.get(spec.id)
            if event is None or status is None or status.state not in {"queued", "downloading"}:
                return False
            event.set()
            self._statuses[spec.id] = replace(status, state="cancel_requested")
            return True

    def download(
        self,
        spec: ModelSpec,
        *,
        progress: Callable[[DownloadStatus], None] | None = None,
    ) -> Path:
        self.ensure()
        destination = self.model_path(spec)
        partial = self.partial_path(spec)
        with self._lock:
            status = self._statuses.get(spec.id)
            if status and status.state == "downloading":
                raise DownloadError(f"Model {spec.id} is already downloading")
            self._statuses[spec.id] = DownloadStatus(
                spec.id,
                "downloading",
                partial.stat().st_size if partial.exists() else 0,
                spec.size_bytes,
            )
            cancel_event = self._cancel_events.setdefault(spec.id, threading.Event())

        try:
            if cancel_event.is_set():
                raise DownloadCancelled(f"Download canceled for {spec.id}")
            if self.is_installed(spec, verify=True):
                status = DownloadStatus(spec.id, "installed", spec.size_bytes, spec.size_bytes)
                self._set_status(status)
                return destination

            downloaded = partial.stat().st_size if partial.exists() else 0
            if downloaded > spec.size_bytes:
                partial.unlink()
                downloaded = 0

            request = urllib.request.Request(spec.url)
            if downloaded:
                request.add_header("Range", f"bytes={downloaded}-")

            try:
                response = urllib.request.urlopen(request, timeout=60)
            except urllib.error.URLError as exc:
                raise DownloadError(f"Could not download {spec.id}: {exc}") from exc

            response_status = getattr(response, "status", response.getcode())
            if downloaded and response_status != 206:
                downloaded = 0
                partial.unlink(missing_ok=True)

            hasher = hashlib.sha256()
            if downloaded:
                _update_hash_from_file(hasher, partial)

            mode = "ab" if downloaded else "wb"
            with response, partial.open(mode) as target:
                while chunk := response.read(1024 * 1024):
                    if cancel_event.is_set():
                        raise DownloadCancelled(f"Download canceled for {spec.id}")
                    target.write(chunk)
                    hasher.update(chunk)
                    downloaded += len(chunk)
                    status = DownloadStatus(
                        spec.id,
                        "downloading",
                        downloaded,
                        spec.size_bytes,
                    )
                    self._set_status(status)
                    if progress:
                        progress(status)
                target.flush()
                os.fsync(target.fileno())

            if downloaded != spec.size_bytes:
                raise DownloadError(
                    f"Size mismatch for {spec.id}: expected {spec.size_bytes}, got {downloaded}"
                )
            digest = hasher.hexdigest()
            if digest != spec.sha256:
                raise DownloadError(
                    f"SHA-256 mismatch for {spec.id}: expected {spec.sha256}, got {digest}"
                )

            os.replace(partial, destination)
            status = DownloadStatus(spec.id, "installed", downloaded, spec.size_bytes)
            self._set_status(status)
            if progress:
                progress(status)
            return destination
        except DownloadCancelled as exc:
            current = self.status(spec)
            canceled = replace(current, state="canceled", message=str(exc))
            self._set_status(canceled)
            raise
        except Exception as exc:
            current = self.status(spec)
            failed = replace(current, state="failed", message=str(exc))
            self._set_status(failed)
            raise
        finally:
            with self._lock:
                self._cancel_events.pop(spec.id, None)

    def remove(self, spec: ModelSpec) -> bool:
        with self._lock:
            active = self._statuses.get(spec.id)
            if active and active.state == "downloading":
                raise DownloadError(f"Cannot remove {spec.id} while it is downloading")
            self._statuses.pop(spec.id, None)
            self._cancel_events.pop(spec.id, None)
        removed = False
        for path in (self.model_path(spec), self.partial_path(spec)):
            if path.exists():
                path.unlink()
                removed = True
        return removed


def _update_hash_from_file(hasher: object, path: Path) -> None:
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            hasher.update(chunk)  # type: ignore[attr-defined]


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    _update_hash_from_file(hasher, path)
    return hasher.hexdigest()

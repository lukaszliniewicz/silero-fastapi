from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor

from .catalog import MODEL_CATALOG, ModelSpec, get_model
from .runtime import SileroRuntime
from .settings import Settings
from .store import DownloadStatus, ModelStore


class ServiceContext:
    def __init__(
        self,
        settings: Settings,
        *,
        store: ModelStore | None = None,
        runtime: SileroRuntime | None = None,
    ) -> None:
        self.settings = settings
        self.store = store or ModelStore(settings.data_dir)
        self.runtime = runtime or SileroRuntime(
            self.store,
            device=settings.device,
            cpu_threads=settings.cpu_threads,
            cache_size=settings.model_cache_size,
        )
        self._executor = ThreadPoolExecutor(
            max_workers=settings.download_workers,
            thread_name_prefix="silero-download",
        )
        self._futures: dict[str, Future[object]] = {}
        self._lock = threading.RLock()

    @property
    def models(self) -> tuple[ModelSpec, ...]:
        return MODEL_CATALOG

    def model(self, model_id: str) -> ModelSpec:
        return get_model(model_id)

    def start_download(self, spec: ModelSpec) -> DownloadStatus:
        with self._lock:
            future = self._futures.get(spec.id)
            if future and not future.done():
                return self.store.status(spec)
            queued = self.store.mark_queued(spec)
            future = self._executor.submit(self.store.download, spec)
            self._futures[spec.id] = future
        return queued

    def remove_model(self, spec: ModelSpec) -> bool:
        self.runtime.unload(spec.id)
        return self.store.remove(spec)

    def cancel_download(self, spec: ModelSpec) -> bool:
        return self.store.cancel(spec)

    def close(self) -> None:
        for spec in self.models:
            self.store.cancel(spec)
        self.runtime.unload()
        self._executor.shutdown(wait=False, cancel_futures=True)

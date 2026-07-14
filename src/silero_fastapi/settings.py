from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_path


def _positive_int(value: str | None, default: int) -> int:
    try:
        parsed = int(value or default)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


@dataclass(frozen=True, slots=True)
class Settings:
    data_dir: Path
    host: str = "127.0.0.1"
    port: int = 8001
    device: str = "cpu"
    cpu_threads: int = 4
    model_cache_size: int = 2
    download_workers: int = 2
    default_model: str = "v5_cis_base_nostress"
    api_key: str = ""

    @classmethod
    def from_env(cls) -> Settings:
        data_dir = Path(
            os.environ.get("SILERO_DATA_DIR")
            or user_data_path("silero-fastapi", "Pandrator", ensure_exists=False)
        ).expanduser()
        return cls(
            data_dir=data_dir,
            host=os.environ.get("SILERO_HOST", "127.0.0.1"),
            port=_positive_int(os.environ.get("SILERO_PORT"), 8001),
            device=os.environ.get("SILERO_DEVICE", "cpu").strip().lower() or "cpu",
            cpu_threads=_positive_int(os.environ.get("SILERO_CPU_THREADS"), 4),
            model_cache_size=_positive_int(os.environ.get("SILERO_MODEL_CACHE_SIZE"), 2),
            download_workers=_positive_int(os.environ.get("SILERO_DOWNLOAD_WORKERS"), 2),
            default_model=(
                os.environ.get("SILERO_DEFAULT_MODEL", "v5_cis_base_nostress").strip()
                or "v5_cis_base_nostress"
            ),
            api_key=os.environ.get("SILERO_API_KEY", ""),
        )


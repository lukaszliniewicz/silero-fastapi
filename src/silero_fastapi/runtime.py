from __future__ import annotations

import html
import importlib.util
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from .audio import audio_to_wav_bytes
from .catalog import ModelSpec, infer_voice_language, iter_voices
from .store import ModelStore
from .stress import StressProcessor, validate_ssml


class RuntimeUnavailableError(RuntimeError):
    pass


class ModelNotInstalledError(FileNotFoundError):
    pass


@dataclass(frozen=True, slots=True)
class SynthesisResult:
    audio: bytes
    model_id: str
    voice_id: str
    language: str
    sample_rate: int
    stress_text: str
    stress_applied: bool
    stress_engine: str
    stress_warning: str


class SileroRuntime:
    def __init__(
        self,
        store: ModelStore,
        *,
        device: str = "cpu",
        cpu_threads: int = 4,
        cache_size: int = 2,
        stress: StressProcessor | None = None,
    ) -> None:
        self.store = store
        self.device = device
        self.cpu_threads = cpu_threads
        self.cache_size = max(1, cache_size)
        self.stress = stress or StressProcessor()
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._cache_lock = threading.RLock()
        self._model_locks: dict[str, threading.RLock] = {}

    @property
    def available(self) -> bool:
        return importlib.util.find_spec("torch") is not None

    def unload(self, model_id: str | None = None) -> None:
        with self._cache_lock:
            if model_id is None:
                self._cache.clear()
            else:
                self._cache.pop(model_id, None)
        if self.available:
            import torch

            if self.device.startswith("cuda") and torch.cuda.is_available():
                torch.cuda.empty_cache()

    def loaded_models(self) -> tuple[str, ...]:
        with self._cache_lock:
            return tuple(self._cache)

    def voices(self, spec: ModelSpec, *, load_installed: bool = True) -> tuple[str, ...]:
        discovered: tuple[str, ...] = ()
        if load_installed and self.store.is_installed(spec) and self.available:
            model = self._load(spec)
            discovered = tuple(str(voice) for voice in getattr(model, "speakers", ()) or ())
        return tuple(voice.id for voice in iter_voices(spec, discovered))

    def synthesize(
        self,
        spec: ModelSpec,
        *,
        text: str,
        voice: str,
        language: str = "",
        sample_rate: int = 48000,
        stress_mode: str = "auto",
        ssml: bool = False,
        speed: float = 1.0,
        put_accent: bool | None = None,
        put_yo: bool | None = None,
        put_stress_homo: bool | None = None,
        put_yo_homo: bool | None = None,
        question_intensity: int | None = None,
    ) -> SynthesisResult:
        if not text.strip():
            raise ValueError("Speech input must not be blank")
        if sample_rate not in spec.sample_rates:
            raise ValueError(
                f"Model {spec.id} supports sample rates: {', '.join(map(str, spec.sample_rates))}"
            )
        if ssml and not spec.supports_ssml:
            raise ValueError(f"Model {spec.id} does not support SSML")
        if ssml:
            validate_ssml(text)

        model = self._load(spec)
        discovered = tuple(str(item) for item in getattr(model, "speakers", ()) or ())
        valid_voices = self.voices(spec, load_installed=False)
        if discovered:
            valid_voices = tuple(dict.fromkeys(valid_voices + discovered))
        selected_voice = voice or (valid_voices[0] if valid_voices else "")
        if not selected_voice:
            raise ValueError(f"No voices are available for {spec.id}")
        if valid_voices and selected_voice not in valid_voices:
            raise ValueError(f"Voice {selected_voice!r} is not available for {spec.id}")

        resolved_language = language or infer_voice_language(selected_voice, spec)
        if resolved_language not in spec.languages:
            raise ValueError(
                f"Language {resolved_language!r} is not supported by {spec.id}"
            )
        stress_result = self.stress.process(
            text,
            language=resolved_language,
            model=spec,
            mode=stress_mode,
            is_ssml=ssml,
        )
        synthesized_text = stress_result.text
        use_ssml = ssml
        if speed != 1.0:
            if ssml:
                raise ValueError("Non-default speed cannot be combined with explicit SSML")
            synthesized_text = (
                f'<speak><prosody rate="{speed:.3g}">'
                f"{html.escape(synthesized_text)}</prosody></speak>"
            )
            use_ssml = True

        kwargs: dict[str, Any] = {
            "speaker": selected_voice,
            "sample_rate": sample_rate,
            "ssml_text" if use_ssml else "text": synthesized_text,
        }
        russian_options = {
            "put_accent": put_accent,
            "put_yo": put_yo,
            "put_stress_homo": put_stress_homo,
            "put_yo_homo": put_yo_homo,
        }
        if spec.built_in_stress_languages:
            kwargs.update(
                {key: value for key, value in russian_options.items() if value is not None}
            )
        if question_intensity is not None:
            if not spec.supports_questions:
                raise ValueError(f"Model {spec.id} does not support question intensity")
            kwargs["intensity"] = question_intensity

        lock = self._model_locks.setdefault(spec.id, threading.RLock())
        with lock:
            audio = model.apply_tts(**kwargs)
        return SynthesisResult(
            audio=audio_to_wav_bytes(audio, sample_rate),
            model_id=spec.id,
            voice_id=selected_voice,
            language=resolved_language,
            sample_rate=sample_rate,
            stress_text=stress_result.text,
            stress_applied=stress_result.applied,
            stress_engine=stress_result.engine,
            stress_warning=stress_result.warning,
        )

    def _load(self, spec: ModelSpec):
        if not self.available:
            raise RuntimeUnavailableError(
                "PyTorch is not installed; install silero-fastapi[inference]"
            )
        if not self.store.is_installed(spec):
            raise ModelNotInstalledError(
                f"Model {spec.id} is not installed; download it before generation"
            )
        with self._cache_lock:
            cached = self._cache.pop(spec.id, None)
            if cached is not None:
                self._cache[spec.id] = cached
                return cached

            import torch

            torch.set_num_threads(self.cpu_threads)
            path = self.store.model_path(spec)
            importer = torch.package.PackageImporter(str(path))
            model = importer.load_pickle("tts_models", "model")
            model.to(torch.device(self.device))
            if hasattr(model, "eval"):
                model.eval()
            self._cache[spec.id] = model
            while len(self._cache) > self.cache_size:
                self._cache.popitem(last=False)
            return model

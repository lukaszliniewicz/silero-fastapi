from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ._version import __version__
from .catalog import ModelSpec, iter_voices, language_name, prettify_voice_id
from .runtime import ModelNotInstalledError, RuntimeUnavailableError
from .schemas import AccentRequest, AccentResponse, ModelDownloadRequest, SpeechRequest
from .service import ServiceContext
from .settings import Settings
from .store import DownloadError


def _error(code: str, message: str, details: dict[str, object] | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def _status_dict(context: ServiceContext, spec: ModelSpec) -> dict[str, object]:
    model_status = context.store.status(spec)
    return {
        "state": model_status.state,
        "bytes_downloaded": model_status.bytes_downloaded,
        "total_bytes": model_status.total_bytes,
        "progress": model_status.progress,
        "message": model_status.message,
        "installed": model_status.state == "installed",
        "loaded": spec.id in context.runtime.loaded_models(),
    }


def _model_dict(context: ServiceContext, spec: ModelSpec) -> dict[str, object]:
    return {
        "id": spec.id,
        "object": "model",
        "owned_by": "silero",
        "display_name": spec.display_name,
        "pack": spec.pack,
        "languages": [
            {"code": code, "name": language_name(code)} for code in spec.languages
        ],
        "sample_rates": list(spec.sample_rates),
        "license": {
            "id": spec.license.id,
            "name": spec.license.name,
            "url": spec.license.url,
            "commercial_use_allowed": spec.license.commercial_use_allowed,
        },
        "features": {
            "ssml": spec.supports_ssml,
            "homographs": spec.supports_homographs,
            "questions": spec.supports_questions,
            "built_in_stress_languages": list(spec.built_in_stress_languages),
            "requires_stress_languages": list(spec.requires_stress_languages),
        },
        "recommended": spec.recommended,
        "legacy": spec.legacy,
        "size_bytes": spec.size_bytes,
        "sha256": spec.sha256,
        "status": _status_dict(context, spec),
    }


def _context(request: Request) -> ServiceContext:
    return request.app.state.context


Context = Annotated[ServiceContext, Depends(_context)]


def create_app(
    settings: Settings | None = None,
    *,
    context: ServiceContext | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.context = context or ServiceContext(resolved_settings)
        app.state.context.store.ensure()
        try:
            yield
        finally:
            if context is None:
                app.state.context.close()

    app = FastAPI(
        title="Silero FastAPI",
        summary="Reproducible Silero TTS service for Pandrator",
        version=__version__,
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def authenticate(request: Request, call_next):
        api_key = resolved_settings.api_key
        public_path = request.url.path in {"/", "/health", "/ready", "/openapi.json"}
        public_path = public_path or request.url.path.startswith("/docs")
        if api_key and not public_path:
            header = request.headers.get("authorization", "")
            if not secrets.compare_digest(header, f"Bearer {api_key}"):
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content=_error("unauthorized", "A valid bearer token is required."),
                )
        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error("validation_error", "The request is invalid.", {"errors": exc.errors()}),
        )

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and "error" in detail:
            content = detail
        else:
            content = _error("http_error", str(detail))
        return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)

    @app.exception_handler(KeyError)
    async def unknown_model(_request: Request, exc: KeyError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_error("model_not_found", str(exc).strip("'")),
        )

    @app.exception_handler(ModelNotInstalledError)
    async def missing_model(_request: Request, exc: ModelNotInstalledError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_error("model_not_installed", str(exc)),
        )

    @app.exception_handler(RuntimeUnavailableError)
    async def missing_runtime(_request: Request, exc: RuntimeUnavailableError):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=_error("runtime_unavailable", str(exc)),
        )

    @app.exception_handler(DownloadError)
    async def download_error(_request: Request, exc: DownloadError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_error("download_error", str(exc)),
        )

    @app.exception_handler(ValueError)
    async def value_error(_request: Request, exc: ValueError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error("invalid_value", str(exc)),
        )

    @app.get("/")
    def root() -> dict[str, str]:
        return {"name": "silero-fastapi", "version": __version__, "docs": "/docs"}

    @app.get("/health")
    def health(service: Context) -> dict[str, object]:
        return {
            "status": "ok",
            "version": __version__,
            "device": service.settings.device,
            "torch_available": service.runtime.available,
            "stress_available": service.runtime.stress.available,
        }

    @app.get("/ready")
    def ready(service: Context) -> Response:
        payload = {
            "status": "ready" if service.runtime.available else "runtime_unavailable",
            "torch_available": service.runtime.available,
        }
        return JSONResponse(payload, status_code=200 if service.runtime.available else 503)

    @app.get("/v1/capabilities")
    def capabilities(service: Context) -> dict[str, object]:
        return {
            "service": "silero",
            "version": __version__,
            "stateless_generation": True,
            "prebuilt_voices": True,
            "voice_cloning": False,
            "devices": ["cpu", "cuda"],
            "active_device": service.settings.device,
            "stress_available": service.runtime.stress.available,
            "formats": ["wav"],
            "default_model": service.settings.default_model,
        }

    @app.get("/v1/models")
    def models(service: Context) -> dict[str, object]:
        return {"object": "list", "data": [_model_dict(service, item) for item in service.models]}

    @app.get("/v1/models/{model_id}")
    def model(model_id: str, service: Context) -> dict[str, object]:
        return _model_dict(service, service.model(model_id))

    @app.get("/v1/models/{model_id}/status")
    def model_status(model_id: str, service: Context) -> dict[str, object]:
        spec = service.model(model_id)
        return {"model": spec.id, **_status_dict(service, spec)}

    @app.post("/v1/models/{model_id}/download", status_code=202)
    def download_model(
        model_id: str,
        request: ModelDownloadRequest,
        service: Context,
    ) -> dict[str, object]:
        spec = service.model(model_id)
        if not spec.license.commercial_use_allowed and not request.acknowledge_noncommercial:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=_error(
                    "license_acknowledgement_required",
                    f"{spec.display_name} is licensed for non-commercial use.",
                    {"license": spec.license.id, "url": spec.license.url},
                ),
            )
        download_status = service.start_download(spec)
        return {
            "model": spec.id,
            "state": download_status.state,
            "status_url": f"/v1/models/{spec.id}/status",
        }

    @app.delete("/v1/models/{model_id}")
    def remove_model(model_id: str, service: Context) -> dict[str, object]:
        spec = service.model(model_id)
        return {"model": spec.id, "removed": service.remove_model(spec)}

    @app.post("/v1/models/{model_id}/cancel")
    def cancel_model_download(model_id: str, service: Context) -> dict[str, object]:
        spec = service.model(model_id)
        return {"model": spec.id, "cancel_requested": service.cancel_download(spec)}

    @app.get("/v1/audio/voices")
    def voices(
        service: Context,
        model: str = Query(default=""),
        language: str = Query(default=""),
        include_unavailable: bool = Query(default=True),
    ) -> dict[str, object]:
        selected_models = [service.model(model)] if model else list(service.models)
        data: list[dict[str, object]] = []
        for spec in selected_models:
            installed = service.store.is_installed(spec)
            if not include_unavailable and not installed:
                continue
            discovered = service.runtime.voices(spec) if installed else ()
            for voice in iter_voices(spec, discovered):
                if language and voice.language != language:
                    continue
                data.append(
                    {
                        "id": voice.id,
                        "object": "voice",
                        "display_name": voice.display_name or prettify_voice_id(voice.id),
                        "language": voice.language,
                        "language_name": language_name(voice.language),
                        "model": spec.id,
                        "available": installed,
                        "license": {
                            "id": spec.license.id,
                            "commercial_use_allowed": spec.license.commercial_use_allowed,
                        },
                    }
                )
        return {"object": "list", "data": data}

    @app.post("/v1/text/accent", response_model=AccentResponse)
    def accent(request: AccentRequest, service: Context) -> AccentResponse:
        spec = service.model(request.model)
        result = service.runtime.stress.process(
            request.input,
            language=request.language,
            model=spec,
            mode=request.stress_mode,
            is_ssml=request.ssml,
        )
        return AccentResponse(
            input=request.input,
            output=result.text,
            language=request.language,
            applied=result.applied,
            engine=result.engine,
            warning=result.warning,
        )

    @app.post("/v1/audio/speech")
    def speech(
        request: SpeechRequest,
        service: Context,
        x_request_id: Annotated[str | None, Header()] = None,
    ) -> Response:
        spec = service.model(request.model)
        result = service.runtime.synthesize(
            spec,
            text=request.input,
            voice=request.voice,
            language=request.language,
            sample_rate=request.sample_rate,
            stress_mode=request.stress_mode,
            ssml=request.ssml,
            speed=request.speed,
            put_accent=request.put_accent,
            put_yo=request.put_yo,
            put_stress_homo=request.put_stress_homo,
            put_yo_homo=request.put_yo_homo,
            question_intensity=request.question_intensity,
        )
        headers = {
            "X-Silero-Model": result.model_id,
            "X-Silero-Voice": result.voice_id,
            "X-Silero-Language": result.language,
            "X-Silero-License": spec.license.id,
            "X-Silero-Stress": result.stress_engine,
            "X-Silero-Stress-Applied": str(result.stress_applied).lower(),
        }
        if result.stress_warning:
            headers["X-Silero-Warning"] = result.stress_warning
        if x_request_id:
            headers["X-Request-ID"] = x_request_id
        return Response(result.audio, media_type="audio/wav", headers=headers)

    return app

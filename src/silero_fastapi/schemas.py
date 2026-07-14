from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SpeechRequest(BaseModel):
    model: str = "v5_cis_base_nostress"
    input: str = Field(min_length=1, max_length=20_000)
    voice: str = ""
    language: str = ""
    response_format: Literal["wav"] = "wav"
    speed: float = Field(default=1.0, ge=0.25, le=4.0)
    sample_rate: int = 48_000
    stress_mode: Literal["auto", "manual", "off"] = "auto"
    ssml: bool = False
    put_accent: bool | None = None
    put_yo: bool | None = None
    put_stress_homo: bool | None = None
    put_yo_homo: bool | None = None
    question_intensity: int | None = Field(default=None, ge=1, le=5)


class AccentRequest(BaseModel):
    model: str = "v5_cis_base_nostress"
    input: str = Field(min_length=1, max_length=20_000)
    language: str
    stress_mode: Literal["auto", "manual", "off"] = "auto"
    ssml: bool = False


class AccentResponse(BaseModel):
    input: str
    output: str
    language: str
    applied: bool
    engine: str
    warning: str = ""


class ModelDownloadRequest(BaseModel):
    # Kept for compatibility with early clients. Licence information is exposed
    # by the catalogue, but acknowledgement is not a download gate.
    acknowledge_noncommercial: bool = False


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, object] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    error: ErrorBody

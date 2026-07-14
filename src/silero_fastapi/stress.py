from __future__ import annotations

import importlib.util
import threading
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from .catalog import ModelSpec

ALLOWED_SSML_TAGS = {"speak", "p", "s", "break", "prosody", "emphasis"}
ALLOWED_SSML_ATTRIBUTES = {
    "break": {"time", "strength"},
    "prosody": {"rate", "pitch"},
    "emphasis": {"level"},
}


@dataclass(frozen=True, slots=True)
class StressResult:
    text: str
    applied: bool
    engine: str
    warning: str = ""


class StressProcessor:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._accentors: dict[str, object] = {}

    @property
    def available(self) -> bool:
        return importlib.util.find_spec("silero_stress") is not None

    def process(
        self,
        text: str,
        *,
        language: str,
        model: ModelSpec,
        mode: str = "auto",
        is_ssml: bool = False,
    ) -> StressResult:
        if mode not in {"auto", "manual", "off"}:
            raise ValueError("stress mode must be auto, manual, or off")
        if mode == "off" or language in model.built_in_stress_languages:
            engine = "model" if language in model.built_in_stress_languages else "none"
            return StressResult(text=text, applied=False, engine=engine)
        if language not in model.requires_stress_languages:
            return StressResult(text=text, applied=False, engine="not-required")
        if mode == "manual":
            warning = "" if "+" in text else "No explicit stress marks were found."
            return StressResult(text=text, applied=False, engine="manual", warning=warning)
        if not self.available:
            raise RuntimeError(
                f"Automatic stress for {language} requires the silero-stress package"
            )

        accent = self._accent_function(language)
        if is_ssml:
            processed = transform_ssml_text(text, accent)
        else:
            processed = accent(text)
        engine = (
            "silero-stress-accentor"
            if language in {"ru", "ukr", "bel"}
            else "silero-stress-simple"
        )
        warning = ""
        if language not in {"ru", "ukr", "bel"}:
            warning = "Low-resource stress uses a dictionary with a fallback heuristic."
        return StressResult(
            text=processed,
            applied=processed != text,
            engine=engine,
            warning=warning,
        )

    def _accent_function(self, language: str):
        with self._lock:
            accentor = self._accentors.get(language)
            if accentor is not None:
                return accentor

            if language in {"ru", "ukr", "bel"}:
                from silero_stress import load_accentor

                accentor = load_accentor(lang=language)
            else:
                from silero_stress.simple_accentor import SimpleAccentor

                accentor = SimpleAccentor(lang=language)
            self._accentors[language] = accentor
            return accentor


def validate_ssml(ssml: str) -> ET.Element:
    lowered = ssml.lower()
    if "<!doctype" in lowered or "<!entity" in lowered:
        raise ValueError("DOCTYPE and entity declarations are not allowed in SSML")
    try:
        root = ET.fromstring(ssml)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid SSML: {exc}") from exc
    if root.tag != "speak":
        raise ValueError("SSML must have a <speak> root element")
    for element in root.iter():
        if element.tag not in ALLOWED_SSML_TAGS:
            raise ValueError(f"Unsupported SSML element: <{element.tag}>")
        allowed = ALLOWED_SSML_ATTRIBUTES.get(element.tag, set())
        unsupported = set(element.attrib) - allowed
        if unsupported:
            names = ", ".join(sorted(unsupported))
            raise ValueError(f"Unsupported attributes on <{element.tag}>: {names}")
    return root


def transform_ssml_text(ssml: str, transform) -> str:
    root = validate_ssml(ssml)
    for element in root.iter():
        if element.text:
            element.text = transform(element.text)
        if element.tail:
            element.tail = transform(element.tail)
    return ET.tostring(root, encoding="unicode")

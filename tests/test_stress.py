import pytest

from silero_fastapi.catalog import get_model
from silero_fastapi.stress import StressProcessor, transform_ssml_text, validate_ssml


class FakeStressProcessor(StressProcessor):
    @property
    def available(self) -> bool:
        return True

    def _accent_function(self, language: str):
        return lambda text: text.replace("книга", "кн+ига").replace("книгу", "кн+игу")


def test_ukrainian_stress_is_applied_for_modern_base() -> None:
    result = FakeStressProcessor().process(
        "Я читаю книгу",
        language="ukr",
        model=get_model("v5_cis_base_nostress"),
    )
    assert result.applied is True
    assert "кн+игу" in result.text
    assert result.engine == "silero-stress-accentor"


def test_russian_v55_uses_model_stress() -> None:
    result = FakeStressProcessor().process(
        "Обычный текст",
        language="ru",
        model=get_model("v5_5_ru"),
    )
    assert result.applied is False
    assert result.engine == "model"


def test_manual_stress_warns_when_no_marks_are_present() -> None:
    result = FakeStressProcessor().process(
        "Я читаю книгу",
        language="ukr",
        model=get_model("v5_cis_base_nostress"),
        mode="manual",
    )
    assert result.warning


def test_ssml_text_is_transformed_without_losing_markup() -> None:
    output = transform_ssml_text(
        '<speak>книга <break time="200ms"/> і книгу</speak>',
        lambda text: text.replace("книга", "кн+ига").replace("книгу", "кн+игу"),
    )
    assert "<break" in output
    assert "кн+ига" in output
    assert "кн+игу" in output


@pytest.mark.parametrize(
    "ssml",
    [
        "<p>not rooted in speak</p>",
        "<speak><audio src='file:///tmp/a.wav'/></speak>",
        "<speak><break onclick='bad'/></speak>",
    ],
)
def test_unsafe_or_unsupported_ssml_is_rejected(ssml: str) -> None:
    with pytest.raises(ValueError):
        validate_ssml(ssml)


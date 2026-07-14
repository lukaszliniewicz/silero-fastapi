from silero_fastapi.catalog import (
    MODEL_CATALOG,
    get_model,
    infer_voice_language,
    iter_voices,
    prettify_voice_id,
)


def test_catalogue_ids_and_hashes_are_stable() -> None:
    assert len({model.id for model in MODEL_CATALOG}) == len(MODEL_CATALOG)
    for model in MODEL_CATALOG:
        assert len(model.sha256) == 64
        assert model.sha256 == model.sha256.lower()
        assert model.size_bytes > 1_000_000


def test_modern_base_is_mit_and_recommended() -> None:
    model = get_model("v5_cis_base_nostress")
    assert model.recommended is True
    assert model.license.id == "MIT"
    assert model.license.commercial_use_allowed is True
    assert {"ukr", "bel", "tat", "kaz"}.issubset(model.languages)
    assert len(model.voices) == 60
    assert any(voice.id == "ru_zhadyra" for voice in model.voices)


def test_extended_ukrainian_voices_are_explicitly_noncommercial() -> None:
    model = get_model("v5_cis_ext")
    ukrainian = [voice.id for voice in model.voices if voice.language == "ukr"]
    assert ukrainian == [
        "ukr_kateryna",
        "ukr_lada",
        "ukr_mykyta",
        "ukr_oleksa",
        "ukr_tetiana",
    ]
    assert model.license.id == "CC-BY-NC-SA-4.0"
    assert model.license.commercial_use_allowed is False


def test_voice_prettification_and_discovery() -> None:
    model = get_model("v5_cis_base_nostress")
    voices = iter_voices(model, ["ru_zhadyra", "ukr_igor"])
    assert len([voice for voice in voices if voice.id == "ukr_igor"]) == 1
    assert infer_voice_language("ru_zhadyra", model) == "ru"
    assert prettify_voice_id("ukr_kateryna") == "Kateryna"

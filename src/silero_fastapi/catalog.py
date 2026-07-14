from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class LicenseSpec:
    id: str
    name: str
    url: str
    commercial_use_allowed: bool


@dataclass(frozen=True, slots=True)
class VoiceSpec:
    id: str
    language: str
    display_name: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "language": self.language,
            "display_name": self.display_name or prettify_voice_id(self.id),
        }


@dataclass(frozen=True, slots=True)
class ModelSpec:
    id: str
    display_name: str
    pack: str
    url: str
    sha256: str
    size_bytes: int
    license: LicenseSpec
    languages: tuple[str, ...]
    voices: tuple[VoiceSpec, ...] = field(default_factory=tuple)
    sample_rates: tuple[int, ...] = (8000, 24000, 48000)
    requires_stress_languages: tuple[str, ...] = field(default_factory=tuple)
    built_in_stress_languages: tuple[str, ...] = field(default_factory=tuple)
    supports_homographs: bool = False
    supports_questions: bool = False
    supports_ssml: bool = True
    recommended: bool = False
    legacy: bool = False
    discover_voices: bool = True

    @property
    def filename(self) -> str:
        return self.url.rsplit("/", 1)[-1]


MIT_CIS = LicenseSpec(
    id="MIT",
    name="MIT (Silero CIS Base)",
    url="https://github.com/snakers4/silero-models/blob/master/LICENSE_CIS",
    commercial_use_allowed=True,
)

CC_BY_NC_SA_4 = LicenseSpec(
    id="CC-BY-NC-SA-4.0",
    name="Creative Commons BY-NC-SA 4.0",
    url="https://github.com/snakers4/silero-models/blob/master/LICENSE",
    commercial_use_allowed=False,
)

LANGUAGE_NAMES: dict[str, str] = {
    "as": "Assamese",
    "aze": "Azerbaijani",
    "bak": "Bashkir",
    "bel": "Belarusian",
    "bn": "Bengali",
    "chv": "Chuvash",
    "de": "German",
    "en": "English",
    "en-in": "Indian English",
    "erz": "Erzya",
    "es": "Spanish",
    "fr": "French",
    "gu": "Gujarati",
    "hi": "Hindi",
    "hye": "Armenian",
    "indic": "Indic languages",
    "kat": "Georgian",
    "kaz": "Kazakh",
    "kbd": "Kabardian-Cherkess",
    "kir": "Kyrgyz",
    "kjh": "Khakas",
    "kn": "Kannada",
    "mdf": "Moksha",
    "ml": "Malayalam",
    "mni": "Manipuri",
    "raj": "Rajasthani",
    "ru": "Russian",
    "sah": "Yakut",
    "ta": "Tamil",
    "tat": "Tatar",
    "te": "Telugu",
    "tgk": "Tajik",
    "udm": "Udmurt",
    "ukr": "Ukrainian",
    "uzb": "Uzbek",
    "xal": "Kalmyk",
}


def _voice_ids(language: str, *names: str) -> tuple[VoiceSpec, ...]:
    return tuple(VoiceSpec(name, language) for name in names)


BASE_NATIVE_VOICES = (
    _voice_ids("aze", "aze_gamat")
    + _voice_ids("hye", "hye_zara")
    + _voice_ids("bak", "bak_aigul", "bak_alfia", "bak_alfia2", "bak_miyau", "bak_ramilia")
    + _voice_ids("bel", "bel_anatoliy", "bel_dmitriy", "bel_larisa")
    + _voice_ids("kat", "kat_vika")
    + _voice_ids("kbd", "kbd_eduard")
    + _voice_ids("kaz", "kaz_zhadyra", "kaz_zhazira")
    + _voice_ids("xal", "xal_kejilgan", "xal_kermen")
    + _voice_ids("kir", "kir_nurgul")
    + _voice_ids("mdf", "mdf_oksana")
    + _voice_ids("tgk", "tgk_onaoy", "tgk_safarhuja")
    + _voice_ids("tat", "tat_albina", "tat_marat")
    + _voice_ids("udm", "udm_bogdan")
    + _voice_ids("uzb", "uzb_saida")
    + _voice_ids("ukr", "ukr_igor", "ukr_roman")
    + _voice_ids("kjh", "kjh_karina", "kjh_sibday")
    + _voice_ids("chv", "chv_ekaterina")
    + _voice_ids("erz", "erz_alexandr")
    + _voice_ids("sah", "sah_zinaida")
)

BASE_RUSSIAN_VOICES = tuple(
    VoiceSpec(
        voice_id,
        "ru",
        f"{voice_id.removeprefix('ru_').replace('_', ' ').title()} (Russian)",
    )
    for voice_id in (
        "ru_aigul",
        "ru_albina",
        "ru_alexandr",
        "ru_alfia",
        "ru_alfia2",
        "ru_bogdan",
        "ru_dmitriy",
        "ru_ekaterina",
        "ru_vika",
        "ru_gamat",
        "ru_igor",
        "ru_karina",
        "ru_kejilgan",
        "ru_kermen",
        "ru_marat",
        "ru_miyau",
        "ru_nurgul",
        "ru_oksana",
        "ru_onaoy",
        "ru_ramilia",
        "ru_roman",
        "ru_safarhuja",
        "ru_saida",
        "ru_sibday",
        "ru_zara",
        "ru_zhadyra",
        "ru_zhazira",
        "ru_zinaida",
        "ru_eduard",
    )
)

BASE_VOICES = BASE_NATIVE_VOICES + BASE_RUSSIAN_VOICES

EXT_VOICES = (
    _voice_ids("kaz", "kaz_abai", "kaz_aidana", "kaz_aisha", "kaz_bakir", "kaz_danara")
    + _voice_ids("xal", "xal_delghir", "xal_erdni")
    + _voice_ids(
        "tat",
        "tat_adiba",
        "tat_alsou",
        "tat_amir",
        "tat_azat",
        "tat_batir",
        "tat_bulat",
        "tat_damir",
        "tat_guzel",
        "tat_ildar",
        "tat_ilgiz",
        "tat_karim",
        "tat_mansur",
        "tat_murat",
        "tat_rasima",
        "tat_rustem",
        "tat_timur",
        "tat_zifa",
        "tat_zufar",
        "tat_zulfiya",
    )
    + _voice_ids("uzb", "uzb_anora", "uzb_dilnavoz")
    + _voice_ids("ukr", "ukr_kateryna", "ukr_lada", "ukr_mykyta", "ukr_oleksa", "ukr_tetiana")
    + _voice_ids("chv", "chv_aihwa", "chv_alima")
)

RUSSIAN_VOICES = _voice_ids("ru", "aidar", "baya", "kseniya", "xenia", "eugene")
ENGLISH_VOICES = tuple(
    VoiceSpec(f"en_{index}", "en", f"English Voice {index + 1}") for index in range(118)
) + (VoiceSpec("random", "en", "Random English Voice"),)

GERMAN_VOICES = _voice_ids(
    "de", "bernd_ungerer", "eva_k", "friedrich", "hokuspokus", "karlsson"
) + (VoiceSpec("random", "de", "Random German Voice"),)

SPANISH_VOICES = tuple(
    VoiceSpec(f"es_{index}", "es", f"Spanish Voice {index + 1}") for index in range(3)
) + (VoiceSpec("random", "es", "Random Spanish Voice"),)

FRENCH_VOICES = tuple(
    VoiceSpec(f"fr_{index}", "fr", f"French Voice {index + 1}") for index in range(6)
) + (VoiceSpec("random", "fr", "Random French Voice"),)

INDIAN_ENGLISH_VOICES = _voice_ids(
    "en-in",
    "tamil_female",
    "bengali_female",
    "malayalam_male",
    "manipuri_female",
    "assamese_female",
    "gujarati_male",
    "telugu_male",
    "kannada_male",
    "hindi_female",
    "rajasthani_female",
    "kannada_female",
    "bengali_male",
    "tamil_male",
    "gujarati_female",
    "assamese_male",
) + (VoiceSpec("random", "en-in", "Random Indian English Voice"),)

INDIC_VOICES = (
    _voice_ids("bn", "bengali_female", "bengali_male")
    + _voice_ids("gu", "gujarati_female", "gujarati_male")
    + _voice_ids("hi", "hindi_female", "hindi_male")
    + _voice_ids("kn", "kannada_female", "kannada_male")
    + _voice_ids("ml", "malayalam_female", "malayalam_male")
    + _voice_ids("mni", "manipuri_female")
    + _voice_ids("raj", "rajasthani_female", "rajasthani_male")
    + _voice_ids("ta", "tamil_female", "tamil_male")
    + _voice_ids("te", "telugu_female", "telugu_male")
    + (VoiceSpec("random", "indic", "Random Indic Voice"),)
)


MODEL_CATALOG: tuple[ModelSpec, ...] = (
    ModelSpec(
        id="v5_cis_base_nostress",
        display_name="Modern CIS Base (regional stress)",
        pack="modern-cis-base",
        url="https://models.silero.ai/models/tts/ru/v5_cis_base_nostress.pt",
        sha256="0405777e332906f0644e08a680f7cfdc2137ea864090079c1fdd30a43c1b8761",
        size_bytes=91_685_438,
        license=MIT_CIS,
        languages=(
            "aze",
            "hye",
            "bak",
            "bel",
            "kat",
            "kbd",
            "kaz",
            "xal",
            "kir",
            "mdf",
            "ru",
            "tgk",
            "tat",
            "udm",
            "uzb",
            "ukr",
            "kjh",
            "chv",
            "erz",
            "sah",
        ),
        voices=BASE_VOICES,
        requires_stress_languages=("ru", "ukr", "bel"),
        recommended=True,
    ),
    ModelSpec(
        id="v5_cis_base",
        display_name="Modern CIS Base (full stress)",
        pack="modern-cis-base",
        url="https://models.silero.ai/models/tts/ru/v5_cis_base.pt",
        sha256="ba41b18f6a707ad93605a162998865e7c087153d2e010a26dd02229dab0e672a",
        size_bytes=91_680_514,
        license=MIT_CIS,
        languages=(
            "aze",
            "hye",
            "bak",
            "bel",
            "kat",
            "kbd",
            "kaz",
            "xal",
            "kir",
            "mdf",
            "ru",
            "tgk",
            "tat",
            "udm",
            "uzb",
            "ukr",
            "kjh",
            "chv",
            "erz",
            "sah",
        ),
        voices=BASE_VOICES,
        requires_stress_languages=(
            "aze",
            "hye",
            "bak",
            "bel",
            "kat",
            "kbd",
            "kaz",
            "xal",
            "kir",
            "mdf",
            "ru",
            "tgk",
            "tat",
            "udm",
            "uzb",
            "ukr",
            "kjh",
            "chv",
            "erz",
            "sah",
        ),
    ),
    ModelSpec(
        id="v5_cis_ext",
        display_name="High-quality CIS Extended",
        pack="high-quality-cis-extended",
        url="https://models.silero.ai/models/tts/ru/v5_cis_ext.pt",
        sha256="e8185323fc5a341c229f8a8c9928512f665bf2736021bc600512499d0506eed2",
        size_bytes=91_651_972,
        license=CC_BY_NC_SA_4,
        languages=("kaz", "xal", "tat", "uzb", "ukr", "chv"),
        voices=EXT_VOICES,
        requires_stress_languages=("kaz", "xal", "tat", "uzb", "ukr", "chv"),
    ),
    ModelSpec(
        id="v5_5_ru",
        display_name="Russian v5.5",
        pack="russian-v5",
        url="https://models.silero.ai/models/tts/ru/v5_5_ru.pt",
        sha256="50081637b602126ee06cb3bc8a744d25651d2da149ee8864b9a379bfdd934437",
        size_bytes=145_420_684,
        license=CC_BY_NC_SA_4,
        languages=("ru",),
        voices=RUSSIAN_VOICES,
        built_in_stress_languages=("ru",),
        supports_homographs=True,
        supports_questions=True,
    ),
    ModelSpec(
        id="v3_en",
        display_name="English v3",
        pack="legacy-international",
        url="https://models.silero.ai/models/tts/en/v3_en.pt",
        sha256="02b71034d9f13bc4001195017bac9db1c6bb6115e03fea52983e8abcff13b665",
        size_bytes=57_194_546,
        license=CC_BY_NC_SA_4,
        languages=("en",),
        voices=ENGLISH_VOICES,
        legacy=True,
    ),
    ModelSpec(
        id="v3_en_indic",
        display_name="Indian English v3",
        pack="legacy-international",
        url="https://models.silero.ai/models/tts/en/v3_en_indic.pt",
        sha256="8ebf6b8bc4a762117e5f8d9a6ba30ffcbb65eb669f57cecd6954b0f563095429",
        size_bytes=57_089_310,
        license=CC_BY_NC_SA_4,
        languages=("en-in",),
        voices=INDIAN_ENGLISH_VOICES,
        legacy=True,
    ),
    ModelSpec(
        id="v3_de",
        display_name="German v3",
        pack="legacy-international",
        url="https://models.silero.ai/models/tts/de/v3_de.pt",
        sha256="2e22f38619e1d1da96d963bda5fab6d53843e8837438cb5a45dc376882b0354b",
        size_bytes=57_076_082,
        license=CC_BY_NC_SA_4,
        languages=("de",),
        voices=GERMAN_VOICES,
        legacy=True,
    ),
    ModelSpec(
        id="v3_es",
        display_name="Spanish v3",
        pack="legacy-international",
        url="https://models.silero.ai/models/tts/es/v3_es.pt",
        sha256="36206add75fb89d0be16d5ce306ba7a896c6fa88bab7e3247403f4f4a520eced",
        size_bytes=57_079_302,
        license=CC_BY_NC_SA_4,
        languages=("es",),
        voices=SPANISH_VOICES,
        legacy=True,
    ),
    ModelSpec(
        id="v3_fr",
        display_name="French v3",
        pack="legacy-international",
        url="https://models.silero.ai/models/tts/fr/v3_fr.pt",
        sha256="02ed062cfff1c7097324929ca05c455a25d4f610fd14d51b89483126e50f15cb",
        size_bytes=57_085_158,
        license=CC_BY_NC_SA_4,
        languages=("fr",),
        voices=FRENCH_VOICES,
        legacy=True,
    ),
    ModelSpec(
        id="v3_indic",
        display_name="Indic v3",
        pack="legacy-international",
        url="https://models.silero.ai/models/tts/indic/v3_indic.pt",
        sha256="f82129e01d4ccdfb6044ad642224be756c754dd0d82056971ff140ff7f60f87f",
        size_bytes=57_109_001,
        license=CC_BY_NC_SA_4,
        languages=("bn", "gu", "hi", "kn", "ml", "mni", "raj", "ta", "te", "indic"),
        voices=INDIC_VOICES,
        legacy=True,
    ),
)

MODEL_BY_ID = {model.id: model for model in MODEL_CATALOG}


def get_model(model_id: str) -> ModelSpec:
    try:
        return MODEL_BY_ID[model_id]
    except KeyError as exc:
        raise KeyError(f"Unknown Silero model: {model_id}") from exc


def language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code, code)


def infer_voice_language(voice_id: str, model: ModelSpec) -> str:
    for voice in model.voices:
        if voice.id == voice_id:
            return voice.language
    prefix = voice_id.split("_", 1)[0]
    if prefix in model.languages:
        return prefix
    return model.languages[0] if len(model.languages) == 1 else ""


def prettify_voice_id(voice_id: str) -> str:
    if voice_id == "random":
        return "Random Voice"
    parts = voice_id.replace("-", "_").split("_")
    if parts and parts[0] in LANGUAGE_NAMES:
        parts = parts[1:]
    return " ".join(part.capitalize() for part in parts) or voice_id


def iter_voices(model: ModelSpec, discovered: Iterable[str] = ()) -> tuple[VoiceSpec, ...]:
    known = {voice.id: voice for voice in model.voices}
    for voice_id in discovered:
        if voice_id not in known:
            known[voice_id] = VoiceSpec(
                id=voice_id,
                language=infer_voice_language(voice_id, model),
            )
    return tuple(known.values())

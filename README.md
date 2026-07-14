# Silero FastAPI

A maintained, reproducible Silero text-to-speech service built for Pandrator.

The service replaces the old stateful `silero-api-server` integration. Every
generation request identifies its model, language, voice, sample rate, and
stress policy, so concurrent jobs cannot change one another's configuration.

## Highlights

- Modern Ukrainian, Belarusian, Russian, and other regional-language voices.
- OpenAI-shaped `/v1/audio/speech`, `/v1/models`, and `/v1/audio/voices` APIs.
- Resumable model downloads with pinned byte sizes and SHA-256 verification.
- Clear per-model licence metadata, including non-commercial warnings.
- Optional automatic stress through `silero-stress`.
- Persistent, installer-controlled model storage outside `site-packages`.
- CPU-first operation without a `torchaudio` dependency.
- Optional bearer-token protection for non-loopback deployments.

## Model packs

| Pack | Models | Notable coverage | Licence |
| --- | --- | --- | --- |
| Modern CIS Base | `v5_cis_base`, `v5_cis_base_nostress` | 20 regional languages; full-stress and regional-stress variants with the same 60 voices | MIT |
| High-quality CIS Extended | `v5_cis_ext` | Five Ukrainian voices; expanded Kazakh, Tatar, Uzbek, Kalmyk, and Chuvash | CC BY-NC-SA 4.0 |
| Russian v5 | `v5_5_ru` | Automatic stress, homographs, and question intonation | CC BY-NC-SA 4.0 |
| Legacy International | `v3_en`, `v3_en_indic`, `v3_de`, `v3_es`, `v3_fr`, `v3_indic` | Older English, German, Spanish, French, and Indic voices | CC BY-NC-SA 4.0 |

The service code is MIT-licensed. Model licences are independent. The API
returns the selected model licence with catalogue entries and generated audio.
See [MODEL_LICENSES.md](MODEL_LICENSES.md) before distributing or commercially
using model-derived output.

## Installation

### Pixi

```console
pixi install
pixi run serve
```

The default Pixi environment resolves Torch from the official CPU-only wheel
index. A Pandrator-managed CUDA environment can be added independently without
changing the model store.

### Python

Install the PyTorch build suitable for your system, then install the service:

```console
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -e ".[inference]"
silero-fastapi serve
```

The server listens on `127.0.0.1:8001` by default. API documentation is at
`http://127.0.0.1:8001/docs`.

## Download a model

The recommended MIT model is:

```console
silero-fastapi download v5_cis_base_nostress
```

Install an individual catalogue model:

```console
silero-fastapi download v5_cis_ext
```

Install and verify the complete supported catalogue, including every voice pack:

```console
silero-fastapi download-all
```

Model licences are shown in the catalogue and API. Downloads are not blocked by
licence type; deciding whether a model is appropriate for an intended use is the
user's responsibility.

Downloads resume from a `.part` file when the upstream host supports byte
ranges. A model is promoted into the active store only after its pinned size
and SHA-256 digest match.

## Generate speech

```console
curl http://127.0.0.1:8001/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{
    "model": "v5_cis_base_nostress",
    "input": "Я люблю слухати цікаві книжки.",
    "voice": "ukr_igor",
    "language": "ukr",
    "stress_mode": "auto"
  }' \
  --output preview.wav
```

The response is mono 16-bit PCM WAV. Provenance headers identify the model,
voice, language, licence, and stress engine.

### Speech request fields

- `model`: canonical Silero model ID.
- `input`: plain text or SSML.
- `voice`: model voice ID. It is never stored as global server state.
- `language`: language code; inferred from the voice where unambiguous.
- `sample_rate`: `8000`, `24000`, or `48000` for the included models.
- `stress_mode`: `auto`, `manual`, or `off`.
- `ssml`: interpret `input` as validated SSML.
- `speed`: `0.25`–`4.0`; plain text is wrapped in Silero SSML.
- Russian v5 options: `put_accent`, `put_yo`, `put_stress_homo`,
  `put_yo_homo`, and `question_intensity`.

Only a conservative SSML subset is accepted: `speak`, `p`, `s`, `break`,
`prosody`, and `emphasis` with their supported attributes.

## Stress handling

- Russian v5.5 uses its built-in stress and homograph processing.
- Russian, Ukrainian, and Belarusian CIS voices use trained
  `silero-stress` accentors in automatic mode.
- Other CIS languages can use the supplementary dictionary plus fallback
  heuristic. The API reports a warning because this is less reliable.
- Manual mode preserves user-provided `+` stress marks.
- `/v1/text/accent` lets clients preview and store pronunciation text before
  generation.

Original text is never overwritten by this service. Pandrator should store the
returned pronunciation form with the generation attempt.

## Model and voice discovery

```console
curl http://127.0.0.1:8001/v1/models
curl "http://127.0.0.1:8001/v1/audio/voices?language=ukr"
curl http://127.0.0.1:8001/v1/models/v5_cis_ext/status
curl -X POST http://127.0.0.1:8001/v1/models/v5_cis_ext/cancel
```

Catalogue responses include unavailable voices so Pandrator can render them as
downloadable. Once installed, voices discovered from the model are merged with
the pinned catalogue.

## Configuration

| Environment variable | Default | Meaning |
| --- | --- | --- |
| `SILERO_DATA_DIR` | Platform user-data directory | Models and runtime data |
| `SILERO_HOST` | `127.0.0.1` | Listen address |
| `SILERO_PORT` | `8001` | Listen port |
| `SILERO_DEVICE` | `cpu` | PyTorch device, such as `cpu` or `cuda` |
| `SILERO_CPU_THREADS` | `4` | PyTorch CPU inference threads |
| `SILERO_MODEL_CACHE_SIZE` | `2` | Loaded-model LRU size |
| `SILERO_DOWNLOAD_WORKERS` | `2` | Concurrent model downloads |
| `SILERO_DEFAULT_MODEL` | `v5_cis_base_nostress` | UI/service default |
| `SILERO_API_KEY` | empty | Optional bearer token |

Non-loopback deployments should set an API key and be placed behind the same
authenticated reverse proxy as Pandrator.

## CLI

```console
silero-fastapi serve --device cpu --cpu-threads 4
silero-fastapi catalog
silero-fastapi catalog --json
silero-fastapi download v5_cis_base_nostress
silero-fastapi download-all
silero-fastapi remove v3_en
silero-fastapi doctor
```

## Development

```console
python -m pip install -e ".[test]"
pytest
ruff check src tests
```

Tests use fake Torch models by default. A separately marked real-model smoke
test is used during Pandrator release qualification so ordinary CI does not
download hundreds of megabytes.

## Upstream

- [Silero models](https://github.com/snakers4/silero-models)
- [Silero Stress](https://github.com/snakers4/silero-stress)

Silero and its model names are the property of their respective owners. This
project is an independent integration maintained for Pandrator.

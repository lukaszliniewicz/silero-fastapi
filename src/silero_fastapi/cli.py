from __future__ import annotations

import argparse
import json
import sys

import uvicorn

from .app import create_app
from .catalog import MODEL_CATALOG, get_model
from .runtime import SileroRuntime
from .settings import Settings
from .store import ModelStore


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="silero-fastapi")
    parser.add_argument("--data-dir", help="Model and runtime data directory")
    subparsers = parser.add_subparsers(dest="command")

    serve = subparsers.add_parser("serve", help="Start the HTTP service")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)
    serve.add_argument("--device", default=None)
    serve.add_argument("--cpu-threads", type=int, default=None)

    catalogue = subparsers.add_parser("catalog", help="Print the supported model catalogue")
    catalogue.add_argument("--json", action="store_true")

    download = subparsers.add_parser("download", help="Download and verify a model")
    download.add_argument("model")
    download.add_argument("--acknowledge-noncommercial", action="store_true")

    remove = subparsers.add_parser("remove", help="Remove an installed model")
    remove.add_argument("model")

    subparsers.add_parser("doctor", help="Inspect runtime and model readiness")
    return parser


def _settings(args: argparse.Namespace) -> Settings:
    base = Settings.from_env()
    values = {
        field: getattr(base, field)
        for field in Settings.__dataclass_fields__
    }
    if args.data_dir:
        from pathlib import Path

        values["data_dir"] = Path(args.data_dir).expanduser()
    for field in ("host", "port", "device", "cpu_threads"):
        if hasattr(args, field) and getattr(args, field) is not None:
            values[field] = getattr(args, field)
    return Settings(**values)


def _catalogue_payload() -> list[dict[str, object]]:
    return [
        {
            "id": spec.id,
            "name": spec.display_name,
            "pack": spec.pack,
            "languages": list(spec.languages),
            "voices": [voice.as_dict() for voice in spec.voices],
            "license": spec.license.id,
            "commercial_use_allowed": spec.license.commercial_use_allowed,
            "recommended": spec.recommended,
            "legacy": spec.legacy,
        }
        for spec in MODEL_CATALOG
    ]


def main(argv: list[str] | None = None) -> None:
    parser = _parser()
    args = parser.parse_args(argv)
    if not args.command:
        args.command = "serve"
    settings = _settings(args)

    if args.command == "serve":
        uvicorn.run(create_app(settings), host=settings.host, port=settings.port)
        return
    if args.command == "catalog":
        payload = _catalogue_payload()
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            for item in payload:
                suffix = " (recommended)" if item["recommended"] else ""
                print(f"{item['id']}: {item['name']}{suffix} [{item['license']}]")
        return

    store = ModelStore(settings.data_dir)
    if args.command == "download":
        spec = get_model(args.model)
        if not spec.license.commercial_use_allowed and not args.acknowledge_noncommercial:
            parser.error(
                f"{spec.display_name} is non-commercial; pass --acknowledge-noncommercial"
            )

        def report(download_status) -> None:
            percent = download_status.progress * 100
            print(f"\r{spec.id}: {percent:6.2f}%", end="", flush=True)

        path = store.download(spec, progress=report)
        print(f"\nInstalled {spec.id} at {path}")
        return
    if args.command == "remove":
        spec = get_model(args.model)
        print("Removed" if store.remove(spec) else "Not installed")
        return
    if args.command == "doctor":
        runtime = SileroRuntime(store, device=settings.device)
        print(f"PyTorch runtime: {'available' if runtime.available else 'missing'}")
        print(f"Silero Stress: {'available' if runtime.stress.available else 'missing'}")
        for spec in MODEL_CATALOG:
            print(f"{spec.id}: {store.status(spec).state}")
        if not runtime.available:
            sys.exit(2)


if __name__ == "__main__":
    main()


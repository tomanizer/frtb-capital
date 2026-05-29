"""Import every workspace package root listed in the maturity registry."""

from __future__ import annotations

import argparse
import importlib
import tomllib
from dataclasses import dataclass
from pathlib import Path

REGISTRY_PATH = Path("docs/quality/package_maturity.toml")


@dataclass(frozen=True)
class ImportFailure:
    """Import failure detail for one package root."""

    import_name: str
    exception_type: str
    message: str


def import_roots_from_registry(registry_path: Path, *, root: Path = Path.cwd()) -> list[str]:
    """Return import roots from the TOML maturity registry."""

    data = tomllib.loads((root / registry_path).read_text(encoding="utf-8"))
    packages = data.get("packages")
    if not isinstance(packages, list):
        raise ValueError(f"{registry_path}: missing packages list")

    import_names: list[str] = []
    for package in packages:
        if not isinstance(package, dict):
            raise ValueError(f"{registry_path}: package entry must be a table")
        import_name = package.get("import_name")
        if not isinstance(import_name, str) or not import_name:
            raise ValueError(f"{registry_path}: package entry has invalid import_name")
        import_names.append(import_name)
    return import_names


def run_import_smoke(import_names: list[str]) -> list[ImportFailure]:
    """Import each root and return all failures instead of stopping early."""

    failures: list[ImportFailure] = []
    for import_name in import_names:
        try:
            importlib.import_module(import_name)
        except Exception as exc:
            failures.append(
                ImportFailure(
                    import_name=import_name,
                    exception_type=type(exc).__name__,
                    message=str(exc),
                )
            )
    return failures


def failures_to_jsonable(failures: list[ImportFailure]) -> list[dict[str, str]]:
    """Return failures in a deterministic JSON-ready shape for tests."""

    return [
        {
            "import_name": failure.import_name,
            "exception_type": failure.exception_type,
            "message": failure.message,
        }
        for failure in failures
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    args = parser.parse_args(argv)

    import_names = import_roots_from_registry(args.registry)
    failures = run_import_smoke(import_names)
    if failures:
        print("Import smoke check failed:")
        for failure in failures:
            print(f"  {failure.import_name}: {failure.exception_type}: {failure.message}")
        return 1

    print(f"imported {len(import_names)} package roots")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

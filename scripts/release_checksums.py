"""Generate release checksum manifests for built artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ARTIFACT_SUFFIXES = (".whl", ".tar.gz")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifacts",
        type=Path,
        default=Path("dist/release"),
        help="Directory containing built wheel and sdist artifacts.",
    )
    parser.add_argument(
        "--sbom",
        type=Path,
        default=Path("dist/sbom/frtb-capital.cdx.json"),
        help="CycloneDX SBOM to include in the checksum manifest.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dist/release/SHA256SUMS"),
        help="Text checksum manifest to write.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=Path("dist/release/release-checksums.json"),
        help="Machine-readable checksum manifest to write.",
    )
    args = parser.parse_args()

    entries = checksum_entries(args.artifacts, args.sbom)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_sha256sums(entries), encoding="utf-8")
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(
            {
                "schema_version": "frtb_capital_release_checksums_v1",
                "algorithm": "sha256",
                "entries": entries,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.output}")
    print(f"wrote {args.json_output}")
    return 0


def checksum_entries(artifacts_dir: Path, sbom_path: Path) -> list[dict[str, str]]:
    if not artifacts_dir.is_dir():
        raise FileNotFoundError(f"artifacts directory not found: {artifacts_dir}")
    paths = sorted(
        path
        for path in artifacts_dir.iterdir()
        if path.is_file() and any(path.name.endswith(suffix) for suffix in ARTIFACT_SUFFIXES)
    )
    if not paths:
        raise FileNotFoundError(f"no wheel or sdist artifacts found in {artifacts_dir}")
    if not sbom_path.is_file():
        raise FileNotFoundError(f"SBOM not found: {sbom_path}")
    paths.append(sbom_path)
    return [
        {
            "path": _portable_path(path),
            "sha256": sha256_file(path),
        }
        for path in paths
    ]


def render_sha256sums(entries: list[dict[str, str]]) -> str:
    return "".join(f"{entry['sha256']}  {entry['path']}\n" for entry in entries)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _portable_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Export machine-readable schemas from public handoff ColumnSpec tuples."""

from __future__ import annotations

import argparse
import importlib
import json
from collections.abc import Sequence
from pathlib import Path

from frtb_common import (
    ColumnSpec,
    arrow_schema_to_dict,
    column_specs_to_arrow_schema,
    column_specs_to_json_schema,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, help="Import package or module, e.g. frtb_drc")
    parser.add_argument("--module", help="Optional module override if specs are not top-level")
    parser.add_argument("--spec", required=True, help="ColumnSpec tuple symbol to export")
    parser.add_argument(
        "--format",
        choices=("json-schema", "arrow"),
        default="json-schema",
        help="Schema format to write. 'arrow' writes a JSON representation of pa.Schema.",
    )
    parser.add_argument("--title", help="JSON Schema title; defaults to package.spec")
    parser.add_argument("--description", help="Optional JSON Schema description")
    parser.add_argument("--output", required=True, type=Path, help="Output file path")
    args = parser.parse_args(argv)

    module = importlib.import_module(args.module or args.package)
    specs = _load_specs(module, args.spec)
    if args.format == "json-schema":
        payload = column_specs_to_json_schema(
            specs,
            title=args.title or f"{args.package}.{args.spec}",
            description=args.description,
        )
    else:
        payload = arrow_schema_to_dict(column_specs_to_arrow_schema(specs))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0


def _load_specs(module: object, spec_name: str) -> tuple[ColumnSpec, ...]:
    candidate = getattr(module, spec_name)
    specs = tuple(candidate)
    if not all(isinstance(spec, ColumnSpec) for spec in specs):
        raise TypeError(f"{spec_name} must be a sequence of ColumnSpec instances")
    return specs


if __name__ == "__main__":
    raise SystemExit(main())

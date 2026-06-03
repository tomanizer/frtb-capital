"""Command line administration for ``frtb-result-store``."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path

from frtb_common.hashing import stable_json_dumps

from frtb_result_store.io import DuckDbParquetResultStore
from frtb_result_store.model import ResultStoreContractError


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    store = DuckDbParquetResultStore(args.root)
    try:
        if args.command == "inspect":
            return _emit(store.inspect())
        if args.command == "list-runs":
            return _emit({"runs": [_run_payload(store, run.run_id) for run in store.list_runs()]})
        if args.command == "refresh-catalog":
            store.refresh_catalog()
            return _emit({"refreshed": True, "catalog_path": str(store.catalog_path)})
        if args.command == "export-run":
            return _emit(store.export_run(args.run_id, args.output_path, overwrite=args.overwrite))
        if args.command == "validate-store":
            result = store.validate_store()
            _emit(result)
            return 0 if getattr(result, "ok", False) else 1
    except ResultStoreContractError as exc:
        sys.stderr.write(f"Error: {exc}\n")
        return 1
    parser.error(f"unknown command: {args.command}")
    return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="frtb-result-store",
        description="Administer a manifest-gated FRTB result store.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="summarize a result-store root")
    inspect_parser.add_argument("root", type=Path)

    list_runs_parser = subparsers.add_parser("list-runs", help="list committed runs")
    list_runs_parser.add_argument("root", type=Path)

    refresh_parser = subparsers.add_parser(
        "refresh-catalog",
        help="rebuild the derived DuckDB catalog views",
    )
    refresh_parser.add_argument("root", type=Path)

    export_parser = subparsers.add_parser("export-run", help="export one committed run")
    export_parser.add_argument("root", type=Path)
    export_parser.add_argument("run_id")
    export_parser.add_argument("output_path", type=Path)
    export_parser.add_argument("--overwrite", action="store_true")

    validate_parser = subparsers.add_parser(
        "validate-store",
        help="validate committed manifests and referenced files",
    )
    validate_parser.add_argument("root", type=Path)

    return parser


def _emit(payload: object) -> int:
    sys.stdout.write(stable_json_dumps(_jsonable(payload)) + "\n")
    return 0


def _run_payload(store: DuckDbParquetResultStore, run_id: str) -> dict[str, object]:
    run = store.get_run(run_id)
    latest = store.latest_status(run_id)
    if run is None:
        return {"run_id": run_id, "missing": True}
    return {
        "run_id": run.run_id,
        "run_group_id": run.run_group_id,
        "as_of_date": run.as_of_date.isoformat(),
        "regime_id": run.regime_id,
        "base_currency": run.base_currency,
        "latest_status": None if latest is None else latest.value,
    }


def _jsonable(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        to_dict = getattr(value, "to_dict", None)
        if callable(to_dict):
            return _jsonable(to_dict())
        return _jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    return value


if __name__ == "__main__":
    raise SystemExit(main())

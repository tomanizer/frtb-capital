"""Loader for the committed synthetic non-securitisation DRC fixture (v2).

The fixture bundles:
  - positions.json: serialised ``DrcPosition`` snapshot of ``demo_data.ALL_POSITIONS``
  - expected_outputs.json: golden calculation results (gross, scaled, net, buckets, totals)
  - manifest.json: SHA-256 checksums for reproducible verification

Call ``load_drc_nonsec_v2_fixture()`` to load and verify the fixture.  The
returned ``DrcNonSecFixture`` exposes positions, context, and expected outputs
for use in notebooks and regression tests.  Use ``run_fixture_workflow()`` to
re-run the calculation and compare against golden values.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from frtb_drc.data_models import (
    DrcCalculationContext,
    DrcPosition,
    DrcSourceLineage,
)
from frtb_drc.scaffold import calculate_drc_capital

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DRC_NONSEC_V2_ROOT = ROOT / "tests" / "fixtures" / "drc_nonsec_v2"


@dataclass(frozen=True)
class DrcNonSecFixture:
    """Loaded DRC non-securitisation fixture."""

    root: Path
    manifest: dict[str, Any]
    positions: tuple[DrcPosition, ...]
    context: DrcCalculationContext
    expected_outputs: dict[str, Any]


def load_drc_nonsec_v2_fixture() -> DrcNonSecFixture:
    """Load the repository's canonical DRC non-securitisation v2 fixture."""
    return load_drc_nonsec_fixture(DEFAULT_DRC_NONSEC_V2_ROOT)


def load_drc_nonsec_fixture(root: Path) -> DrcNonSecFixture:
    """Load and verify a DRC non-securitisation fixture from *root*."""
    manifest = _read_json(root / "manifest.json")
    _verify_checksums(root, manifest)
    raw = _read_json(root / "positions.json")
    positions = tuple(_position_from_dict(item) for item in raw["positions"])
    context_raw = raw["context"]
    from datetime import date

    context = DrcCalculationContext(
        run_id=str(context_raw["run_id"]),
        calculation_date=date.fromisoformat(str(context_raw["calculation_date"])),
        base_currency=str(context_raw["base_currency"]),
        profile_id=str(context_raw["profile_id"]),
        desk_id=str(context_raw.get("desk_id", "")),
        legal_entity=str(context_raw.get("legal_entity", "")),
        citation_policy=str(context_raw.get("citation_policy", "strict")),
    )
    expected_outputs = _read_json(root / "expected_outputs.json")
    return DrcNonSecFixture(
        root=root,
        manifest=manifest,
        positions=positions,
        context=context,
        expected_outputs=expected_outputs,
    )


def run_fixture_workflow(fixture: DrcNonSecFixture) -> dict[str, object]:
    """Re-run the fixture through ``calculate_drc_capital`` and return a summary."""
    result = calculate_drc_capital(fixture.positions, context=fixture.context)
    buckets: dict[str, dict[str, object]] = {}
    for category in result.categories:
        for bucket in category.bucket_results:
            buckets[bucket.bucket_key] = {
                "capital": bucket.capital,
                "floor_applied": bucket.floor_applied,
                "hbr": bucket.hbr.ratio,
                "weighted_long": bucket.weighted_long,
                "weighted_short": bucket.weighted_short,
            }
    return {
        "input_count": result.input_count,
        "input_hash": result.input_hash,
        "profile_hash": result.profile_hash,
        "buckets": buckets,
        "category_capital": result.categories[0].capital,
        "total_drc": result.total_drc,
    }


def _position_from_dict(raw: dict[str, Any]) -> DrcPosition:
    lineage_raw = raw.get("lineage")
    lineage = None
    if lineage_raw is not None:
        lineage = DrcSourceLineage(
            source_system=str(lineage_raw["source_system"]),
            source_file=str(lineage_raw["source_file"]),
            source_row_id=str(lineage_raw["source_row_id"]),
            source_column_map=dict(lineage_raw.get("source_column_map") or {}),
        )
    return DrcPosition(
        position_id=str(raw["position_id"]),
        source_row_id=str(raw["source_row_id"]),
        desk_id=str(raw["desk_id"]),
        legal_entity=str(raw["legal_entity"]),
        risk_class=str(raw["risk_class"]),
        instrument_type=str(raw["instrument_type"]),
        default_direction=str(raw["default_direction"]),
        issuer_id=raw.get("issuer_id"),
        tranche_id=raw.get("tranche_id"),
        index_series_id=raw.get("index_series_id"),
        bucket_key=raw.get("bucket_key"),
        seniority=raw.get("seniority"),
        credit_quality=raw.get("credit_quality"),
        notional=raw["notional"],
        market_value=raw.get("market_value"),
        cumulative_pnl=raw.get("cumulative_pnl"),
        maturity_years=raw["maturity_years"],
        currency=str(raw["currency"]),
        lgd_override=raw.get("lgd_override"),
        is_defaulted=bool(raw.get("is_defaulted", False)),
        is_gse=bool(raw.get("is_gse", False)),
        is_pse=bool(raw.get("is_pse", False)),
        is_covered_bond=bool(raw.get("is_covered_bond", False)),
        lineage=lineage,
        citation_ids=tuple(str(c) for c in (raw.get("citation_ids") or [])),
    )


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return data


def _verify_checksums(root: Path, manifest: dict[str, Any]) -> None:
    resolved_root = root.resolve()
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise AssertionError("manifest must contain file checksums")
    for filename, metadata in files.items():
        if not isinstance(filename, str) or not isinstance(metadata, dict):
            raise AssertionError("manifest files must map file names to metadata")
        expected = metadata.get("sha256")
        if not isinstance(expected, str):
            raise AssertionError(f"manifest checksum missing for {filename}")
        target = (resolved_root / filename).resolve()
        if not target.is_relative_to(resolved_root):
            raise AssertionError(f"manifest path escapes fixture root: {filename}")
        actual = _sha256(target)
        if actual != expected:
            raise AssertionError(
                f"manifest checksum mismatch for {filename}: expected {expected}, actual {actual}"
            )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

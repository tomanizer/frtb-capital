"""Generate the drc_nonsec_v2 integration fixture.

Writes three files to ``tests/fixtures/drc_nonsec_v2/``:

  positions.json       -- serialised ALL_POSITIONS + DEMO_CONTEXT
  expected_outputs.json -- golden calculation results with breakdown
  manifest.json        -- SHA-256 checksums of the above two files

Run from the frtb-drc package root:

    uv run python scripts/generate_fixture.py [--out PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from frtb_common import jsonable
from frtb_drc.audit import result_json
from frtb_drc.demo_data import ALL_POSITIONS, DEMO_CONTEXT
from frtb_drc.scaffold import calculate_drc_capital

FIXTURE_ID = "drc_nonsec_v2"
SCHEMA_VERSION = "drc_nonsec_fixture_v2"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=(Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "drc_nonsec_v2"),
        help="output directory (default: tests/fixtures/drc_nonsec_v2)",
    )
    args = parser.parse_args()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)

    result = calculate_drc_capital(ALL_POSITIONS, context=DEMO_CONTEXT)

    positions_payload = _build_positions_payload()
    positions_text = _canonical_json(positions_payload)

    expected_outputs_payload = _build_expected_outputs(result)
    expected_outputs_text = _canonical_json(expected_outputs_payload)

    positions_path = out / "positions.json"
    expected_outputs_path = out / "expected_outputs.json"
    manifest_path = out / "manifest.json"

    positions_path.write_text(positions_text, encoding="utf-8")
    expected_outputs_path.write_text(expected_outputs_text, encoding="utf-8")

    manifest_payload = {
        "fixture_id": FIXTURE_ID,
        "schema_version": SCHEMA_VERSION,
        "files": {
            "positions.json": {"sha256": _sha256(positions_path)},
            "expected_outputs.json": {"sha256": _sha256(expected_outputs_path)},
        },
    }
    manifest_path.write_text(_canonical_json(manifest_payload), encoding="utf-8")

    print(f"Generated fixture in {out}")
    print(f"  positions:        {len(ALL_POSITIONS)} positions")
    print(f"  total_drc:        {result.total_drc:,.2f}")
    for cat in result.categories:
        for bucket in cat.bucket_results:
            print(
                f"  {bucket.bucket_key:<22} capital={bucket.capital:>14,.2f}"
                f"  hbr={bucket.hbr.ratio:.4f}"
            )


def _build_positions_payload() -> dict[str, Any]:
    return {
        "fixture_id": FIXTURE_ID,
        "schema_version": SCHEMA_VERSION,
        "positions": [jsonable(p.as_dict()) for p in ALL_POSITIONS],
        "context": jsonable(DEMO_CONTEXT.as_dict()),
    }


def _build_expected_outputs(result: Any) -> dict[str, Any]:
    gross: dict[str, float] = {}
    maturity_weights: dict[str, float] = {}
    scaled: dict[str, float] = {}
    for gross_jtd in result.gross_jtds:
        gross[gross_jtd.position_id] = gross_jtd.gross_jtd
    for scaled_jtd in result.maturity_scaled_jtds:
        maturity_weights[scaled_jtd.position_id] = scaled_jtd.maturity_weight
        scaled[scaled_jtd.position_id] = scaled_jtd.scaled_jtd

    net: dict[str, dict[str, Any]] = {}
    for net_jtd in result.net_jtds:
        net[net_jtd.net_jtd_id] = {
            "amount": net_jtd.net_amount,
            "bucket": net_jtd.bucket_key,
            "direction": net_jtd.net_direction,
            "issuer": net_jtd.obligor_or_tranche_key,
            "rejected_offsets": [r.reason_code for r in net_jtd.rejected_offsets],
        }

    buckets: dict[str, dict[str, Any]] = {}
    for cat in result.categories:
        for bucket in cat.bucket_results:
            buckets[bucket.bucket_key] = {
                "capital": bucket.capital,
                "floor_applied": bucket.floor_applied,
                "hbr": bucket.hbr.ratio,
                "weighted_long": bucket.weighted_long,
                "weighted_short": bucket.weighted_short,
            }

    return {
        "fixture_id": FIXTURE_ID,
        "input_count": result.input_count,
        "input_hash": result.input_hash,
        "profile_hash": result.profile_hash,
        "result_json_sha256": _sha256_str(result_json(result)),
        "gross": gross,
        "maturity_weights": maturity_weights,
        "scaled": scaled,
        "net": net,
        "buckets": buckets,
        "category_capital": result.categories[0].capital,
        "total_drc": result.total_drc,
    }


def _canonical_json(payload: Any) -> str:
    return json.dumps(jsonable(payload), sort_keys=True, indent=2, ensure_ascii=False)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_str(text: str) -> str:
    return hashlib.sha256(bytes(text, "utf-8")).hexdigest()


if __name__ == "__main__":
    main()

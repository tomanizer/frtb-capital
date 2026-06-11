from __future__ import annotations

from pathlib import Path

import frtb_sbm

HANDOFF_SPECS = (
    "GIRR_DELTA_ARROW_COLUMN_SPECS",
    "GIRR_VEGA_ARROW_COLUMN_SPECS",
    "GIRR_CURVATURE_ARROW_COLUMN_SPECS",
    "FX_DELTA_ARROW_COLUMN_SPECS",
    "FX_VEGA_ARROW_COLUMN_SPECS",
    "FX_CURVATURE_ARROW_COLUMN_SPECS",
    "EQUITY_DELTA_ARROW_COLUMN_SPECS",
    "EQUITY_VEGA_ARROW_COLUMN_SPECS",
    "EQUITY_CURVATURE_ARROW_COLUMN_SPECS",
    "COMMODITY_DELTA_ARROW_COLUMN_SPECS",
    "COMMODITY_VEGA_ARROW_COLUMN_SPECS",
    "COMMODITY_CURVATURE_ARROW_COLUMN_SPECS",
    "CSR_NONSEC_DELTA_ARROW_COLUMN_SPECS",
    "CSR_NONSEC_VEGA_ARROW_COLUMN_SPECS",
    "CSR_NONSEC_CURVATURE_ARROW_COLUMN_SPECS",
    "CSR_SEC_NONCTP_DELTA_ARROW_COLUMN_SPECS",
    "CSR_SEC_NONCTP_VEGA_ARROW_COLUMN_SPECS",
    "CSR_SEC_NONCTP_CURVATURE_ARROW_COLUMN_SPECS",
    "CSR_SEC_CTP_DELTA_ARROW_COLUMN_SPECS",
    "CSR_SEC_CTP_VEGA_ARROW_COLUMN_SPECS",
    "CSR_SEC_CTP_CURVATURE_ARROW_COLUMN_SPECS",
)

ATTRIBUTION_AND_IMPACT = (
    "calculate_sbm_attribution",
    "calculate_sbm_capital_impact",
)

REGISTRY_SURFACE = (
    "SBM_BATCH_SPECS",
    "SBM_BATCH_PATH_ORDER",
    "SbmBatchSpec",
    "build_sbm_batch",
    "build_sbm_batch_from_arrow",
    "calculate_sbm_capital_from_arrow",
    "calculate_sbm_capital_from_batch",
    "input_hash_for_batch",
    "normalize_sbm_arrow_table",
)


def test_documented_handoff_surface_is_top_level_importable() -> None:
    exported = set(frtb_sbm.__all__)
    documented = _public_api_doc()
    for name in (*HANDOFF_SPECS, *ATTRIBUTION_AND_IMPACT, *REGISTRY_SURFACE):
        assert name in exported
        assert hasattr(frtb_sbm, name)
        assert f"`{name}`" in documented


def test_top_level_public_api_surface_remains_bounded() -> None:
    assert len(frtb_sbm.__all__) < 400


def _public_api_doc() -> str:
    root = Path(__file__).resolve().parents[3]
    return (root / "docs/modules/frtb-sbm/PUBLIC_API.md").read_text()

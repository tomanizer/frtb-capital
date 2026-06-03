from __future__ import annotations

from pathlib import Path

import frtb_sbm


HANDOFF_SPECS = (
    "GIRR_DELTA_HANDOFF_COLUMN_SPECS",
    "GIRR_VEGA_HANDOFF_COLUMN_SPECS",
    "GIRR_CURVATURE_HANDOFF_COLUMN_SPECS",
    "FX_DELTA_HANDOFF_COLUMN_SPECS",
    "FX_VEGA_HANDOFF_COLUMN_SPECS",
    "FX_CURVATURE_HANDOFF_COLUMN_SPECS",
    "EQUITY_DELTA_HANDOFF_COLUMN_SPECS",
    "EQUITY_VEGA_HANDOFF_COLUMN_SPECS",
    "EQUITY_CURVATURE_HANDOFF_COLUMN_SPECS",
    "COMMODITY_DELTA_HANDOFF_COLUMN_SPECS",
    "COMMODITY_VEGA_HANDOFF_COLUMN_SPECS",
    "COMMODITY_CURVATURE_HANDOFF_COLUMN_SPECS",
    "CSR_NONSEC_DELTA_HANDOFF_COLUMN_SPECS",
    "CSR_NONSEC_VEGA_HANDOFF_COLUMN_SPECS",
    "CSR_NONSEC_CURVATURE_HANDOFF_COLUMN_SPECS",
    "CSR_SEC_NONCTP_DELTA_HANDOFF_COLUMN_SPECS",
    "CSR_SEC_NONCTP_VEGA_HANDOFF_COLUMN_SPECS",
    "CSR_SEC_NONCTP_CURVATURE_HANDOFF_COLUMN_SPECS",
    "CSR_SEC_CTP_DELTA_HANDOFF_COLUMN_SPECS",
    "CSR_SEC_CTP_VEGA_HANDOFF_COLUMN_SPECS",
    "CSR_SEC_CTP_CURVATURE_HANDOFF_COLUMN_SPECS",
)

NORMALIZERS = (
    "normalize_girr_delta_arrow_table",
    "normalize_girr_vega_arrow_table",
    "normalize_girr_curvature_arrow_table",
    "normalize_fx_delta_arrow_table",
    "normalize_fx_vega_arrow_table",
    "normalize_fx_curvature_arrow_table",
    "normalize_equity_delta_arrow_table",
    "normalize_equity_vega_arrow_table",
    "normalize_equity_curvature_arrow_table",
    "normalize_commodity_delta_arrow_table",
    "normalize_commodity_vega_arrow_table",
    "normalize_commodity_curvature_arrow_table",
    "normalize_csr_nonsec_delta_arrow_table",
    "normalize_csr_nonsec_vega_arrow_table",
    "normalize_csr_nonsec_curvature_arrow_table",
    "normalize_csr_sec_nonctp_delta_arrow_table",
    "normalize_csr_sec_nonctp_vega_arrow_table",
    "normalize_csr_sec_nonctp_curvature_arrow_table",
    "normalize_csr_sec_ctp_delta_arrow_table",
    "normalize_csr_sec_ctp_vega_arrow_table",
    "normalize_csr_sec_ctp_curvature_arrow_table",
)


def test_documented_handoff_surface_is_top_level_importable() -> None:
    exported = set(frtb_sbm.__all__)
    documented = _public_api_doc()
    for name in (*HANDOFF_SPECS, *NORMALIZERS):
        assert name in exported
        assert hasattr(frtb_sbm, name)
        assert f"`{name}`" in documented


def test_top_level_public_api_surface_remains_bounded() -> None:
    assert len(frtb_sbm.__all__) < 340


def _public_api_doc() -> str:
    root = Path(__file__).resolve().parents[3]
    return (root / "docs/modules/frtb-sbm/PUBLIC_API.md").read_text()

from __future__ import annotations

import pyarrow as pa
from frtb_cva import (
    build_cva_netting_set_batch_from_arrow,
    build_sa_cva_sensitivity_batch_from_arrow,
    normalize_cva_netting_set_arrow_table,
    normalize_sa_cva_sensitivity_arrow_table,
)


def test_cva_arrow_batch_preserves_exposure_and_surface_provenance() -> None:
    netting_set_batch = build_cva_netting_set_batch_from_arrow(
        normalize_cva_netting_set_arrow_table(
            pa.table(
                {
                    "netting_set_id": ["ns-1"],
                    "counterparty_id": ["cp-1"],
                    "ead": [1_000_000.0],
                    "effective_maturity": [2.0],
                    "discount_factor": [0.95],
                    "currency": ["USD"],
                    "sign_convention": ["non_negative"],
                    "uses_imm_ead": [False],
                    "source_row_id": ["row-ns-1"],
                    "exposure_time_series_id": ["ts-cva-exposure-ns-1"],
                    "lineage_source_system": ["risk-engine"],
                    "lineage_source_file": ["netting_sets.csv"],
                }
            )
        )
    )

    sensitivity_batch = build_sa_cva_sensitivity_batch_from_arrow(
        normalize_sa_cva_sensitivity_arrow_table(
            pa.table(
                {
                    "sensitivity_id": ["sens-1"],
                    "risk_class": ["GIRR"],
                    "risk_measure": ["VEGA"],
                    "sensitivity_tag": ["CVA"],
                    "bucket_id": ["USD"],
                    "risk_factor_key": ["RATE"],
                    "amount": [100.0],
                    "amount_currency": ["USD"],
                    "sign_convention": ["positive_loss"],
                    "source_row_id": ["row-sens-1"],
                    "tenor": ["5Y"],
                    "volatility_input": [0.25],
                    "volatility_surface_id": ["surface-usd-swaption"],
                    "volatility_surface_point_id": ["surface-usd-swaption:5y:atm"],
                    "shock_id": ["shock-cva-vega-up"],
                    "lineage_source_system": ["risk-engine"],
                    "lineage_source_file": ["sa_cva_sensitivities.csv"],
                }
            )
        )
    )

    assert netting_set_batch.exposure_time_series_ids is not None
    assert netting_set_batch.exposure_time_series_ids.tolist() == ["ts-cva-exposure-ns-1"]
    assert sensitivity_batch.volatility_surface_ids is not None
    assert sensitivity_batch.volatility_surface_ids.tolist() == ["surface-usd-swaption"]
    assert sensitivity_batch.volatility_surface_point_ids is not None
    assert sensitivity_batch.volatility_surface_point_ids.tolist() == [
        "surface-usd-swaption:5y:atm"
    ]
    assert sensitivity_batch.shock_ids is not None
    assert sensitivity_batch.shock_ids.tolist() == ["shock-cva-vega-up"]
